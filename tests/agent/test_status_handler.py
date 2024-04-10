from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport


class TestStatusHandler(TestCase):

    def setUp(self):
        self.test_module = StatusReport(
            origin_module='test_module',
            module_status='RUNNING',
            date=datetime.now(),
            message='Test message'
        )
        self.test_module_2 = StatusReport(
            origin_module='test_module',
            module_status='RUNNING',
            date=datetime.now(),
            message='Test message'
        )

        self.test_status_handler = NuvlaEdgeStatusHandler()

    def test_add_module(self):
        self.test_status_handler.add_module(self.test_module)
        self.assertEqual(self.test_status_handler.module_reports[self.test_module.origin_module], self.test_module)

    def test_remove_module(self):
        # Test with module name
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.remove_module(self.test_module.origin_module)
        self.assertEqual(self.test_status_handler.module_reports, {})

        # Test with StatusReport
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.remove_module(self.test_module)
        self.assertEqual(self.test_status_handler.module_reports, {})

    def test_process_status(self):
        # Test with all modules in RUNNING
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.add_module(self.test_module_2)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler._status, 'OPERATIONAL')

        # Test with one module in STOPPED
        self.test_module.module_status = 'FAILING'
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler._status, 'DEGRADED')

    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.add_module')
    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.process_status')
    def test_update_status(self, mock_process, mock_add):
        mock_queue = Mock()
        self.test_status_handler.status_channel = mock_queue

        mock_queue.empty.return_value = True
        self.test_status_handler.update_status()
        mock_queue.get.assert_not_called()
        mock_process.assert_called_once()

        mock_process.reset_mock()
        mock_queue.empty.side_effect = [False, True]
        mock_queue.get.return_value = 'test_report'
        self.test_status_handler.update_status()
        mock_queue.get.assert_called_once()
        mock_add.assert_called_once_with('test_report')
        mock_process.assert_called_once()

    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.update_status')
    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler._get_system_manager_status')
    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler._get_coe_status')
    def test_get_status(self, mock_coe, mock_sm_status, mock_update):
        self.test_status_handler._status = 'OPERATIONAL'
        self.test_status_handler._notes = ['Test note']
        self.assertEqual(self.test_status_handler.get_status(Mock()), ('OPERATIONAL', ['Test note']))
        mock_update.assert_called_once()

