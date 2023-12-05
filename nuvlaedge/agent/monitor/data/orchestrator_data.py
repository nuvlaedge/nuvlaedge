"""
    NuvlaEdge data structure for container stats
"""
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.agent.monitor import BaseDataStructure


class ContainerStatsData(BaseDataStructure):
    """ Data structure for docker information report """
    id: str | None
    name: str | None
    container_status: str | None
    cpu_percent: str | None
    mem_usage_limit: str | None
    mem_percent: str | None
    net_in_out: str | None
    blk_in_out: str | None
    restart_count: int | None


class ClusterStatusData(NuvlaEdgeBaseModel):
    """
    Cluster related data structure
    """
    # ID's
    node_id: str | None = None
    cluster_id: str | None = None

    # Cluster handling
    orchestrator: str | None = None
    cluster_node_role: str | None = None
    cluster_managers: list | None = None
    cluster_join_address: str | None = None
    cluster_nodes: list | None = None
    cluster_node_labels: list[dict] | None = None


class DeploymentData(BaseDataStructure):
    """ Data structure to gather the container stats together """
    # Container information
    containers: dict[str, ContainerStatsData] | None

    # Cluster data
    cluster_data: ClusterStatusData | None

    # Orchestrator version
    docker_server_version: str | None
    kubelet_version: str | None
    swarm_node_cert_expiry_date: str | None
