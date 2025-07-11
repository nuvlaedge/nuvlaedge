import logging
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch, PropertyMock

from nuvlaedge.agent.job import Job
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.nuvla.resources.telemetry_payload import TelemetryPayloadAttributes
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.nuvla.resources.nuvlaedge_res import State
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent import AgentSettings
from nuvlaedge.agent.agent import Agent
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.timed_actions import ActionHandler


class TestAgent(TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.settings = Mock(spec=AgentSettings)
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

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        assert isinstance(self.agent.settings, AgentSettings)
        assert isinstance(self.agent._exit, Event)

    def test_assert_current_state(self):
        mock_settings = Mock()
        self.agent.settings = mock_settings
        self.mock_nuvla_client.nuvlaedge_uuid = 'some_uuid'
        self.mock_nuvla_client.nuvlaedge_credentials = None
        self.mock_nuvla_client.irs = None
        mock_settings.nuvla_client = self.mock_nuvla_client
        self.assertEqual(State.NEW, self.agent._assert_current_state())

        self.mock_nuvla_client.irs = 'irs'
        self.mock_nuvla_client.nuvlaedge_credentials = None
        self.mock_nuvla_client.nuvlaedge.state = "ACTIVATED"
        self.assertEqual(State.ACTIVATED, self.agent._assert_current_state())

        self.mock_nuvla_client.irs = None
        self.mock_nuvla_client.nuvlaedge_credentials = 'creds'
        self.mock_nuvla_client.nuvlaedge.state = "COMMISSIONED"
        self.assertEqual(State.COMMISSIONED, self.agent._assert_current_state())

    @patch('nuvlaedge.agent.manager.WorkerManager.add_worker')
    def test_init_workers(self, mock_add_worker):
        self.mock_nuvla_client.nuvlaedge_uuid = 'some_uuid'
        self.mock_nuvla_client.nuvlaedge_client = Mock()
        mock_settings = Mock()
        self.agent.settings = mock_settings
        mock_settings.nuvlaedge_excluded_monitors = []
        self.agent._init_workers()
        self.assertEqual(4, mock_add_worker.call_count)

    @patch('nuvlaedge.common.timed_actions.ActionHandler.add')
    def test_init_actions(self, mock_add):
        self.agent._init_actions()
        self.assertEqual(3, mock_add.call_count)

    @patch('nuvlaedge.agent.agent.logger')
    def test_watch_workers(self, mock_logger):
        self.agent.worker_manager = Mock()
        self.agent._watch_workers()
        self.agent.worker_manager.heal_workers.assert_called_once()
        self.agent.worker_manager.summary.assert_called_once()
        self.assertEqual(2, mock_logger.info.call_count)

    def test_install_ssh_key(self):

        self.settings.host_home = None
        self.settings.nuvlaedge_immutable_ssh_pub_key = None
        self.agent._install_ssh_key()
        self.mock_coe_client.install_ssh_key.assert_not_called()

        self.settings.nuvlaedge_immutable_ssh_pub_key = "key"
        self.settings.host_home = "host"
        self.agent._install_ssh_key()
        self.mock_coe_client.install_ssh_key.assert_called_with("key", "host")

    @patch('nuvlaedge.agent.agent.logger')
    @patch('nuvlaedge.agent.agent.Agent._install_ssh_key')
    @patch('nuvlaedge.agent.agent.Agent._init_workers')
    @patch('nuvlaedge.agent.agent.Agent._init_actions')
    @patch('nuvlaedge.agent.agent.Agent._assert_current_state')
    @patch('nuvlaedge.agent.agent.Agent._run_controlled_startup')
    def test_start_agent(self, mock_run_startup, mock_assert_current_state, mock_init_actions, mock_init_workers, mock_install_ssh, mock_logger):
        mock_assert_current_state.return_value = State.NEW
        self.mock_nuvla_client.activate.return_value = True

        self.agent.start_agent()
        mock_install_ssh.assert_called_once()
        self.mock_nuvla_client.activate.assert_called_once()
        mock_init_actions.assert_called_once()
        mock_init_workers.assert_called_once()

        mock_init_actions.reset_mock()
        mock_init_workers.reset_mock()

        mock_assert_current_state.return_value = State.DECOMMISSIONED
        with self.assertRaises(SystemExit):
            self.agent.start_agent()
        mock_logger.error.assert_called_with("Force exiting the agent due to wrong state DECOMMISSIONED")
        mock_init_actions.assert_not_called()
        mock_init_workers.assert_not_called()
        mock_run_startup.assert_not_called()

        mock_logger.reset_mock()

        mock_assert_current_state.return_value = State.DECOMMISSIONING
        with self.assertRaises(SystemExit):
            self.agent.start_agent()
        mock_logger.error.assert_called_with("Force exiting the agent due to wrong state DECOMMISSIONING")

        self.agent.telemetry_payload = Mock()
        mock_assert_current_state.return_value = State.COMMISSIONED

        self.agent.start_agent()
        self.agent.telemetry_payload.update.assert_called_once()

    @patch('nuvlaedge.agent.agent.logger')
    @patch('nuvlaedge.agent.agent.Agent._telemetry_worker', new_callable=PropertyMock)
    @patch('nuvlaedge.agent.agent.Agent._commission_worker', new_callable=PropertyMock)
    @patch('nuvlaedge.agent.agent.Agent._telemetry')
    def test_run_controlled_startup(self, mock_telemetry, mock_commissioner_worker, mock_telemetry_worker, mock_logger):
        commissioner = Mock()
        telemetry = Mock()
        mock_commissioner_worker.return_value = None
        self.agent._run_controlled_startup()
        mock_logger.warning.assert_called_with("Commissioner not found in controlled startup...")

        mock_logger.reset_mock()

        mock_commissioner_worker.return_value = commissioner
        mock_telemetry_worker.return_value = None
        self.agent._run_controlled_startup()
        commissioner.run.assert_called_once()
        mock_logger.warning.assert_called_with("Telemetry not found in controlled startup...")

        mock_logger.reset_mock()
        commissioner.run.reset_mock()

        mock_telemetry_worker.return_value = telemetry
        self.agent.telemetry_payload = TelemetryPayloadAttributes(node_id="mock_id")
        self.mock_nuvla_client.nuvlaedge_status.node_id = "mock_id_2"
        self.agent._run_controlled_startup()
        self.assertEqual(2, commissioner.run.call_count)
        telemetry.run_once.assert_called_once()
        self.assertEqual("mock_id", self.mock_nuvla_client.nuvlaedge_status.node_id)



    def test_gather_status(self):
        mock_status = Mock()
        mock_telemetry = Mock(spec=TelemetryPayloadAttributes)
        self.agent.status_handler = mock_status
        mock_status.get_status.return_value = ("OPERATIONAL", ['RUNNING FINE'])

        self.agent._gather_status(mock_telemetry)
        self.assertEqual("OPERATIONAL", mock_telemetry.status)
        self.assertEqual(["RUNNING FINE"], mock_telemetry.status_notes)

    @patch('nuvlaedge.agent.agent.Agent._telemetry_worker', new_callable=PropertyMock)
    @patch('nuvlaedge.agent.agent.logger')
    def test_update_periodic_actions(self, mock_logger, mock_telemetry_worker):
        self.mock_nuvla_client.nuvlaedge.refresh_interval = 0
        self.mock_nuvla_client.nuvlaedge.heartbeat_interval = 0
        self.agent.telemetry_period = 0
        self.agent.heartbeat_period = 0

        self.agent._update_periodic_actions()
        mock_logger.info.assert_called_with("Updating periodic actions...")

        mock_logger.reset_logger()
        self.mock_nuvla_client.nuvlaedge.refresh_interval = 10

        self.agent._update_periodic_actions()
        self.assertEqual(10, self.agent.telemetry_period)
        self.assertEqual(3, mock_logger.info.call_count)


    @patch('nuvlaedge.agent.agent.Agent._telemetry_worker', new_callable=PropertyMock)
    @patch('nuvlaedge.agent.agent.write_file')
    @patch('nuvlaedge.agent.agent.jsonpatch.make_patch')
    @patch('nuvlaedge.agent.agent.data_gateway_client')
    @patch('nuvlaedge.agent.agent.model_diff')
    @patch('nuvlaedge.agent.agent.Agent._gather_status')
    def test_telemetry(self, mock_status, mock_model_diff, mock_data_gateway, mock_patch, mock_write_file, mock_telemetry_worker):
        mock_telemetry = Mock()
        new_telemetry = TelemetryPayloadAttributes(node_id="node_id")
        self.agent.telemetry_payload = TelemetryPayloadAttributes()
        mock_telemetry.get_telemetry.return_value = new_telemetry
        mock_telemetry_worker.return_value = mock_telemetry
        mock_model_diff.return_value = ({"node_id"}, {})

        # Test normal patch telemetry
        mock_patch.return_value = ["Not None"]
        self.mock_nuvla_client.telemetry_patch.return_value = None
        self.assertIsNone(self.agent._telemetry())

        self.mock_nuvla_client.telemetry_patch.assert_called_once()
        self.mock_nuvla_client.telemetry.assert_not_called()
        mock_status.assert_called_once()
        mock_telemetry.get_telemetry.assert_called_once()
        mock_write_file.assert_not_called()

        # Test Fallback telemetry
        self.mock_nuvla_client.telemetry_patch.side_effect = Exception("Error mock")
        self.mock_nuvla_client.telemetry.return_value = None
        self.mock_nuvla_client.telemetry_patch.reset_mock()
        self.assertIsNone(self.agent._telemetry())

        self.mock_nuvla_client.telemetry.assert_called_once()
        self.mock_nuvla_client.telemetry_patch.assert_called_once()

        # Test whole process
        mock_client = Mock()
        self.agent._nuvla_client = mock_client
        self.agent._nuvla_client.telemetry_patch.reset_mock()
        self.agent._nuvla_client.telemetry.reset_mock()
        mock_response = "Success response"
        self.agent._nuvla_client.telemetry_patch.return_value = mock_response

        self.assertEqual(mock_response, self.agent._telemetry())
        mock_write_file.assert_called_with(new_telemetry, FILE_NAMES.STATUS_FILE)
        self.assertEqual(self.agent.telemetry_payload, new_telemetry)
        mock_data_gateway.send_telemetry.assert_called_with(new_telemetry)

    @patch('nuvlaedge.agent.agent.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.agent.logger')
    def test_heartbeat(self, mock_logger, mock_status_running):
        self.mock_nuvla_client.nuvlaedge.state = State.NEW
        self.assertIsNone(self.agent._heartbeat())
        self.mock_nuvla_client.heartbeat.assert_not_called()
        self.assertEqual(2, mock_logger.info.call_count)
        mock_logger.reset_mock()

        self.mock_nuvla_client.nuvlaedge.state = 'NOTREGISTERD'
        self.assertIsNone(self.agent._heartbeat())
        self.mock_nuvla_client.heartbeat.assert_not_called()
        self.assertEqual(2, mock_logger.info.call_count)
        mock_logger.reset_mock()

        self.mock_nuvla_client.nuvlaedge.state = 'COMMISSIONED'
        self.mock_nuvla_client.heartbeat.return_value = True
        self.assertTrue(self.agent._heartbeat())
        self.mock_nuvla_client.heartbeat.assert_called_once()
        self.assertEqual(2, mock_logger.info.call_count)
        mock_logger.info.assert_called_with("Executing heartbeat... Success")
        mock_status_running.assert_called_once()

        self.mock_nuvla_client.nuvlaedge.state = State.COMMISSIONED
        self.assertTrue(self.agent._heartbeat())

    @patch('nuvlaedge.agent.agent.Agent._process_jobs')
    def test_process_response(self, mock_process_jobs):
        mock_response = {
            "jobs": []
        }
        operation = "mocked_operation"

        self.agent._process_response(mock_response, operation)
        mock_process_jobs.assert_not_called()

        mock_response = {
            "jobs": 'job/mock_id'
        }
        self.agent._process_response(mock_response, operation)
        mock_process_jobs.assert_called_once()

        mock_response = {
            "doc-last-updated": "2021-08-01T00:00:00Z",
        }
        self.agent._nuvla_client.update_nuvlaedge_resource_if_changed = Mock()
        self.agent._update_periodic_actions = Mock()

        self.agent._process_response(mock_response, operation)
        self.agent._nuvla_client.update_nuvlaedge_resource_if_changed.assert_called_once()
        self.agent._update_periodic_actions.assert_called_once()

    @patch('nuvlaedge.agent.agent.Job')
    def test_process_jobs(self, mock_job):
        mocked_instance = Mock(spec=Job)
        mocked_instance.is_job_running = Mock(return_value=True)
        mocked_instance.job_id = 'job/1'
        mocked_instance.launch.return_value = True
        mock_job.return_value = mocked_instance
        self.mock_coe_client.job_engine_lite_image = 'image'
        jobs = [NuvlaID('job/1')]
        self.agent.settings = Mock()
        self.agent._nuvla_client.nuvlaedge_client = Mock()

        self.agent.settings.nuvlaedge_exec_jobs_in_agent = True

        self.agent._process_jobs(jobs)
        mock_job.assert_called_once()
        mocked_instance.assert_not_called()

        mock_job.reset_mock()
        self.agent.settings.nuvlaedge_exec_jobs_in_agent = False

        self.agent._process_jobs(jobs)
        mock_job.assert_called_once()
        mocked_instance.assert_not_called()

        mocked_instance.is_job_running = Mock(return_value=False)
        self.agent._process_jobs(jobs)
        mocked_instance.launch.assert_called_once()

        mocked_instance.launch.side_effect = Exception
        self.agent._process_jobs(jobs)
        self.assertLogs(level="ERROR")

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
        self.assertEqual(1, mock_status_running.call_count)
        mock_action.assert_called_once()

        # mock_action.return_value = "Data"
        # with patch('nuvlaedge.agent.agent.Agent._process_response') as mock_process_response:
        #     self.exit_event.wait.side_effect = [False, True]
        #     self.agent.run()
        #     mock_process_response.assert_called_once()

    @patch('nuvlaedge.agent.agent.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.agent.logger')
    def test_run_normal_execution(self, mock_logger, mock_status):
        mock_action = Mock()
        mock_action.name = "test_action"
        mock_action.period = 5
        mock_action.return_value = {"doc-last-updated": "mock"}

        self.agent.action_handler = Mock()
        self.agent.action_handler.sleep_time.return_value = 1
        self.agent.action_handler.next = mock_action
        self.agent.action_handler.action_finished.return_value = 1

        self.exit_event.wait.side_effect = [False, True]

        # Patch _executor with a mock that has .submit returning a mock future
        mock_future = Mock()
        mock_future.result.return_value = mock_action.return_value

        self.agent._executor = Mock()
        self.agent._executor.submit.return_value = mock_future

        self.agent._process_response = Mock()

        self.agent.run()

        mock_status.assert_called_once()
        self.agent._executor.submit.assert_called_once_with(mock_action)
        self.agent._process_response.assert_called_once_with(mock_action.return_value, mock_action.name)

    @patch('nuvlaedge.agent.agent.logger')
    @patch('nuvlaedge.agent.agent.NuvlaEdgeStatusHandler.running')
    def test_run_timeout_once_then_success(self, mock_status, mock_logger):
        mock_action = Mock()
        mock_action.name = "test_action"
        mock_action.period = 3
        mock_action.return_value = {"doc-last-updated": "mock"}

        self.agent.action_handler = Mock()
        self.agent.action_handler.sleep_time.return_value = 1
        self.agent.action_handler.next = mock_action
        self.agent.action_handler.action_finished.return_value = 1

        self.exit_event.wait.side_effect = [False, True]

        future = Mock()
        future.result.side_effect = [FutureTimeoutError(), mock_action.return_value]
        self.agent._executor = Mock()
        self.agent._executor.submit.return_value = future
        self.agent._process_response = Mock()

        self.agent.run()

        self.assertEqual(future.result.call_count, 2)
        mock_logger.warning.assert_called_with(
            f"Action {mock_action.name} didn't execute in time ({mock_action.period}s timeout). Retrying once..."
        )
        self.agent._process_response.assert_called_once_with(mock_action.return_value, mock_action.name)

    @patch('nuvlaedge.agent.agent.logger')
    @patch('nuvlaedge.agent.agent.NuvlaEdgeStatusHandler.running')
    def test_run_generic_exception_handled(self, mock_status, mock_logger):
        mock_action = Mock()
        mock_action.name = "test_action"
        mock_action.period = 3

        self.agent.action_handler = Mock()
        self.agent.action_handler.sleep_time.return_value = 1
        self.agent.action_handler.next = mock_action

        self.exit_event.wait.side_effect = [False, True]

        future = Mock()
        future.result.side_effect = Exception("Unhandled error")
        self.agent._executor = Mock()
        self.agent._executor.submit.return_value = future
        self.agent._process_response = Mock()

        self.agent.run()

        mock_logger.error.assert_called_with(
            f"Unknown error occured while running {mock_action.name}: Unhandled error"
        )
        self.agent._process_response.assert_not_called()