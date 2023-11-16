from unittest import TestCase
from mock import Mock, patch
import threading

import nuvlaedge
from nuvlaedge import agent
import nuvlaedge.common.timed_actions


class TestAgentMain(TestCase):

    def setUp(self) -> None:
        ...

    @patch.object(nuvlaedge.agent, 'parse_arguments_and_initialize_logging')
    @patch.object(nuvlaedge.agent, 'main')
    def test_entry(self, mock_main, mock_parser):
        agent.entry()
        mock_main.assert_called_once()
        mock_parser.assert_called_once()

    @patch.object(nuvlaedge.common.timed_actions.ActionHandler, 'add')
    @patch('nuvlaedge.agent.TimedAction')
    def test_initialize_action(self, mock_timed_action, mock_add_action):
        mock_timed_action.return_value = 'action'
        agent.initialize_action('Name', 10, Mock())
        mock_add_action.assert_called_with('action')

    @patch.object(nuvlaedge.common.timed_actions.ActionHandler, 'edit_period')
    def test_update_periods(self, mock_edit):
        agent.update_periods({})
        self.assertEqual(2, mock_edit.call_count)

    @patch('nuvlaedge.agent.initialize_action')
    @patch('nuvlaedge.agent.signal')
    @patch('nuvlaedge.agent.socket')
    @patch('nuvlaedge.agent.Agent')
    @patch.object(nuvlaedge.agent.Event, 'is_set')
    @patch.object(nuvlaedge.agent.Event, 'wait')
    @patch.object(nuvlaedge.agent, 'action_handler')
    def test_main(self,
                  mock_action,
                  mock_wait,
                  mock_event,
                  mock_agent,
                  mock_socket,
                  mock_signal,
                  mock_init_actions):
        mock_action.sleep_time.return_value = 10
        mock_event.side_effect = [False, True]
        agent.main()
        self.assertEqual(2, mock_event.call_count)
        self.assertEqual(3, mock_init_actions.call_count)
        mock_wait.assert_called_once()
