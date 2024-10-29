import os
import unittest
from unittest.mock import MagicMock
from nuvlaedge.agent.workers.monitor.components.coe_resources import COEResourcesMonitor

os.environ['KUBERNETES_SERVICE_HOST'] = "localhost"
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient, config

config.load_incluster_config = MagicMock()


class TestCOEResourcesMonitor(unittest.TestCase):

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
            else:
                self.assertEqual(r[0], resource.to_dict())
