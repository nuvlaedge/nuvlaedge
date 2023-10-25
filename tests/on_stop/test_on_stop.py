#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import unittest
import mock

import docker
import docker.errors
from docker.models.nodes import Node

import nuvlaedge.on_stop as on_stop


class OnStopTestCase(unittest.TestCase):

    def setUp(self) -> None:
        on_stop.docker_client = mock.MagicMock()
        self.mock_time_sleep = mock.patch('time.sleep').start()

    @mock.patch('socket.gethostname')
    def test_pause(self, mock_get_hostname):
        container = mock.MagicMock()

        # Nominal case
        on_stop.docker_client.containers.get.return_value = container
        on_stop.pause()
        container.pause.assert_called_once()
        mock_get_hostname.assert_called_once()

        # reset
        container.pause.reset_mock()
        mock_get_hostname.reset_mock()

        # Container not found
        on_stop.docker_client.containers.get.side_effect = docker.errors.NotFound('')
        self.assertRaises(docker.errors.NotFound, on_stop.pause)
        container.pause.assert_not_called()
        mock_get_hostname.assert_called_once()

    def test_prune_old_onstop_containers(self):
        # Nominal case
        with self.assertLogs(level='INFO'):
            on_stop.prune_old_onstop_containers()

        # APIError exception
        on_stop.docker_client.containers.prune.side_effect = docker.errors.APIError('')
        with self.assertLogs(level='DEBUG'):
            on_stop.prune_old_onstop_containers()

    def test_detach_network_container(self):
        container = mock.MagicMock()
        network = mock.MagicMock()

        # Nominal case
        on_stop.detach_network_container(container, network)
        network.disconnect.assert_called_once()

        # reset
        network.disconnect.reset_mock()

        # Not found
        network.disconnect.side_effect = docker.errors.NotFound('')
        on_stop.detach_network_container(container, network)
        network.disconnect.assert_called_once()

    def test_cleanup_networks(self):
        network = mock.MagicMock()
        network.attrs = {'Containers': {'container-id': {}}}
        on_stop.docker_client.networks.list.return_value = [network]

        # Nominal case
        on_stop.cleanup_networks('')
        network.reload.assert_called_once()
        network.remove.assert_called_once()
        network.disconnect.assert_called_once()

        # reset
        network.reload.reset_mock()
        network.remove.reset_mock()
        network.disconnect.reset_mock()

        # Without Containers
        network.attrs = {}
        on_stop.cleanup_networks('')
        network.disconnect.assert_not_called()

        # reset
        network.remove.reset_mock()
        network.disconnect.reset_mock()

        # NotFound
        network.remove.side_effect = docker.errors.NotFound('')
        on_stop.cleanup_networks('')
        network.remove.assert_called_once()

        # reset
        network.remove.reset_mock()

        # One Exception (retry works)
        network.remove.side_effect = [Exception("1st"), mock.DEFAULT]
        on_stop.cleanup_networks('')
        self.assertEqual(network.remove.call_count, 2)

        # reset
        network.remove.reset_mock()

        # Multiple Exception (retry failed)
        network.remove.side_effect = Exception("network remove failed")
        with self.assertLogs(level='ERROR'):
            on_stop.cleanup_networks('')

    def test_cleanup_datagateway(self):
        container = mock.MagicMock()
        service = mock.MagicMock()

        on_stop.docker_client.containers.list.return_value = [container]
        on_stop.docker_client.services.list.return_value = [service]

        # Nominal case without swarm
        on_stop.cleanup_datagateway(False)
        on_stop.docker_client.containers.list.assert_called_once()
        on_stop.docker_client.services.list.assert_not_called()
        container.remove.assert_called_once()
        service.remove.assert_not_called()

        # reset
        on_stop.docker_client.containers.list.reset_mock()
        on_stop.docker_client.services.list.reset_mock()
        container.remove.reset_mock()
        service.remove.reset_mock()

        # Nominal case with swarm
        on_stop.cleanup_datagateway(True)
        on_stop.docker_client.containers.list.assert_not_called()
        on_stop.docker_client.services.list.assert_called_once()
        container.remove.assert_not_called()
        service.remove.assert_called_once()

        # reset
        on_stop.docker_client.containers.list.reset_mock()
        on_stop.docker_client.services.list.reset_mock()
        container.remove.reset_mock()
        service.remove.reset_mock()

        # NotFound
        container.remove.side_effect = docker.errors.NotFound('')
        on_stop.cleanup_datagateway(False)
        container.remove.assert_called_once()

        # reset
        on_stop.docker_client.containers.list.reset_mock()
        container.remove.reset_mock()

        # One Exception (retry works)
        container.remove.side_effect = [Exception("1st"), mock.DEFAULT]
        on_stop.cleanup_datagateway(False)
        self.assertEqual(container.remove.call_count, 2)

        # reset
        container.remove.reset_mock()

        # Multiple Exception (retry failed)
        container.remove.side_effect = Exception("network remove failed")
        with self.assertLogs(level='ERROR'):
            on_stop.cleanup_datagateway(False)

    @mock.patch('docker.models.nodes.Node.update')
    @mock.patch('nuvlaedge.on_stop.prune_old_onstop_containers')
    @mock.patch('nuvlaedge.on_stop.cleanup_datagateway')
    @mock.patch('nuvlaedge.on_stop.cleanup_networks')
    def test_do_cleanup(self, mock_cleanup_networks,
                        mock_cleanup_dg,
                        mock_prune_onstop,
                        mock_node_update):

        # Swarm enabled and manager
        on_stop.docker_client.info.return_value = {
            'Swarm': {'NodeID': 'node-id',
                      'LocalNodeState': 'active',
                      'RemoteManagers': [{'NodeID': 'node-id'}]}
        }
        on_stop.docker_client.nodes.list.return_value = []
        node_attrs = {'Spec': {'Labels': {'nuvlaedge': 'True'}}}
        on_stop.docker_client.nodes.get.return_value = Node(client=on_stop.docker_client,
                                                            attrs=node_attrs)
        on_stop.do_cleanup()
        mock_node_update.assert_called_once()
        mock_prune_onstop.assert_called_once()
        mock_cleanup_dg.assert_not_called()
        mock_cleanup_networks.assert_not_called()

        # reset
        on_stop.docker_client.info.list.reset_mock()
        on_stop.docker_client.nodes.list.reset_mock()
        on_stop.docker_client.nodes.get.reset_mock()
        mock_node_update.reset_mock()
        mock_prune_onstop.reset_mock()
        mock_cleanup_dg.reset_mock()
        mock_cleanup_networks.reset_mock()

        # Swarm enabled and worker
        on_stop.docker_client.info.return_value = {
            'Swarm': {'NodeID': 'another-node-id',
                      'LocalNodeState': 'active',
                      'RemoteManagers': [{'NodeID': 'node-id'}]}
        }
        on_stop.do_cleanup()
        mock_node_update.assert_not_called()
        mock_cleanup_dg.assert_not_called()
        mock_cleanup_networks.assert_not_called()

        # reset
        on_stop.docker_client.info.list.reset_mock()
        mock_node_update.reset_mock()
        mock_cleanup_dg.reset_mock()
        mock_cleanup_networks.reset_mock()

        # Swarm disabled
        on_stop.docker_client.info.return_value = {
            'Swarm': {'NodeID': 'another-node-id',
                      'RemoteManagers': [{'NodeID': 'node-id'}]}
        }
        on_stop.do_cleanup()
        mock_node_update.assert_not_called()
        mock_cleanup_dg.assert_called_once()
        mock_cleanup_networks.assert_called_once()

    @mock.patch('docker.from_env')
    @mock.patch('nuvlaedge.on_stop.pause')
    @mock.patch('nuvlaedge.on_stop.do_cleanup')
    def test_main(self, mock_cleanup, mock_pause, mock_docker_from_env):
        argv = sys.argv.copy()

        # Pause
        sys.argv = ['on-stop', 'paused']
        on_stop.main()
        mock_pause.assert_called_once()
        mock_cleanup.assert_not_called()

        # reset
        mock_pause.reset_mock()
        mock_cleanup.reset_mock()

        # Cleanup
        sys.argv = ['on-stop']
        on_stop.main()
        mock_pause.assert_not_called()
        mock_cleanup.assert_called_once()

        # reset
        mock_pause.reset_mock()
        mock_cleanup.reset_mock()

        # Exception
        sys.argv = ['on-stop', '--log-level', 'RAISE']
        with self.assertRaises(SystemExit):
            on_stop.main()

        # reset
        sys.argv = argv


if __name__ == '__main__':
    unittest.main()


