"""
    NuvlaEdge data structure for container stats
"""
from typing import Union

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.agent.workers.monitor import BaseDataStructure


class ContainerStatsDataOld(BaseDataStructure):
    """ Data structure for docker information report """
    id: str | None = None
    name: str | None = None
    container_status: str | None = None
    cpu_percent: str | None = None
    mem_usage_limit: str | None = None
    mem_percent: str | None = None
    net_in_out: str | None = None
    blk_in_out: str | None = None
    restart_count: int | None = None


class ContainerStatsData(BaseDataStructure):
    id: str | None = None
    name: str | None = None
    image: str | None = None
    status: str | None = None
    state: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    restart_count: int | None = None
    cpu_usage: float | None = None
    cpu_limit: float | None = None
    cpu_capacity: int | None = None
    mem_usage: int | None = None
    mem_limit: int | None = None
    disk_in: int | None = None
    disk_out: int | None = None
    net_in: int | None = None
    net_out: int | None = None


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
    containers: dict[str, Union[ContainerStatsData, ContainerStatsDataOld]] | None = None

    # Cluster data
    cluster_data: ClusterStatusData | None = None

    # Orchestrator version
    docker_server_version: str | None = None
    kubelet_version: str | None = None
    swarm_node_cert_expiry_date: str | None = None
