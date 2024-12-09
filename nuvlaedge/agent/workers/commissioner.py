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

from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.models import model_diff
from nuvlaedge.agent.nuvla.resources import NuvlaID, State
from nuvlaedge.common.file_operations import file_exists_and_not_empty, write_file, read_file
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = get_nuvlaedge_logger(__name__)
_status_module_name = 'Commissioner'


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
        The Commissioner class is responsible for controlling the Commission operation in NuvlaEdge.

        The Commission operation controls infrastructure-services and credentials of the NuvlaEdge. In this case,
        commission controls the credentials of the swarm/kubernetes cluster and the VPN, as well as creating the
        corresponding infrastructure service and cluster resources for either swarm or kubernetes.

        Attributes:
            COMMISSIONING_FILE (Path): Path to the file where commissioning data is stored.
            coe_client (COEClient): Client to interact with the container orchestration engine.
            nuvla_client (NuvlaClientWrapper): Client to interact with Nuvla.
            status_channel (Queue[StatusReport]): Channel to send status updates.
            _last_payload (CommissioningAttributes): The last payload data sent to Nuvla.
            _current_payload (CommissioningAttributes): The current payload data to be sent to Nuvla.
    """

    COMMISSIONING_FILE: Path = FILE_NAMES.COMMISSIONING_FILE

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 status_channel: Queue[StatusReport]):
        """ Constructor
        Args:
            coe_client (COEClient): Client to interact with the container orchestration engine
            nuvla_client (NuvlaClientWrapper): Client to interact with Nuvla
            status_channel (Queue[StatusReport]): Channel to send status updates
        """
        logger.info("Creating commissioner object...")

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client
        self.status_channel: Queue[StatusReport] = status_channel

        self._last_payload: CommissioningAttributes = CommissioningAttributes()
        # Static payload. Address should only change or updated from the agent
        self._current_payload: CommissioningAttributes = CommissioningAttributes()

        # Find the commissioning file and load it as _last_payload if exists
        self._load_previous_commission()

        NuvlaEdgeStatusHandler.starting(self.status_channel, _status_module_name)

    def _commission(self):
        """ Executes the commissioning operation.

        This method compares the last payload sent to Nuvla (_last_payload) and the current payload (_current_payload).
        If there are any changes, it prepares a new commission payload with the changed/new fields and removed fields.
        The new commission payload is then sent to Nuvla for commissioning.

        If the commissioning is successful, the last payload is updated with the current payload and the commissioning data
        is saved to a file.
        """
        # Get new field
        new_fields, removed_fields = model_diff(self._last_payload, self._current_payload)
        logger.debug(f"Commissioning changed/new fields: "
                     f"{self._current_payload.model_dump_json(indent=4, include=new_fields, by_alias=True)} ")
        logger.debug(f"Commissioning removed fields: {removed_fields}")
        _commission_payload: dict = self._current_payload.model_dump(exclude_none=True,
                                                                     exclude={'vpn_csr'},
                                                                     by_alias=True,
                                                                     include=new_fields)
        if len(removed_fields) > 0:
            _commission_payload['removed'] = list(removed_fields)

        if self.nuvla_client.commission(payload=_commission_payload):
            self._last_payload = self._current_payload.model_copy(deep=True)
            self._save_commissioned_data()

    @property
    def nuvlaedge_uuid(self) -> NuvlaID:
        return self.nuvla_client.nuvlaedge_uuid

    def _update_cluster_data(self):
        """
        Updates fields if available:
            'cluster-id'
            'cluster-orchestrator'
            'cluster-managers'
            'cluster-workers'
        Returns: None
        """
        cluster_info = self.coe_client.get_cluster_info(
            default_cluster_name=f"cluster_{self.nuvlaedge_uuid}")

        logger.debug(f"Newly gathered cluster information: {json.dumps(cluster_info, indent=4)}")

        if cluster_info:
            self._current_payload.update(cluster_info)
        logger.debug(f"Current payload: "
                     f"{self._current_payload.model_dump_json(exclude_none=True, by_alias=True)}")

        # Current implementation requires not to commission cluster data until nuvlaedge-status has been updated with
        # node-id. Why not node-id here? Mysteries of life...

    def _update_coe_data(self):
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
        # Construct Swarm/K8s endpoint
        nuvlaedge_endpoint = self._build_nuvlaedge_endpoint()

        # Retrieve TLS keys for Docker endpoints
        tls_keys = self.get_tls_keys()

        # Builds the data structure with the required information for the creation/update of the infrastructure service
        nuvla_infra_service = self.coe_client.define_nuvla_infra_service(nuvlaedge_endpoint, *tls_keys)

        # Update the current payload with the infrastructure service information
        self._current_payload.update(nuvla_infra_service)

        # Only required for Docker
        if self.coe_client.ORCHESTRATOR_COE == 'swarm':
            logger.debug("Updating Swarm Join Tokens")
            manager_token, worker_token = self.coe_client.get_join_tokens()
            self._current_payload.swarm_token_manager = manager_token
            self._current_payload.swarm_token_worker = worker_token

    def _update_attributes(self):
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
        if self.nuvla_client.nuvlaedge_status.node_id is not None:
            logger.info("Updating Cluster data, node id present in NuvlaEdge-status")
            self._update_cluster_data()
        else:
            logger.info("Cluster data not yet pushed to telemetry. Waiting to commission it")

        self._current_payload.capabilities = self._get_nuvlaedge_capabilities()
        self._update_coe_data()

    def run(self):
        """
        Runs the commissioning checks and performs necessary actions based on the current and last payload.

        Returns:
            None
        """
        logger.info("Running Commissioning checks")
        NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)

        # Read the current status of the device and update the attributes
        self._current_payload = CommissioningAttributes()
        self._update_attributes()

        # Compare what have been sent to Nuvla (_last_payload) and whatis locally updated (_current_payload)
        if self._last_payload != self._current_payload:
            logger.info("Commissioning data has changed, commissioning...")
            self._commission()
        else:
            logger.info("Nothing to commission, system configuration remains the same.")

    @staticmethod
    def _get_nuvlaedge_capabilities() -> list[str]:
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

    def _build_nuvlaedge_endpoint(self) -> str | None:
        """
        Based on the available information, builds the NuvlaEdge endpoint. After the rework of the heartbeat and
        first removal of the ComputeAPI, this starts to not make sense.
        If VPN is available, ignore ComputeAPI address and take the port.

        Returns: The IP and port endpoint of NuvlaEdge

        """
        endpoint = "https://{ip}:{port}"
        vpn_ip = VPNHandler.get_vpn_ip()
        api_address, api_port = self.coe_client.get_api_ip_port()

        if vpn_ip and api_port:
            return endpoint.format(ip=vpn_ip, port=api_port)

        if api_address and api_port:
            return endpoint.format(ip=api_address, port=api_port)

        return None

    def _load_previous_commission(self) -> None:
        """ Load previous commissioning data from a file. """
        if not file_exists_and_not_empty(self.COMMISSIONING_FILE):
            logger.info(f"No commissioning file found in {self.COMMISSIONING_FILE}. "
                        f"NuvlaEdge is probably never been commissioned before")
            return

        logger.info("Loading previous commissioning data")
        commissioning_data = read_file(self.COMMISSIONING_FILE, decode_json=True)

        if commissioning_data is None:
            commissioning_data = {}

        self._last_payload = CommissioningAttributes.model_validate(commissioning_data)
        self._current_payload = CommissioningAttributes.model_validate(commissioning_data)

    def _save_commissioned_data(self) -> None:
        """
        Saves the last payload data to a file.

        This method dumps the last payload data into a JSON format, excluding any None values.
        It also adds the NuvlaEdge UUID to the data. The resulting data is then written to the
        commissioning file.

        Raises:
            Any exceptions raised by the `write_file` function will be propagated up.
        """
        data = self._last_payload.model_dump(exclude_none=True, by_alias=True)
        write_file(data, self.COMMISSIONING_FILE)
