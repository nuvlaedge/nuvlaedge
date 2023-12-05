"""

"""
import json
import logging
from pprint import pprint
import time
from pathlib import Path
from typing import Optional

import mock

from agent.common import util
from common import utils
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.common._nuvlaedge_common import get_vpn_ip
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = logging.getLogger(__name__)


class CommissioningAttributes(NuvlaEdgeStaticModel):
    tags:                   Optional[list[str]] = None
    capabilities:           Optional[list[str]] = None #

    # VPN
    vpn_csr:                Optional[dict] = None

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
    cluster_worker_id:      Optional[str] = None #
    cluster_orchestrator:   Optional[str] = None
    cluster_managers:       Optional[list[str]] = None
    cluster_workers:        Optional[list[str]] = None

    removed:                Optional[list[str]] = None


class Commissioner:
    """
    Compares the information in Nuvla with the system configuration and commissions any difference
    """
    COMMISSIONING_FILE: Path = Path("/tmp/nuvlaedge/commissioned_data.json")

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 commission_payload: CommissioningAttributes):
        """

        Args:
            coe_client: Common container orchestration engine (Shared amongst all Agent components)
            nuvla_client: NuvlaEdgeClientWrapper shared in the agent (Only for retrival and commission)
            commission_payload: This is a shared variable between commissioner and VPN handler. VPN handler should only
                edit vpn_csr. The rest is handled by this class
        """

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        self._last_payload: CommissioningAttributes = ...
        # Static payload. Address should only change or updated from the agent
        self._current_payload: CommissioningAttributes = commission_payload

        # Find the commissioning file and load it as _last_payload if exists
        self.load_previous_commission()

    def commission(self):
        # if self.nuvla_client.commission(payload=self._current_payload.model_dump(exclude_none=True)):
        #     self._last_payload = self._current_payload.model_copy(deep=True)

        logger.info(f"Commissioning NuvlaEdge with data:"
                    f" {self._current_payload.model_dump(mode='json', exclude_none=True, by_alias=True)}")
        self._last_payload.update(self._current_payload)

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
            default_cluster_name=f"cluster_{self.nuvla_client.nuvlaedge_uuid}"
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

        Returns:

        """
        """ Gather Infrastructure service information 
        For docker swarm:
            - swarm-endpoint
            - swarm-client-ca
            - swarm-client-cert
            - swarm-client-key
            (If K8s available, we alse parse K8s data)
        For Kubernetes
            - kubernetes-endpoint
            - kubernetes-client-ca
            - kubernetes-client-cert
            - kubernetes-client-key
        """
        nuvlaedge_endpoint = self.build_nuvlaedge_endpoint()
        tls_keys = self.get_tls_keys()
        nuvla_infra_service = self.coe_client.define_nuvla_infra_service(nuvlaedge_endpoint, *tls_keys)
        logger.debug(f"Updating COE data: {json.dumps(nuvla_infra_service, indent=4)}")
        self._current_payload.update(nuvla_infra_service)

        # Only required for Docker
        if self.coe_client.ORCHESTRATOR_COE == 'swarm':
            logger.info("Updating Swarm Join Tokens")
            manager_token, worker_token = self.coe_client.get_join_tokens()
            self._current_payload.swarm_token_manager = manager_token
            self._current_payload.swarm_token_worker = worker_token

    def update_attributes(self):
        self.update_cluster_data()

        self._current_payload.capabilities = self.get_nuvlaedge_capabilities()
        self.update_coe_data()

    def run(self):
        self.update_attributes()

        # Compare what have been sent to Nuvla (_last_payload) and whatis locally updated (_current_payload)
        if self._last_payload != self._current_payload:
            self.commission()

    @staticmethod
    def get_nuvlaedge_capabilities() -> list[str]:
        return ['NUVLA_HEARTBEAT', 'NUVLA_JOB_PULL']

    @staticmethod
    def get_tls_keys():
        """ Finds and returns the Container orchestration API client TLS keys. The keys are created by the
        Compute API """

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

    def build_nuvlaedge_endpoint(self) -> str:
        """
        Based on the available information, builds the NuvlaEdge endpoint. After the rework of the heartbeat and
        first removal of the ComputeAPI, this starts to not make sense.
        If VPN is available, ignore ComputeAPI address and take the port.

        Returns: The IP and port endpoint of NuvlaEdge

        """
        endpoint = "https://{ip}:{port}"
        vpn_ip = get_vpn_ip()
        api_address, api_port = self.coe_client.get_api_ip_port()

        if vpn_ip and api_port:
            endpoint.format(ip=vpn_ip, port=api_port)
            return endpoint

        if api_address and api_port:
            endpoint.format(ip=api_address, port=api_port)
            return endpoint

        return 'local'

    def load_previous_commission(self) -> None:
        """

        Returns:

        """
        if not utils.file_exists_and_not_empty(self.COMMISSIONING_FILE):
            logger.info(f"No commissioning file found in {self.COMMISSIONING_FILE}. "
                        f"NuvlaEdge is probably never commissioned before")
            return

        logger.info("Loading previous commissioning data")
        with self.COMMISSIONING_FILE.open('r') as f:
            self._last_payload = CommissioningAttributes.model_validate_json(json.load(f))

    def save_commissioned_data(self) -> None:
        with self.COMMISSIONING_FILE.open('w') as f:
            json.dump(self._last_payload.model_dump(exclude_none=True, by_alias=True), f)


if __name__ == '__main__':

    payload = CommissioningAttributes()
    comm = Commissioner(
        coe_client=DockerClient(),
        nuvla_client=mock.Mock(),
        commission_payload=payload
    )

    comm.run()
# i = 3
# while i >= 0:
#     comm.run()
#     i -= 1
#     time.sleep(5)
