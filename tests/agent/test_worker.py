import threading
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.worker import Worker, WorkerExitException


class TestWorker(TestCase):
    def setUp(self):
        self.mock_type = Mock(name='mock_type')
        self.mock_type.__class__.__name__ = 'mock_type_class'
        self.mock_type.__name__ = 'mock_type_name'
        self.test_worker = Worker(
            worker_type=self.mock_type,
            period=60,
            init_params=((), {}),
            actions=['mock_action'])
        self.mock_thread = Mock()
        self.test_worker.run_thread = self.mock_thread

    def test_init(self):
        self.setUp()

        self.assertEqual(self.test_worker.worker_name, 'mock_type_name')
        self.assertIsInstance(self.test_worker.exit_event, threading.Event)
        self.assertEqual(self.test_worker._period, 60)
        self.assertEqual(self.test_worker.class_init_parameters, ((), {}))
        self.assertEqual(self.test_worker.actions, ['mock_action'])
        self.assertEqual(self.test_worker.callable_actions, [self.mock_type().mock_action])
        self.assertEqual(self.test_worker.worker_type, self.mock_type)
        self.assertEqual(self.test_worker.run_thread, self.mock_thread)
        self.assertEqual(self.test_worker.error_count, 0)
        self.assertEqual(self.test_worker.exceptions, [])

    def test_init_actions(self):
        def mock_callable():
            return "mock_callable"
        self.test_worker.callable_actions = []
        self.mock_type.return_value.mock_action = mock_callable
        self.test_worker._init_actions()
        self.assertEqual(self.test_worker.callable_actions, [mock_callable])

        self.test_worker.callable_actions = []
        self.mock_type.return_value.mock_action = "notacallable"
        with patch('nuvlaedge.agent.worker.logging.Logger.warning') as mock_warning:
            self.test_worker._init_actions()
            mock_warning.assert_called_once()
            self.assertEqual(self.test_worker.callable_actions, [])

    @patch('nuvlaedge.agent.worker.threading.Thread')
    def test_init_thread(self, mock_thread):
        mock_start = Mock()
        mock_thread.return_value = mock_start
        self.test_worker._init_thread()
        mock_thread.assert_called_once_with(target=self.test_worker.run, daemon=True)
        mock_start.start.assert_called_once()

    def test_process_exception(self):
        mock_ex = Mock(spec=Exception)
        self.test_worker._process_exception(mock_ex)
        self.assertEqual(self.test_worker.error_count, 1)
        self.assertEqual(self.test_worker.exceptions, [mock_ex])

        self.test_worker.error_count = 10
        self.test_worker.exceptions = []
        with self.assertRaises(ExceptionGroup):
            self.test_worker._process_exception(Exception())

        self.test_worker.error_count = 0
        self.test_worker.exceptions = []
        with self.assertRaises(ExceptionGroup):
            self.test_worker._process_exception(WorkerExitException(), is_exit=True)

    @patch.object(threading.Event, 'set')
    def test_stop(self, mock_set):
        self.test_worker.stop()  # call the function
        mock_set.assert_called_once()  # assertion
        self.mock_thread.join.assert_called_once()

    @patch('nuvlaedge.agent.worker.logging.Logger.debug')
    @patch('nuvlaedge.agent.worker.Worker._init_thread')
    def test_start(self, mock_init_th, mock_debug):
        self.test_worker.start()
        mock_init_th.assert_called_once()
        mock_debug.assert_called_once_with("mock_type_name worker started")

    def test_reset_worker(self):
        self.mock_type.reset_mock()
        self.test_worker.reset_worker()
        self.mock_type.assert_called_once()
        self.mock_type.reset_mock()

        test_params = ((), {'mock_key': 'mock_value'})
        self.test_worker.reset_worker(test_params)
        self.assertEqual(self.test_worker.class_init_parameters, test_params)
        self.mock_type.assert_called_once_with(*test_params[0], **test_params[1])

    @patch('nuvlaedge.agent.worker.Worker._init_thread')
    @patch('nuvlaedge.agent.worker.Worker._process_exception')
    def test_run(self, mock_process, mock_init_th):
        mock_callable = Mock()
        mock_callable.__name__ = 'mock_callable'
        mock_exit = Mock()
        self.test_worker.exit_event = mock_exit
        self.test_worker.callable_actions = [mock_callable]

        # Test Normal Execution
        mock_exit.wait.side_effect = [False, True]
        mock_callable.return_value = None
        with patch('nuvlaedge.agent.worker.logging.Logger.debug') as mock_debug:
            self.test_worker.run()
            mock_callable.assert_called_once()
            self.assertEqual(mock_debug.call_count, 4)
            mock_process.assert_not_called()

        # Test normal exception
        mock_callable.reset_mock()
        mock_process.reset_mock()
        mock_exit.wait.side_effect = [False, True]
        ex = Exception('mock_exception')
        mock_callable.side_effect = ex

        self.test_worker.run()
        mock_callable.assert_called_once()
        mock_process.assert_called_once_with(ex)
        mock_init_th.assert_called_once()

        # Test WorkerExitException
        mock_callable.reset_mock()
        mock_process.reset_mock()
        mock_exit.wait.side_effect = [False, True]
        ex = WorkerExitException('mock_exception')
        mock_callable.side_effect = ex

        with patch('nuvlaedge.agent.worker.logging.Logger.debug') as mock_debug:
            self.test_worker.run()
            mock_callable.assert_called_once()
            mock_process.assert_called_once_with(ex, is_exit=True)
            self.assertEqual(mock_debug.call_count, 3)






