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
from nuvlaedge.agent.workers.monitor.data.coe_resources_data import \
    COEResourcesData, DockerData, KubernetesData, kubernetes_data_attributes


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
        match self.coe_client.ORCHESTRATOR:
            case 'docker':
                self._update_data_docker()
            case 'kubernetes':
                self._update_data_kubernetes()
            case _:
                self.logger.error(
                    f'Raw data not updated. Unsupported orchestrator:'
                    f' {self.coe_client.ORCHESTRATOR}')

    def _update_data_docker(self):
        docker_data = DockerData()
        # Warning: the order of the list below is important, swarm only resources should be at the end
        for resource_type in ['images', 'volumes', 'networks', 'containers',
                              'services', 'tasks', 'configs', 'secrets']:
            try:
                setattr(docker_data, resource_type,
                        self.coe_client.list_raw_resources(resource_type))
            except Exception as e:
                if 'not a swarm manager' in str(e):
                    self.logger.debug(
                        'This docker node is not a swarm manager. '
                        'Cannot get services,tasks,configs,secrets.')
                    break
                self.logger.error(f'Failed to get docker {resource_type}: {e}')
        self.data.docker = docker_data

    def _update_data_kubernetes(self):
        data = KubernetesData()
        for object_type in kubernetes_data_attributes():
            try:
                setattr(data, object_type,
                        self.coe_client.list_raw_resources(object_type))
            except Exception as e:
                self.logger.error(f'Failed to get k8s {object_type}: {e}')
        self.data.kubernetes = data

    def populate_nb_report(self, nuvla_report: dict):
        data = self.data.model_dump(exclude_none=True, by_alias=True)
        nuvla_report['coe-resources'] = data


