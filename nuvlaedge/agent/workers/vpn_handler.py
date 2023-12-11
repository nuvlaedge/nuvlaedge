import json
import logging
import string
import time
from pathlib import Path
from queue import Queue
from typing import Optional

import docker.errors

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


logger: logging.Logger = logging.getLogger(__name__)


class VPNConfigurationMissmatch(Exception):
    """ Raised when VPN handler, nuvlabox resource and nuvlaedge engine configurations do not match"""
    ...


class VPNCredentialCreationTimeOut(Exception):
    """ Raised when the VPN credential is not created in time. This makes impossible for the VPN the work"""


class VPNConfig(NuvlaEdgeStaticModel):
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

    def certificates_exists(self) -> bool:
        return (utils.file_exists_and_not_empty(self.VPN_KEY_FILE) and
                utils.file_exists_and_not_empty(self.VPN_CSR_FILE))

    @staticmethod
    def get_vpn_ip():
        """

        Returns:

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
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time < timeout:
            if self.nuvla_client.vpn_credential is not None:
                self.vpn_credential = self.nuvla_client.vpn_credential.model_copy(deep=True)
                logger.info("VPN credential created in Nuvla")
                self.save_credential()
                return True

        logger.info(f"VPN credential not created in time with timeout {timeout}")
        return False

    def generate_certificates(self, wait: bool = True):
        """
        Generates the certificates for the VPN. If invoked, it will remove any previous certificate before starting
        Returns: None

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
        Checks if it is either the first time we run the NuvlaEdge or Nuvla VPN server has changed
        Returns: bool

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
        with self.VPN_KEY_FILE.open('r') as file:
            return file.read()

    def map_endpoints(self) -> str:
        vpn_conf_endpoints = ''
        for connection in self.vpn_server.vpn_endpoints:
            vpn_conf_endpoints += \
                "\n<connection>\nremote {} {} {}\n</connection>\n".format(
                    connection["endpoint"],
                    connection["port"],
                    connection["protocol"])
        return vpn_conf_endpoints

    def configure_vpn_client(self):

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
