from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.manager import WorkerManager


class TestManager(TestCase):
    default_period = 60

    def setUp(self):
        self.test_manager = WorkerManager()

    def test_add_worker(self):
        self.test_manager.registered_workers['mock_type_name'] = Mock()

        with patch('nuvlaedge.agent.manager.logging.Logger.info') as mock_info:
            mock_name = Mock()
            mock_name.__class__.__name__ = 'mock_type_name'
            mock_name.__name__ = 'mock_type_name'
            self.assertFalse(self.test_manager.add_worker(
                period=self.default_period,
                worker_type=mock_name,
                init_params=((), {}),
                actions=['mock_action']))

            mock_info.assert_called_once_with(f"Worker {mock_name.__name__} already registered")

        self.test_manager.registered_workers = {}
        with patch('nuvlaedge.agent.manager.Worker') as mock_worker:
            with patch('nuvlaedge.agent.manager.logging.Logger.info') as mock_info:
                mock_name.__class__.__name__ = 'mock_type_name_2'
                mock_name.__name__ = 'mock_type_name_2'
                self.assertTrue(self.test_manager.add_worker(
                    period=self.default_period,
                    worker_type=mock_name,
                    init_params=((), {}),
                    actions=['mock_action']))
                self.assertEqual(1, len(self.test_manager.registered_workers))
                self.assertIn('mock_type_name_2', self.test_manager.registered_workers)
                mock_worker.assert_called_once()
                mock_info.assert_called_once_with("Registering worker: mock_type_name_2 in manager")

    def test_status_report(self):
        mock_worker = Mock()
        mock_worker.status_report.return_value = {'mock_key': 'mock_value'}
        mock_worker.exceptions = []
        self.test_manager.registered_workers['mock_type_name'] = mock_worker

        with patch('nuvlaedge.agent.manager.logging.Logger.info') as mock_info:
            self.test_manager.status_report()
            mock_info.assert_called_once()

    def test_start(self):
        worker_1 = Mock()
        self.test_manager.registered_workers['mock_type_name'] = worker_1
        self.test_manager.registered_workers['mock_type_name_2'] = worker_1
        self.test_manager.start()
        self.assertEqual(2, worker_1.start.call_count)

    def test_stop(self):
        worker_1 = Mock()
        self.test_manager.registered_workers['mock_type_name'] = worker_1
        self.test_manager.registered_workers['mock_type_name_2'] = worker_1
        self.test_manager.stop()
        self.assertEqual(2, worker_1.stop.call_count)
