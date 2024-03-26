from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.manager import WorkerManager


class TestManager(TestCase):
    default_period = 60

    def setUp(self):
        self.test_manager = WorkerManager()

    def test_add_worker(self):
        self.test_manager.registered_workers['mock_type_name'] = Mock()

        with patch('nuvlaedge.agent.manager.logging.Logger.warning') as mock_warning:
            mock_name = Mock()
            mock_name.__class__.__name__ = 'mock_type_name'
            mock_name.__name__ = 'mock_type_name'
            self.assertFalse(self.test_manager.add_worker(
                period=self.default_period,
                worker_type=mock_name,
                init_params=((), {}),
                actions=['mock_action']))

            mock_warning.assert_called_once_with(f"Worker {mock_name.__name__} already registered")

        self.test_manager.registered_workers = {}
        with patch('nuvlaedge.agent.manager.Worker') as mock_worker:
            with patch('nuvlaedge.agent.manager.logging.Logger.debug') as mock_debug:
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
                mock_debug.assert_called_once_with("Registering worker: mock_type_name_2 in manager")

    @patch('nuvlaedge.agent.manager.Worker')
    def test_summary(self, mock_worker):
        mock_worker = Mock()
        mock_worker.status_report.return_value = {'mock_key': 'mock_value'}
        mock_worker.exceptions = []
        self.test_manager.registered_workers['mock_type_name'] = mock_worker
        mock_worker.worker_summary.return_value = 'mock_summary'
        sample = (f'Worker Summary:\n{"Name":<20} {"Period":>10} {"Rem. Time":>10} {"Err. Count":>10}'
                  f' {"Errors":>25}\n')
        self.assertEqual(sample + 'mock_summary',self.test_manager.summary())

    # Tests for heal_workers
    @patch('nuvlaedge.agent.manager.logging.Logger.info')
    def test_heal_workers(self, mock_info):
        mock_worker = Mock()
        mock_worker.is_running = False
        mock_worker.worker_name = 'mock_type_name'
        self.test_manager.registered_workers['mock_type_name'] = mock_worker
        self.test_manager.heal_workers()
        mock_worker.reset_worker.assert_called_once()
        mock_info.assert_called_once_with("Worker mock_type_name is not running, restarting...")

        mock_worker.is_running = True
        self.test_manager.heal_workers()
        mock_worker.reset_worker.assert_called_once()
        mock_info.assert_called_once_with("Worker mock_type_name is not running, restarting...")

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

    # Tests edit_period
    @patch('nuvlaedge.agent.manager.logging.Logger.warning')
    @patch('nuvlaedge.agent.manager.logging.Logger.error')
    def test_edit_period(self, mock_error, mock_warning):
        worker_1 = Mock()
        self.test_manager.registered_workers[type(worker_1).__name__] = worker_1
        self.test_manager.edit_period(type(worker_1), 20)
        worker_1.edit_period.assert_called_once_with(20)

        self.test_manager.edit_period('mock_type_name_2', 10)
        mock_error.assert_called_once_with('Worker mock_type_name_2 is not registered on manager, '
                                           'cannot update its period')

        self.test_manager.edit_period(type(worker_1).__name__, 10)
        mock_warning.assert_called_once_with(f"Workers should not have less than 15 seconds of periodic execution, "
                                             f"cannot update with {10}")
