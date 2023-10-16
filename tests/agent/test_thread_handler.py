import logging
import threading
import time
from unittest import TestCase
from mock import patch, Mock


from nuvlaedge.agent.common.thread_handler import (log,
                                                   is_thread_creation_needed,
                                                   create_start_thread)


class TestThreadHandler(TestCase):

    def setUp(self) -> None:
        self.alive_flag = True

    @patch.object(logging.Logger, 'log')
    def test_log(self, mock_logger):
        log(logging.INFO, 'Mock message No: {}', 1)
        mock_logger.assert_called_with(logging.INFO, 'Mock message No: 1')

    def dummy_thread(self):
        while self.alive_flag:
            time.sleep(0.1)

    def test_is_thread_creation_needed(self):
        name = 'Test_thread'
        thread = threading.Thread(target=self.dummy_thread, daemon=True)

        with patch.object(logging.Logger, 'log') as mock_log:
            self.assertTrue(is_thread_creation_needed(
                name,
                thread,
                log_not_alive=(logging.INFO, 'DEAD')))
            mock_log.assert_called_with(logging.INFO, 'DEAD')

        thread.start()
        with patch.object(logging.Logger, 'log') as mock_log:
            self.assertFalse(is_thread_creation_needed(
                name,
                thread,
                log_alive=(logging.INFO, 'RUNNING')))
            mock_log.assert_called_with(logging.INFO, 'RUNNING')
        self.alive_flag = False
        thread.join(1)

        with patch.object(logging.Logger, 'log') as mock_log:
            self.assertTrue(is_thread_creation_needed(
                name,
                thread,
                log_not_alive=(logging.INFO, 'STOPPED')))
            mock_log.assert_called_with(logging.INFO, 'STOPPED')

        with patch.object(logging.Logger, 'log') as mock_log:
            self.assertTrue(is_thread_creation_needed(
                name,
                None,
                log_not_exist=(logging.INFO, 'EMPTY')))
            mock_log.assert_called_with(logging.INFO, 'EMPTY')

    def test_create_start_thread(self):
        th = create_start_thread(target=self.dummy_thread)
        self.assertTrue(th.is_alive())
        self.alive_flag = False
        th.join(1)
        self.assertFalse(th.is_alive())

