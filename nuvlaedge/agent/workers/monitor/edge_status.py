""" NuvlaEdge Edge Status

Gathers all the requiremets for status reporting
"""
from typing import Optional

import pydantic

from nuvlaedge.agent.workers.monitor.data.coe_resources_data import COEResourcesData
from nuvlaedge.agent.workers.monitor.data.geolocation_data import GeoLocationData
from nuvlaedge.agent.workers.monitor.data.network_data import NetworkingData
from nuvlaedge.agent.workers.monitor.data.nuvlaedge_data import NuvlaEdgeData
from nuvlaedge.agent.workers.monitor.data.orchestrator_data import DeploymentData
from nuvlaedge.agent.workers.monitor.data.power_data import PowerData
from nuvlaedge.agent.workers.monitor.data.resources_data import ResourcesData
from nuvlaedge.agent.workers.monitor.data.temperature_data import TemperatureData
from nuvlaedge.agent.workers.monitor.data.vulnerabilities_data import VulnerabilitiesData
from nuvlaedge.agent.workers.monitor.data.gpio_data import GpioData


class EdgeStatus(pydantic.BaseModel):
    """
    Pydantic class to gather together all the information on the NuvlaEdge device
    """
    # General NuvlaEdge data information
    nuvlaedge_info:     Optional[NuvlaEdgeData] = None

    # Networking data report
    iface_data:         Optional[NetworkingData] = None

    # Resource utilization report
    resources:          Optional[ResourcesData] = None

    # Temperature status report
    temperatures:       Optional[TemperatureData] = None

    # Deployed container stats
    container_stats:    Optional[DeploymentData] = None

    # Geolocation data
    inferred_location:  Optional[GeoLocationData] = None

    # Vulnerabilities data
    vulnerabilities:    Optional[VulnerabilitiesData] = None

    # Power data report. (Only for Jetson-Boards)
    power:              Optional[PowerData] = None

    # GPIO Pins
    gpio_pins:          Optional[GpioData] = None

    # Modification time controlled by Telemetry
    current_time:       Optional[str] = None

    # COE raw resources
    coe_resources:      Optional[COEResourcesData] = None
