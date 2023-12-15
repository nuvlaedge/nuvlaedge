import json
import logging
import string
import time
from pathlib import Path
from queue import Queue
from typing import Optional

import docker.errors

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.agent.common import StatusReport, NuvlaEdgeStatusHandler
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.nuvla.resources.infrastructure_service import InfrastructureServiceResource
from nuvlaedge.agent.nuvla.resources.credential import CredentialResource
from nuvlaedge.agent.worker import WorkerExitException
from nuvlaedge.common import utils
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.common import util
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class VPNConfigurationMissmatch(Exception):
    """ Raised when VPN handler, nuvlabox resource and nuvlaedge engine configurations do not match"""
    ...


class VPNCredentialCreationTimeOut(Exception):
    """ Raised when the VPN credential is not created in time. This makes impossible for the VPN the work"""


class VPNConfig(NuvlaEdgeStaticModel):
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

    def dump_to_template(self) -> dict:
        temp_model = self.model_dump(exclude_none=True)
        temp_model["vpn_intermediate_ca"] = ' '.join(self.vpn_intermediate_ca)
        temp_model["vpn_intermediate_ca_is"] = ' '.join(self.vpn_intermediate_ca_is)
        return temp_model


class VPNHandler:
    """
    VPNHandler
    ----------
    Controls and configures the VPN client based on configuration parsed by the agent. It commissions itself via the commissioner class by editing the field `self.commission_payload.vpn
    *_csr`. If this object is instantiated and then running, we assume VPN is enabled. It should be the agent (via configuration) who starts/stops/disables the VPN.

    Attributes:
        VPN_FOLDER (Path): Path to the VPN folder
        VPN_CSR_FILE (Path): Path to the VPN CSR file
        VPN_KEY_FILE (Path): Path to the VPN key file
        VPN_CONF_FILE (Path): Path to the VPN client config file
        VPN_PLAIN_CONF_FILE (Path): Path to the VPN handler config file
        VPN_CREDENTIAL_FILE (Path): Path to the VPN credential file
        VPN_SERVER_FILE (Path): Path to the VPN server file
        VPN_INTERFACE_NAME (str): Name of the VPN interface

    Args:
        coe_client (COEClient): Instance of COEClient class
        nuvla_client (NuvlaClientWrapper): Instance of NuvlaClientWrapper class
        vpn_channel (Queue[str]): Channel where the VPN CSR is sent to the commissioner to be included in the commissioning
        vpn_extra_conf (str): Extra VPN configuration

    Methods:
        __init__(coe_client: COEClient, nuvla_client: NuvlaClientWrapper, vpn_channel: Queue[str], vpn_extra_conf: str) -> None:
            Initializes the VPNHandler object

        certificates_exists() -> bool:
            Checks if VPN key and CSR files exist

        get_vpn_ip() -> str:
            Returns the VPN IP

        check_vpn_client_state() -> Tuple[bool, bool]:
            Checks if the VPN client container exists and if it is running

        wait_certificates_ready(timeout: int = 25) -> None:
            Waits for the generated certificates to be ready

        wait_credential_creation(timeout: int = 25) -> bool:
            Waits for the VPN credential to be created

        generate_certificates(wait: bool = True) -> None:
            Generates the certificates for the VPN

        trigger_commission() -> None:
            Triggers the commissioning operation by changing the commission payload

        vpn_needs_commission() -> bool:
            Checks if the VPN needs commissioning

        get_vpn_key() -> str:
            Returns the VPN key

        map_endpoints() -> str:
            Maps the VPN endpoints

        configure_vpn_client() -> None:
            Configures the VPN client
    """
    VPN_FOLDER: Path = FILE_NAMES.VPN_FOLDER
    VPN_CSR_FILE: Path = FILE_NAMES.VPN_CSR_FILE
    VPN_KEY_FILE: Path = FILE_NAMES.VPN_KEY_FILE
    VPN_CONF_FILE: Path = FILE_NAMES.VPN_CLIENT_CONF_FILE
    VPN_PLAIN_CONF_FILE: Path = FILE_NAMES.VPN_HANDLER_CONF
    VPN_CREDENTIAL_FILE: Path = FILE_NAMES.VPN_CREDENTIAL
    VPN_SERVER_FILE: Path = FILE_NAMES.VPN_SERVER_FILE
    VPN_INTERFACE_NAME: str = 'vpn'

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 vpn_channel: Queue[str],
                 status_channel: Queue[StatusReport],
                 vpn_extra_conf: str):
        """
        Controls and configures the VPN client based on configuration parsed by the agent. It  commissions itself
        via the commissioner class by editing the field `self.commission_payload.vpn_csr`.

        If this object is instantiated and then running, we assume VPN is enabled. It should be the agent (via
        configuration) who starts/stops/disables the VPN.

        Args:
            coe_client:
            nuvla_client:
            vpn_channel: channel where the VPN CSR is sent to the commissioner to be included in the commissioning
        """
        logger.info("Creating VPN handler object")

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        # Shared static commission payload. Only vpn-csr field shall be edited by this class
        self.vpn_channel: Queue[str] = vpn_channel
        self.status_channel: Queue[StatusReport] = status_channel

        # VPN Server ID variables
        self._local_server_id: NuvlaID | None = None
        self._nuvla_server_id: NuvlaID = self.nuvla_client.nuvlaedge.vpn_server_id

        # Client configuration data structure
        self.vpn_config: VPNConfig | None = None
        self.load_vpn_config()
        self.vpn_extra_conf: str = vpn_extra_conf

        # Last VPN credentials used to create the VPN configuration
        self.vpn_credential: CredentialResource = ...
        self.load_credential()

        # Last VPN server configuration used to create the client VPN configuration
        self.vpn_server: InfrastructureServiceResource = ...
        self.load_vpn_server()

        if not self.VPN_FOLDER.exists():
            logger.info("Create VPN directory tree")
            self.VPN_FOLDER.mkdir()

        NuvlaEdgeStatusHandler.starting(self.status_channel, self.__class__.__name__)

    def certificates_exists(self) -> bool:
        """
        Checks if the VPN key and certificate signing request files exist and are not empty.

        Returns:
            bool: True if both files exist and are not empty, False otherwise.
        """
        return (utils.file_exists_and_not_empty(self.VPN_KEY_FILE) and
                utils.file_exists_and_not_empty(self.VPN_CSR_FILE))

    @staticmethod
    def get_vpn_ip():
        """
        Static method to retrieve the VPN IP from a file.

        Returns:
            str or None: The VPN IP address read from the file, or None if the file is empty or doesn't exist.


        """
        if utils.file_exists_and_not_empty(FILE_NAMES.VPN_IP_FILE):
            with FILE_NAMES.VPN_IP_FILE.open('r') as f:
                return f.read().splitlines()[0]
        else:
            logger.error(f"Cannot infer VPN IP.")
            return None

    def check_vpn_client_state(self) -> tuple[bool, bool]:
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

    def wait_certificates_ready(self, timeout: int = 25):
        """
        Waits for generated certificates to be ready.
        Args:
            timeout: (25s) Time before raising timeout

        Returns: None
        Raises: Timeout if certificates files do not show in the location (Class Constant) after Timeout
        """
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time < timeout:

            if self.certificates_exists():
                return
            time.sleep(0.3)

        raise TimeoutError("Certificates not generated in time in target locations: \n"
                           f"KEY: {self.VPN_KEY_FILE} \n"
                           f"CSR: {self.VPN_CSR_FILE}")

    def wait_credential_creation(self, timeout: int = 25):
        """
        Waits for the creation of VPN credentials in Nuvla for a given timeout period.

        Args:
            timeout (int): The maximum time in seconds to wait for the credentials to be created. Default is 25 seconds.

        Returns:
            bool: True if the credentials are created within the timeout period, False otherwise.

        """
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time < timeout:

            if self.nuvla_client.vpn_credential is not None:
                self.vpn_credential = self.nuvla_client.vpn_credential.model_copy(deep=True)
                logger.info("VPN credential created in Nuvla")
                self.save_credential()
                return True
            time.sleep(0.1)

        logger.info(f"VPN credential not created in time with timeout {timeout}")
        return False

    def generate_certificates(self, wait: bool = True):
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
        if utils.file_exists_and_not_empty(self.VPN_KEY_FILE):
            self.VPN_KEY_FILE.unlink(True)
        if utils.file_exists_and_not_empty(self.VPN_CSR_FILE):
            self.VPN_CSR_FILE.unlink(True)

        cmd = ['openssl', 'req', '-batch', '-nodes', '-newkey', 'ec', '-pkeyopt',
               'ec_paramgen_curve:secp521r1',
               '-keyout', str(self.VPN_KEY_FILE),
               '-out', str(self.VPN_CSR_FILE),
               '-subj', f'/CN={self.nuvla_client.nuvlaedge_uuid.split("/")[-1]}']

        logger.info(f"Requesting certificates with command: \n {' '.join(cmd)}")
        r = util.execute_cmd(cmd, method_flag=False)

        logger.info(f"Certificate generation response: \n{r.get('stdout')} \n {r.get('stderr')}")
        if r.get('returncode', -1) != 0:
            logger.error(f'Cannot generate certificates for VPN connection: '
                         f'{r.get("stdout")} | {r.get("stderr")}')
            return

        if wait:
            logger.info("Waiting for the certificates to appear")
            self.wait_certificates_ready()

    def trigger_commission(self):
        """
        Commissioning operation is always executed by the Commissioner class.
        Calling this method, we change the commission payload, thus we trigger the commission in the next process.

        Returns: None

        """
        with self.VPN_CSR_FILE.open('r') as f:
            vpn_data = f.read()
            logger.info(f"Triggering commission with VPN Data: {vpn_data}")
            self.vpn_channel.put(vpn_data)

    def vpn_needs_commission(self):
        """
        Checks if a Virtual Private Network (VPN) needs commissioning. There are several conditions that cause
        this method to return True, indicating that commissioning is needed:

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
        if not self.nuvla_client.vpn_credential:
            # There is a VPN server ID defined but there is no VPN credential created
            logger.info("VPN need commission due to missing VPN credential in Nuvla")
            return True

        if self.vpn_credential != self.nuvla_client.vpn_credential:
            # There is missmatch between local credential and Nuvla credential
            logger.info("VPN needs commission due to missmatch local VPN credential and Nuvla credential")
            logger.info(f"Local credential: \n {self.vpn_credential.model_dump_json(indent=True, exclude_none=True)}")
            logger.info(f"Nuvla credential: \n "
                        f"{self.nuvla_client.vpn_credential.model_dump_json(indent=4, exclude_none=True)}")
            return True

        if self.vpn_server.id != self.nuvla_client.nuvlaedge.vpn_server_id:
            # VPN server ID has changed
            logger.info("VPN needs commission due to change in VPN server ID")
            logger.info(f"Server ID: \n {self.vpn_server.id}")
            logger.info(f"Nuvla Server ID: \n {self.nuvla_client.nuvlaedge.vpn_server_id}")
            return True

        return False

    def get_vpn_key(self) -> str:
        """
        Retrieves the VPN key from the VPN key file.

        Returns:
            str: The VPN key read from the VPN key file.

        Raises:
            FileNotFoundError: If the VPN key file is not found.
        """
        with self.VPN_KEY_FILE.open('r') as file:
            return file.read()

    def map_endpoints(self) -> str:
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

    def configure_vpn_client(self):
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
        # Update VPN server data
        self.vpn_config.update(self.nuvla_client.vpn_server)
        # Infrastructure service CA comes with the same key as the VPN credential CA
        # So we need to move it to its corresponding field, then the CA will be automatically
        # replaced
        self.vpn_config.vpn_intermediate_ca_is = self.vpn_server.vpn_intermediate_ca
        logger.debug(f"VPN Configured with VPN Server data \n"
                     f" {self.vpn_config.model_dump_json(indent=4, exclude_none=True)}")
        self.vpn_server = self.nuvla_client.vpn_server.model_copy(deep=True)

        # Update Credentials data
        self.vpn_config.update(self.vpn_credential)
        logger.debug(f"VPN Configured with VPN credential data \n"
                     f" {self.vpn_config.model_dump_json(indent=4, exclude_none=True)}")

        # VPN interface name can be renamed from the agent settings, assign it here
        self.vpn_config.vpn_interface_name = self.VPN_INTERFACE_NAME

        temp_ca = self.vpn_server.vpn_intermediate_ca
        self.vpn_config.vpn_intermediate_ca_is = temp_ca
        self.vpn_config.nuvlaedge_vpn_key = self.get_vpn_key()
        self.vpn_config.vpn_endpoints_mapped = self.map_endpoints()

        # Then save the configuration
        vpn_client_configuration: str = (
            string.Template(util.VPN_CONFIG_TEMPLATE).substitute(self.vpn_config.dump_to_template()))

        self.save_vpn_config(vpn_client_configuration)

    def run(self):
        """
        Main function of the VPN handler has 4 responsibilities:
        - Commissions the VPN, if the VPN-SERVER-ID exists (First time)
            - After, watches the vpn credential in Nuvla. If there are any changes, re-commissions the VPN and
            generates new certificates
        - Generates the certificates of the VPN
        - Configures the OpenVPN client running in a different container using VPN_CONF_FILE

        Returns:

        """
        NuvlaEdgeStatusHandler.running(self.status_channel, 'VPNHandler')

        if not self.nuvla_client.nuvlaedge.vpn_server_id:
            logger.error("VPN is disabled, we should have not reached this point, exiting VPN handler")
            raise WorkerExitException("VPN handler needs a NuvlaEdge with VPN Enabled ")

        vpn_client_exists, _ = self.check_vpn_client_state()
        if not vpn_client_exists:
            logger.error("VPN Client container doesn't exist, this means that it has been disabled in the installation"
                         "process. However, it was activated during NuvlaEdge creation.")
            raise VPNConfigurationMissmatch("VPN client is not running although the VPN was enabled when creating the "
                                            "NuvlaEdge, cannot run...")

        if not self.vpn_needs_commission():
            logger.info("VPN credentials aligned. No need for commissioning")
            return

        logger.info("Starting VPN commissioning...")

        # Generate SSL certificates
        logger.info("Request SSL certificate generation")
        self.generate_certificates()

        logger.info("Conform the certificate sign request and send it to Nuvla via commissioning")
        self.trigger_commission()

        # Wait for VPN credential to show up in Nuvla (Timeout needs to be commissioner_period + sometime
        if not self.wait_credential_creation(timeout=60+15):
            logger.info("VPN credential wasn't created in time. Cannot start the VPN client. Will try in the next"
                        "iteration")
            # VPN credential wasn't created in time. Do not continue
            raise VPNCredentialCreationTimeOut("VPN credential wasn't created in time. Cannot start the VPN client")

        # Then we need to (re)configure the VPN client
        self.configure_vpn_client()

    def load_credential(self):
        if utils.file_exists_and_not_empty(self.VPN_CREDENTIAL_FILE):
            with self.VPN_CREDENTIAL_FILE.open('r') as f:
                self.vpn_credential = CredentialResource.model_validate(json.load(f))
        else:
            self.vpn_credential = CredentialResource()

    def save_credential(self):
        with self.VPN_CREDENTIAL_FILE.open('w') as f:
            json.dump(self.nuvla_client.vpn_credential.model_dump(exclude_none=True, by_alias=True), f)

    def load_vpn_config(self):
        if utils.file_exists_and_not_empty(self.VPN_CONF_FILE):
            with self.VPN_CONF_FILE.open('r') as f:
                self.vpn_config = VPNConfig.model_validate(json.load(f))
        else:
            self.vpn_config = VPNConfig()

    def save_vpn_config(self, vpn_client_conf: str):
        with self.VPN_PLAIN_CONF_FILE.open('w') as f:
            json.dump(self.vpn_config.model_dump(exclude_none=True, by_alias=True), f)

        utils.atomic_write(self.VPN_CONF_FILE, vpn_client_conf)

    def load_vpn_server(self):
        if utils.file_exists_and_not_empty(self.VPN_SERVER_FILE):
            with self.VPN_SERVER_FILE.open('r') as f:
                self.vpn_server = InfrastructureServiceResource.model_validate(json.load(f))
        else:
            self.vpn_server = InfrastructureServiceResource()

    def save_vpn_server(self):
        with self.VPN_SERVER_FILE.open('w') as f:
            json.dump(self.vpn_server.model_dump(exclude_none=True, by_alias=True), f)
