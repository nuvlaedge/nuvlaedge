from queue import Empty
from unittest import TestCase

from mock.mock import Mock, patch

from nuvlaedge.agent.nuvla.resources.telemetry_payload import TelemetryPayloadAttributes
from nuvlaedge.agent.workers.monitor import Monitor


# Define a concrete subclass of Monitor for testing purposes
class MockMonitor(Monitor):
    def update_data(self):
        pass

    def populate_telemetry_payload(self):
        pass


class TestMonitor(TestCase):
    def setUp(self):
        self.monitor_name = 'mock_monitor'
        self.data_type = Mock
        self.period = 60
        self.mock_logger = Mock()
        self.monitor = MockMonitor(self.monitor_name, self.data_type, True, self.period)
        self.monitor.logger = self.mock_logger

    def test_constructor(self):
        monitor = MockMonitor(self.monitor_name, self.data_type, True, 60)
        self.assertEqual(self.monitor_name, monitor.name)
        self.assertTrue(monitor.enabled_monitor)
        self.assertEqual(60, monitor._period)
        self.assertIsNotNone(monitor.report_channel)
        self.assertIsNotNone(monitor.telemetry_data)
        self.assertIsNotNone(monitor.logger)
        self.assertIsNone(monitor.last_process_duration)
        self.assertIsNotNone(monitor._last_update)
        self.assertIsNotNone(monitor._exit_event)

    def test_set_period(self):
        monitor = MockMonitor(self.monitor_name, self.data_type, True, 60)
        monitor.set_period(30)
        self.assertEqual(30, monitor._period)

    def test_send_telemetry_data(self):
        expected_payload = TelemetryPayloadAttributes(node_id='mock_node_id')
        self.monitor.telemetry_data = expected_payload
        self.monitor.send_telemetry_data()

        self.assertEqual(TelemetryPayloadAttributes(), self.monitor.telemetry_data)
        self.assertTrue(self.monitor.report_channel.full())


        self.monitor.send_telemetry_data()
        self.mock_logger.warning.assert_called_once()

        self.monitor.report_channel = Mock()
        self.monitor.report_channel.full.return_value = True
        self.monitor.report_channel.get_nowait.side_effect = Empty
        self.monitor.send_telemetry_data()
        self.mock_logger.debug.assert_called_with("Channel was empty, no need to discard data")

    @patch('nuvlaedge.agent.workers.monitor.time')
    @patch('tests.agent.workers.monitor.test_monitor.MockMonitor.update_data')
    @patch('tests.agent.workers.monitor.test_monitor.MockMonitor.populate_telemetry_payload')
    @patch('tests.agent.workers.monitor.test_monitor.MockMonitor.send_telemetry_data')
    def test_run_update_data(self, mock_send_data, mock_populate, mock_update, mock_time):
        monitor_name = "mock_monitor"

        mock_time.time_ns.side_effect = [1.0*1e9, 2.0*1e9]
        mock_time.time.return_value = 3.0

        self.monitor.run_update_data()
        self.assertEqual(3.0, self.monitor._last_update)
        self.assertEqual(1.0, self.monitor.last_process_duration)
        mock_send_data.assert_called_once()
        mock_populate.assert_called_once()
        mock_update.assert_called_once()
        self.mock_logger.exception.assert_not_called()

        expected_ex = Exception('mock_exception')
        mock_time.reset_mock()
        mock_time.time_ns.side_effect = [1.0 * 1e9, 2.0 * 1e9]
        mock_time.time.return_value = 3.0
        mock_send_data.side_effect = expected_ex
        self.monitor.run_update_data()
        self.mock_logger.exception.assert_called_with(f'Something went wrong updating monitor {self.monitor_name}: {expected_ex}')

        mock_time.reset_mock()
        mock_time.time_ns.side_effect = [1.0 * 1e9, 2.0 * 1e9]
        mock_time.time.return_value = 3.0
        mock_send_data.side_effect = expected_ex
        self.monitor.run_update_data("new_name")
        self.mock_logger.exception.assert_called_with(
            f'Something went wrong updating monitor {'new_name'}: {expected_ex}')

    @patch('tests.agent.workers.monitor.test_monitor.MockMonitor._compute_wait_time')
    @patch('tests.agent.workers.monitor.test_monitor.MockMonitor.run_update_data')
    def test_run(self, mock_run_update, mock_compute_wait_time):
        mock_compute_wait_time.side_effect = [1.0, 2.0]
        mock_event = Mock()
        self.monitor._exit_event = mock_event
        self.monitor._exit_event.wait.side_effect = [False, True]

        self.monitor.run()
        mock_run_update.assert_called_once()
        self.assertEqual(2, mock_event.wait.call_count)
        self.assertEqual(2, mock_compute_wait_time.call_count)

        mock_compute_wait_time.side_effect = [1.0, -2.0]
        self.monitor._exit_event.wait.side_effect = [False, True]
        self.monitor.run()
        self.mock_logger.warning.assert_called_once()

