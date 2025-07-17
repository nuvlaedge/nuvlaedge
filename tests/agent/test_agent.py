import asyncio
import logging
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch, PropertyMock
import pytest

from nuvlaedge.agent.common.exceptions import ActionTimeoutError
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

    @patch("nuvlaedge.agent.agent.asyncio")
    def test_run(self, mock_asyncio):
        mock_worker_manager = Mock()
        mock_event = Mock()
        mock_loop = Mock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.Event.return_value = mock_event

        self.agent.worker_manager = mock_worker_manager
        self.agent.main = Mock()

        def run_until_complete(coro):
            return coro

        mock_loop.run_until_complete.side_effect = run_until_complete

        self.agent.run()

        mock_worker_manager.start.assert_called_once()
        mock_asyncio.new_event_loop.assert_called_once()
        mock_asyncio.set_event_loop.assert_called_once_with(mock_loop)
        self.agent.main.assert_called_once()  # Only check it was called
        mock_loop.close.assert_called_once()

    @patch("nuvlaedge.agent.agent.asyncio")
    def test_run_exception_handling(self, mock_asyncio):
        mock_worker_manager = Mock()
        mock_loop = Mock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.Event.return_value = Mock()

        self.agent.worker_manager = mock_worker_manager
        self.agent.main = Mock(side_effect=Exception("Test exception"))

        mock_loop.run_until_complete.side_effect = lambda coro: coro

        with patch("nuvlaedge.agent.agent.logger") as mock_logger:
            self.agent.run()
            mock_logger.error.assert_any_call(
                "Exception in async main: Test exception", exc_info=True
            )
            mock_loop.stop.assert_called_once()
            mock_loop.close.assert_called_once()

@pytest.mark.asyncio
async def test_main_handles_action_timeout():
    agent = Agent(exit_event=Mock(), settings=Mock())

    async def fake_periodic_action(*args, **kwargs):
        raise agent.__class__.__bases__[0].__dict__.get('ActionTimeoutError', Exception)("heartbeat", 10)

    agent._periodic_action = fake_periodic_action

    with patch("nuvlaedge.agent.agent.sys.exit") as mock_exit, \
            patch("nuvlaedge.agent.agent.logger") as mock_logger:
        await agent.main(Mock())
        mock_logger.error.assert_any_call("Forcing system exit...")
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_main_handles_generic_exception():
    agent = Agent(exit_event=Mock(), settings=Mock())

    async def fake_periodic_action(*args, **kwargs):
        raise Exception("Critical error")

    agent._periodic_action = fake_periodic_action

    with patch("nuvlaedge.agent.agent.sys.exit") as mock_exit, \
            patch("nuvlaedge.agent.agent.logger") as mock_logger:
        await agent.main(Mock())
        mock_logger.error.assert_any_call("Forcing system exit...")
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_main_normal_exit():
    agent = Agent(exit_event=Mock(), settings=Mock())

    async def fake_periodic_action(*args, **kwargs):
        return None  # Simulate normal completion

    agent._periodic_action = fake_periodic_action

    with patch("nuvlaedge.agent.agent.sys.exit") as mock_exit, \
            patch("nuvlaedge.agent.agent.logger") as mock_logger:
        await agent.main(Mock())
        mock_logger.error.assert_any_call("Forcing system exit...")
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_periodic_action_success_once():
    agent = Agent(Mock(), Mock())

    mock_action = Mock(return_value={"jobs": []})
    mock_get_period = Mock(return_value=0.01)
    mock_exit_event = asyncio.Event()

    with patch.object(agent, "_process_response") as mock_process:
        async def exit_after_first(*args, **kwargs):
            mock_exit_event.set()

        # Patch asyncio.sleep to skip actual sleep and simulate exit
        with patch("nuvlaedge.agent.agent.asyncio.sleep", side_effect=exit_after_first):
            await agent._periodic_action("test", mock_get_period, mock_action, mock_exit_event)

        mock_action.assert_called_once()
        mock_process.assert_called_once_with({"jobs": []}, "test")

@pytest.mark.asyncio
async def test_periodic_action_no_result():
    agent = Agent(Mock(), Mock())

    mock_action = Mock(return_value=None)
    mock_get_period = Mock(return_value=0.01)
    mock_exit_event = asyncio.Event()

    async def exit_soon(*args, **kwargs):
        mock_exit_event.set()

    with patch("nuvlaedge.agent.agent.asyncio.sleep", side_effect=exit_soon), \
         patch.object(agent, "_process_response") as mock_process:
        await agent._periodic_action("noop", mock_get_period, mock_action, mock_exit_event)

    mock_action.assert_called_once()
    mock_process.assert_not_called()

@pytest.mark.asyncio
async def test_periodic_action_first_timeout_then_success():
    agent = Agent(Mock(), Mock())
    mock_exit_event = asyncio.Event()
    mock_get_period = Mock(return_value=0.01)

    # A real function (not a mock), to avoid un-awaited coroutine warnings
    def action():
        return {"jobs": []}

    # Counter to simulate first timeout, then success
    call_count = 0

    async def wait_for_mock(coro, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        return await coro

    async def mock_to_thread(func, *args, **kwargs):
        return func()

    with patch("nuvlaedge.agent.agent.asyncio.to_thread", side_effect=mock_to_thread), \
         patch("nuvlaedge.agent.agent.asyncio.wait_for", side_effect=wait_for_mock), \
         patch.object(agent, "_process_response", new=Mock()) as mock_process, \
         patch("nuvlaedge.agent.agent.asyncio.sleep", side_effect=lambda s: mock_exit_event.set()):

        await agent._periodic_action("test", mock_get_period, action, mock_exit_event)

    assert call_count == 2
    mock_process.assert_called_once_with({"jobs": []}, "test")

@pytest.mark.asyncio
async def test_periodic_action_timeout_twice_raises():
    agent = Agent(Mock(), Mock())
    mock_exit_event = asyncio.Event()
    mock_get_period = Mock(return_value=0.01)

    with patch("nuvlaedge.agent.agent.asyncio.wait_for", side_effect=asyncio.TimeoutError), \
         patch("nuvlaedge.agent.agent.asyncio.to_thread", return_value=Mock()), \
         patch("nuvlaedge.agent.agent.logger") as mock_logger:
        with pytest.raises(ActionTimeoutError):
            await agent._periodic_action("test", mock_get_period, Mock(), mock_exit_event)

        assert mock_logger.warning.call_count == 1
        assert mock_logger.error.call_count == 1

@pytest.mark.asyncio
async def test_periodic_action_unexpected_exception():
    agent = Agent(Mock(), Mock())
    mock_exit_event = asyncio.Event()
    mock_get_period = Mock(return_value=0.01)

    def raise_unexpected():
        raise ValueError("Unexpected failure")

    async def mock_to_thread(*args, **kwargs):
        raise_unexpected()

    async def mock_wait_for(coro, timeout):
        return await coro

    with patch("nuvlaedge.agent.agent.asyncio.to_thread", side_effect=mock_to_thread), \
         patch("nuvlaedge.agent.agent.asyncio.wait_for", side_effect=mock_wait_for), \
         patch("nuvlaedge.agent.agent.logger") as mock_logger:
        with pytest.raises(ValueError, match="Unexpected failure"):
            await agent._periodic_action("fail", mock_get_period, raise_unexpected, mock_exit_event)

    # Optional: check logger was called with error
    mock_logger.error.assert_any_call("Error in action fail: Unexpected failure", exc_info=True)

@pytest.mark.asyncio
async def test_periodic_action_exit_event_set_immediately():
    agent = Agent(Mock(), Mock())
    mock_exit_event = asyncio.Event()
    mock_exit_event.set()

    mock_action = Mock()
    mock_get_period = Mock(return_value=0.1)

    await agent._periodic_action("exit_immediately", mock_get_period, mock_action, mock_exit_event)

    mock_action.assert_not_called()