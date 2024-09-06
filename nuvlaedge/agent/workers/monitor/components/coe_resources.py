# -*- coding: utf-8 -*-
""" NuvlaEdge IP address monitoring class.

This class is devoted to finding and reporting IP addresses of the Host,
Docker Container, and VPN along with their corresponding interface names.
It also reports and handles the IP geolocation system.

"""
import logging

from ..components import monitor
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.workers.monitor.data.coe_resources_data import COEResourcesData, DockerData


@monitor('coe_resources_monitor')
class COEResourcesMonitor(Monitor):
    """
    Handles the retrieval of raw COE resources.
    """
    def __init__(self, name: str, telemetry, enable_monitor=True):

        super().__init__(self.__class__.__name__, COEResourcesData,
                         enable_monitor=enable_monitor)

        self.logger = logging.getLogger(self.__class__.__name__)

        self.coe_client: COEClient = telemetry.coe_client

        # Initialize the corresponding data on the EdgeStatus class
        if not telemetry.edge_status.coe_resources:
            telemetry.edge_status.coe_resources = self.data

    def update_data(self) -> None:
        if self.coe_client.ORCHESTRATOR != 'docker':
            return

        docker_data = DockerData()
        docker_data.images = self.coe_client.list_raw_resources('images')
        docker_data.volumes = self.coe_client.list_raw_resources('volumes')
        docker_data.networks = self.coe_client.list_raw_resources('networks')
        docker_data.containers = self.coe_client.list_raw_resources('containers')

        self.data.docker = docker_data

    def populate_nb_report(self, nuvla_report: dict):
        data = self.data.model_dump(exclude_none=True, by_alias=True)
        nuvla_report['coe-resources'] = data


