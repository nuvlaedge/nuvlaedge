import os
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.job import Job
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.workers.telemetry import TelemetryPayloadAttributes
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.settings import AgentSettingsMissMatch, InsufficientSettingsProvided
from nuvlaedge.agent.nuvla.resources.nuvlaedge_res import State
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent import AgentSettings
from nuvlaedge.agent.agent import Agent


class TestAgent(TestCase):

    def setUp(self):

        self.settings = Mock(spec=AgentSettings(nuvlaedge_uuid='some_uuid'))
        self.exit_event = Mock(spec=Event)
        self.mock_nuvla_client = Mock(spec=NuvlaClientWrapper)
        self.mock_coe_client = Mock(spec=COEClient)

        # Create the agent
        with patch('nuvlaedge.agent.agent.get_coe_client') as mock_coe:
            mock_coe.return_value = self.mock_coe_client
            self.agent = Agent(self.exit_event, self.settings)

        # Mock the agent's nuvla client and COE client
        self.agent._coe_client = self.mock_coe_client
        self.agent._nuvla_client = self.mock_nuvla_client

    def test_init(self):
        assert isinstance(self.agent.settings, AgentSettings)
        assert isinstance(self.agent._exit, Event)

    @patch('nuvlaedge.agent.worker.logging.Logger.info')
    @patch('nuvlaedge.agent.worker.logging.Logger.warning')
    def test_check_uuid_missmatch(self, mock_warning, mock_info):
        self.mock_nuvla_client.nuvlaedge_uuid = None
        self.settings.nuvlaedge_uuid = None

        # Test non valid uuid cases
        with self.assertRaises(InsufficientSettingsProvided):
            self.agent.check_uuid_missmatch()

        self.settings.nuvlaedge_uuid = NuvlaID('')
        self.mock_nuvla_client.nuvlaedge_uuid = NuvlaID('')
        with self.assertRaises(InsufficientSettingsProvided):
            self.agent.check_uuid_missmatch()

        self.mock_nuvla_client.nuvlaedge_uuid = NuvlaID('some_uuid/1')
        self.agent.check_uuid_missmatch()
        self.assertEqual(self.settings.nuvlaedge_uuid, NuvlaID('some_uuid/1'))

        self.settings.nuvlaedge_uuid = NuvlaID('some_uuid/2')
        self.mock_nuvla_client.nuvlaedge_uuid = NuvlaID('')
        mock_info.reset_mock()
        self.agent.check_uuid_missmatch()
        mock_info.assert_called_once_with(f"Starting NuvlaEdge from provided UUID: {self.settings.nuvlaedge_uuid}")

        self.settings.nuvlaedge_uuid = NuvlaID('some_uuid/2')
        self.mock_nuvla_client.nuvlaedge_uuid = NuvlaID('some_uuid/1')
        self.agent.check_uuid_missmatch()
        mock_warning.assert_called_once()


    @patch('nuvlaedge.agent.agent.Agent._create_nuvla_client')
    @patch('nuvlaedge.agent.agent.Agent.check_uuid_missmatch')
    def test_assert_current_state(self, mock_missmatch, mock_nuvla_client):
        mock_nuvla_client.return_value = self.mock_nuvla_client
        self.mock_nuvla_client.nuvlaedge_uuid = 'some_uuid'
        self.mock_nuvla_client.nuvlaedge_credentials = None

        self.assertEqual(State.NEW, self.agent._assert_current_state())
        mock_missmatch.assert_called_once()

        self.mock_nuvla_client.nuvlaedge_credentials = 'creds'
        self.mock_nuvla_client.nuvlaedge.state = "ACTIVATED"
        self.assertEqual(State.ACTIVATED, self.agent._assert_current_state())

    @patch('nuvlaedge.agent.manager.WorkerManager.add_worker')
    def test_init_workers(self, mock_add_worker):
        self.mock_nuvla_client.nuvlaedge_uuid = 'some_uuid'
        self.mock_nuvla_client.nuvlaedge_client = Mock()
        self.agent._init_workers()
        self.assertEqual(4, mock_add_worker.call_count)

    @patch('nuvlaedge.common.timed_actions.ActionHandler.add')
    def test_init_actions(self, mock_add):
        self.agent._init_actions()
        self.assertEqual(4, mock_add.call_count)

    @patch('nuvlaedge.agent.agent.Agent._init_workers')
    @patch('nuvlaedge.agent.agent.Agent._init_actions')
    @patch('nuvlaedge.agent.agent.Agent._assert_current_state')
    def test_start_agent(self, mock_assert_current_state, mock_init_actions, mock_init_workers):
        mock_assert_current_state.return_value = State.NEW
        self.mock_nuvla_client.activate.return_value = True

        self.agent.start_agent()
        self.mock_nuvla_client.activate.assert_called_once()
        mock_init_actions.assert_called_once()
        mock_init_workers.assert_called_once()

        mock_assert_current_state.return_value = State.DECOMMISSIONED
        with self.assertRaises(SystemExit):
            self.agent.start_agent()

    @patch('nuvlaedge.agent.common.status_handler.NuvlaEdgeStatusHandler.get_status')
    def test_gather_status(self, mock_get_status):
        mock_telemetry = Mock(spec=TelemetryPayloadAttributes)
        mock_get_status.return_value = ("OPERATIONAL", ['RUNNING FINE'])

        self.agent._gather_status(mock_telemetry)
        self.assertEqual("OPERATIONAL", mock_telemetry.status)
        self.assertEqual(["RUNNING FINE"], mock_telemetry.status_notes)

    @patch('nuvlaedge.agent.agent.model_diff')
    @patch('nuvlaedge.agent.agent.Agent._gather_status')
    def test_telemetry(self, mock_status, mock_model_diff):
        mock_channel = Mock()
        mock_payload = Mock(spec=TelemetryPayloadAttributes)
        mock_channel.empty.return_value = True
        mock_payload.model_copy.return_value = mock_payload
        self.agent.telemetry_channel = mock_channel
        self.agent.telemetry_payload = mock_payload

        mock_model_diff.return_value = ('send', 'delete')
        mock_payload.model_dump.return_value = {}
        mock_payload.model_dump.return_value = "Data to send"

        self.mock_nuvla_client.telemetry.return_value = None

        self.assertIsNone(self.agent._telemetry())
        mock_payload.model_dump.assert_called_once()
        mock_payload.model_copy.assert_called_once()
        mock_payload.model_dump_json.assert_called_once()
        mock_status.assert_called_with(mock_payload)

        mock_payload.reset_mock()
        mock_response = Mock()
        mock_response.data = mock_response
        self.mock_nuvla_client.telemetry.return_value = mock_response
        with patch('nuvlaedge.agent.agent.write_file') as mock_json:
            self.assertEqual(mock_response, self.agent._telemetry())
        self.assertEqual(2, mock_payload.model_copy.call_count)

        mock_channel.empty.return_value = False
        mock_channel.get.return_value = mock_payload
        with patch('nuvlaedge.agent.agent.write_file') as mock_json:
            self.assertEqual(mock_response, self.agent._telemetry())
        mock_channel.get.assert_called_once()

    def test_heartbeat(self):
        self.mock_nuvla_client.nuvlaedge.state = State.NEW
        self.assertIsNone(self.agent._heartbeat())

        self.mock_nuvla_client.nuvlaedge.state = 'NOTREGISTERD'
        self.assertIsNone(self.agent._heartbeat())

        self.mock_nuvla_client.nuvlaedge.state = 'COMMISSIONED'
        self.mock_nuvla_client.heartbeat.return_value = True
        self.assertTrue(self.agent._heartbeat())

        self.mock_nuvla_client.nuvlaedge.state = State.COMMISSIONED
        self.assertTrue(self.agent._heartbeat())

    @patch('nuvlaedge.agent.agent.Agent._process_jobs')
    def test_process_response(self, mock_process_jobs):
        mock_response = Mock()
        operation = "mocked_operation"
        mock_response.get.return_value = []

        self.agent._process_response(mock_response, operation)
        mock_process_jobs.assert_not_called()

        mock_response.get.return_value = ['job/mock_id']
        self.agent._process_response(mock_response, operation)
        mock_process_jobs.assert_called_once()

    @patch('nuvlaedge.agent.agent.Job')
    def test_process_jobs(self, mock_job):
        mocked_instance = Mock(spec=Job)
        mocked_instance.do_nothing = True
        mocked_instance.job_id = 'job/1'
        mocked_instance.launch.return_value = True
        mock_job.return_value = mocked_instance
        self.mock_coe_client.job_engine_lite_image = 'image'
        jobs = [NuvlaID('job/1')]

        self.agent._process_jobs(jobs)
        mock_job.assert_called_once()
        mocked_instance.assert_not_called()

        mocked_instance.do_nothing = False
        self.agent._process_jobs(jobs)
        mocked_instance.launch.assert_called_once()

    def test_stop(self):
        self.agent.stop()
        self.exit_event.set.assert_called_once()

    @patch('nuvlaedge.agent.agent.NuvlaEdgeStatusHandler.running')
    def test_run(self, mock_status_running):
        mock_manager = Mock()
        mock_actions = Mock()
        self.agent.worker_manager = mock_manager
        self.agent.action_handler = mock_actions
        self.exit_event.wait.return_value = True
        self.agent.run()

        # Test once for each call before the infinite loop
        mock_manager.start.assert_called_once()
        mock_actions.sleep_time.assert_called_once()
        mock_status_running.reset_mock()

        # Enter the infinite loop once
        self.exit_event.wait.side_effect = [False, True]
        mock_action = Mock()
        mock_action.return_value = None
        mock_action.name = 'mock_action'
        mock_actions.sleep_time.return_value = 10
        mock_actions.next = mock_action

        self.agent.run()
        self.assertEqual(2, mock_status_running.call_count)
        mock_action.assert_called_once()

        mock_action.return_value = "Data"
        with patch('nuvlaedge.agent.agent.Agent._process_response') as mock_process_response:
            self.exit_event.wait.side_effect = [False, True]
            self.agent.run()
            mock_process_response.assert_called_once()



