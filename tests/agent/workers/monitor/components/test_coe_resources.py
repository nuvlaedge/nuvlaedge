# -*- coding: utf-8 -*-
import os
import unittest

import docker.errors
from mock import Mock, MagicMock

from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.workers.monitor.components.coe_resources import COEResourcesMonitor

os.environ['KUBERNETES_SERVICE_HOST'] = "localhost"
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient, config

config.load_incluster_config = MagicMock()

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

    def test_update_data_kubernetes(self):
        resource = MagicMock()
        resource.to_dict = MagicMock()
        resource.to_dict.return_value = \
            {'metadata':
                 {'name': 'unit-test',
                  'creation_timestamp': '2021-09-01T00:00:00Z'}}
        result = [resource]

        image = MagicMock()
        image.to_dict = MagicMock()
        image.to_dict.return_value = {'names': ['unit-test']}
        nodes = MagicMock()
        nodes.status.images = [image]

        k8s_client = KubernetesClient()
        k8s_client._list_helm_releases = MagicMock()
        k8s_client._list_helm_releases.return_value = [{'foo': 'bar'}]
        k8s_client.client = MagicMock()
        k8s_client.client.read_node.return_value = nodes
        k8s_client.client.list_node.return_value.items = result
        k8s_client.client.list_namespace.return_value.items = result
        k8s_client.client.list_persistent_volume.return_value.items = result
        k8s_client.client.list_persistent_volume_claim_for_all_namespaces.return_value.items = result
        k8s_client.client.list_config_map_for_all_namespaces.return_value.items = result
        k8s_client.client.list_secret_for_all_namespaces.return_value.items = result
        k8s_client.client.list_service_for_all_namespaces.return_value.items = result
        k8s_client.client.list_pod_for_all_namespaces.return_value.items = result
        k8s_client.client_network = MagicMock()
        k8s_client.client_network.list_ingress_for_all_namespaces.return_value.items = result
        k8s_client.client_batch_api = MagicMock()
        k8s_client.client_batch_api.list_cron_job_for_all_namespaces.return_value.items = result
        k8s_client.client_batch_api.list_job_for_all_namespaces.return_value.items = result
        k8s_client.client_apps = MagicMock()
        k8s_client.client_apps.list_stateful_set_for_all_namespaces.return_value.items = result
        k8s_client.client_apps.list_daemon_set_for_all_namespaces.return_value.items = result
        k8s_client.client_apps.list_deployment_for_all_namespaces.return_value.items = result

        telemetry = MagicMock()
        telemetry.coe_client = k8s_client
        monitor = COEResourcesMonitor('test_monitor', telemetry)
        monitor._update_data_kubernetes()

        for r_name in monitor.data.kubernetes.model_fields.keys():
            r = getattr(monitor.data.kubernetes, r_name)
            self.assertEqual(len(r), 1)
            if r_name == 'images':
                self.assertEqual(r[0], image.to_dict())
            elif r_name == 'helmreleases':
                self.assertEqual(r[0], {'foo': 'bar'})
            else:
                self.assertEqual(r[0], resource.to_dict())
