"""
    NuvlaEdge data structure for container stats
"""
from typing import Union, Dict, List

from nuvlaedge.agent.monitor import BaseDataStructure


class ContainerStatsData(BaseDataStructure):
    """ Data structure for docker information report """
    id: Union[str, None]
    name: Union[str, None]
    container_status: Union[str, None]
    cpu_percent: Union[str, None]
    mem_usage_limit: Union[str, None]
    mem_percent: Union[str, None]
    net_in_out: Union[str, None]
    blk_in_out: Union[str, None]
    restart_count: Union[int, None]


class ClusterStatusData(BaseDataStructure):
    """
    Cluster related data structure
    """
    # ID's
    node_id: Union[str, None]
    cluster_id: Union[str, None]

    # Cluster handling
    orchestrator: Union[str, None]
    cluster_node_role: Union[str, None]
    cluster_managers: Union[List, None]
    cluster_join_address: Union[str, None]
    cluster_nodes: Union[List, None]
    cluster_node_labels: Union[List[Dict], None]


class DeploymentData(BaseDataStructure):
    """ Data structure to gather the container stats together"""
    # Container information
    containers: Union[Dict[str, ContainerStatsData], None]

    # Cluster data
    cluster_data: Union[ClusterStatusData, None]

    # Orchestrator version
    docker_server_version: Union[str, None]
    kubelet_version: Union[str, None]
    swarm_node_cert_expiry_date: Union[str, None]
