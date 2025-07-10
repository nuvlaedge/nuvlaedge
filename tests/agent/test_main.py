import unittest
from unittest.mock import patch, MagicMock


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
