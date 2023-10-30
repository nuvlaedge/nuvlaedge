import sys
import threading
import traceback
import faulthandler
from unittest import TestCase
from mock import Mock, patch

import nuvlaedge
from nuvlaedge.common.thread_tracer import log_threads_stacks_traces, signal_usr1


class TestThreadTracer(TestCase):
    @patch.object(threading, 'enumerate')
    @patch.object(faulthandler, 'dump_traceback')
    @patch.object(traceback, 'print_stack')
    @patch.object(sys, '_current_frames')
    def test_log_threads(self,
                         mock_current_frames,
                         mock_traceback,
                         mock_fault_handler,
                         mock_threading):

        mock_threading.return_value = []
        mock_traceback.return_value = 'TRACE'
        log_threads_stacks_traces()
        mock_fault_handler.assert_called_once()
        mock_traceback.assert_not_called()

        mock_th = Mock()
        mock_th.ident = 0
        mock_threading.return_value = [mock_th]
        log_threads_stacks_traces()
        mock_traceback.assert_called_once()

    @patch.object(nuvlaedge.common.thread_tracer, 'log_threads_stacks_traces')
    def test_signal_usr1(self, mock_log):
        signal_usr1(1, 1)
        mock_log.assert_called_once()

