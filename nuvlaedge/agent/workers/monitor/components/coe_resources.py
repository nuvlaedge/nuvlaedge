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
        super().__init__(name, COEResourcesData, enable_monitor)

        if not telemetry.coe_resources_supported:
            self.logger.info(f'coe-resources not supported by Nuvla. Disabling {self.name}')
            self.enabled_monitor = False

        self.coe_client: COEClient = telemetry.coe_client

        # Initialize the corresponding data on the EdgeStatus class
        if not telemetry.edge_status.coe_resources:
            telemetry.edge_status.coe_resources = self.data

    def update_data(self) -> None:
        if self.coe_client.ORCHESTRATOR != 'docker':
            return

        docker_data = DockerData()
        # Warning: the order of the list below is important, swarm only resources should be at the end
        for resource_type in ['images', 'volumes', 'networks', 'containers',
                              'services', 'tasks', 'configs', 'secrets']:
            try:
                setattr(docker_data, resource_type, self.coe_client.list_raw_resources(resource_type))
            except Exception as e:
                if 'not a swarm manager' in str(e):
                    self.logger.debug('This docker node is not a swarm manager. '
                                      'Cannot get services,tasks,configs,secrets.')
                    break
                self.logger.error(f'Failed to get docker {resource_type}: {e}')

        self.data.docker = docker_data

    def populate_nb_report(self, nuvla_report: dict):
        data = self.data.model_dump(exclude_none=True, by_alias=True)
        nuvla_report['coe-resources'] = data


