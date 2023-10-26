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

    @patch('nuvlaedge.agent.update_periods')
    def test_update_nuvlaedge_configuration(self, mock_update_periods):
        mock_current = {
            'updated': 0,
            'vpn-server-id': 'ID'
        }
        mock_old = {
            'updated': 0,
            'vpn-server-id': 'ID'
        }

        mock_infra = Mock()
        # Resource hasn't been updated since the last check, do nothing
        agent.update_nuvlaedge_configuration(mock_current, mock_old, mock_infra)
        mock_infra.commission_vpn.assert_not_called()
        mock_update_periods.assert_not_called()

        # Resource changed, with same vpn id
        mock_current['updated'] = 1
        agent.update_nuvlaedge_configuration(mock_current, mock_old, mock_infra)
        mock_update_periods.assert_called_once()
        mock_infra.commission_vpn.assert_not_called()
        mock_update_periods.reset_mock()

        # Everything has changed
        mock_current['vpn-server-id'] = 'ID_BIS'
        agent.update_nuvlaedge_configuration(mock_current, mock_old, mock_infra)
        mock_update_periods.assert_called_once()
        mock_infra.commission_vpn.assert_called_once()

    @patch('nuvlaedge.agent.update_nuvlaedge_configuration')
    def test_resource_synchronization(self, mock_update_config):
        mock_activator = Mock()
        mock_exit = Mock()
        mock_infra = Mock()

        # If the nuvlaedge has been decommissioned
        mock_activator.get_nuvlaedge_info.return_value = {'state': 'DECOMMISSIONING'}
        agent.resource_synchronization(mock_activator, mock_exit, mock_infra)
        mock_exit.set.assert_called_once()

        # Normal state
        mock_activator.get_nuvlaedge_info.return_value = {'state': 'ACTIVATED',
                                                          'vpn-server-id': None}
        agent.resource_synchronization(mock_activator, mock_exit, mock_infra)
        mock_update_config.assert_called_once()
        mock_activator.create_nb_document_file.assert_called_once()
        mock_infra.watch_vpn_credential.assert_not_called()

        mock_activator.get_nuvlaedge_info.return_value = {'state': 'ACTIVATED',
                                                          'vpn-server-id': 'ID'}
        agent.resource_synchronization(mock_activator, mock_exit, mock_infra)
        mock_infra.watch_vpn_credential.assert_called_with('ID')

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
