import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from nuvlaedge.agent.nuvla.resources.infrastructure_service import InfrastructureServiceResource
from nuvlaedge.agent.nuvla.resources.credential import CredentialResource
from nuvlaedge.agent.worker.worker import WorkerExitException
from nuvlaedge.common import utils
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.common import util
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.worker.workers.commissioner import CommissioningAttributes

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = logging.getLogger(__name__)


class VPNConfig(NuvlaEdgeStaticModel):
    vpn_certificate: str
    vpn_intermediate_ca: str
    vpn_intermediate_ca_is: bool
    vpn_ca_certificate: str
    vpn_shared_key: str
    vpn_common_name_prefix: str
    vpn_interface_name: str
    nuvlaedge_vpn_key: str
    vpn_extra_config: str


class VPNHandler:
    VPN_FOLDER: Path = Path('/tmp/nuvlaedge/vpn/')
    VPN_IP_FILE: Path = Path('/tmp/nuvlaedge/vpn/ip')
    VPN_CSR_FILE: Path = Path('/tmp/nuvlaedge/vpn/nuvlaedge-vpn.csr')
    VPN_KEY_FILE: Path = Path('/tmp/nuvlaedge/vpn/nuvlaedge-vpn.key')
    VPN_CONF_FILE: Path = Path('/tmp/nuvlaedge/vpn/nuvlaedge.conf')
    VPN_PLAIN_CONF_FILE: Path = Path('/tmp/nuvlaedge/vpn/client_vpn_conf.json')
    VPN_CREDENTIAL_FILE: Path = Path('/tmp/nuvlaedge/vpn/vpn-credential')
    VPN_SERVER_FILE: Path = Path('/tmp/nuvlaedge/vpn/vpn-server')
    VPN_INTERFACE_NAME: str = 'vpn'

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 commission_payload: CommissioningAttributes):
        """
        Controls and configures the VPN client based on configuration parsed by the agent. It  commissions itself
        via the commissioner class by editing the field `self.commission_payload.vpn_csr`.

        If this object is instantiated and then running, we assume VPN is enabled. It should be the agent (via
        configuration) who starts/stops/disables the VPN.

        Args:
            coe_client:
            nuvla_client:
            commission_payload:
        """
        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        # Shared static commission payload. Only vpn-csr field shall be edited by this class
        self.commission_payload: CommissioningAttributes = commission_payload

        # VPN Server ID variables
        self._local_server_id: NuvlaID | None = None
        self._nuvla_server_id: NuvlaID = self.nuvla_client.nuvlaedge.vpn_server_id

        self.nuvla_client.add_watched_field("nuvlabox", "vpn-server-id")

        # Client configuration data structure
        self.vpn_config: VPNConfig = ...
        self.load_vpn_config()

        # Last VPN credentials used to create the VPN configuration
        self.vpn_credential: CredentialResource = ...
        self.load_credential()

        # Last VPN server configuration used to create the client VPN configuration
        self.vpn_server: InfrastructureServiceResource = ...
        self.load_vpn_server()

    def certificates_exists(self) -> bool:
        return (utils.file_exists_and_not_empty(self.VPN_KEY_FILE) and
                utils.file_exists_and_not_empty(self.VPN_CSR_FILE))

    def get_vpn_ip(self):
        """

        Returns:

        """
        if utils.file_exists_and_not_empty(self.VPN_IP_FILE):
            with self.VPN_IP_FILE.open('r') as f:
                return f.read().splitlines()[0]
        else:
            logger.error(f"Cannot infer VPN IP.")
            return None

    def wait_certificates_ready(self, timeout: int = 25):
        """
        Waits for generated certificates to be ready.
        Args:
            timeout: (25s) Time before raising timeout

        Returns: None
        Raises: Timeout if certificates files do not show in the location (Class Constant) after Timeout
        """
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time > timeout:
            if self.certificates_exists():
                return
            time.sleep(0.3)

        raise TimeoutError("Certificates not generated in time in target locations: \n"
                           f"KEY: {self.VPN_KEY_FILE} \n"
                           f"CSR: {self.VPN_CSR_FILE}")

    def wait_credential_creation(self, timeout: int = 25):
        start_time: float = time.perf_counter()

        while time.perf_counter() - start_time > timeout:
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
            self.VPN_KEY_FILE.unlink(True)

        cmd = ['openssl', 'req', '-batch', '-nodes', '-newkey', 'ec', '-pkeyopt',
               'ec_paramgen_curve:secp521r1',
               '-keyout', str(self.VPN_KEY_FILE.name),
               '-out', str(self.VPN_CSR_FILE),
               '-subj', f'/CN={self.nuvla_client.nuvlaedge_uuid.split("/")[-1]}']

        r = util.execute_cmd(cmd, method_flag=False)

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
            vpn_data = json.load(f)
            logger.info(f"Triggering commission with VPN Data: {vpn_data}")
            self.commission_payload.vpn_csr = json.load(f)

    def vpn_needs_commission(self):
        """
        Checks if it is either the first time we run the NuvlaEdge or Nuvla VPN server has changed
        Returns: bool

        """
        if not self.nuvla_client.vpn_credential:
            # There is a VPN server ID defined but there is no VPN credential created
            return True

        if self.vpn_credential != self.nuvla_client.vpn_credential:
            # There is missmatch between local credential and Nuvla credential
            return True

        if self.nuvla_client.nuvlaedge.vpn_server_id != self.vpn_server.id:
            # VPN server ID has changed
            return True

        return False

    def configure_vpn_client(self):
        if not self.vpn_config:
            self.vpn_config = VPNConfig()

        # Update VPN server data
        self.vpn_config.update(self.nuvla_client.vpn_server)
        self.vpn_config = self.nuvla_client.vpn_server.model_copy(deep=True)

        # Update Credentials data
        self.vpn_config.update(self.vpn_credential)

        # Then save the configuration
        self.save_vpn_config()

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

        if self.vpn_needs_commission():
            self.generate_certificates()
            self.trigger_commission()
            # Wait for VPN credential to show up in Nuvla (Timeout needs to be commissioner_period + sometime
            if not self.wait_credential_creation(timeout=60+15):
                logger.info("VPN credential wasn't created in time. Cannot start the VPN client. Will try in the next"
                            "iteration")
                # VPN credential wasn't created in time. Do not continue
                return

            # Then we need to (re)configure the VPN client
            self.configure_vpn_client()

    def load_credential(self):
        if utils.file_exists_and_not_empty(self.VPN_CREDENTIAL_FILE):
            with self.VPN_CREDENTIAL_FILE.open('r') as f:
                self.vpn_credential = CredentialResource.model_validate_json(json.load(f))

    def save_credential(self):
        with self.VPN_CREDENTIAL_FILE.open('w') as f:
            json.dump(self.nuvla_client.vpn_credential.model_dump(exclude_none=True, by_alias=True), f)

    def load_vpn_config(self):
        if utils.file_exists_and_not_empty(self.VPN_CONF_FILE):
            with self.VPN_CONF_FILE.open('r') as f:
                self.vpn_config = VPNConfig.model_validate_json(json.load(f))

    def save_vpn_config(self):
        with self.VPN_CONF_FILE.open('w') as f:
            json.dump(self.vpn_config.model_dump(exclude_none=True, by_alias=True), f)

    def load_vpn_server(self):
        if utils.file_exists_and_not_empty(self.VPN_SERVER_FILE):
            with self.VPN_SERVER_FILE.open('r') as f:
                self.vpn_server = InfrastructureServiceResource.model_validate_json(json.load(f))

    def save_vpn_server(self):
        with self.VPN_SERVER_FILE.open('w') as f:
            json.dump(self.vpn_server.model_dump(exclude_none=True, by_alias=True), f)





