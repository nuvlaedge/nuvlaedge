from typing import Optional
from enum import auto
from strenum import UppercaseStrEnum

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from .base import AutoUpdateNuvlaEdgeTrackedResource, NuvlaResourceBase


class Status(UppercaseStrEnum):
    OPERATIONAL = auto()
    DEGRADED = auto()
    UNKNOWN = auto()


class StatusTelemetry(NuvlaEdgeBaseModel):
    """

    This class represents the telemetry status of a device in the NuvlaEdge system.

    Attributes:
        resources (Optional[dict]): The resources metrics of the device.
        network (Optional[dict]): The network metrics of the device.
        temperatures (Optional[list]): The temperature metrics of the device.
        ip (Optional[str]): The IP address of the device.
        gpio_pins (Optional[dict]): The GPIO pins metrics of the device.
        inferred_location (Optional[list[float]]): The inferred location of the device.

    """
    # Telemetry metrics
    resources: Optional[dict] = None
    network: Optional[dict] = None
    temperatures: Optional[list] = None
    ip: Optional[str] = None
    gpio_pins: Optional[dict] = None
    inferred_location: Optional[list[float]] = None


class StatusSystemConfiguration(NuvlaEdgeBaseModel):
    """
    Class representing the system configuration of a status system.

    Attributes:
        hostname (Optional[str]): The hostname of the system.
        operating_system (Optional[str]): The operating system running on the system.
        architecture (Optional[str]): The architecture of the system.
        last_boot (Optional[str]): The timestamp indicating the last system boot.
        host_user_home (Optional[str]): The home directory of the host user.

    """
    # System configuration
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    architecture: Optional[str] = None
    last_boot: Optional[str] = None
    host_user_home: Optional[str] = None


class StatusNuvlaEdgeConfiguration(NuvlaEdgeBaseModel):
    """
    A class representing the configuration of a NuvlaEdge status.

    Attributes:
        components (Optional[dict]): A dictionary representing the components of the NuvlaEdge system.
        nuvlabox_api_endpoint (Optional[str]): The API endpoint of the NuvlaBox.
        nuvlabox_engine_version (Optional[str]): The version of the NuvlaBox engine.
        installation_parameters (Optional[list]): A list of installation parameters.

    """
    # NuvlaEdge System configuration
    components: Optional[dict] = None
    nuvlabox_api_endpoint: Optional[str] = None
    nuvlabox_engine_version: Optional[str] = None
    installation_parameters: Optional[list] = None


class StatusOrchestrationEngineConfiguration(NuvlaEdgeBaseModel):
    """
    StatusOrchestrationEngineConfiguration

    This class represents the configuration settings for the status of the orchestration engine in Nuvla.
    It inherits from the NuvlaEdgeBaseModel class.

    Attributes:
        orchestrator (Optional[str]): The container orchestration engine used in Nuvla.
        docker_server_version (Optional[str]): The version of the Docker server used in the orchestrator.
        kubelet_version (Optional[str]): The version of the kubelet used in the orchestrator.
        container_plugins (Optional[list[str]]): A list of container plugins used in the orchestrator.
        node_id (Optional[str]): The ID of the node in the swarm cluster.
        cluster_id (Optional[str]): The ID of the swarm cluster.
        cluster_managers (Optional[list[str]]): A list of cluster managers in the swarm cluster.
        cluster_nodes (Optional[list[str]]): A list of nodes in the swarm cluster.
        cluster_node_role (Optional[str]): The role of the node in the swarm cluster.
        swarm_node_cert_expiry_date (Optional[str]): The expiry date of the swarm node certificate.
        cluster_join_address (Optional[str]): The address used to join the swarm cluster.

    """
    # Container orchestration engine
    orchestrator: Optional[str] = None
    docker_server_version: Optional[str] = None
    kubelet_version: Optional[str] = None
    container_plugins: Optional[list[str]] = None

    # Swarm management
    node_id: Optional[str] = None
    cluster_id: Optional[str] = None
    cluster_managers: Optional[list[str]] = None
    cluster_nodes: Optional[list[str]] = None
    cluster_node_role: Optional[str] = None
    swarm_node_cert_expiry_date: Optional[str] = None
    cluster_join_address: Optional[str] = None


class NuvlaEdgeStatusResource(NuvlaResourceBase,
                              StatusTelemetry,
                              StatusSystemConfiguration,
                              StatusOrchestrationEngineConfiguration):
    """
    This class represents a Nuvla Edge status resource.

    It inherits from the following classes:
    - NuvlaResourceBase: Provides basic functionality for interacting with Nuvla.
    - StatusTelemetry: Provides functions related to telemetry status.
    - StatusSystemConfiguration: Provides functions related to system configuration status.
    - StatusOrchestrationEngineConfiguration: Provides functions related to orchestration engine configuration status.

    Attributes:
        status (Optional[Status]): The current status of the resource.
        status_notes (Optional[list[str]]): Additional notes related to the status of the resource.
        current_time (Optional[str]): The current time of the resource.
        vulnerabilities (Optional[dict]): Information about vulnerabilities.

    Example usage:
        # Create a NuvlaEdgeStatusResource object
        edge_status = NuvlaEdgeStatusResource()

        # Set the status attribute
        edge_status.status = Status.RUNNING

        # Set the status_notes attribute
        edge_status.status_notes = ["Startup successful"]

        # Display the current time
        print(edge_status.current_time)

        # Set the vulnerabilities attribute
        edge_status.vulnerabilities = {"CVE-2022-1234": "High"}

    """
    status: Optional[Status] = None
    status_notes: Optional[list[str]] = None

    current_time: Optional[str] = None

    vulnerabilities: Optional[dict] = None


class AutoNuvlaEdgeStatusResource(NuvlaEdgeStatusResource,
                                  AutoUpdateNuvlaEdgeTrackedResource):
    ...
