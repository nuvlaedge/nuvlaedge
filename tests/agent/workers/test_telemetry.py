from queue import Queue, Full
from threading import Thread
from unittest import TestCase
from unittest.mock import Mock, patch

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
                                            True)

    @patch('nuvlaedge.agent.workers.telemetry.Telemetry._initialize_monitors')
    def test_init_excluded_monitors(self, mock_init_monitors):
        excluded_monitors = 'gpio_monitor,power_monitor'
        telemetry = Telemetry(
            self.mock_coe_client,
            self.mock_status_channel,
            self.uuid,
            excluded_monitors,
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

    # @patch('nuvlaedge.agent.workers.telemetry.TelemetryPayloadAttributes.model_validate')
    # def test_collect_monitor_metrics(self, mock_update):
    #     mock_monitor = Mock()
    #     mock_monitor.name = 'mock_monitor'
    #
    #     # Test not updated
    #     with patch('nuvlaedge.agent.workers.telemetry.logging.Logger.info') as mock_info:
    #         self.test_telemetry.monitor_list = {'mock_monitor': mock_monitor}
    #         mock_monitor.updated = False
    #         self.test_telemetry._collect_monitor_metrics()
    #         mock_monitor.populate_nb_report.assert_not_called()
    #         mock_info.assert_called_once_with(f'Data not updated yet in monitor {mock_monitor.name}')
    #
    #     # Normal execution
    #     mock_update.reset_mock()
    #     mock_monitor.reset_mock()
    #     mock_monitor.updated = True
    #     mock_monitor.populate_nb_report.return_value = None
    #
    #     self.test_telemetry.monitor_list = {'mock_monitor': mock_monitor}
    #
    #     self.test_telemetry._collect_monitor_metrics()
    #     mock_monitor.populate_nb_report.assert_called_once_with({})
    #     mock_update.assert_called_once_with({})
    #
    #     # Test exception
    #     mock_update.reset_mock()
    #     mock_monitor.reset_mock()
    #     mock_monitor.updated = True
    #     mock_monitor.populate_nb_report.side_effect = Exception('mock_exception')
    #     with patch('nuvlaedge.agent.workers.telemetry.logging.Logger.exception') as mock_exception:
    #         self.test_telemetry._collect_monitor_metrics()
    #         mock_monitor.populate_nb_report.assert_called_once_with({})
    #         mock_update.assert_called_once_with({})
    #         mock_exception.assert_called_once()

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
