import io
import sys
import unittest
from unittest.mock import patch, MagicMock, Mock

from nuvlaedge.agent import print_threads


class TestMainFunction(unittest.TestCase):

    @patch("builtins.print")
    @patch("time.sleep", return_value=None)
    @patch("os.getenv", return_value="False")
    @patch("nuvlaedge.agent.__init__.Thread")
    @patch("nuvlaedge.agent.agent.Agent")
    @patch("nuvlaedge.agent.__init__.get_agent_settings")
    @patch("signal.signal")
    def test_main_runs_and_joins_thread(self, mock_signal, mock_get_settings,
                                        mock_agent_class, mock_thread_class,
                                        mock_getenv, mock_sleep, mock_print):

        mock_settings = MagicMock()
        mock_settings.nuvlaedge_debug = False
        mock_settings.nuvlaedge_log_level = "INFO"
        mock_settings.nuvlaedge_logging_directory = "/tmp"
        mock_settings.disable_file_logging = False
        mock_get_settings.return_value = mock_settings

        mock_agent = MagicMock()
        mock_agent.start_agent = MagicMock()
        mock_agent.run = MagicMock()
        mock_agent_class.return_value = mock_agent

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        mock_thread_class.return_value = mock_thread

        from nuvlaedge.agent.__init__ import main
        main()

        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()
        mock_agent.run.assert_called()


    @patch("builtins.print")
    @patch("time.sleep", return_value=None)
    @patch("os.getenv", return_value="True")
    @patch("nuvlaedge.agent.__init__.print_threads")
    @patch("nuvlaedge.agent.__init__.Thread")
    @patch("nuvlaedge.agent.agent.Agent")
    @patch("nuvlaedge.agent.__init__.get_agent_settings")
    @patch("signal.signal")
    def test_main_debug_threads_enabled(self, mock_signal, mock_get_settings,
                                        mock_agent_class, mock_thread_class,
                                        mock_print_threads, mock_getenv,
                                        mock_sleep, mock_print):

        mock_settings = MagicMock()
        mock_settings.nuvlaedge_debug = True
        mock_settings.nuvlaedge_log_level = "DEBUG"
        mock_settings.nuvlaedge_logging_directory = "/tmp"
        mock_settings.disable_file_logging = False
        mock_get_settings.return_value = mock_settings

        mock_agent = MagicMock()
        mock_agent.start_agent = MagicMock()
        mock_agent.run = MagicMock()
        mock_agent_class.return_value = mock_agent

        mock_thread = MagicMock()
        call_count = iter([True, False])
        mock_thread.is_alive.side_effect = lambda: next(call_count, False)
        mock_thread_class.return_value = mock_thread

        from nuvlaedge.agent.__init__ import main
        main()

        mock_print_threads.assert_called_once()
        mock_agent.run.assert_called()

    @patch("nuvlaedge.agent.__init__.print_threads")
    @patch("nuvlaedge.agent.__init__.time.sleep")
    @patch("nuvlaedge.agent.__init__.os.getenv", return_value="True")
    @patch("nuvlaedge.agent.__init__.Thread")
    @patch("nuvlaedge.agent.agent.Agent")
    @patch("nuvlaedge.agent.__init__.get_agent_settings")
    def test_main_keyboard_interrupt(self, mock_get_settings, mock_agent_cls,
                                     mock_thread_cls, mock_getenv,
                                     mock_sleep, mock_print_threads):
        # Agent settings mock
        dummy_settings = MagicMock()
        dummy_settings.nuvlaedge_debug = False
        dummy_settings.nuvlaedge_log_level = "INFO"
        dummy_settings.nuvlaedge_logging_directory = "/tmp"
        dummy_settings.disable_file_logging = False
        mock_get_settings.return_value = dummy_settings

        # Agent mock
        mock_agent = Mock()
        mock_agent_cls.return_value = mock_agent

        # Thread mock: thread is alive once
        mock_thread = Mock()
        mock_thread.is_alive.side_effect = [True, True]  # Still alive
        mock_thread_cls.return_value = mock_thread

        # Sleep raises KeyboardInterrupt AFTER print_threads is called
        def sleep_side_effect(_):
            raise KeyboardInterrupt()

        mock_sleep.side_effect = sleep_side_effect

        from nuvlaedge.agent.__init__ import main
        main()

        # Assert that it ran the thread and debug print
        mock_agent.start_agent.assert_called_once()
        mock_thread.start.assert_called_once()
        mock_print_threads.assert_called_once()
        mock_sleep.assert_called_once()

    @patch("builtins.print")
    @patch("nuvlaedge.agent.__init__.time.sleep", side_effect=Exception("Simulated exception"))
    @patch("nuvlaedge.agent.__init__.os.getenv", return_value="True")
    @patch("nuvlaedge.agent.__init__.Thread")
    @patch("nuvlaedge.agent.agent.Agent")
    @patch("nuvlaedge.agent.__init__.get_agent_settings")
    def test_main_generic_exception(self, mock_get_settings, mock_agent_cls,
                                    mock_thread_cls, mock_getenv,
                                    mock_sleep, mock_print):
        # Agent settings mock
        dummy_settings = MagicMock()
        dummy_settings.nuvlaedge_debug = False
        dummy_settings.nuvlaedge_log_level = "INFO"
        dummy_settings.nuvlaedge_logging_directory = "/tmp"
        dummy_settings.disable_file_logging = False
        mock_get_settings.return_value = dummy_settings

        # Agent mock
        mock_agent = Mock()
        mock_agent_cls.return_value = mock_agent

        # Thread mock
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread_cls.return_value = mock_thread

        from nuvlaedge.agent.__init__ import main
        main()

        # ✅ Check that the generic exception message was printed
        mock_print.assert_any_call("\n[UNKNOWN ERROR] An unknown error triggered agent exit: \n\n")
        mock_print.assert_any_call("\n Simulated exception")

        # Ensure the thread was started and is_alive was called
        mock_thread.start.assert_called_once()
        mock_thread.is_alive.assert_called()


class TestPrintThreads(unittest.TestCase):

    @patch('nuvlaedge.agent.threading.enumerate')
    @patch('nuvlaedge.agent.sys._current_frames')
    @patch('nuvlaedge.agent.traceback.format_stack')
    def test_print_threads_output(self, mock_format_stack, mock_current_frames, mock_enumerate):
        # Setup a mock thread
        mock_thread = Mock()
        mock_thread.ident = 123
        mock_thread.name = 'MockThread'
        mock_thread.is_alive.return_value = True
        mock_enumerate.return_value = [mock_thread]

        # Setup mock current frame
        mock_frame = Mock()
        mock_current_frames.return_value = {123: mock_frame}

        # Mock the formatted stack trace
        mock_format_stack.return_value = ['line1\n', 'line2\n']

        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            print_threads()
        finally:
            sys.stdout = sys.__stdout__  # Always restore stdout

        output = captured_output.getvalue()

        self.assertIn("THREAD DEBUG DUMP START", output)
        self.assertIn("Thread ID: 123", output)
        self.assertIn("Name: MockThread", output)
        self.assertIn("Alive: True", output)
        self.assertIn("line1", output)
        self.assertIn("line2", output)
        self.assertIn("THREAD DEBUG DUMP STOP", output)