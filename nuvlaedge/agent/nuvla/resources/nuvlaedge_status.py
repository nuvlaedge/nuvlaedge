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
    resources: Optional[dict]
    network: Optional[dict]
    temperatures: Optional[dict]
    ip: Optional[str]
    gpio_pins: Optional[dict]
    inferred_location: Optional[list[float]]


class StatusSystemConfiguration(NuvlaEdgeBaseModel):
    # System configuration
    hostname: Optional[str]
    operating_system: Optional[str]
    architecture: Optional[str]
    last_boot: Optional[str]
    host_user_home: Optional[str]


class StatusNuvlaEdgeConfiguration(NuvlaEdgeBaseModel):
    # NuvlaEdge System configuration
    components: Optional[dict]
    nuvlabox_api_endpoint: Optional[str]
    nuvlabox_engine_version: Optional[str]
    installation_parameters: Optional[list]


class StatusOrchestrationEngineConfiguration(NuvlaEdgeBaseModel):
    # Container orchestration engine
    orchestrator: Optional[str]
    docker_server_version: Optional[str]
    kubelet_version: Optional[str]
    container_plugins: Optional[list[str]]

    # Swarm management
    node_id: Optional[str]
    cluster_id: Optional[str]
    cluster_managers: Optional[str]
    cluster_nodes: Optional[str]
    cluster_node_role: Optional[str]
    swarm_node_cert_expiry_date: Optional[str]
    cluster_join_address: Optional[str]


class NuvlaEdgeStatusResource(NuvlaResourceBase,
                              StatusTelemetry,
                              StatusSystemConfiguration,
                              StatusOrchestrationEngineConfiguration):
    status: Status
    status_notes: Optional[list[str]]

    current_time: datetime

    vulnerabilities: Optional[dict]
