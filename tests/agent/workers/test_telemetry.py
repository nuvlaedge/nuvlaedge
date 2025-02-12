import json
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from threading import Thread
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.nuvla.resources.telemetry_payload import TelemetryPayloadAttributes
from nuvlaedge.agent.workers.monitor.data.nuvlaedge_data import NuvlaEdgeData
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.workers.telemetry import Telemetry
from nuvlaedge.agent.workers.telemetry import logger as telemetry_logger
from nuvlaedge.agent.orchestrator import COEClient


class TestTelemetry(TestCase):
    def setUp(self):
        self.mock_coe_client = Mock(spec=COEClient)
        self.mock_status_channel = Mock(spec=Queue)
        self.uuid = NuvlaID('nuvlabox/uuid')
        self.excluded_monitors = []
        self.endpoint = 'https://nuvla.io'
        with patch('nuvlaedge.agent.workers.telemetry.Telemetry._initialize_monitors') as mock_init_monitors:
            self.test_telemetry = Telemetry(self.mock_coe_client,
                                            self.mock_status_channel,
                                            self.uuid,
                                            self.excluded_monitors,
                                            True,
                                            True,
                                            True)

    def test_set_period(self):
        monitor_1 = Mock()
        monitor_2 = Mock()
        self.test_telemetry.monitor_list = {'monitor_1': monitor_1, 'monitor_2': monitor_2}
        mock_period = 19
        self.test_telemetry.set_period(mock_period)
        monitor_1.set_period.assert_called_once_with(mock_period)
        monitor_2.set_period.assert_called_once_with(mock_period)
        self.assertEqual(mock_period, self.test_telemetry.period)

    @patch('nuvlaedge.agent.workers.telemetry.Telemetry._initialize_monitors')
    def test_init_excluded_monitors(self, mock_init_monitors):
        excluded_monitors = 'gpio_monitor,power_monitor'
        telemetry = Telemetry(
            self.mock_coe_client,
            self.mock_status_channel,
            self.uuid,
            excluded_monitors,
            True,
            True,
            True)
        self.assertEqual(['gpio_monitor', 'power_monitor'], telemetry.excluded_monitors)


    @patch('nuvlaedge.agent.workers.telemetry.get_monitor')
    def test_initialize_monitors(self, mock_get_monitor):
        mock_get_monitor.return_value.return_value = Mock()
        self.test_telemetry._initialize_monitors(60)
        monitor_count = len(self.test_telemetry.monitor_list)

        self.test_telemetry.monitor_list = {}
        self.test_telemetry.excluded_monitors = ['power', 'container_stats']
        self.test_telemetry._initialize_monitors(60)
        self.assertEqual(monitor_count - 2, len(self.test_telemetry.monitor_list))

    @patch('nuvlaedge.agent.workers.telemetry.logger')
    @patch('nuvlaedge.agent.workers.telemetry.TelemetryPayloadAttributes.model_validate')
    def test_collect_monitor_metrics(self, mock_update, mock_logger):
        monitor_1 = Mock()
        monitor_1.name = 'monitor_1'
        monitor_2 = Mock()
        monitor_2.name = 'monitor_2'
        monitor_1.enabled_monitor = False
        monitor_1.report_channel = Mock()
        monitor_1.report_channel.get_nowait.return_value = {'node-id': 'mock_node_id'}
        monitor_2.enabled_monitor = False
        monitor_2.report_channel = Mock()
        monitor_2.report_channel.get_nowait.return_value = {'cluster-id': 'mock_cluster_id'}
        self.test_telemetry.monitor_list = {'monitor_1': monitor_1, 'monitor_2': monitor_2}

        self.assertEqual('', self.test_telemetry._collect_monitor_metrics())
        self.assertEqual(2, mock_logger.info.call_count)

        monitor_1.enabled_monitor = True
        monitor_2.enabled_monitor = True

        self.assertEqual('', self.test_telemetry._collect_monitor_metrics())
        self.assertEqual("mock_node_id", self.test_telemetry._local_telemetry.node_id)
        self.assertEqual("mock_cluster_id", self.test_telemetry._local_telemetry.cluster_id)

        monitor_2.report_channel.get_nowait.side_effect = Empty
        expected_report = f"\tMonitor {monitor_2.name} not sending metrics\n"
        self.assertEqual(expected_report, self.test_telemetry._collect_monitor_metrics())
        mock_logger.warning.assert_called_once()

    @patch('nuvlaedge.agent.workers.telemetry.is_thread_creation_needed')
    @patch('nuvlaedge.agent.workers.telemetry.get_monitor')
    @patch('nuvlaedge.agent.workers.telemetry.logger')
    def test_check_monitors_health(self, mock_logger, mock_get_monitor, mock_is_thread_creation_needed):
        mock_logger.level = 40
        mock_monitor = Mock()
        mock_monitor.name = 'mock_monitor'
        mock_monitor.last_process_duration = 0.92

        # Test no creation needed
        self.test_telemetry.monitor_list = {'mock_monitor': mock_monitor}
        mock_is_thread_creation_needed.return_value = False
        self.test_telemetry._check_monitors_health()
        mock_get_monitor.assert_not_called()

        # Test threaded and creation needed
        mock_is_thread_creation_needed.return_value = True
        mock_get_monitor.return_value.return_value = mock_monitor
        self.test_telemetry._check_monitors_health()
        mock_get_monitor.assert_called_once_with('mock_monitor')

        mock_logger.reset_mock()
        mock_logger.level = 10
        self.test_telemetry._check_monitors_health()
        self.assertEqual(2, mock_logger.debug.call_count)

    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.workers.telemetry.Telemetry._check_monitors_health')
    def test_run(self, mock_health, mock_status_handler):
        self.test_telemetry.run()
        mock_health.assert_called_once()
        mock_status_handler.assert_called_once()

    def test_local_telemetry_json(self):
        self.test_telemetry._local_telemetry = TelemetryPayloadAttributes(node_id='mock_node_id')

        self.assertEqual(TelemetryPayloadAttributes(node_id='mock_node_id').model_dump_json(exclude_none=True, by_alias=True), self.test_telemetry._local_telemetry_json)

    @patch('nuvlaedge.agent.workers.telemetry.time')
    @patch('nuvlaedge.agent.workers.telemetry.logger')
    def test_run_once(self, mock_logger, mock_time):
        monitor_1 = Mock()
        monitor_1.last_process_duration = 1.3
        monitor_1.enabled_monitor = True
        self.test_telemetry.monitor_list = {'monitor_1': monitor_1}
        mock_time.side_effect = [1.0, 2.0]

        self.test_telemetry.run_once()
        self.assertEqual(3, mock_logger.info.call_count)
        monitor_1.run_update_data.assert_called_once()
        monitor_1.start.assert_called_once()

        monitor_1.start.reset_mock()
        monitor_1.enabled_monitor = False
        self.test_telemetry.run_once()
        monitor_1.start.assert_not_called()

    @patch('nuvlaedge.agent.workers.telemetry.datetime')
    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.workers.telemetry.Telemetry._collect_monitor_metrics')
    def test_get_telemetry(self, mock_collect, mock_status_running, mock_datetime):
        mock_collect.return_value = "mock_report"
        self.test_telemetry._local_telemetry = TelemetryPayloadAttributes(node_id='mock_node_id')
        # Mock the datetime object
        mock_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        # mock_datetime.now.return_value.isoformat.return_value = mock_now.isoformat()

        ret_telemetry = self.test_telemetry.get_telemetry()
        self.assertEqual('mock_node_id', ret_telemetry.node_id)
        expected_time = '2023-01-01T12:00:00+00:00Z'
        self.assertEqual(expected_time, ret_telemetry.current_time)
        mock_status_running.assert_called_once()