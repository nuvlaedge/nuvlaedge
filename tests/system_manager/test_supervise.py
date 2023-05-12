#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import docker
import logging
import mock
import requests
import unittest

import nuvlaedge.system_manager.Supervise as Supervise
from nuvlaedge.system_manager.common.ContainerRuntime import Containers
import tests.system_manager.utils.fake as fake


class SuperviseTestCase(unittest.TestCase):

    def setUp(self) -> None:
        Supervise.__bases__ = (fake.Fake.imitate(Containers),)

        self.obj = Supervise.Supervise()
        self.obj.container_runtime = mock.MagicMock()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # the base class should also have been set
        self.assertEqual(self.obj.agent_dg_failed_connection, 0,
                         'Failed to initialize Supervise class')

    def test_classify_this_node(self):
        self.obj.container_runtime.get_node_id.return_value = 'id'
        # if COE is disabled, get None and set attrs to false
        self.obj.container_runtime.is_coe_enabled.return_value = False
        self.assertIsNone(self.obj.classify_this_node(),
                          'Tried to classify node where COE is disabled')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, False),
                         'Saying node has cluster mode enabled when it has not')

        self.obj.container_runtime.is_coe_enabled.return_value = True
        self.obj.container_runtime.get_node_id.return_value = None
        self.assertIsNone(self.obj.classify_this_node(),
                          'Tried to classify node without a node ID')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, False),
                         'Saying node has cluster mode enabled when it does not even have a node ID')

        # otherwise, cluster mode is True
        self.obj.container_runtime.get_node_id.return_value = 'id'
        self.obj.container_runtime.get_cluster_managers.return_value = []
        self.assertIsNone(self.obj.classify_this_node(),
                          'Failed to classify node which is not a manager')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (False, True),
                         'Failed to classify when node is not a manager but cluster is enabled')

        # and if cluster is a manager, also label it
        self.obj.container_runtime.get_cluster_managers.return_value = ['id']
        self.obj.container_runtime.set_nuvlaedge_node_label.return_value = (None, None)
        self.assertIsNone(self.obj.classify_this_node(),
                          'Failed to classify manager node')
        self.assertEqual((self.obj.i_am_manager, self.obj.is_cluster_enabled), (True, True),
                         'Node should be a manager in cluster mode')
        self.obj.container_runtime.set_nuvlaedge_node_label.assert_called_once_with('id')

        # and is labeling fails, set degraded state
        self.obj.container_runtime.set_nuvlaedge_node_label.return_value = (None, 'label-error')
        self.obj.classify_this_node()
        self.assertIn((Supervise.utils.status_degraded, 'label-error'), self.obj.operational_status,
                      'Failed to set degraded state')

    @mock.patch('OpenSSL.crypto.load_certificate')
    @mock.patch('OpenSSL.crypto')
    @mock.patch('os.path.isfile')
    def test_is_cert_rotation_needed(self, mock_isfile, mock_crypto, mock_load_cert):
        # if tls sync is not a file, get False
        mock_isfile.return_value = False
        self.assertFalse(self.obj.is_cert_rotation_needed(),
                         'Failed to check that TLS sync file is not a real file')

        # otherwise
        mock_isfile.reset_mock(return_value=True)

        # if cert files do no exist, get False
        mock_isfile.side_effect = [True, False, False, False]  # TLS file + 3 cert files
        self.assertFalse(self.obj.is_cert_rotation_needed(),
                         'Got True even though cert files do not exist')

        # otherwise
        mock_crypto.FILETYPE_PEM = ''
        cert_obj = mock.MagicMock()
        # a valid certificate is in the future, more than 5 days
        cert_obj.get_notAfter.return_value = b'99990309161546Z'
        mock_load_cert.return_value = cert_obj
        mock_isfile.side_effect = [True, True, True, True]  # TLS file + 3 cert files
        with mock.patch('nuvlaedge.system_manager.Supervise.open'):
            self.assertFalse(self.obj.is_cert_rotation_needed(),
                             'Failed to recognize valid certificates')

        # with less than 5 days to expire, return false
        cert_obj.get_notAfter.return_value = b'20200309161546Z'
        mock_load_cert.return_value = cert_obj
        mock_isfile.side_effect = [True, True, True, True]  # TLS file + 3 cert files
        with mock.patch('nuvlaedge.system_manager.Supervise.open'):
            self.assertTrue(self.obj.is_cert_rotation_needed(),
                            'Failed to recognize certificates in need of renewal')

    @mock.patch('os.remove')
    @mock.patch('os.path.isfile')
    def test_request_rotate_certificates(self, mock_isfile, mock_rm):
        self.obj.container_runtime.restart_credentials_manager.return_value = None
        # always returns None, but if file exists, calls fn to remove certs and recreate them
        mock_isfile.return_value = False
        self.assertIsNone(self.obj.request_rotate_certificates(),
                          'Tried to rotate certs without needing it')
        mock_rm.assert_not_called()
        self.obj.container_runtime.restart_credentials_manager.assert_not_called()

        mock_isfile.return_value = True
        self.assertIsNone(self.obj.request_rotate_certificates(),
                          'Failed to rotate certs')
        mock_rm.assert_called_once_with(Supervise.utils.tls_sync_file)
        self.obj.container_runtime.restart_credentials_manager.assert_called_once()

    def test_launch_data_gateway(self):
        # if self.is_cluster_enabled and not self.i_am_manager, cannot even start fn
        self.obj.i_am_manager = False
        self.obj.is_cluster_enabled = True
        self.assertRaises(Supervise.ClusterNodeCannotManageDG, self.obj.launch_data_gateway, 'dg')

        # otherwise, run
        self.obj.i_am_manager = True
        self.obj.container_runtime.client.services.create.return_value = None
        self.obj.container_runtime.client.containers.run.return_value = None

        # if in swarm, CREATE DG
        self.assertIsNone(self.obj.launch_data_gateway('dg'),
                          'Failed to create data-gateway service')
        self.obj.container_runtime.client.services.create.assert_called_once()
        self.obj.container_runtime.client.containers.run.assert_not_called()

        # otherwise, RUN DG container
        self.obj.is_cluster_enabled = False
        self.assertIsNone(self.obj.launch_data_gateway('dg'),
                          'Failed to create data-gateway container')
        self.obj.container_runtime.client.containers.run.assert_called_once()

        # if docker fails, parse error
        self.obj.container_runtime.client.containers.run.side_effect = docker.errors.APIError('', requests.Response())
        self.assertFalse(self.obj.launch_data_gateway('dg'),
                         'Says it launched the DG even though DG failed with an exception')

        self.obj.container_runtime.client.services.create.side_effect = docker.errors.APIError('409',
                                                                                               requests.Response())
        # when 409, simply restart the DG
        component = mock.MagicMock()
        component.restart.return_value = None
        component.force_update.return_value = None
        self.obj.container_runtime.client.containers.get.return_value = component
        self.obj.container_runtime.client.services.get.return_value = component
        self.obj.is_cluster_enabled = True
        self.assertTrue(self.obj.launch_data_gateway('dg'),
                        'Failed to restart data-gateway service')
        self.obj.container_runtime.client.services.get.assert_called_once_with('dg')
        self.obj.container_runtime.client.containers.get.assert_not_called()

        self.obj.is_cluster_enabled = False
        self.obj.container_runtime.client.containers.run.side_effect = docker.errors.APIError('409',
                                                                                              requests.Response())
        self.assertTrue(self.obj.launch_data_gateway('dg'),
                        'Failed to restart data-gateway container')
        self.obj.container_runtime.client.containers.get.assert_called_once_with('dg')

    def test_find_nuvlaedge_agent(self):
        # if cannot find it, get None and append to op status
        l = len(self.obj.operational_status)
        self.obj.container_runtime.find_nuvlaedge_agent_container.return_value = (None, True)
        self.assertIsNone(self.obj.find_nuvlaedge_agent(),
                          'Claming the agent was found when it does not exist')
        self.assertEqual(len(self.obj.operational_status), l+1,
                         'Failed to append operational status due to agent not being found')

        # otherwise succeed
        self.obj.container_runtime.find_nuvlaedge_agent_container.return_value = ('container', False)
        self.assertEqual(self.obj.find_nuvlaedge_agent(), 'container',
                         'Failed to find NB agent container')

    def test_check_dg_network(self):
        target_network = mock.MagicMock()
        target_network.connect.return_value = None

        # if no data_gateway_object, get None
        self.obj.data_gateway_object = None
        self.assertIsNone(self.obj.check_dg_network(mock.MagicMock()),
                          'Tried to check DG net even though data_gateway_object does not exist')

        # when in container mode
        self.obj.is_cluster_enabled = False
        self.obj.data_gateway_object = fake.MockContainer()
        # if network is already set, do nothing
        target_network.name = list(fake.MockContainer().attrs['NetworkSettings']['Networks'].keys())[0]
        target_network.id = list(fake.MockContainer().attrs['NetworkSettings']['Networks'].keys())[0]
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is already set')
        target_network.connect.assert_not_called()

        # same for cluster mode
        self.obj.is_cluster_enabled = True
        self.obj.data_gateway_object = fake.MockService('service-name', 'net-id')
        target_network.name = 'net-id'
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is already set in cluster mode')
        target_network.connect.assert_not_called()

        # and if it is not set, connect DG to it
        target_network.name = 'new-net'
        target_network.id = 'new-net-id'
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is not set in cluster mode')
        self.assertTrue(self.obj.data_gateway_object.updated,
                        'Should have updated DG service to connect to DG network, but did not')

        # same for containers
        self.obj.is_cluster_enabled = False
        self.obj.data_gateway_object = fake.MockContainer('container-name')
        self.assertIsNone(self.obj.check_dg_network(target_network),
                          'Failed to see that DG network is not set')
        target_network.connect.assert_called_once_with('container-name')

    @mock.patch.object(Supervise.Supervise, 'destroy_docker_network')
    @mock.patch.object(Supervise.Supervise, 'setup_docker_network')
    def test_manage_docker_data_gateway_network(self, mock_setup_docker_network, mock_destroy_network):
        # if empty data_gateway_networks, setup the network
        data_gateway_networks = []
        mock_setup_docker_network.return_value = None
        self.assertRaises(Supervise.BreakDGManagementCycle,
                          self.obj.manage_docker_data_gateway_network, data_gateway_networks)
        mock_setup_docker_network.assert_called_once_with(Supervise.utils.nuvlaedge_shared_net)

        mock_setup_docker_network.side_effect = Supervise.ClusterNodeCannotManageDG
        self.assertIsNone(self.obj.manage_docker_data_gateway_network(data_gateway_networks),
                          'Failed to manage DG network when node is a cluster worker')

        # otherwise
        net = mock.MagicMock()
        data_gateway_networks = [net]
        # if is_cluster_enabled is False, get the network
        self.obj.is_cluster_enabled = False
        self.assertEqual(self.obj.manage_docker_data_gateway_network(data_gateway_networks), net,
                         'Failed to manage existing DG network')
        mock_destroy_network.assert_not_called()

        # otherwise, destroy all bridge networks
        self.obj.is_cluster_enabled = True
        net_bridge_one = mock.MagicMock()
        net_bridge_two = mock.MagicMock()
        net_bridge_one.attrs = {'Driver': 'bridge'}
        net_bridge_two.attrs = {'Driver': 'bridge'}
        net_bridge_one.reload.return_value = None
        net_bridge_two.reload.return_value = None
        net.attrs = {'Driver': 'overlay'}
        data_gateway_networks = [net, net_bridge_one, net_bridge_two]
        # if old dg container exists, delete it
        mock_destroy_network.return_value = None
        self.obj.container_runtime.client.containers.get.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertEqual(self.obj.manage_docker_data_gateway_network(data_gateway_networks), net,
                         'Failed to manage leftover bridge DG networks')
        self.assertTrue(self.obj.container_runtime.client.containers.get.call_count==mock_destroy_network.call_count==2,
                        'Failed to search and delete leftover DG container for the 2 leftover bridge networks')
        self.obj.container_runtime.client.api.remove_container.assert_not_called()

        # if leftover containers exist, delete them
        self.obj.container_runtime.client.containers.get.reset_mock(side_effect=True)
        self.obj.container_runtime.client.containers.get.return_value = None
        self.obj.container_runtime.client.api.remove_container.return_value = None
        # also is no overlay net is passed, we get None
        data_gateway_networks = [net_bridge_one, net_bridge_two]
        self.assertEqual(self.obj.manage_docker_data_gateway_network(data_gateway_networks), None,
                         'Failed to manage DG networks when there is no overlay net in cluster mode')
        self.assertEqual(self.obj.container_runtime.client.api.remove_container.call_count, 2,
                         'Failed to delete leftover DG containers')

    @mock.patch.object(Supervise.Supervise, 'launch_data_gateway')
    @mock.patch.object(Supervise.Supervise, 'check_dg_network')
    def test_manage_docker_data_gateway_object(self, mock_check_dg_network, mock_launch_data_gateway):
        # if cluster worker, get None and do nothing
        self.obj.is_cluster_enabled = True
        self.obj.i_am_manager = False
        self.assertIsNone(self.obj.manage_docker_data_gateway_object(mock.MagicMock()),
                          'Tried to manage DG object when being a cluster worker')
        self.assertEqual(self.obj.data_gateway_object, None,
                         'data_gateway_object should be None')

        # otherwise, if the dg object is changed (!=None), get None and check the network
        self.obj.i_am_manager = True

        def assign_data_gateway_object(*args,**kwargs):
            self.obj.data_gateway_object = mock.MagicMock()

        with mock.patch.object(Supervise.Supervise, 'find_data_gateway') as mock_find_data_gateway:
            mock_find_data_gateway.side_effect = assign_data_gateway_object
            self.assertIsNone(self.obj.manage_docker_data_gateway_object('net'),
                              'Failed to manage DG object when it is set to none')
            mock_check_dg_network.assert_called_once_with('net')
            mock_launch_data_gateway.assert_not_called()

        # if the data_gateway_object cannot be found though, try to launch it
        with mock.patch.object(Supervise.Supervise, 'find_data_gateway') as mock_find_data_gateway:
            mock_find_data_gateway.return_value = None
            mock_launch_data_gateway.return_value = None    # meaning the launch fails
            l = len(self.obj.operational_status)
            self.assertRaises(Supervise.BreakDGManagementCycle, self.obj.manage_docker_data_gateway_object, 'net')
            self.assertEqual(l+1, len(self.obj.operational_status),
                             'Failure to launch DG should have added something to the operational status')
            mock_launch_data_gateway.assert_called_once()

    def test_manage_docker_data_gateway_connect_to_network(self):
        # no containers to connect, do nothing
        containers_to_connect = []
        self.assertIsNone(self.obj.manage_docker_data_gateway_connect_to_network(containers_to_connect, 'id'),
                          'Tried to connect containers to DG network when there are none')

        c1 = fake.MockContainer('c1')
        c2 = fake.MockContainer('agent')

        # if the DG net is already part of these containers, do nothing
        c1.attrs['NetworkSettings']['Networks'][Supervise.utils.nuvlaedge_shared_net] = True
        containers_to_connect = [c1]
        self.assertIsNone(self.obj.manage_docker_data_gateway_connect_to_network(containers_to_connect, 'id'),
                          'Failed to notice that containers are already connected to DG network')
        self.obj.container_runtime.client.api.connect_container_to_network.assert_not_called()
        # otherwise
        containers_to_connect = [c1, c2]
        self.assertIsNone(self.obj.manage_docker_data_gateway_connect_to_network(containers_to_connect, 'id'),
                          'Failed to connect containers to DG network')
        self.obj.container_runtime.client.api.connect_container_to_network.assert_called_once_with(c2.id,
                                                                                                   Supervise.utils.nuvlaedge_shared_net)

        # if the connection fails, add a status note
        l = len(self.obj.operational_status)
        self.obj.container_runtime.client.api.connect_container_to_network.side_effect = Exception('notfound')
        self.assertIsNone(self.obj.manage_docker_data_gateway_connect_to_network(containers_to_connect, c2.id),
                          'Failed to handle net connection error')
        self.assertEqual(l+1, len(self.obj.operational_status),
                         'Failure to connect container to DG net should have added something to the operational status')

        # and if the error is related with the agent, raise exception
        self.obj.container_runtime.client.api.connect_container_to_network.side_effect = Exception
        self.assertRaises(Supervise.BreakDGManagementCycle, self.obj.manage_docker_data_gateway_connect_to_network,
                          containers_to_connect, c2.id)
        self.assertEqual(l+2, len(self.obj.operational_status),
                         'Failure to handle agent connection error to DG net')

    @mock.patch.object(Supervise.Supervise, 'restart_data_gateway')
    @mock.patch.object(Supervise.Supervise, 'manage_docker_data_gateway_connect_to_network')
    @mock.patch.object(Supervise.Supervise, 'find_nuvlaedge_agent')
    @mock.patch.object(Supervise.Supervise, 'manage_docker_data_gateway_object')
    @mock.patch.object(Supervise.Supervise, 'manage_docker_data_gateway_network')
    @mock.patch.object(Supervise.Supervise, 'find_docker_network')
    def test_manage_docker_data_gateway(self, mock_find_docker_network, mock_manage_docker_data_gateway_network,
                                        mock_manage_docker_data_gateway_object, mock_find_nuvlaedge_agent,
                                        mock_manage_docker_data_gateway_connect_to_network, mock_restart_data_gateway):
        mock_find_docker_network.return_value = None
        # when Break is called, the fn stops
        mock_manage_docker_data_gateway_network.side_effect = Supervise.BreakDGManagementCycle
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to interrupt DG mgmt cycle when net is being created')
        mock_manage_docker_data_gateway_object.assert_not_called()

        mock_manage_docker_data_gateway_network.reset_mock(side_effect=True)
        mock_manage_docker_data_gateway_network.return_value = 'data-gateway-network'
        # same if the DG needs to be created
        mock_manage_docker_data_gateway_object.side_effect = Supervise.BreakDGManagementCycle
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to interrupt DG mgmt cycle when DG component is being created')
        mock_find_nuvlaedge_agent.assert_not_called()
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to interrupt DG mgmt cycle when net is being created')

        # if it passes, get the containers for connecting
        mock_manage_docker_data_gateway_object.reset_mock(side_effect=True)
        mock_manage_docker_data_gateway_object.return_value = None
        self.obj.container_runtime.client.containers.list.return_value = [fake.MockContainer('data-source')]

        # if agent container is not found, add operational status
        mock_find_nuvlaedge_agent.return_value = None
        l = len(self.obj.operational_status)
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to manage DG when agent container is not found')
        self.assertEqual(l+1, len(self.obj.operational_status),
                         'Failure to add operational status when agent cannot be found')

        # otherwise manage_docker_data_gateway_connect_to_network
        mock_find_nuvlaedge_agent.return_value = fake.MockContainer('agent')
        mock_manage_docker_data_gateway_connect_to_network.side_effect = Supervise.BreakDGManagementCycle
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to interrupt DG mgmt cycle when container cannot be connected to DB network')

        mock_manage_docker_data_gateway_connect_to_network.reset_mock(side_effect=True)
        mock_manage_docker_data_gateway_connect_to_network.return_value = None

        # if agent API is not found, increment fail flag
        fail_flag = self.obj.agent_dg_failed_connection
        self.obj.container_runtime.test_agent_connection.return_value = (fake.FakeRequestsResponse(status_code=404),
                                                                         None)
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to increment agent errors')
        mock_restart_data_gateway.assert_not_called()

        # after 3 attempts, restart the DG
        self.obj.agent_dg_failed_connection = 4
        mock_restart_data_gateway.return_value = None
        self.obj.container_runtime.test_agent_connection.return_value = (fake.FakeRequestsResponse(), None)
        self.assertIsNone(self.obj.manage_docker_data_gateway(),
                          'Failed to restart data gateway')
        self.assertEqual(self.obj.agent_dg_failed_connection, 0,
                         'Failed to reset DG-Agent connection failures')

    def test_restart_data_gateway(self):
        self.obj.data_gateway_object = mock.MagicMock()
        # restart, depending on whether it is running in cluster or standalone mode
        self.obj.i_am_manager = True
        self.obj.is_cluster_enabled = True
        self.assertIsNone(self.obj.restart_data_gateway(),
                          'Failed to restart DG as a cluster manager')
        self.obj.data_gateway_object.force_update.assert_called_once()
        self.obj.data_gateway_object.restart.assert_not_called()

        self.obj.is_cluster_enabled = False
        self.assertIsNone(self.obj.restart_data_gateway(),
                          'Failed to restart DG as a standalone worker')
        self.obj.data_gateway_object.restart.assert_called_once()

    def test_find_data_gateway(self):
        # if cluster_workers_cannot_manage, throw it
        self.obj.i_am_manager = False
        self.obj.is_cluster_enabled = True
        self.assertRaises(Supervise.ClusterNodeCannotManageDG, self.obj.find_data_gateway)

        # otherwise
        self.obj.i_am_manager = True
        # define dg object and return True
        self.obj.container_runtime.client.services.get.return_value = 'dg'
        self.assertTrue(self.obj.find_data_gateway('foo'),
                        'Failed to find DG service')
        self.assertEqual(self.obj.data_gateway_object, 'dg',
                         'Failed to set DG object')
        self.obj.container_runtime.client.containers.get.assert_not_called()

        # same for containers
        self.obj.i_am_manager = False
        self.obj.is_cluster_enabled = False
        self.obj.container_runtime.client.containers.get.return_value = 'dgc'
        self.assertTrue(self.obj.find_data_gateway('foo'),
                        'Failed to find DG container')
        self.assertEqual(self.obj.data_gateway_object, 'dgc',
                         'Failed to set DG object in container mode')

        # in case of errors, get false and set obj to None
        self.obj.container_runtime.client.containers.get.side_effect = docker.errors.APIError('', requests.Response())
        self.assertFalse(self.obj.find_data_gateway('foo'),
                         'Unable to cope with find error')
        self.assertIsNone(self.obj.data_gateway_object,
                          'Failed to reset DG object to None')

    def test_find_docker_network(self):
        # lookup
        self.obj.container_runtime.client.networks.list.return_value = ['foo']
        self.assertEqual(self.obj.find_docker_network(['net']), ['foo'],
                         'Failed to find Docker network')

    def test_destroy_docker_network(self):
        net = fake.MockNetwork('my-net')

        # when no containers attached, just remove network
        net.attrs['Containers'] = {}
        self.assertIsNone(self.obj.destroy_docker_network(net),
                          'Failed to remove orphan network')
        net.remove_counter.assert_called_once()
        net.disconnect_counter.assert_not_called()

        # otherwise, disconnect first
        net = fake.MockNetwork('my-net')
        self.assertIsNone(self.obj.destroy_docker_network(net),
                          'Failed to disconnect and remove network')
        self.assertEqual(net.disconnect_counter.call_count, 2,
                         'Failed to disconnect the two containers from the network')

    def test_setup_docker_network(self):
        self.obj.container_runtime.get_node_info.return_value = {}
        # if cluster_workers_cannot_manage, throw it
        self.obj.i_am_manager = False
        self.obj.is_cluster_enabled = True
        self.assertRaises(Supervise.ClusterNodeCannotManageDG, self.obj.setup_docker_network)

        # otherwise
        self.obj.i_am_manager = True

        # without any assumptions or error, it just calls the Docker api a few times
        self.obj.container_runtime.client.services.get.return_value = None
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network')
        self.obj.container_runtime.client.services.create.assert_called_once()
        self.obj.container_runtime.client.services.get.assert_called_once_with(Supervise.utils.overlay_network_service)
        self.obj.container_runtime.client.networks.create.assert_called_once()

        # if ack exists, return earlier
        ack = mock.MagicMock()
        self.obj.container_runtime.client.services.get.return_value = ack
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network when ack service exists')
        ack.force_update.assert_called_once()

        # in standalone mode, we just exit
        self.obj.container_runtime.client.services.get.reset_mock()
        self.obj.is_cluster_enabled = False
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network in standalone mode')
        self.obj.container_runtime.client.services.get.assert_not_called()

        # if ack is not found, keep going and create it
        self.obj.is_cluster_enabled = True
        self.obj.container_runtime.client.services.create.reset_mock()
        self.obj.container_runtime.client.services.get.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network when ack does not exist')
        self.obj.container_runtime.client.services.create.assert_called_once()

        # other ack error return False
        self.obj.container_runtime.client.services.create.reset_mock()
        self.obj.container_runtime.client.services.get.side_effect = docker.errors.APIError('', requests.Response())
        self.assertFalse(self.obj.setup_docker_network('net'),
                         'Tried to setup Docker network when ack failed to be found')
        self.obj.container_runtime.client.services.create.assert_not_called()

        # if there are errors creating the network
        # get False
        self.obj.container_runtime.client.networks.create.side_effect = docker.errors.APIError('', requests.Response())
        self.obj.container_runtime.client.services.get.reset_mock()
        self.assertFalse(self.obj.setup_docker_network('net'),
                         'Tried to setup Docker network when network could not be created')
        self.obj.container_runtime.client.services.get.assert_not_called()

        # unless it is a 409
        self.obj.container_runtime.client.services.get.reset_mock()
        self.obj.container_runtime.client.services.get.reset_mock(side_effect=True)
        self.obj.container_runtime.client.networks.create.side_effect = docker.errors.APIError('409',
                                                                                               requests.Response())
        # continue in cluster mode
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network when overlay net already exists')
        self.obj.container_runtime.client.services.get.assert_called_once()
        # and stop in standalone mode
        self.obj.container_runtime.client.services.get.reset_mock()
        self.obj.is_cluster_enabled = False
        self.assertTrue(self.obj.setup_docker_network('net'),
                        'Failed to setup Docker network when bridge net already exists')
        self.obj.container_runtime.client.services.get.assert_not_called()

    def test_get_project_name(self):
        l = len(self.obj.operational_status)
        # exit on error, but log
        self.obj.container_runtime.client.containers.get.side_effect = docker.errors.NotFound('', requests.Response())
        self.assertRaises(Exception, self.obj.get_project_name)
        self.assertEqual(len(self.obj.operational_status), l+1,
                         'Failed to add operational status after failing to get project name')

        self.obj.container_runtime.client.containers.get.reset_mock(side_effect=True)
        out_container = fake.MockContainer()
        # get the project name if all goes well
        self.obj.container_runtime.client.containers.get.return_value = out_container
        self.assertEqual(self.obj.get_project_name(), fake.MockContainer().labels['com.docker.compose.project'],
                         'Failed to get project name from container labels')

        # if label does not exist
        out_container.labels.pop('com.docker.compose.project')
        # try the name
        # outcome depends on the naming convention
        out_container.name = 'bad-name'
        self.obj.container_runtime.client.containers.get.return_value = out_container
        self.assertRaises(Exception, self.obj.get_project_name)
        self.assertEqual(len(self.obj.operational_status), l+2,
                         'Failed to add operational status when project name cannot be inferred from container name')

        out_container.name = 'project-good-name'
        self.obj.container_runtime.client.containers.get.return_value = out_container
        self.assertEqual(self.obj.get_project_name(), out_container.name.split('-')[0],
                         'Failed to get project name from container name')

    def test_fix_network_connectivity(self):
        net = fake.MockNetwork('target-net')
        self.assertIsNone(self.obj.fix_network_connectivity([], net),
                          'Tried to fix connectivity when there are no containers to fix')
        net.connect_counter.assert_not_called()

        # host mode containers are ignored
        host_container = fake.MockContainer()
        host_container.attrs['HostConfig'] = {'NetworkMode': 'host'}
        self.assertIsNone(self.obj.fix_network_connectivity(5*[host_container], net),
                          'Tried to fix connectivity for containers in host mode')
        net.connect_counter.assert_not_called()

        # if the container is already connected to the network, skip it
        container = fake.MockContainer()
        net.name = list(container.attrs['NetworkSettings']['Networks'].keys())[0]
        self.assertIsNone(self.obj.fix_network_connectivity(5*[container], net),
                          'Tried to fix connectivity for containers that do not need fixing')
        net.connect_counter.assert_not_called()

        # otherwise, connect container to net
        net.name = 'new-net'
        self.assertIsNone(self.obj.fix_network_connectivity([container], net),
                          'Failed to fix container connectivity')
        net.connect_counter.assert_called_once()

        # if connecting fails
        net.connect_counter.reset_mock()
        # due to "already exists in network", just keep going
        net.connect_counter.side_effect = docker.errors.APIError("already exists in network", requests.Response())
        self.assertIsNone(self.obj.fix_network_connectivity(5*[container], net),
                          'Failed to recognize that containers are already connected to network')
        self.assertEqual(net.connect_counter.call_count, 5,
                         'Should have tried to fix connectivity for 5 containers')

        net.connect_counter.reset_mock()

        # due to "not found", exit immediately
        net.connect_counter.side_effect = docker.errors.APIError("not found", requests.Response())
        self.assertIsNone(self.obj.fix_network_connectivity(5*[container], net),
                          'Failed to abort when network ceases to exist')
        net.connect_counter.assert_called_once()
        net.connect_counter.reset_mock()

        # for other errors, just log the issue
        l = len(self.obj.operational_status)
        net.connect_counter.side_effect = docker.errors.APIError('', requests.Response())
        self.assertIsNone(self.obj.fix_network_connectivity(5*[container]+[host_container], net),
                          'Failed to handle unknown network connection errors')
        self.assertEqual(len(self.obj.operational_status), l+5,
                         'Should log one status note per ')

    @mock.patch.object(Supervise.Supervise, 'fix_network_connectivity')
    @mock.patch.object(Supervise.Supervise, 'get_project_name')
    def test_check_nuvlaedge_docker_connectivity(self, mock_get_project_name, mock_fix_network_connectivity):
        # without a project name, get None
        mock_get_project_name.side_effect = Exception
        self.assertIsNone(self.obj.check_nuvlaedge_docker_connectivity(),
                          'Tried to check Docker connectivity without a project name')
        self.obj.container_runtime.client.containers.list.assert_not_called()

        # otherwise get containers and networks
        mock_get_project_name.reset_mock(side_effect=True)
        self.obj.container_runtime.client.containers.list.return_value = []
        self.obj.container_runtime.client.networks.list.return_value = []
        # without container or networks, return none and add operational status
        l = len(self.obj.operational_status)
        self.assertIsNone(self.obj.check_nuvlaedge_docker_connectivity(),
                          'Tried to check Docker connectivity without any containers or networks')
        self.assertEqual(len(self.obj.operational_status), l+1,
                         'Failed to add operational status when there are no containers or networks to be checked')
        mock_fix_network_connectivity.assert_not_called()

        # otherwise, fix the connectivity
        c = fake.MockContainer()
        n = fake.MockNetwork('net')
        self.obj.container_runtime.client.containers.list.return_value = [c]
        self.obj.container_runtime.client.networks.list.return_value = [n]
        self.assertIsNone(self.obj.check_nuvlaedge_docker_connectivity(),
                          'Failed to check NB Docker connectivity')
        mock_fix_network_connectivity.assert_called_once_with([c], n)

    def test_heal_created_container(self):
        # simple action calling
        self.obj.container_runtime.client.api.start.return_value = None
        self.assertIsNone(self.obj.heal_created_container(fake.MockContainer()),
                          'Failed to heal container in created state')

        self.obj.container_runtime.client.api.start.side_effect = docker.errors.APIError('', requests.Response())
        self.assertIsNone(self.obj.heal_created_container(fake.MockContainer()),
                          'Failed to handle Docker API error when healing container in created state')

    @mock.patch.object(Supervise.Supervise, 'restart_container')
    @mock.patch('nuvlaedge.system_manager.Supervise.Timer')
    def test_heal_exited_container(self, mock_timer, mock_restart_container):
        container = fake.MockContainer()
        container.attrs['State'] = {'ExitCode': 0}  # nothing to do
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Tried to heal an exited container with status 0')
        mock_timer.assert_not_called()
        container.is_alive_counter.assert_not_called()

        container.attrs['State'] = {'ExitCode': 1, 'Restarting': True}  # already restarting, nothing to do
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Tried to heal an exited container that is already restarting')
        mock_timer.assert_not_called()
        container.is_alive_counter.assert_not_called()

        container.attrs['State']['Restarting'] = False
        container.attrs['HostConfig'] = {'RestartPolicy': {'Name': 'no'}}   # not to be restarted, nothing to do
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Tried to heal an exited container that is not supposed to be restarted')
        mock_timer.assert_not_called()
        container.is_alive_counter.assert_not_called()

        container.attrs['HostConfig']['RestartPolicy']['Name'] = 'always'
        # container can be in restarting list, but if it is alive, do nothing
        self.obj.nuvlaedge_containers_restarting[container.name] = container
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Tried to heal an exited container that is not known')
        mock_timer.assert_not_called()
        container.is_alive_counter.assert_called_once()

        # if container not alive, restart it
        container.am_i_alive = False
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Failed to heal an exited container that is not alive')
        mock_timer.assert_called_once_with(30, mock_restart_container, (container.name, container.id))
        self.assertEqual(container.is_alive_counter.call_count, 2,
                         'Should have seen if container is alive, twice')

        # if container is not restarting, restart it
        self.obj.nuvlaedge_containers_restarting.pop(container.name)
        self.assertIsNone(self.obj.heal_exited_container(container),
                          'Failed to heal an exited container that is not restarting')
        self.assertEqual(mock_timer.call_count, 2,
                         'Should have called called a restart twice')

    @mock.patch.object(Supervise.Supervise, 'heal_exited_container')
    @mock.patch.object(Supervise.Supervise, 'heal_created_container')
    def test_docker_container_healer(self, mock_heal_created_container, mock_heal_exited_container):
        # without NB containers, do nothing
        self.obj.nuvlaedge_containers = []
        self.assertIsNone(self.obj.docker_container_healer(),
                          'Tried to heal containers when there are none')

        # if there are obsolete containers, remove them from the obsolete list
        obsolete_container = fake.MockContainer()
        # if ["paused", "running", "restarting"], do nothing
        self.obj.nuvlaedge_containers = [fake.MockContainer('1', status='paused'),
                                        fake.MockContainer('2', status='running'),
                                        fake.MockContainer('3', status='restarting')]
        self.obj.nuvlaedge_containers_restarting = {**{c.name: {} for c in self.obj.nuvlaedge_containers},
                                                    **{obsolete_container.name: {}}}
        self.assertIsNone(self.obj.docker_container_healer(),
                          'Tried to heal containers that are in a good state, which are not to be healed')
        self.assertEqual(len(self.obj.nuvlaedge_containers_restarting), 3,
                         'Failed to pop obsolete containers from memory')
        mock_heal_created_container.assert_not_called()
        mock_heal_exited_container.assert_not_called()

        # created containers are started
        created_container = fake.MockContainer(status='created')
        self.obj.nuvlaedge_containers.append(created_container)
        self.assertIsNone(self.obj.docker_container_healer(),
                          'Failed to heal created containers')
        mock_heal_created_container.assert_called_once_with(created_container)
        mock_heal_exited_container.assert_not_called()

        # exited containers are restarted
        exited_container = fake.MockContainer(status='exited')
        self.obj.nuvlaedge_containers.append(exited_container)
        self.assertIsNone(self.obj.docker_container_healer(),
                          'Failed to heal exited containers')
        mock_heal_exited_container.assert_called_once_with(exited_container)

    def test_restart_container(self):
        self.assertIsNone(self.obj.restart_container('name', 'id'),
                          'Failed to restart container')
        self.obj.container_runtime.client.api.restart.assert_called_once_with('id')

        # when it fail, add status note
        self.obj.container_runtime.client.api.restart.side_effect = docker.errors.APIError('', requests.Response())
        l = len(self.obj.operational_status)
        self.assertIsNone(self.obj.restart_container('name', 'id'),
                          'Failed to cope with error while restarting container')
        self.assertEqual(len(self.obj.operational_status), l+1,
                         'Failed to append operational status when cannot restart container')
        self.obj.container_runtime.client.api.disconnect_container_from_network.assert_not_called()

        # if error is network related, try to disconnect container from network
        self.obj.container_runtime.client.api.restart.side_effect = docker.errors.APIError('network not found',
                                                                                           requests.Response())
        self.assertIsNone(self.obj.restart_container('name', 'id'),
                          'Failed to disconnect container from network when restart fails')
        self.obj.container_runtime.client.api.disconnect_container_from_network.assert_called_once_with('id',
                                                                                                        Supervise.utils.nuvlaedge_shared_net)

        # if disconnect fails, add a second operations status
        l = len(self.obj.operational_status)
        self.obj.container_runtime.client.api.disconnect_container_from_network.side_effect = docker.errors.APIError('',
                                                                                                                     requests.Response())
        self.assertIsNone(self.obj.restart_container('name', 'id'),
                          'Failed to handle network disconnection error')
        self.assertEqual(len(self.obj.operational_status), l+2,
                         'Failed to append operational status for container restart error and net disconnect error')
