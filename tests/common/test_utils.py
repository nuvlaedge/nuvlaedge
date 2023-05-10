import threading

from unittest import TestCase
import mock

from nuvlaedge.common.utils import timed_event


class TestUtils(TestCase):
    def setUp(self) -> None:
        self.timeout = 2

    def test_timed_event(self):
        with mock.patch.object(threading.Timer, 'start') as mock_start, \
                mock.patch.object(threading.Timer, 'cancel') as mock_cancel:
            with timed_event(self.timeout):
                mock_start.assert_called_once()
                mock_cancel.assert_not_called()

            mock_cancel.assert_called_once()
