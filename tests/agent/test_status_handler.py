from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

import mock

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

        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.remove_module("Not in dict")
        self.assertEqual(self.test_status_handler.module_reports, {self.test_module.origin_module: self.test_module})

    def test_process_status(self):
        # Test with all modules in RUNNING
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.add_module(self.test_module_2)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler._status, 'OPERATIONAL')

        # Test with one module in STOPPED
        self.test_module.module_status = 'STOPPED'
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler._status, 'OPERATIONAL')

        # Test with one module in FAILING
        self.test_module.module_status = 'FAILING'
        self.test_status_handler.add_module(self.test_module)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler._status, 'DEGRADED')

    def test_process_status_outdated(self):
        self.test_status_handler.add_module(self.test_module)
        self.test_module.date = datetime.now().replace(year=2020)
        self.test_status_handler.process_status()
        self.assertEqual(self.test_status_handler.module_reports, {})

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

    @patch('nuvlaedge.agent.common.status_handler.read_file')
    @patch('os.getenv')
    def test_get_system_manager_status(self, mock_getenv, mock_read_file):
        sm_module_name = "System Manager"
        self.test_status_handler.module_reports[sm_module_name] = mock.Mock()
        mock_getenv.return_value = ""
        self.test_status_handler._get_system_manager_status()
        self.assertNotIn(sm_module_name, self.test_status_handler.module_reports)
        self.assertTrue(self.test_status_handler.status_channel.empty())

        self.test_status_handler.module_reports[sm_module_name] = mock.Mock()
        mock_getenv.return_value = "string"
        self.test_status_handler._get_system_manager_status()
        self.assertNotIn(sm_module_name, self.test_status_handler.module_reports)
        self.assertTrue(self.test_status_handler.status_channel.empty())

        self.test_status_handler.module_reports[sm_module_name] = mock.Mock()
        mock_getenv.return_value = 0
        self.test_status_handler._get_system_manager_status()
        self.assertNotIn(sm_module_name, self.test_status_handler.module_reports)
        self.assertTrue(self.test_status_handler.status_channel.empty())

        mock_getenv.return_value = 1
        mock_read_file.side_effect = ['OPERATIONAL', 'Test note']
        self.test_status_handler._get_system_manager_status()
        self.assertFalse(self.test_status_handler.status_channel.empty())
        status = self.test_status_handler.status_channel.get(block=False)
        self.assertEqual(status.origin_module, sm_module_name)
        self.assertEqual(status.module_status, 'RUNNING')

        mock_read_file.side_effect = ['DEGRADED', 'Test note']
        self.test_status_handler._get_system_manager_status()
        self.assertFalse(self.test_status_handler.status_channel.empty())
        status = self.test_status_handler.status_channel.get(block=False)
        self.assertEqual(status.origin_module, sm_module_name)
        self.assertEqual(status.module_status, 'FAILING')

        mock_read_file.side_effect = ['Mock', 'Test note']
        self.test_status_handler._get_system_manager_status()
        self.assertFalse(self.test_status_handler.status_channel.empty())
        status = self.test_status_handler.status_channel.get(block=False)
        self.assertEqual(status.origin_module, sm_module_name)
        self.assertEqual(status.module_status, 'UNKNOWN')

    def test_coe_status(self):

        coe_client = Mock()
        coe_client.read_system_issues.return_value = (['Error 1', 'Error 2'], None)
        self.test_status_handler._get_coe_status(coe_client)

        self.assertFalse(self.test_status_handler.status_channel.empty())
        status_report = self.test_status_handler.status_channel.get_nowait()
        self.assertEqual(status_report.origin_module, 'COE')
        self.assertEqual(status_report.module_status, 'FAILING')
        self.assertEqual(status_report.message, 'Error 1\nError 2')

        coe_client.read_system_issues.return_value = (None, None)
        self.test_status_handler._get_coe_status(coe_client)
        self.assertTrue(self.test_status_handler.status_channel.empty())

    def test_send_status(self):
        mock_queue = Mock()
        date_now = datetime.now()
        self.test_status_handler.send_status(
            mock_queue,
            'test_module',
            'RUNNING',
            'Test message',
            date=date_now
        )
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='RUNNING',
            message='Test message',
            date=date_now
        ))

    def test_status_methods(self):
        mock_queue = Mock()
        date_now = datetime.now()

        self.test_status_handler.starting(mock_queue, 'test_module', 'Starting...', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='STARTING',
            message='Starting...',
            date=date_now
        ))

        mock_queue.put.reset_mock()
        self.test_status_handler.running(mock_queue, 'test_module', 'Running...', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='RUNNING',
            message='Running...',
            date=date_now
        ))

        mock_queue.put.reset_mock()
        self.test_status_handler.stopped(mock_queue, 'test_module', 'Stopped.', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='STOPPED',
            message='Stopped.',
            date=date_now
        ))

        mock_queue.put.reset_mock()
        self.test_status_handler.failing(mock_queue, 'test_module', 'Failing...', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='FAILING',
            message='Failing...',
            date=date_now
        ))

        mock_queue.put.reset_mock()
        self.test_status_handler.failed(mock_queue, 'test_module', 'Failed!', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='FAILED',
            message='Failed!',
            date=date_now
        ))

        mock_queue.put.reset_mock()
        self.test_status_handler.warning(mock_queue, 'test_module', 'Warning!', date_now)
        mock_queue.put.assert_called_once_with(StatusReport(
            origin_module='test_module',
            module_status='WARNING',
            message='Warning!',
            date=date_now
        ))
