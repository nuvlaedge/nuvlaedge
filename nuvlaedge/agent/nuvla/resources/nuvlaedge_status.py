import pprint
from typing import Optional
from datetime import datetime
from enum import auto
from strenum import UppercaseStrEnum

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase


class Status(UppercaseStrEnum):
    OPERATIONAL = auto()
    DEGRADED = auto()
    UNKNOWN = auto()


class StatusTelemetry(NuvlaEdgeBaseModel):
    # Telemetry metrics
    resources: Optional[dict] = None
    network: Optional[dict] = None
    temperatures: Optional[dict] = None
    ip: Optional[str] = None
    gpio_pins: Optional[dict] = None
    inferred_location: Optional[list[float]] = None


class StatusSystemConfiguration(NuvlaEdgeBaseModel):
    # System configuration
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    architecture: Optional[str] = None
    last_boot: Optional[str] = None
    host_user_home: Optional[str] = None


class StatusNuvlaEdgeConfiguration(NuvlaEdgeBaseModel):
    # NuvlaEdge System configuration
    components: Optional[dict] = None
    nuvlabox_api_endpoint: Optional[str] = None
    nuvlabox_engine_version: Optional[str] = None
    installation_parameters: Optional[list] = None


class StatusOrchestrationEngineConfiguration(NuvlaEdgeBaseModel):
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
    status: Optional[Status] = None
    status_notes: Optional[list[str]] = None

    current_time: Optional[str] = None

    vulnerabilities: Optional[dict] = None
