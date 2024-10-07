import json
import logging
import string
import time
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Optional, ClassVar

import docker.errors
from pydantic import BaseModel

from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.nuvla.resources import (InfrastructureServiceResource, CredentialResource, NuvlaID, State)
from nuvlaedge.agent.common import util
from nuvlaedge.common.file_operations import file_exists_and_not_empty
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common import file_operations

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.models import are_models_equal

logger: logging.Logger = get_nuvlaedge_logger(__name__)
_status_module_name = 'VPN Handler'


class VPNConfigurationMissmatch(Exception):
    """ Raised when VPN handler, nuvlabox resource and nuvlaedge engine configurations do not match"""
    ...


class VPNCredentialCreationTimeOut(Exception):
    """ Raised when the VPN credential is not created in time. This makes impossible for the VPN the work"""


class VPNConfig(BaseModel):
    """
    Class that represents the configuration of a VPN.

    Attributes:
        vpn_certificate (str): The VPN certificate.
        vpn_intermediate_ca (list[str]): List of intermediate CAs.
        vpn_intermediate_ca_is (list[str]): List of intermediate CAs IS.
        vpn_ca_certificate (str): The CA certificate.
        vpn_shared_key (str): The shared key for the VPN.
        vpn_common_name_prefix (str): The common name prefix for the VPN.
        vpn_interface_name (str): The interface name for the VPN.
        nuvlaedge_vpn_key (str): The key for the NuvlaEdge VPN.
        vpn_extra_config (str): Additional configuration for the VPN.
        vpn_endpoints_mapped (str): Mapped endpoints for the VPN.

    Methods:
        dump_to_template(): Dumps the VPN configuration to a dictionary format.

    """
    vpn_certificate:        Optional[str] = None
    vpn_intermediate_ca:    Optional[list[str]] = None
    vpn_intermediate_ca_is: Optional[list[str]] = None
    vpn_ca_certificate:     Optional[str] = None
    vpn_shared_key:         Optional[str] = None
    vpn_common_name_prefix: Optional[str] = None
    vpn_interface_name:     Optional[str] = None
    nuvlaedge_vpn_key:      Optional[str] = None
    vpn_extra_config:       Optional[str] = ''
    vpn_endpoints_mapped:   Optional[str] = None

    update_lock: ClassVar[Lock] = Lock()

    def dump_to_template(self) -> dict:
        temp_model = self.model_dump(exclude_none=True, by_alias=False)
        temp_model["vpn_intermediate_ca"] = ' '.join(self.vpn_intermediate_ca)
        temp_model["vpn_intermediate_ca_is"] = ' '.join(self.vpn_intermediate_ca_is)
        return temp_model

    def update(self, data: BaseModel):
        dict_data = data.model_dump(exclude_none=True, by_alias=False)
        for k, v in dict_data.items():
            if hasattr(self, k):
                with self.update_lock:
                    self.__setattr__(k, v)


class VPNHandler:
    """
    VPNHandler
    ----------
    Controls and configures the VPN client based on configuration parsed by the agent. It commissions itself via the
     commissioner class by editing the field `self.commission_payload.vpn
    *_csr`. If this object is instantiated and then running, we assume VPN is enabled. It should be the agent
     (via configuration) who starts/stops/disables the VPN.

    Attributes:
        VPN_FOLDER (Path): Path to the VPN folder
        VPN_CSR_FILE (Path): Path to the VPN CSR file
        VPN_KEY_FILE (Path): Path to the VPN key file
        VPN_PLAIN_CONF_FILE (Path): Path to the VPN handler config file
        VPN_CREDENTIAL_FILE (Path): Path to the VPN credential file
        VPN_SERVER_FILE (Path): Path to the VPN server file

    """
    VPN_FOLDER: Path = FILE_NAMES.VPN_FOLDER
    VPN_CSR_FILE: Path = FILE_NAMES.VPN_CSR_FILE
    VPN_KEY_FILE: Path = FILE_NAMES.VPN_KEY_FILE
    VPN_CLIENT_CONF_FILE: Path = FILE_NAMES.VPN_CLIENT_CONF_FILE
    VPN_PLAIN_CONF_FILE: Path = FILE_NAMES.VPN_HANDLER_CONF
    VPN_CREDENTIAL_FILE: Path = FILE_NAMES.VPN_CREDENTIAL
    VPN_SERVER_FILE: Path = FILE_NAMES.VPN_SERVER_FILE

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 status_channel: Queue[StatusReport],
                 vpn_extra_conf: str,
                 vpn_enable_flag: int,
                 interface_name: str = 'vpn'):
        """
        Controls and configures the VPN client based on configuration parsed by the agent. It  commissions itself
        via the commissioner class by editing the field `self.commission_payload.vpn_csr`.

        If this object is instantiated and then running, we assume VPN is enabled. It should be the agent (via
        configuration) who starts/stops/disables the VPN.

        Args:
            coe_client (COEClient): The COE client.
            nuvla_client (NuvlaClientWrapper): The Nuvla client.
            status_channel (Queue[StatusReport]): The status channel.
            vpn_extra_conf (str): Additional configuration for the VPN.
        """

        logger.debug("Creating VPN handler object")

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        # Shared static commission payload. Only vpn-csr field shall be edited by this class
        self.status_channel: Queue[StatusReport] = status_channel

        # VPN Server ID variables
        self._local_server_id: NuvlaID | None = None
        self._nuvla_server_id: NuvlaID = self.nuvla_client.nuvlaedge.vpn_server_id

        # Client configuration data structure
        self.vpn_config: VPNConfig | None = None

        self.vpn_extra_conf: str = vpn_extra_conf
        self.interface_name: str = interface_name
        self.vpn_enable_flag: int = vpn_enable_flag

        # Last VPN credentials used to create the VPN configuration
        self.vpn_credential: CredentialResource | None = None

        # Last VPN server configuration used to create the client VPN configuration
        self.vpn_server: InfrastructureServiceResource = ...
        self._load_configurations()

        if not self.VPN_FOLDER.exists():
            logger.debug("Creating VPN directory tree")
            self.VPN_FOLDER.mkdir()

        NuvlaEdgeStatusHandler.starting(self.status_channel, _status_module_name)

    def _certificates_exists(self) -> bool:
        """
        Checks if the VPN key and certificate signing request files exist and are not empty.

        Returns:
            bool: True if both files exist and are not empty, False otherwise.
        """
        return (file_operations.file_exists_and_not_empty(self.VPN_KEY_FILE) and
                file_operations.file_exists_and_not_empty(self.VPN_CSR_FILE))

    @staticmethod
    def get_vpn_ip():
        """
        Static method to retrieve the VPN IP from a file.

        Returns:
            str or None: The VPN IP address read from the file, or None if the file is empty or doesn't exist.

        """
        try:
            ip = file_operations.read_file(FILE_NAMES.VPN_IP_FILE)
            if ip and isinstance(ip, str):
                ip = ip.strip()
            return ip
        except Exception as e:
            logger.error(f'Failed to read VPN IP: {e}')
        return None

    def _check_vpn_client_state(self) -> tuple[bool, bool]:
        """
        Looks for the VPN Client container
        Returns: a tuple where the first boolean indicates the client existence and the second whether it is running

        """
        exists, running = False, False
        try:
            running = self.coe_client.is_vpn_client_running()
            exists = True
        except docker.errors.NotFound:
            exists = False
        return exists, running

    def _wait_certificates_ready(self, timeout: int = 25):
        """
        Waits for generated certificates to be ready.
        Args:
            timeout: (25s) Time before raising timeout

        Returns: None
        Raises: Timeout if certificates files do not show in the location (Class Constant) after Timeout
        """
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time < timeout:

            if self._certificates_exists():
                logger.debug("Certificates ready")
                return
            time.sleep(0.3)

        raise TimeoutError("Certificates not generated in time in target locations: \n"
                           f"KEY: {self.VPN_KEY_FILE} \n"
                           f"CSR: {self.VPN_CSR_FILE}")

    def _wait_credential_creation(self, timeout: int = 25):
        """
        Waits for the creation of VPN credentials in Nuvla for a given timeout period.

        Args:
            timeout (int): The maximum time in seconds to wait for the credentials to be created. Default is 25 seconds.

        Returns:
            bool: True if the credentials are created within the timeout period, False otherwise.

        """
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time < timeout:
            if self.nuvla_client.vpn_credential.vpn_certificate is not None:
                self.vpn_credential = self.nuvla_client.vpn_credential.model_copy()
                logger.debug(f"VPN credential {self.nuvla_client.vpn_credential.id} created in Nuvla")
                self._save_vpn_credential()
                return True
            time.sleep(1)

        logger.warning(f"VPN credential not created in time with timeout {timeout}")
        return False

    def _generate_certificates(self, wait: bool = True):
        """
        This method generates new VPN certificates using OpenSSL, and it also removes any existing certificates.

        The generation of certificates involves creating a new elliptic curve private key and a certificate request
         with the NuvlaEdge UUID as the Common Name. The generated files are stored locally.

        Args:
            wait (bool): A flag which indicates whether the function should wait for the certificates to be ready. Default is True.
                         If it is set to True, the method will block and keep checking until the certificates are created.
                         If it is False, the function will return immediately after attempting to generate the certificates.

        Raises:
            An error message will be logged when the certificate generation process fails.
        """
        if file_operations.file_exists_and_not_empty(self.VPN_KEY_FILE):
            self.VPN_KEY_FILE.unlink(True)
        if file_operations.file_exists_and_not_empty(self.VPN_CSR_FILE):
            self.VPN_CSR_FILE.unlink(True)

        cmd = ['openssl', 'req', '-batch', '-nodes', '-newkey', 'ec', '-pkeyopt',
               'ec_paramgen_curve:secp521r1',
               '-keyout', str(self.VPN_KEY_FILE),
               '-out', str(self.VPN_CSR_FILE),
               '-subj', f'/CN={self.nuvla_client.nuvlaedge_uuid.split("/")[-1]}']

        logger.info("Requesting VPN certificates creation to OpenSSL...")
        r = util.execute_cmd(cmd, method_flag=False)

        if r.get('returncode', -1) != 0:
            logger.error(f'Cannot generate certificates for VPN connection: '
                         f'{r.get("stdout")} | {r.get("stderr")}')
            return

        if wait:
            logger.debug("Waiting for the certificates to appear")
            self._wait_certificates_ready()
        logger.info("Requesting VPN certificates creation to OpenSSL... Success")

    def _trigger_commission(self):
        """
        Commissioning operation is always executed by the Commissioner class.
        Calling this method, we change the commission payload, thus we trigger the commission in the next process.

        Returns: None

        """
        logger.info("Commissioning VPN...")
        vpn_data = file_operations.read_file(self.VPN_CSR_FILE)
        logger.debug(f"Triggering commission with VPN Data: {vpn_data}")

        vpn_payload: dict = {'vpn-csr': vpn_data}
        logger.debug(f"Commissioning VPN with payload: {json.dumps(vpn_payload, indent=4)}")

        commission_response: dict = self.nuvla_client.commission(vpn_payload)
        if not commission_response:
            logger.error("Error commissioning VPN.")
            NuvlaEdgeStatusHandler.failing(self.status_channel,
                                           _status_module_name,
                                           "Error commissioning VPN. Will retry in 60s")
        else:
            logger.info("Commissioning VPN... Success")
            NuvlaEdgeStatusHandler.starting(self.status_channel, _status_module_name)

        logger.debug(f"Commission response: {json.dumps(commission_response, indent=4)}")

    def _is_nuvlaedge_commissioned(self) -> bool:
        """
        Checks if the NuvlaEdge is commissioned.

        Returns:
            bool: True if the NuvlaEdge is commissioned, False otherwise.

        """
        return self.nuvla_client.nuvlaedge.state == State.COMMISSIONED

    def _vpn_needs_commission(self):
        """
        Checks if a Virtual Private Network (VPN) needs commissioning. There are several conditions that cause
        this method to return True, indicating that commissioning is needed:

        0. If NuvlaEdge is not on COMMISSION
        1. If no VPN credential exists in the Nuvla client - This could be caused by a VPN server ID being
           defined, but no VPN credential has been created.

        2. If there's a mismatch between the locally stored VPN credential and the VPN credential stored in the
           Nuvla client - This could suggest that the VPN has been updated, but the changes have not been
           reflected in the local storage.

        3. If the VPN server ID has changed - This points to a possible major change in the VPN configuration,
           requiring re-commissioning.

        Each of these conditions checks different aspects of the VPN configuration, and if any are met, the
        function will return True. If none are met, the function will return False, indicating no need for
        commissioning.

        Returns:
            bool: True if VPN needs commissioning, False otherwise.

        """
        if not self._is_nuvlaedge_commissioned():
            logger.info(f"Cannot commission VPN with NuvlaEdge in state {self.nuvla_client.nuvlaedge.state}")
            return False

        if not self.nuvla_client.vpn_credential.vpn_certificate:
            # There is a VPN server ID defined but there is no VPN credential created
            logger.info("VPN need commission due to missing VPN credential in Nuvla")
            return True

        if not are_models_equal(self.vpn_credential, self.nuvla_client.vpn_credential):
            # There is missmatch between local credential and Nuvla credential
            logger.info("VPN needs commission due to missmatch local VPN credential and Nuvla credential")
            return True

        if self.vpn_server.id != self.nuvla_client.nuvlaedge.vpn_server_id:
            # VPN server ID has changed
            logger.info("VPN needs commission due to change in VPN server ID")
            logger.debug(f"Server ID: \n {self.vpn_server.id}")
            logger.debug(f"Nuvla Server ID: \n {self.nuvla_client.nuvlaedge.vpn_server_id}")
            return True

        return False

    def _get_vpn_key(self) -> str | None:
        """
        Retrieves the VPN key from the VPN key file.

        Returns:
            str: The VPN key read from the VPN key file.
            None: when no key is being read from the VPN key file
        """
        return file_operations.read_file(self.VPN_KEY_FILE)

    def _map_endpoints(self) -> str:
        """
        Maps VPN connection endpoints to a string representation of VPN configuration endpoints.

        Returns:
            str: The string representation of VPN configuration endpoints.

        """
        vpn_conf_endpoints = ''
        for connection in self.vpn_server.vpn_endpoints:
            vpn_conf_endpoints += \
                "\n<connection>\nremote {} {} {}\n</connection>\n".format(
                    connection["endpoint"],
                    connection["port"],
                    connection["protocol"])
        return vpn_conf_endpoints

    def _configure_vpn_client(self):
        """
        Configures the VPN client by updating the VPN server data and credentials.

        This method performs a series of operations to ensure the VPN client is
        correctly configured:

            - Updates the `vpn_config` with the VPN server data from the `nuvla_client`,
              which includes various VPN server configurations

            - Moves the intermediate CA credentials from the `vpn_server` to the `vpn_config`.

            - Creates a deep copy of the VPN server data from the `nuvla_client` and assigns
              it back to the `vpn_server`.

            - The credentials for the VPN are then updated in the `vpn_configuring` the
              `vpn_credential`.

            - The VPN interface name is then updated in the `vpn_config` based on the
              agent settings.

            - The method then makes a local copy of intermediate CA from `vpn_server`
              and assigns it back to `vpn_config`.

            - The nuvlaedge VPN key is then assigned to the `vpn_config`.

            - The corresponding endpoints are then mapped in the `vpn_config`.

            - Finally, the method saves the configuration in `vpn_client_configuration` string.

        Each data update operation is logged for debugging purposes.

        Note: while configuring the VPN client the Infrastructure service CA comes with the
        same key as the VPN credential CA. It needs to be moved to its corresponding field,
        and the CA will be automatically replaced.

        """
        # Sync local VPN server data with Nuvla VPN server configuration.
        self.vpn_config.update(self.nuvla_client.vpn_server)

        # Infrastructure service CA comes with the same key as the VPN credential CA
        # So we need to move it to its corresponding field, then the CA will be automatically
        # replaced
        self.vpn_config.vpn_intermediate_ca_is = self.vpn_server.vpn_intermediate_ca
        logger.debug(f"VPN Configured with VPN Server data \n"
                     f" {self.vpn_config.model_dump_json(indent=4, exclude_none=True)}")
        self.vpn_server = self.nuvla_client.vpn_server.model_copy()

        # Update Credentials data
        self.vpn_config.update(self.vpn_credential)
        logger.debug(f"VPN Configured with VPN credential data \n"
                     f" {self.vpn_config.model_dump_json(indent=4, exclude_none=True)}")

        # VPN interface name can be renamed from the agent settings, assign it here
        self.vpn_config.vpn_interface_name = self.interface_name

        temp_ca = self.vpn_server.vpn_intermediate_ca
        self.vpn_config.vpn_intermediate_ca_is = temp_ca
        self.vpn_config.nuvlaedge_vpn_key = self._get_vpn_key()
        self.vpn_config.vpn_endpoints_mapped = self._map_endpoints()

        if self.vpn_extra_conf is not None:
            # If self.vpn_extra_conf is not none means it has been intentionally defined
            # in NuvlaEdge settings. Either to overwrite a previous configuration if it is
            # an empty string or just to add extra custom configuration.
            self.vpn_config.vpn_extra_config = self.vpn_extra_conf

        # Then save the configuration
        vpn_client_configuration: str = (
            string.Template(util.VPN_CONFIG_TEMPLATE).substitute(self.vpn_config.dump_to_template()))

        self._save_vpn_config(vpn_client_configuration)
        self._save_vpn_credential()
        self._save_vpn_server()

    def run(self):
        """
        Main function of the VPN handler has 4 responsibilities:
        - Commissions the VPN, if the VPN-SERVER-ID exists (First time)
            - After, watches the vpn credential in Nuvla. If there are any changes, re-commissions the VPN and
            generates new certificates
        - Generates the certificates of the VPN
        - Configures the OpenVPN client running in a different container using VPN_CLIENT_CONF_FILE

        """

        if not self.nuvla_client.nuvlaedge.vpn_server_id:
            NuvlaEdgeStatusHandler.stopped(self.status_channel, _status_module_name)
            logger.info("VPN is disabled from Nuvla, Wait for next iteration")
            return

        vpn_client_exists, _ = self._check_vpn_client_state()
        if not vpn_client_exists:
            if self.vpn_enable_flag == 0:
                logger.info("VPN is disabled from env. settings, Wait for next iteration")
                NuvlaEdgeStatusHandler.stopped(self.status_channel, _status_module_name)
                return

            NuvlaEdgeStatusHandler.failing(self.status_channel, _status_module_name,
                                           message="VPN Client container doesn't exist.")
            logger.warning("VPN Client container doesn't exist, cannot start VPN client. Waiting for next iteration...")
            return

        NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)

        if not self._vpn_needs_commission():
            logger.info("VPN credentials aligned. No need for commissioning")
            return

        logger.info("Starting VPN commissioning and configuration...")

        # Generate SSL certificates
        logger.debug("Request SSL certificate generation")
        self._generate_certificates()

        logger.debug("Conform the certificate sign request and send it to Nuvla via commissioning")
        self._trigger_commission()

        # Wait for VPN credential to show up in Nuvla (Timeout needs to be commissioner_period + sometime
        if not self._wait_credential_creation(timeout=60 + 15):
            logger.info("VPN credential wasn't created in time. Cannot start the VPN client. Will try in the next"
                        "iteration")
            # VPN credential wasn't created in time. Do not continue
            raise VPNCredentialCreationTimeOut("VPN credential wasn't created in time. Cannot start the VPN client")

        # Then we need to (re)configure the VPN client
        self._configure_vpn_client()
        logger.info("Starting VPN commissioning and configuration... Success")

    def _load_vpn_config(self):
        """ Loads the VPN configuration from the file system."""
        config = file_operations.read_file(self.VPN_PLAIN_CONF_FILE, decode_json=True)
        if config:
            self.vpn_config = VPNConfig.model_validate(config)
        else:
            self.vpn_config = VPNConfig()

    def _save_vpn_config(self, vpn_client_conf: str):
        """ Saves the VPN configuration to the file system.

        Args:
            vpn_client_conf (str): The VPN client configuration.
        """
        file_operations.write_file(self.vpn_config, self.VPN_PLAIN_CONF_FILE, exclude_none=True, by_alias=True)
        file_operations.write_file(vpn_client_conf, self.VPN_CLIENT_CONF_FILE)

    def _load_vpn_server(self):
        """ Loads the VPN server from the file system."""
        _server = file_operations.read_file(self.VPN_SERVER_FILE, decode_json=True)
        if _server:
            self.vpn_server = InfrastructureServiceResource.model_validate(_server)
            return
        if file_exists_and_not_empty(self.VPN_CLIENT_CONF_FILE):
            self.vpn_server = self.nuvla_client.vpn_server.model_copy()
        else:
            self.vpn_server = InfrastructureServiceResource()

    def _save_vpn_server(self):
        """ Saves the VPN server to the file system."""
        file_operations.write_file(self.vpn_server, self.VPN_SERVER_FILE, exclude_none=True, by_alias=True)

    def _load_vpn_credential(self):
        _credential = file_operations.read_file(self.VPN_CREDENTIAL_FILE, decode_json=True)
        if _credential:
            self.vpn_credential = CredentialResource.model_validate(_credential)
            return
        if file_exists_and_not_empty(self.VPN_CLIENT_CONF_FILE):
            self.vpn_credential = self.nuvla_client.vpn_credential.model_copy()
        else:
            self.vpn_credential = CredentialResource()

    def _save_vpn_credential(self):
        """ Saves the VPN credential to the file system."""
        file_operations.write_file(self.vpn_credential, self.VPN_CREDENTIAL_FILE, exclude_none=True, by_alias=True)

    def _load_configurations(self):
        """ Loads the VPN configurations from the file system."""
        self._load_vpn_config()
        self._load_vpn_server()
        self._load_vpn_credential()
