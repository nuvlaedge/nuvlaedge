import os
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.nuvla.resources.nuvlaedge import State
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent import AgentSettings, Agent


class TestAgent(TestCase):

    def setUp(self):

        self.settings = Mock(spec=AgentSettings(nuvlaedge_uuid='some_uuid'))
        self.exit_event = Mock(spec=Event)
        self.agent = Agent(self.exit_event, self.settings)

    def test_init(self):
        assert isinstance(self.agent.settings, AgentSettings)
        assert isinstance(self.agent._exit, Event)

    @patch('nuvlaedge.agent.agent.file_exists_and_not_empty')
    @patch('nuvlaedge.agent.agent.NuvlaClientWrapper.from_agent_settings')
    def test_assert_current_state_with_no_local_session_and_no_api_keys(self,
                                                                        mock_from_agent_settings,
                                                                        mock_file_exists):
        """ This test asserts that the agent state is set to NEW when there is no Nuvla session file and no API keys """
        self.agent.settings.nuvlaedge_api_key = None
        self.agent.settings.nuvlaedge_api_secret = None
        self.agent.settings.nuvlaedge_uuid = 'some_uuid'
        mock_file_exists.return_value = False
        mock_from_agent_settings.return_value = Mock(spec=NuvlaClientWrapper)
        mock_from_agent_settings.return_value.nuvlaedge.state = State.NEW
        result = self.agent.assert_current_state()

        # Returned state should be NEW
        self.assertEqual(result, State.NEW)
        mock_file_exists.assert_called_once_with(FILE_NAMES.NUVLAEDGE_SESSION)

    @patch('nuvlaedge.agent.agent.file_exists_and_not_empty')
    @patch('nuvlaedge.agent.agent.NuvlaClientWrapper.from_nuvlaedge_credentials')
    def test_assert_current_state_with_api_keys_no_local(self, mock_from_nuvla_creds, mock_file_exists):
        self.agent.settings.nuvlaedge_api_key = 'some_key'
        self.agent.settings.nuvlaedge_api_secret = 'some_secret'
        self.agent.settings.nuvla_endpoint = "nuvla.io"
        # self.agent.settings.nuvla_endpoint_insecure = False
        self.agent.settings.nuvlaedge_uuid = None
        mock_file_exists.return_value = False
        mock_from_nuvla_creds.return_value = Mock(spec=NuvlaClientWrapper)
        mock_from_nuvla_creds.return_value.nuvlaedge.state = State.ACTIVATED
        result = self.agent.assert_current_state()
        self.assertEqual(result, State.ACTIVATED)
        mock_file_exists.assert_called_once_with(FILE_NAMES.NUVLAEDGE_SESSION)

    def test_init_workers(self):
        assert True
    
    def test_init_actions(self):
        assert True

    def test_start_agent(self):
        assert True

    def test_telemetry(self):
        assert True

    def test_heartbeat(self):
        assert True

    def test_process_response(self):
        assert True

    def test_process_jobs(self):
        assert True

    def test_stop(self):
        assert True

    def test_run(self):
        assert True
