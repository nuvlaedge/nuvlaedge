# -*- coding: utf-8 -*-
import unittest
from mock import Mock, patch
import time

from nuvlaedge.agent.workers.monitor.components.nuvlaedge_info import NuvlaEdgeInfoMonitor

from nuvlaedge.agent.workers.monitor.data.nuvlaedge_data import NuvlaEdgeData


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
        telemetry_mock = Mock()
        telemetry_mock.coe_client = Mock()
        telemetry_mock.coe_client.current_image = '2.0.0'

        return NuvlaEdgeInfoMonitor('test_monitor', telemetry_mock, True)

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

    def test_populate_telemetry_payload(self):
        test_monitor: NuvlaEdgeInfoMonitor = self.get_base_monitor()

        mock_data = NuvlaEdgeData()
        mock_data.nuvlabox_engine_version = '1.2.3'
        mock_data.installation_home = '/opt/nuvlaedge'
        mock_data.operating_system = 'Linux'

        test_monitor.data = mock_data

        test_monitor.populate_telemetry_payload()
        self.assertEqual(test_monitor.telemetry_data.nuvlabox_engine_version, '1.2.3')
        self.assertEqual(test_monitor.telemetry_data.host_user_home, '/opt/nuvlaedge')
        self.assertEqual(test_monitor.telemetry_data.operating_system, 'Linux')
