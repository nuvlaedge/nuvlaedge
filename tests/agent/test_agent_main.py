from unittest import TestCase
from mock import Mock, patch
import threading

import nuvlaedge
from nuvlaedge import agent


class TestAgentMain(TestCase):

    def setUp(self) -> None:
        ...

    @patch.object(nuvlaedge.agent, 'parse_arguments_and_initialize_logging')
    @patch.object(nuvlaedge.agent, 'main')
    def test_entry(self, mock_main, mock_parser):
        agent.entry()
        mock_main.assert_called_once()
        mock_parser.assert_called_once()

    def test_preflight_check(self):
        ...

    @patch('threading.Event.wait')
    @patch('threading.Event.is_set')
    @patch.object(nuvlaedge.agent, 'Agent')
    @patch.object(nuvlaedge.agent, 'action_handler')
    @patch.object(nuvlaedge.agent, 'Thread')
    def test_main(self,
                  mock_thread,
                  mock_actions,
                  mock_agent,
                  mock_is_set,
                  mock_wait):
        tmp_mock = Mock()
        tmp_mock.initialize_agent.return_value = None
        tmp_mock.run_single_cycle.return_value = None
        mock_agent.return_value = tmp_mock

        tmp_thread = Mock()
        tmp_thread.is_alive.return_value = None
        tmp_thread.start.return_value = None
        mock_thread.return_value = tmp_thread

        mock_is_set.return_value = True
        agent.main()
        mock_wait.assert_not_called()
        tmp_mock.run_single_cycle.assert_not_called()
        tmp_thread.start.assert_not_called()

        mock_is_set.side_effect = [False, False, True]
        tmp_thread.is_alive.side_effect = [False, False, True]
        mock_wait.return_value = None

        agent.main()
        self.assertEqual(2, tmp_mock.initialize_agent.call_count)
        self.assertEqual(2, mock_thread.call_count)
        self.assertEqual(2, mock_wait.call_count)
        self.assertEqual(2, tmp_mock.run_single_cycle.call_count)
        self.assertEqual(2, tmp_thread.start.call_count)
