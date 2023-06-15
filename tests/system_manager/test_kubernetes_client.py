#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import mock
import os
import sys
import unittest
import tests.system_manager.utils.fake as fake


class KubernetesTestCase(unittest.TestCase):

    def setUp(self) -> None:
        os.environ.setdefault('KUBERNETES_SERVICE_HOST', 'force-k8s-coe')
        with mock.patch.dict(sys.modules):
            # sys.modules.clear()
            if 'nuvlaedge.system_manager.common.ContainerRuntime' in sys.modules:
                del sys.modules['nuvlaedge.system_manager.common.ContainerRuntime']
            import nuvlaedge.system_manager.common.container_runtime as ContainerRuntime

        with mock.patch('kubernetes.client.CoreV1Api') as mock_k8s_client_CoreV1Api:
            with mock.patch('kubernetes.client.AppsV1Api') as mock_k8s_client_AppsV1Api:
                with mock.patch('kubernetes.config.load_incluster_config') as mock_k8s_config:
                    mock_k8s_client_CoreV1Api.return_value = mock.MagicMock()
                    mock_k8s_client_AppsV1Api.return_value = mock.MagicMock()
                    mock_k8s_config.return_value = True
                    self.obj = ContainerRuntime.Kubernetes(logging)

        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # the base class should also have been set
        self.assertEqual(self.obj.namespace, "nuvlaedge",
                         'Kubernetes client was not properly initialized')

    def test_list_internal_components(self):
        pods = mock.MagicMock()
        pods.items = 'foo'
        self.obj.client.list_namespaced_pod.return_value = pods
        # this is a simple lookup
        self.assertEqual(self.obj.list_internal_components('label'), 'foo',
                         'Failed to list internal pods')
        self.obj.client.list_namespaced_pod.assert_called_once_with(namespace='nuvlaedge', label_selector='label')

    def test_fetch_container_logs(self):
        self.obj.client.read_namespaced_pod_log.return_value = 'foo\nbar'
        component = fake.mock_kubernetes_pod('name')
        expected_output = [[
            ' [name] foo',
            ' [name] bar'
        ]]  # just for 1 container
        self.assertEqual(self.obj.fetch_container_logs(component, 0), expected_output,
                         'Failed to get container logs')

    def test_get_component_name(self):
        component = fake.mock_kubernetes_pod('name')

        # simple lookup
        self.assertEqual(self.obj.get_component_name(component), 'name',
                         'Failed to lookup pod name')

    def test_get_component_id(self):
        component = fake.mock_kubernetes_pod('id')

        # simple lookup
        self.assertEqual(self.obj.get_component_id(component), 'id',
                         'Failed to lookup pod ID')

    def test_get_node_info(self):
        # if host_node_name is none, get None
        self.obj.host_node_name = None
        self.assertIsNone(self.obj.get_node_info(),
                          'Got node info when host_node_name is None')

        # otherwise
        self.obj.host_node_name = 'host-node-name'
        self.obj.client.read_node.return_value = {'foo': 'bar'}

        self.assertEqual(self.obj.get_node_info(), {'foo': 'bar'},
                         'Failed to lookup k8s node information')

    def test_get_ram_capacity(self):
        node_info = mock.MagicMock()
        node_info.status.capacity = {
            'memory': '1024Ki'
        }
        self.obj.get_node_info = mock.Mock()
        self.obj.get_node_info.return_value = node_info

        # get the mem and convert
        self.assertEqual(self.obj.get_ram_capacity(), 1,
                         'Failed to get RAM capacity')

    @mock.patch('nuvlaedge.system_manager.common.ContainerRuntime.Kubernetes.get_version')
    def test_is_version_compatible(self, mock_get_version):
        # for old versions, False
        mock_get_version.return_value = 'v1.2'
        self.assertFalse(self.obj.is_version_compatible(),
                         'Saying old version is compatible when it should not be')

        # otherwise, true
        mock_get_version.return_value = 'v1.23'
        self.assertTrue(self.obj.is_version_compatible(),
                        'Failed to check if Kubernetes version is compatible')

    def test_is_coe_enabled(self):
        # always True for k8s
        self.assertTrue(self.obj.is_coe_enabled())

    def test_infer_on_stop_docker_image(self):
        # n/a for k8s
        self.assertIsNone(self.obj.infer_on_stop_docker_image(),
                          'Tried to infer on-stop details for k8s, where it is not applicable')

    def test_launch_nuvlaedge_on_stop(self):
        # n/a for k8s
        self.assertIsNone(self.obj.launch_nuvlaedge_on_stop('none'),
                          'Tried to infer on-stop details for k8s, where it is not applicable')

    def test_get_node_id(self):
        self.obj.get_node_info = mock.Mock()
        self.obj.get_node_info.return_value = fake.mock_kubernetes_node('node-name')
        # lookup
        self.assertTrue(self.obj.get_node_id().startswith('node-name'),
                        'Failed to get Kubernetes Node ID')

    def test_list_nodes(self):
        list_nodes = mock.MagicMock()
        list_nodes.items = [fake.mock_kubernetes_node('1'), fake.mock_kubernetes_node('2')]
        self.obj.client.list_node.return_value = list_nodes

        out = self.obj.list_nodes()
        self.assertEqual(len(out), 2,
                         'Failed to list all k8s nodes')
        self.obj.client.list_node.assert_called_once_with()
        self.assertEqual(list(map(lambda x: x.metadata.name[0], out)), ['1', '2'],
                         'Returned k8s nodes do not match the expected')

    def test_get_cluster_managers(self):
        node_one = fake.mock_kubernetes_node('1')
        node_two = fake.mock_kubernetes_node('2')
        self.obj.list_nodes = mock.Mock()
        # if nodes have no labels, then there are no managers
        self.obj.list_nodes.return_value = [node_one, node_two]
        self.assertEqual(self.obj.get_cluster_managers(), [],
                         'Got cluster managers even though there are none')

        # if master keywords are not in the labels, then there are no managers again
        node_one.metadata.labels = ['not-a-manager']
        self.obj.list_nodes.return_value = [node_one, node_two]
        self.assertEqual(self.obj.get_cluster_managers(), [],
                         'Mistaken a worker by a manager')

        # otherwise, get the manager
        node_two.metadata.labels = ['node-role.kubernetes.io/master']
        self.assertEqual(self.obj.get_cluster_managers(), [node_two.metadata.name],
                         'Failed to get k8s cluster manager')

    def test_read_system_issues(self):
        # not implemented for k8s
        self.assertEqual(self.obj.read_system_issues(None), ([], []),
                         'Failed to read system errors and warnings for k8s')

    def test_set_nuvlaedge_node_label(self):
        # n/a for k8s
        self.assertEqual(self.obj.set_nuvlaedge_node_label(), (True, None),
                         'Unexpected output for method which is not applicable to k8s')

    def test_restart_credentials_manager(self):
        # it just logs and waits for the container to restart itself
        self.assertIsNone(self.obj.restart_credentials_manager(),
                          'Should just wait for pod to restart itself')

    def test_find_nuvlaedge_agent_container(self):
        pods = mock.MagicMock()
        # if cannot find pod, get None
        pods.items = []
        self.obj.client.list_namespaced_pod.return_value = pods
        self.assertEqual(self.obj.find_nuvlaedge_agent_container()[0], None,
                         'Found agent pod when it should not exist')
        self.assertTrue(self.obj.find_nuvlaedge_agent_container()[1].startswith('There are no pods'),
                        'Got the wrong error message when no pods are found')

        # if it exists, but the name is not "agent", get None
        pods.items = [fake.mock_kubernetes_pod('pod-wrong-name')]
        self.obj.client.list_namespaced_pod.return_value = pods
        self.assertEqual(self.obj.find_nuvlaedge_agent_container()[0], None,
                         'Found agent pod when pod name does not match')
        self.assertTrue(self.obj.find_nuvlaedge_agent_container()[1].startswith('Cannot find agent container within'),
                        'Got the wrong error message when there is a pod name mismatch')

        # otherwise, get the container back
        pods.items = [fake.mock_kubernetes_pod('nuvlaedge-agent')]

        self.assertEqual(self.obj.find_nuvlaedge_agent_container()[0].name, 'nuvlaedge-agent',
                         'Failed to find agent container')
        self.assertIsNone(self.obj.find_nuvlaedge_agent_container()[1],
                          'Got an error message on success')

    def test_list_all_containers_in_this_node(self):
        # no containers = get []
        pods = mock.MagicMock()
        pods.items = []
        self.obj.client.list_pod_for_all_namespaces.return_value = pods
        self.assertEqual(self.obj.list_all_containers_in_this_node(), [],
                         'Got k8s containers when there are none')

        # otherwise, get all their info
        pods = mock.MagicMock()
        pods.items = [fake.mock_kubernetes_pod('one'), fake.mock_kubernetes_pod('two')]
        self.obj.client.list_pod_for_all_namespaces.return_value = pods
        self.assertEqual(len(self.obj.list_all_containers_in_this_node()),
                         len(pods.items) * len(fake.mock_kubernetes_pod().status.container_statuses),
                         'Failed to get all k8s containers')

        self.assertTrue(all(True for x in self.obj.list_all_containers_in_this_node() if isinstance(x, str)),
                        'Expecting list of strings')

    def test_count_images_in_this_host(self):
        # lookup
        self.obj.get_node_info = mock.Mock()
        self.obj.get_node_info.return_value = fake.mock_kubernetes_node()
        self.assertEqual(self.obj.count_images_in_this_host(), len(fake.mock_kubernetes_node().status.images),
                         'Failed to get count of images in k8s node')

    @mock.patch('nuvlaedge.system_manager.common.ContainerRuntime.Kubernetes.get_node_info')
    def test_get_version(self, mock_get_node_info):
        # lookup
        mock_get_node_info.return_value = fake.mock_kubernetes_node()
        self.assertEqual(self.obj.get_version(), 'v1',
                         'Failed to get kubelet version')
