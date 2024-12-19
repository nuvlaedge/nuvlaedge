from typing import Optional

from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import Status
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel


class TelemetryPayloadAttributes(NuvlaEdgeStaticModel):
    """

    The TelemetryPayloadAttributes class represents the attributes of a telemetry payload for NuvlaEdge.

    Attributes:
        status (Optional[Status]): The status of the NuvlaEdge system.
        status_notes (Optional[list[str]]): Any additional notes about the status.
        current_time (Optional[str]): The current time of the NuvlaEdge system.

        components (Optional[list[str]]): The components of the NuvlaEdge system.
        nuvlabox_api_endpoint (Optional[str]): The API endpoint of the NuvlaBox.
        nuvlabox_engine_version (Optional[str]): The version of the NuvlaBox engine.
        installation_parameters (Optional[dict]): The installation parameters of the NuvlaBox.
        host_user_home (Optional[str]): The home directory of the NuvlaBox host user.

        resources (Optional[dict]): The resources of the NuvlaEdge system.
        last_boot (Optional[str]): The last boot time of the NuvlaEdge system.
        gpio_pins (Optional[dict]): The GPIO pins of the NuvlaEdge system.
        vulnerabilities (Optional[dict]): The vulnerabilities of the NuvlaEdge system.
        inferred_location (Optional[list[float]]): The inferred location of the NuvlaEdge system.
        network (Optional[dict]): The network configuration of the NuvlaEdge system.
        temperatures (Optional[list]): The temperatures of the NuvlaEdge system.

        operating_system (Optional[str]): The operating system of the NuvlaEdge system.
        architecture (Optional[str]): The architecture of the NuvlaEdge system.
        ip (Optional[str]): The IP address of the NuvlaEdge system.
        hostname (Optional[str]): The hostname of the NuvlaEdge system.
        docker_server_version (Optional[str]): The version of the Docker server.

        node_id (Optional[str]): The ID of the cluster node.
        cluster_id (Optional[str]): The ID of the cluster.
        cluster_managers (Optional[list[str]]): The managers of the cluster.
        cluster_nodes (Optional[list[str]]): The nodes of the cluster.
        cluster_node_role (Optional[str]): The role of the cluster node.
        cluster_node_labels (Optional[list[dict]]): The labels of the cluster node.
        swarm_node_cert_expiry_date (Optional[str]): The expiry date of the swarm node certificate.
        cluster_join_address (Optional[str]): The join address of the cluster.
        orchestrator (Optional[str]): The orchestrator used by the cluster.
        container_plugins (Optional[list[str]]): The container plugins used by the cluster.
        kubelet_version (Optional[str]): The version of the kubelet.

    """
    status:                         Optional[Status] = None
    status_notes:                   Optional[list[str]] = None
    current_time:                   Optional[str] = None

    # NuvlaEdge System configuration
    components:                     Optional[list[str]] = None
    nuvlabox_api_endpoint:          Optional[str] = None
    nuvlabox_engine_version:        Optional[str] = None
    installation_parameters:        Optional[dict] = None
    host_user_home:                 Optional[str] = None

    # Metrics
    resources:                      Optional[dict] = None
    last_boot:                      Optional[str] = None
    gpio_pins:                      Optional[dict] = None
    vulnerabilities:                Optional[dict] = None
    inferred_location:              Optional[list[float]] = None
    network:                        Optional[dict] = None
    temperatures:                   Optional[list] = None

    # System Configuration
    operating_system:               Optional[str] = None
    architecture:                   Optional[str] = None
    ip:                             Optional[str] = None
    hostname:                       Optional[str] = None
    docker_server_version:          Optional[str] = None

    # Cluster information
    node_id:                        Optional[str] = None
    cluster_id:                     Optional[str] = None
    cluster_managers:               Optional[list[str]] = None
    cluster_nodes:                  Optional[list[str]] = None
    cluster_node_role:              Optional[str] = None
    cluster_node_labels:            Optional[list[dict]] = None
    swarm_node_cert_expiry_date:    Optional[str] = None
    cluster_join_address:           Optional[str] = None
    orchestrator:                   Optional[str] = None
    container_plugins:              Optional[list[str]] = None
    kubelet_version:                Optional[str] = None

    # COE raw resources
    coe_resources:                  Optional[dict] = None
