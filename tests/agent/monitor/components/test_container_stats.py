# -*- coding: utf-8 -*-
import unittest
from mock import Mock, patch, MagicMock
import docker
import docker.errors
import requests
import tests.agent.utils.fake as fake

from nuvlaedge.agent.workers.monitor.components.container_stats import ContainerStatsMonitor
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus


class TestContainerStatsMonitor(unittest.TestCase):

    @staticmethod
    def get_base_monitor() -> ContainerStatsMonitor:
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        return ContainerStatsMonitor('test_monitor', Mock(), True)

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    def test_refresh_container_info(self, mock_check_support):
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()

        test_monitor.coe_client.collect_container_metrics.return_value = []
        # Container should stay empty when no containers available
        test_monitor.refresh_container_info()
        self.assertFalse(test_monitor.data.containers)

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    @patch('time.sleep', side_effect=InterruptedError)
    def test_run(self, mock_sleep, mock_check_support):
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        with patch('nuvlaedge.agent.workers.monitor.components.container_stats.'
                   'ContainerStatsMonitor.refresh_container_info') as mock_refresh, \
                patch('nuvlaedge.agent.workers.monitor.components.container_stats.'
                      'ContainerStatsMonitor.update_data') as mock_update:

            with self.assertRaises(InterruptedError):
                test_monitor.run()
                self.assertFalse(test_monitor.data.containers)
                mock_update.assert_called_once()
                mock_refresh.assert_called_once()

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    def test_get_cluster_manager_attrs(self, mock_check_support):
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        self.assertEqual(test_monitor.get_cluster_manager_attrs([], 'node-id'),
                         (False, []),
                         'Tried to get Cluster manager attrs even though node is not a '
                         'manager')

        # otherwise, get nodes
        node_1 = fake.MockDockerNode()
        node_2 = fake.MockDockerNode()
        test_monitor.coe_client.list_nodes.return_value = [node_1, node_2]
        # if there's an error, get False and [] again
        test_monitor.coe_client.list_nodes.side_effect = \
            docker.errors.APIError('', requests.Response())
        self.assertEqual(test_monitor.get_cluster_manager_attrs(['node-id'], 'node-id'),
                         (False, []),
                         'Returned cluster attrs even though nodes could not be listed')

        # otherwise, return nodes if active
        test_monitor.coe_client.is_node_active.return_value = True
        test_monitor.coe_client.list_nodes.reset_mock(side_effect=True)
        self.assertEqual(test_monitor.get_cluster_manager_attrs(['node-id'], 'node-id'),
                         (True, [node_1.id, node_2.id]),
                         'Failed to get cluster manager attributes')

        test_monitor.coe_client.is_node_active.return_value = False
        self.assertEqual(test_monitor.get_cluster_manager_attrs(['node-id'], 'node-id'),
                         (True, []),
                         'Failed to get cluster manager attributes when no nodes '
                         'are active')

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    @patch.object(ContainerStatsMonitor, 'get_cluster_manager_attrs')
    def test_update_cluster_data(self, mock_get_cluster_manager_attrs, mock_check_support):
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        mock_get_cluster_manager_attrs.return_value = (False, [])
        test_monitor.coe_client.get_cluster_join_address.return_value = None
        # if there's no node-id, then certain keys shall not be in body
        test_monitor.coe_client.get_node_id.return_value = None
        test_monitor.coe_client.get_cluster_id.return_value = None
        test_monitor.coe_client.get_cluster_managers.return_value = None
        test_monitor.coe_client.get_node_labels.return_value = None
        test_monitor.update_cluster_data()
        self.assertTrue(
            all(x not in test_monitor.data
                for x in ["node-id", "orchestrator", "cluster-node-role"]),
            'Node ID attrs were included in status body even though there is no Node ID')

        # if cluster-id is None, then it is not added
        test_monitor.coe_client.get_cluster_id.return_value = None

        test_monitor.update_cluster_data()
        self.assertIsNone(test_monitor.data.cluster_data.cluster_id,
                          'Cluster ID was added to status even though it does not exist')

        # same for cluster-managers
        test_monitor.coe_client.get_cluster_managers.return_value = []

        test_monitor.update_cluster_data()
        self.assertIsNone(test_monitor.data.cluster_data.cluster_managers,
                          'Cluster managers were added to status even though there '
                          'are none')

        test_monitor.coe_client.get_node_id.return_value = 'node-id'
        # if node is not a manager, skip those fields
        test_monitor.coe_client.get_cluster_managers.return_value = ['node-id-2']
        test_monitor.coe_client.ORCHESTRATOR_COE = 'coe'

        test_monitor.update_cluster_data()
        test_monitor.coe_client.get_cluster_join_address.assert_called_once()
        self.assertEqual(test_monitor.data.cluster_data.node_id, 'node-id',
                         'Node ID does not match')
        self.assertEqual(test_monitor.data.cluster_data.cluster_node_role, 'worker',
                         'Saying node is not a worker when it is')

        # if it is a manager, then get all manager related attrs
        test_monitor.coe_client.get_cluster_id.return_value = 'cluster-id'
        test_monitor.coe_client.get_cluster_managers.return_value = ['node-id']
        mock_get_cluster_manager_attrs.return_value = (True, ['node-id'])
        test_monitor.coe_client.get_cluster_join_address.return_value = 'addr:port'
        test_monitor.coe_client.get_node_labels.return_value = [{'name': 'coe-label', 'value': 'coe-value'}]

        test_monitor.update_cluster_data()
        all_fields = ["node-id", "orchestrator", "cluster-node-role", "cluster-id",
                      "cluster-join-address", "cluster-managers", "cluster-nodes", "cluster-node-labels"]
        self.assertEqual(sorted(all_fields),
                         sorted(test_monitor.data.cluster_data.model_dump(by_alias=True, exclude_none=True).keys()),
                         'Unable to set cluster status')

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.execute_cmd')
    @patch('os.path.exists')
    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    def test_get_swarm_certificate_expiration_date(self, mock_check_support, mock_exists, mock_run):
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        # if swarm cert does not exist, get None
        mock_exists.return_value = False
        self.assertIsNone(test_monitor.get_swarm_certificate_expiration_date(),
                          'Tried to get swarm cert exp date even though there is no '
                          'certificate')
        mock_run.execute_cmd.assert_not_called()

        # otherwise, run openssl

        mock_exists.return_value = True
        mock_run.execute_cmd.return_value = MagicMock()

        # if openssl fails, get None
        mock_run.execute_cmd.return_value.returncode = 1

        self.assertIsNone(test_monitor.get_swarm_certificate_expiration_date(),
                          'Tried to get swarm cert exp date even though openssl failed '
                          'to execute')

        mock_run.assert_called_once()

        # otherwise, get the expiration date
        mock_run.return_value.returncode = 0
        exp_date = 'Feb  6 05:41:00 2022 GMT'
        mock_run.return_value.stdout = f'notAfter={exp_date}\n'

        self.assertEqual(test_monitor.get_swarm_certificate_expiration_date(),
                         '2022-02-06T05:41:00.000Z',
                         'Unable to get Swarm node certificate expiration date')

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor.'
           'refresh_container_info')
    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor.'
           'update_cluster_data')
    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor.'
           'get_swarm_certificate_expiration_date')
    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
           '._check_support_container_stats_new')
    def test_update_data(self, mock_check_support, mock_cert, mock_update, refresh_container):
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        mock_update.return_value = None
        mock_cert.return_value = None

        test_monitor.coe_client.get_client_version.return_value = '1.0'

        refresh_container.return_value = None
        test_monitor.coe_client.ORCHESTRATOR = 'docker'
        test_monitor.update_data()

        self.assertEqual(test_monitor.data.docker_server_version, '1.0')
        mock_cert.assert_called_once()
        mock_update.assert_called_once()

        test_monitor.coe_client.ORCHESTRATOR = 'not_docker'
        test_monitor.coe_client.get_client_version.return_value = '1.0'
        test_monitor.update_data()
        self.assertEqual(test_monitor.data.kubelet_version, '1.0')

        mock_cert.return_value = "Expired"
        test_monitor.update_data()
        self.assertEqual(test_monitor.data.swarm_node_cert_expiry_date, "Expired")

    @patch('nuvlaedge.agent.workers.monitor.components.container_stats.ContainerStatsMonitor'
            '._check_support_container_stats_new')
    def test_populate_nb_report(self, mock_check_support):
        nb_report: dict = {}
        mock_check_support.return_value = False
        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        test_monitor.data = Mock()
        test_monitor.data.containers = {}
        test_monitor.data.cluster_data = None
        test_monitor.data.swarm_node_cert_expiry_date = None
        test_monitor.populate_nb_report(nb_report)
        self.assertIsNotNone(nb_report.get('resources', None))

        test_monitor.data.cluster_data = Mock()
        test_monitor.data.cluster_data.dict.return_value = {'some_Data': 1}
        test_monitor.populate_nb_report(nb_report)
        self.assertIn('some_Data', nb_report)

        container_data = Mock()
        container_data.name = 'container_name'
        test_monitor.data.containers = {'container': container_data}
        test_monitor.populate_nb_report(nb_report)

        test_monitor: ContainerStatsMonitor = self.get_base_monitor()
        test_monitor.data = Mock()
        test_monitor.data.cluster_data = None
        test_monitor.data.containers = {}
        test_monitor.data.swarm_node_cert_expiry_date = "A"
        test_monitor.data.dict.return_value = {'more_data': 2}
        test_monitor.populate_nb_report(nb_report)
        self.assertIn('more_data', nb_report)
