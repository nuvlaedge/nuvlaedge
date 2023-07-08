# -*- coding: utf-8 -*-
import unittest
from mock import Mock, patch
import time
from nuvlaedge.agent.monitor.components.nuvlaedge_info import NuvlaEdgeInfoMonitor
from nuvlaedge.agent.monitor.edge_status import EdgeStatus


class TestNuvlaEdgeInfoMonitor(unittest.TestCase):

    get_installation_parameters_result = {
        'project-name': 'nuvlaedge',
        'working-dir': '/opt/nuvlaedge',
        'config-files': [
            'docker-compose.yml',
            'docker-compose.usb.yml'
        ],
        'environment': [
            'NUVLABOX_ENGINE_VERSION=1.2.3',
            'NUVLABOX_DATA_GATEWAY_IMAGE=eclipse-mosquitto:1.6.12',
            'SECURITY_SCAN_INTERVAL=1800'
        ]
    }

    @staticmethod
    def get_base_monitor() -> NuvlaEdgeInfoMonitor:
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        return NuvlaEdgeInfoMonitor('test_monitor', Mock(), True)

    def test_init(self):
        telemetry = Mock()
        telemetry.edge_status.nuvlaedge_info = None
        NuvlaEdgeInfoMonitor('test_monitor', telemetry, True)
        self.assertTrue(telemetry.edge_status.nuvlaedge_info)

    @patch('psutil.boot_time')
    def test_update_data(self, mock_boot):

        test_monitor: NuvlaEdgeInfoMonitor = self.get_base_monitor()
        test_monitor.ne_id = 'id'
        test_monitor.ne_engine_version = 'ne_version'
        test_monitor.installation_home = 'home_path'
        test_monitor.coe_client.get_host_os.return_value = 'host_os'
        test_monitor.coe_client.get_host_architecture.return_value = 'arch'
        test_monitor.coe_client.get_hostname.return_value = 'hostname'
        test_monitor.coe_client.get_container_plugins.return_value = ['no']
        mock_boot.return_value = time.time()
        test_monitor.data.installation_parameters = None
        test_monitor.coe_client.get_installation_parameters.return_value = \
            self.get_installation_parameters_result
        test_monitor.coe_client.get_all_nuvlaedge_components.return_value = \
            ['component_1']
        test_monitor.update_data()
        self.assertTrue(test_monitor.data)

    @patch('psutil.boot_time')
    def test_populate_nb_report(self, mock_boot):
        test_nb_report: dict = {}
        test_monitor: NuvlaEdgeInfoMonitor = self.get_base_monitor()
        test_monitor.ne_id = 'id'
        test_monitor.ne_engine_version = 'ne_version'
        test_monitor.installation_home = 'home_path'
        test_monitor.coe_client.get_host_os.return_value = 'host_os'
        test_monitor.coe_client.get_host_architecture.return_value = 'arch'
        test_monitor.coe_client.get_hostname.return_value = 'hostname'
        test_monitor.coe_client.get_container_plugins.return_value = ['no']
        mock_boot.return_value = time.time()
        test_monitor.data.installation_parameters = None
        test_monitor.coe_client.get_installation_parameters.return_value = \
            self.get_installation_parameters_result
        test_monitor.coe_client.get_all_nuvlaedge_components.return_value = \
            ['component_1']
        test_monitor.update_data()
        test_monitor.populate_nb_report(test_nb_report)
        self.assertTrue(test_nb_report)
        self.assertEqual(test_nb_report.get('installation-parameters', {}),
                         self.get_installation_parameters_result)
