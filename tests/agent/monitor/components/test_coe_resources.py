# -*- coding: utf-8 -*-

import unittest

import docker.errors
from mock import Mock

from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.workers.monitor.components.coe_resources import COEResourcesMonitor
from nuvlaedge.agent.workers.monitor.data.coe_resources_data import COEResourcesData


def list_raw_resources(resource_type):
    if resource_type in ['services', 'tasks', 'configs', 'secrets']:
        raise docker.errors.APIError('This node is not a swarm manager.')
    return [{'id': '1', 'name': f'{resource_type}-1'},
            {'id': '2', 'name': f'{resource_type}-2'}]


class TestCOEResourcesMonitor(unittest.TestCase):

    def test_coe_resource_not_supported_by_nuvla(self):
        telemetry = Mock()
        telemetry.coe_resources_supported = False
        coe_resources_monitor = COEResourcesMonitor('test_monitor', telemetry, True)
        self.assertFalse(coe_resources_monitor.enabled_monitor)

    def test_coe_resource_monitor(self):
        telemetry = Mock()
        test_monitor = COEResourcesMonitor('test_monitor', telemetry, True)
        test_monitor.coe_client.list_raw_resources = list_raw_resources

        test_monitor.coe_client.ORCHESTRATOR = 'not_docker'
        test_monitor.update_data()
        self.assertIsNone(test_monitor.data.docker)

        test_monitor.coe_client.ORCHESTRATOR = 'docker'
        test_monitor.update_data()
        self.assertIsNotNone(test_monitor.data.docker)


        test_monitor.populate_telemetry_payload()
        expected_data = {
            'docker': {
                'images': [{'id': '1', 'name': 'images-1'},
                           {'id': '2', 'name': 'images-2'}],
                'volumes': [{'id': '1', 'name': 'volumes-1'},
                            {'id': '2', 'name': 'volumes-2'}],
                'networks': [{'id': '1', 'name': 'networks-1'},
                             {'id': '2', 'name': 'networks-2'}],
                'containers': [{'id': '1', 'name': 'containers-1'},
                               {'id': '2', 'name': 'containers-2'}],
                'services': [], 'tasks': [], 'configs': [], 'secrets': [], 'nodes': []}}
        self.assertEqual(test_monitor.telemetry_data.coe_resources, expected_data)

    def test_coe_resource_docker(self):
        test_monitor = COEResourcesMonitor('test_monitor', Mock(), True)
        test_monitor.coe_client = DockerClient()

        test_monitor.update_data()

        self.assertIsNotNone(test_monitor.data.docker.images)
        self.assertIsNotNone(test_monitor.data.docker.volumes)
        self.assertIsNotNone(test_monitor.data.docker.networks)
        self.assertIsNotNone(test_monitor.data.docker.containers)

    def test_coe_resource_docker_error(self):
        test_monitor = COEResourcesMonitor('test_monitor', Mock(), True)
        test_monitor.coe_client = DockerClient()

        test_monitor.coe_client.list_raw_resources = Mock()
        test_monitor.coe_client.list_raw_resources.side_effect = docker.errors.APIError("fake")

        with self.assertLogs(logger=test_monitor.logger, level='ERROR'):
            test_monitor.update_data()
