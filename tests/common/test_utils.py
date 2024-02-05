import threading

from unittest import TestCase
import mock

from nuvlaedge.common.utils import timed_event, dump_dict_to_str


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


def test_dump_dict_to_str():
    d = {'a': 1, 'b': 2}
    assert dump_dict_to_str(d) == '{\n    "a": 1,\n    "b": 2\n}'
    assert dump_dict_to_str({}) == ''
    assert dump_dict_to_str('a') == ''
    assert dump_dict_to_str(1) == ''
