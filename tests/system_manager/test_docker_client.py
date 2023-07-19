#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import docker
import docker.errors
import logging
import mock
import os
import requests
import unittest
import nuvlaedge.system_manager.common.coe_client as coe_client
import tests.system_manager.utils.fake as fake


class DockerTestCase(unittest.TestCase):

    @mock.patch('nuvlaedge.system_manager.common.coe_client.Docker.load_data_gateway_network_options')
    def setUp(self, mock_load_data_gateway_network_options) -> None:
        mock_load_data_gateway_network_options.return_value = {}
        self.obj = coe_client.Docker(logging)
        self.obj.client = mock.MagicMock()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # the base class should also have been set
        self.assertEqual(self.obj.dg_encrypt_options, {},
                         'Network encryption should be enabled by default')
        self.assertEqual(self.obj.my_component_name, "nuvlaedge-system-manager",
                         'Docker client was not properly initialized')

    @mock.patch.object(coe_client.Docker, 'find_network')
    @mock.patch('nuvlaedge.system_manager.common.coe_client.Path')
    @mock.patch('os.path.exists')
    def test_load_data_gateway_network_options(self, mock_exists, mock_path, mock_find_network):
        logging_backup = self.obj.logging
        self.obj.logging = mock.MagicMock()
        # if no env and NO previous file, get the default TRUE for encryption
        mock_exists.return_value = False
        self.assertEqual(self.obj.load_data_gateway_network_options(), {"encrypted": "True"},
                         'Failed to set default encryption for Data Gateway network')
        mock_exists.assert_called_once_with(coe_client.utils.nuvlaedge_shared_net_unencrypted)

        # if no env BUT previous "unencrypt" file, get the FALSE for encryption
        mock_exists.return_value = True
        self.assertEqual(self.obj.load_data_gateway_network_options(), {},
                         'Failed to grab persisted config for unencrypted Data Gateway network')

        self.obj.logging.warning.assert_not_called()
        # when env exists
        os.environ.setdefault('DATA_GATEWAY_NETWORK_ENCRYPTION', 'something')
        # if network exists, log and return True, unless explicitly False
        mock_find_network.return_value = True
        path_obj = mock.MagicMock()
        path_obj.touch.return_value = None
        mock_path.return_value = path_obj

        self.assertEqual(self.obj.load_data_gateway_network_options(), {"encrypted": "True"},
                         'Failed to default to encrypted network when provided env is not explicitly False')
        mock_path.assert_not_called()
        mock_find_network.assert_called_once_with(coe_client.utils.nuvlaedge_shared_net)
        self.obj.logging.warning.assert_called_once()

        # if network does not exist, same output but no logging
        mock_find_network.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertEqual(self.obj.load_data_gateway_network_options(), {"encrypted": "True"},
                         'Failed to default to encrypted network when data gateway network does not exist')
        mock_path.assert_not_called()
        self.obj.logging.warning.assert_called_once()

        # when env var is False, get False and touch file
        os.environ['DATA_GATEWAY_NETWORK_ENCRYPTION'] = 'FaLsE'
        self.assertEqual(self.obj.load_data_gateway_network_options(), {},
                         'Failed to catch request for unencrypted network from env var')
        mock_path.assert_called_once_with(coe_client.utils.nuvlaedge_shared_net_unencrypted)
        self.obj.logging = logging_backup
        os.environ.pop('DATA_GATEWAY_NETWORK_ENCRYPTION')

    def test_find_network(self):
        self.obj.client.networks.get.return_value = fake.MockNetwork('foo')
        # this is a simple lookup
        self.assertEqual(self.obj.find_network('foo').name, 'foo',
                         'Failed to get Docker network')

    def test_list_internal_components(self):
        self.assertIsNotNone(coe_client.utils.base_label,
                             'Failed to inherit utility variables from utils')

        self.obj.client.containers.list.return_value = [True]
        # this is a simple lookup
        self.assertEqual(self.obj.list_internal_components(), [True],
                         'Failed to list internal components')

    def test_fetch_container_logs(self):
        self.obj.client.api.logs.return_value = b'logs'
        component = mock.MagicMock()
        component.id = 'id'

        # get the decoded logs
        self.assertEqual(self.obj.fetch_container_logs(component, 'since'), 'logs',
                         'Failed to fetch container logs')

    def test_get_component_name(self):
        component = mock.MagicMock()
        component.name = 'name'

        # simple lookup
        self.assertEqual(self.obj.get_component_name(component), 'name',
                         'Failed to lookup component name')

    def test_get_component_id(self):
        component = mock.MagicMock()
        component.id = 'id'

        # simple lookup
        self.assertEqual(self.obj.get_component_id(component), 'id',
                         'Failed to lookup component ID')

    def test_get_node_info(self):
        self.obj.client.info.return_value = {'foo': 'bar'}

        self.assertEqual(self.obj.get_node_info(), {'foo': 'bar'},
                         'Failed to lookup node information')

    @mock.patch.object(coe_client.Docker, 'get_node_info')
    def test_get_ram_capacity(self, mock_get_node_info):
        mock_get_node_info.return_value = {'MemTotal': 1}

        # get the mem and convert
        self.assertEqual(self.obj.get_ram_capacity(), 1/1024/1024,
                         'Failed to get RAM capacity')

    @mock.patch.object(coe_client.Docker, 'get_version')
    def test_is_version_compatible(self, mock_get_version):
        # for old versions, False
        mock_get_version.return_value = 1
        self.assertFalse(self.obj.is_version_compatible(),
                         'Saying old version is compatible when it should not be')

        # otherwise, true
        mock_get_version.return_value = 20
        self.assertTrue(self.obj.is_version_compatible(),
                        'Failed to check if Docker version is compatible')

    def test_is_coe_enabled(self):
        self.obj.client.info.return_value = {'Swarm': {}}
        # if not Swarm node ID, get False
        self.assertFalse(self.obj.is_coe_enabled(),
                         'Falsely claiming Swarm is enabled, even though node does not have an ID')

        # if it has an ID, but is inactive, also False
        self.obj.client.info.return_value = {'Swarm': {'NodeID': 'id'}}
        self.assertFalse(self.obj.is_coe_enabled(),
                         'Falsely claiming Swarm is enabled, even though node is missing Inactive field')
        self.obj.client.info.return_value = {'Swarm': {'NodeID': 'id', 'LocalNodeState': 'inactive'}}
        self.assertFalse(self.obj.is_coe_enabled(),
                         'Falsely claiming Swarm is enabled, even though node is inactive')

        # otherwise, True
        self.obj.client.info.return_value = {'Swarm': {'NodeID': 'id', 'LocalNodeState': 'active'}}
        self.assertTrue(self.obj.is_coe_enabled(),
                        'Failed to check that COE is enabled')

    def test_infer_on_stop_docker_image(self):
        default_on_stop_docker_image = 'sixsq/nuvlaedge:latest'

        # if container does not exist, take the latest dev image
        self.obj.client.containers.get.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertEqual(self.obj.infer_on_stop_docker_image(), default_on_stop_docker_image,
                         'Failed to provide fallback nuvlaedge image for on-stop if container not found in the system')

        # if any other error, get None
        self.obj.client.containers.get.side_effect = Exception
        self.assertEqual(self.obj.infer_on_stop_docker_image(), default_on_stop_docker_image,
                         'Failed to provide fallback nuvlaedge image for on-stop when exception happens')

        # otherwise
        self.obj.client.containers.get.reset_mock(side_effect=True)
        container = mock.MagicMock()
        # if on-stop exists and is not pause, get fallback nuvlaedge image
        container.status = 'running'
        container.attrs = {'Config': {'Image': 'sixsq/nuvlaedge:1.2.3'}}

        self.obj.client.containers.get.return_value = container
        self.assertEqual(self.obj.infer_on_stop_docker_image(), default_on_stop_docker_image,
                         'Got the wrong image with a running on-stop container')

        # otherwise, get image name
        container.status = 'paused'
        self.obj.client.containers.get.return_value = container
        self.assertEqual(self.obj.infer_on_stop_docker_image(), 'sixsq/nuvlaedge:1.2.3',
                         'Unable to infer on-stop image')

    @mock.patch('socket.gethostname')
    @mock.patch.object(coe_client.Docker, 'infer_on_stop_docker_image')
    def test_launch_nuvlaedge_on_stop(self, mock_infer_on_stop_docker_image, mock_gethostname):
        # if on-stop image is not given, need to infer, and returns None if cannot be inferred
        mock_infer_on_stop_docker_image.return_value = None
        self.assertIsNone(self.obj.launch_nuvlaedge_on_stop(None),
                          'Tried to launch on-stop container even though its image is not known')
        mock_infer_on_stop_docker_image.assert_called_once()
        mock_gethostname.assert_not_called()

        # otherwise, use the given image name and try to launch the container
        mock_gethostname.return_value = 'localhost'
        self.obj.client.containers.get.side_effect = docker.errors.NotFound('', requests.Response())
        self.obj.client.containers.run.return_value = None
        self.assertIsNone(self.obj.launch_nuvlaedge_on_stop('image'),
                          'Failed to launch on-stop without project name')
        self.assertEqual(mock_gethostname.call_count, 1,
                         'Failed to catch container NotFound exception')
        self.obj.client.containers.run.assert_called_once()

        self.obj.client.containers.get.reset_mock(side_effect=True)
        self.assertIsNone(self.obj.launch_nuvlaedge_on_stop('image'),
                          'Failed to launch on-stop container')
        self.assertEqual(mock_gethostname.call_count, 2,
                         'Failed to find "self" container')

    @mock.patch.object(coe_client.Docker, 'get_node_info')
    def test_get_node_id(self, mock_get_node_info):
        mock_get_node_info.return_value = {'Swarm': {'NodeID': 'id'}}
        # lookup
        self.assertEqual(self.obj.get_node_id(), 'id',
                         'Failed to get Node ID')

    def test_list_nodes(self):
        self.obj.client.nodes.list.return_value = ['node']
        self.assertEqual(self.obj.list_nodes(optional_filter={'filter': 'foo'}), ['node'],
                         'Failed to list nodes')
        self.obj.client.nodes.list.assert_called_once_with(filters={'filter': 'foo'})

    @mock.patch.object(coe_client.Docker, 'get_node_info')
    def test_get_cluster_managers(self, mock_get_node_info):
        # if RemoteManagers is invalid, get []
        mock_get_node_info.return_value = {}
        self.assertEqual(self.obj.get_cluster_managers(), [],
                         'Got cluster manager even though RemoteManagers is not set')

        mock_get_node_info.return_value = {'Swarm': {'RemoteManagers': {}}}
        self.assertEqual(self.obj.get_cluster_managers(), [],
                         'Got cluster manager even though RemoteManagers has the wrong type (is not a list)')

        # otherwise get list of IDs
        mock_get_node_info.return_value = {'Swarm': {'RemoteManagers': [{'NodeID': 'id1'}, {'NodeID': 'id2'}]}}
        self.assertEqual(self.obj.get_cluster_managers(), ['id1', 'id2'],
                         'Failed to get cluster managers')

    def test_read_system_issues(self):
        # simply lookup errors and warning from the provided node info
        node_info = {
            'Swarm': {}
        }
        self.assertEqual(self.obj.read_system_issues(node_info), ([], []),
                         'Got system issues when there are none')

        node_info = {
            'Swarm': {'Error': 'error'}
        }
        self.assertEqual(self.obj.read_system_issues(node_info), (['error'], []),
                         'Failed to read system error')

        node_info['Warnings'] = ['warn1', 'warn2']
        self.assertEqual(self.obj.read_system_issues(node_info), (['error'], ['warn1', 'warn2']),
                         'Failed to read system errors and warnings')

    @mock.patch.object(coe_client.Docker, 'read_system_issues')
    @mock.patch.object(coe_client.Docker, 'get_node_info')
    @mock.patch.object(coe_client.Docker, 'get_node_id')
    def test_set_nuvlaedge_node_label(self, mock_get_node_id, mock_get_node_info, mock_read_system_issues):
        # handle Docker errors
        self.obj.client.nodes.get.side_effect = docker.errors.APIError('', requests.Response())
        out = self.obj.set_nuvlaedge_node_label('id')
        self.assertFalse(out[0],
                         'Set node label even though Docker ended up in an error')
        self.assertTrue(out[1].startswith('Unable to set NuvlaEdge node label'),
                        'Got the wrong error message while failing to set node label')

        self.obj.client.nodes.get.side_effect = docker.errors.APIError(self.obj.lost_quorum_hint, requests.Response())
        mock_get_node_info.return_value = None
        mock_read_system_issues.return_value = ([], [])
        out = self.obj.set_nuvlaedge_node_label('id')
        self.assertFalse(out[0],
                         'Set node label even though Swarm quorum was lost')
        self.assertTrue(out[1].startswith('Quorum is lost'),
                        'Got the wrong error message when quorum is lost')
        mock_read_system_issues.assert_called_once_with(None)

        # also fail if Node is missing Spec
        self.obj.client.nodes.get.reset_mock(side_effect=True)
        node = mock.MagicMock()
        node.attrs = {}
        self.obj.client.nodes.get.return_value = node
        out = self.obj.set_nuvlaedge_node_label('id')
        self.assertFalse(out[0],
                         'Set node label even though Node is missing its Spec')
        self.assertTrue(out[1].startswith('Unable to set NuvlaEdge node label'),
                        'Got the wrong error message while failing to set node label due to invalid Node')

        # otherwise, get its labels. update only if label is missing
        node.attrs = {'Spec': {'Labels': {coe_client.utils.node_label_key: 'foo'}}}   # already labeled
        self.obj.client.nodes.get.return_value = node
        self.assertEqual(self.obj.set_nuvlaedge_node_label('id'), (True, None),
                         'Failed to set node label when label is already set')
        node.update.assert_not_called()

        node.attrs = {'Spec': {'Labels': {}}}   # no labels
        self.obj.client.nodes.get.return_value = node
        self.assertEqual(self.obj.set_nuvlaedge_node_label('id'), (True, None),
                         'Failed to update node label')
        node.update.assert_called_once_with({'Labels': {coe_client.utils.node_label_key: 'True'}})

        # and if Node id is not provided, infer it
        mock_get_node_id.assert_not_called()
        mock_get_node_id.return_value = 'id2'
        self.assertEqual(self.obj.set_nuvlaedge_node_label(), (True, None),
                         'Failed to update node label when no node ID is provided')
        mock_get_node_id.assert_called_once()

    def test_restart_credentials_manager(self):
        self.obj.client.api.restart.return_value = None
        self.assertIsNone(self.obj.restart_credentials_manager(),
                          'Failed to restart credentials manager')

        # same if NotFound
        self.obj.client.api.restart.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertIsNone(self.obj.restart_credentials_manager(),
                          'Failed to cope with component not being found')

        # and raise otherwise
        self.obj.client.api.restart.side_effect = docker.errors.APIError('', requests.Response())
        self.assertRaises(docker.errors.APIError, self.obj.restart_credentials_manager)

    @mock.patch.object(coe_client.Docker, 'get_current_container')
    def test_find_nuvlaedge_agent_container(self, mock_current_container):
        labels = mock.MagicMock()
        labels.labels = {'com.docker.compose.project': 'nuvlaedge'}
        mock_current_container.return_value = labels
        self.obj.client.containers.list.return_value = ['foo']
        self.assertEqual(self.obj.find_nuvlaedge_agent_container(), ('foo', None),
                         'Failed to find Agent container')

        self.obj.client.containers.list.return_value = []
        self.assertEqual(self.obj.find_nuvlaedge_agent_container(), (None, 'Agent container not found'))

        mock_current_container.return_value = None
        self.assertEqual(self.obj.find_nuvlaedge_agent_container(), (None, 'Cannot find Agent container'))

    def test_list_all_containers_in_this_node(self):
        # simple lookup
        self.obj.client.containers.list.return_value = []
        self.assertEqual(self.obj.list_all_containers_in_this_node(), [],
                         'Failed to list all containers')
        self.obj.client.containers.list.assert_called_once_with(all=True)

    @mock.patch.object(coe_client.Docker, 'get_node_info')
    def test_count_images_in_this_host(self, mock_get_node_info):
        # lookup
        mock_get_node_info.return_value = {'Images': 123}
        self.assertEqual(self.obj.count_images_in_this_host(), 123,
                         'Failed to get count of images')

    def test_get_version(self):
        self.obj.client.version.return_value = {
            "Components": [
                {"Version": "1.2"}
            ]
        }
        # lookup the major version
        self.assertEqual(self.obj.get_version(), '1',
                         'Failed to get Docker major version')

        # also work for non-standard versions
        self.obj.client.version.return_value = {
            "Components": [
                {"Version": "v1.2"}
            ]
        }
        self.assertEqual(self.obj.get_version(), '1',
                         'Failed to get Docker major version from non-standard installation')
