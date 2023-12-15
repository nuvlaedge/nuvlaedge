"""
Commissioner controls the Commission operation in NuvlaEdge

Commission operation controls infrastructure-services and credentails of the NuvlaEdge
In this case, commission controls the credentials of the swarm/kubernetes cluster and the vpn.
As well as creating the corresponding infrastructure service and cluster resources for either swarm or kubernetes

"""
import json
import logging
from pathlib import Path
from queue import Queue
from typing import Optional

from nuvlaedge.agent.common import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.agent.workers.telemetry import model_diff
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.common.utils import file_exists_and_not_empty
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class CommissioningAttributes(NuvlaEdgeStaticModel):
    tags:                   Optional[list[str]] = None
    capabilities:           Optional[list[str]] = None

    # VPN
    vpn_csr:                Optional[str] = None

    # Docker
    swarm_endpoint:         Optional[str] = None
    swarm_token_manager:    Optional[str] = None
    swarm_token_worker:     Optional[str] = None
    swarm_client_key:       Optional[str] = None
    swarm_client_cert:      Optional[str] = None
    swarm_client_ca:        Optional[str] = None

    # Minio
    minio_endpoint:         Optional[str] = None
    minio_access_key:       Optional[str] = None
    minio_secret_key:       Optional[str] = None

    # Kubernetes
    kubernetes_endpoint:    Optional[str] = None
    kubernetes_client_key:  Optional[str] = None
    kubernetes_client_cert: Optional[str] = None
    kubernetes_client_ca:   Optional[str] = None

    # Clusters
    cluster_id:             Optional[str] = None
    cluster_worker_id:      Optional[str] = None
    cluster_orchestrator:   Optional[str] = None
    cluster_managers:       Optional[list[str]] = None
    cluster_workers:        Optional[list[str]] = None

    removed:                Optional[list[str]] = None


class Commissioner:
    """
    Compares the information in Nuvla with the system configuration and commissions any difference
    """
    COMMISSIONING_FILE: Path = FILE_NAMES.COMMISSIONING_FILE

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 status_channel: Queue[StatusReport],
                 vpn_channel: Queue[str]):
        """

        Args:
            coe_client: Common container orchestration engine (Shared amongst all Agent components)
            nuvla_client: NuvlaEdgeClientWrapper shared in the agent (Only for retrival and commission)
            commission_payload: This is a shared variable between commissioner and VPN handler. VPN handler should only
                edit vpn_csr. The rest is handled by this class
        """

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client
        self.vpn_channel: Queue[str] = vpn_channel
        self.status_channel: Queue[StatusReport] = status_channel

        self._last_payload: CommissioningAttributes = CommissioningAttributes()
        # Static payload. Address should only change or updated from the agent
        self._current_payload: CommissioningAttributes = CommissioningAttributes()

        # Find the commissioning file and load it as _last_payload if exists
        self.load_previous_commission()

        NuvlaEdgeStatusHandler.starting(self.status_channel, 'commissioner')

    def commission(self):
        logger.info(f"Commissioning NuvlaEdge with data:"
                    f" {self._current_payload.model_dump(mode='json', exclude_none=True, by_alias=True)}")

        # Get new field
        new_fields, removed_fields = model_diff(self._last_payload, self._current_payload)
        logger.info("New fields: \n {}".format(new_fields))
        logger.info("Removed fields:\n {}".format(removed_fields))

        if self.nuvla_client.commission(payload=self._current_payload.model_dump(exclude_none=True,
                                                                                 by_alias=True,
                                                                                 include=new_fields)):
            self._last_payload = self._current_payload.model_copy(deep=True)
            self.save_commissioned_data()

    @property
    def nuvlaedge_uuid(self) -> NuvlaID:
        return self.nuvla_client.nuvlaedge_uuid

    def update_cluster_data(self):
        """
        Updates fields if available:
            'cluster-id'
            'cluster-orchestrator'
            'cluster-managers'
            'cluster-workers'
        Returns: None
        """
        cluster_info = self.coe_client.get_cluster_info(
            default_cluster_name=f"cluster_{self.nuvlaedge_uuid}"
        )
        logger.debug(f"Newly gathered cluster information: {json.dumps(cluster_info, indent=4)}")

        if cluster_info:
            self._current_payload.update(cluster_info)
        logger.debug(f"Current payload: "
                     f"{json.dumps(self._current_payload.model_dump(exclude_none=True, by_alias=True))}")

        # Current implementation requires not to commission cluster data until nuvlaedge-status has been updated with
        # node-id. Why not node-id here? Mysteries of life...

    def update_coe_data(self):
        """
        Gather Infrastructure service information

        For docker swarm:
        - swarm-endpoint
        - swarm-client-ca
        - swarm-client-cert
        - swarm-client-key
        (If K8s available, we also parse K8s data)

        For Kubernetes:
        - kubernetes-endpoint
        - kubernetes-client-ca
        - kubernetes-client-cert
        - kubernetes-client-key
        """
        nuvlaedge_endpoint = self.build_nuvlaedge_endpoint()
        tls_keys = self.get_tls_keys()
        nuvla_infra_service = self.coe_client.define_nuvla_infra_service(nuvlaedge_endpoint, *tls_keys)
        logger.info(f"Updating COE data: {json.dumps(nuvla_infra_service, indent=4)}")
        self._current_payload.update(nuvla_infra_service)

        # Only required for Docker

        if self.coe_client.ORCHESTRATOR_COE == 'swarm':
            logger.info("Updating Swarm Join Tokens")
            manager_token, worker_token = self.coe_client.get_join_tokens()
            self._current_payload.swarm_token_manager = manager_token
            self._current_payload.swarm_token_worker = worker_token

    def update_attributes(self):
        """

        This method updates the attributes of the object based on the current status of the Nuvla Box
        and the Nuvla Edge status.

        - If the Nuvla Edge status contains a node_id, the cluster data is updated by calling `update_cluster_data()`.
        - Otherwise, a log message is displayed indicating that the Nuvla Box status is not yet ready.

        After updating the cluster data, the method retrieves the Nuvla Edge capabilities
        using `get_nuvlaedge_capabilities()` and updates the COE data.

        Returns:
            None.
        """
        if self.nuvla_client.nuvlaedge_status.node_id:
            logger.info("Updating Cluster data, node id present in NuvlaEdge-status")
            self.update_cluster_data()
        else:
            logger.info(f"Nuvlabox-status still not ready. It should be updated in a bit...")

        self._current_payload.capabilities = self.get_nuvlaedge_capabilities()
        self.update_coe_data()

    def run(self):
        """
        Runs the commissioning checks and performs necessary actions based on the current and last payload.

        Returns:
            None
        """
        logger.info("Running Commissioning checks")
        NuvlaEdgeStatusHandler.running(self.status_channel, 'commissioner')

        self.update_attributes()
        if not self.vpn_channel.empty():
            logger.info("Retrieving certificate sign requests from VPN")
            vpn_csr = self.vpn_channel.get(block=False)

            logger.info(f"Data received from VPN: {vpn_csr}")
            self._current_payload.vpn_csr = vpn_csr

        # Compare what have been sent to Nuvla (_last_payload) and whatis locally updated (_current_payload)
        if self._last_payload != self._current_payload:
            logger.info("Payloads are different, go commission")
            logger.info(f"Last Payload: \n {json.dumps(sorted(self._last_payload.model_dump(exclude_none=True)),indent=4)}")
            logger.info(f"Current Payload: \n {json.dumps(sorted(self._current_payload.model_dump(exclude_none=True)), indent=4)}")
            self.commission()

            # VPN CSR needs to be removed after commissioning from last payload. TODO: Maybe not...
            # self._last_payload.vpn_csr = None
            # self._current_payload.vpn_csr = None
        else:
            logger.info("Nothing to commission, system configuration remains the same.")

    @staticmethod
    def get_nuvlaedge_capabilities() -> list[str]:
        return ['NUVLA_HEARTBEAT', 'NUVLA_JOB_PULL']

    @staticmethod
    def get_tls_keys() -> tuple:
        """
        Retrieves the TLS keys required for container orchestration API.

        Returns:
            Tuple: A tuple containing the client CA, client certificate, and client key as strings.

            If the TLS keys have not been set yet or if there is any error in reading the keys, an empty tuple will
             be returned.

        """
        try:
            with FILE_NAMES.CA.open('r') as file:
                client_ca = file.read()
            with FILE_NAMES.CERT.open('r') as file:
                client_cert = file.read()
            with FILE_NAMES.KEY.open('r') as file:
                client_key = file.read()

        except (FileNotFoundError, IndexError):
            logger.debug("Container orchestration API TLS keys have not been set yet!")
            return ()

        return client_ca, client_cert, client_key

    def build_nuvlaedge_endpoint(self) -> str | None:
        """
        Based on the available information, builds the NuvlaEdge endpoint. After the rework of the heartbeat and
        first removal of the ComputeAPI, this starts to not make sense.
        If VPN is available, ignore ComputeAPI address and take the port.

        Returns: The IP and port endpoint of NuvlaEdge

        """
        endpoint = "https://{ip}:{port}"
        vpn_ip = VPNHandler.get_vpn_ip()  # TODO: Find a way of retrieving VPN
        api_address, api_port = self.coe_client.get_api_ip_port()

        if vpn_ip and api_port:
            return endpoint.format(ip=vpn_ip, port=api_port)

        if api_address and api_port:
            return endpoint.format(ip=api_address, port=api_port)

        return None

    def load_previous_commission(self) -> None:
        """
        Method to load previous commissioning data from a file.

        """
        if not file_exists_and_not_empty(self.COMMISSIONING_FILE):
            logger.info(f"No commissioning file found in {self.COMMISSIONING_FILE}. "
                        f"NuvlaEdge is probably never been commissioned before")
            return

        logger.info("Loading previous commissioning data")
        with self.COMMISSIONING_FILE.open('r') as f:
            try:
                prev_payload = json.load(f)
                prev_nuvlaedge_uuid = prev_payload['nuvlaedge_uuid']
                if prev_nuvlaedge_uuid != self.nuvlaedge_uuid:
                    logger.warning("Detected previous installation of NuvlaEdge WHAT TO DO????")  # FIXME: Decide what to do here
                    # For the moment just override it
                    self._last_payload = CommissioningAttributes()
                    return
                self._last_payload = CommissioningAttributes.model_validate(prev_payload)
                self._current_payload = self._last_payload.model_copy(deep=True)
            except json.JSONDecodeError:
                logger.warning("Error decoding previous commission")

    def save_commissioned_data(self) -> None:
        with self.COMMISSIONING_FILE.open('w') as f:
            data = self._last_payload.model_dump(exclude_none=True, by_alias=True)
            data['nuvlaedge_uuid'] = self.nuvlaedge_uuid
            json.dump(data, f)
