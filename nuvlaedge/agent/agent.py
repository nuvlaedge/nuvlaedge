"""
The Agent class is central to the operation of the NuvlaEdge software, responsible for configuration management,
worker initialization, periodic operation execution, and response handling. Here is a detailed breakdown of the
responsibilities:

    Configuration Management: Upon initialization, Agent uses the provided settings and an exit event to configure the
        connection with the Nuvla API and the Container Orchestration Engine (either Docker or Kubernetes).
        It also sets up channels (queues) for telemetry and VPN data.
    State Management: The assert_current_state method determines the current state of the NuvlaEdge application,
        retrieves sessions or credentials if they are stored, and initiates new client sessions if needed.
    Worker Initialization: The init_workers method begins key system workers, such as telemetry, VPN handling,
        peripheral management, and others. Each of these workers is configured with specific parameters and added to the worker manager. The initialization of some workers is contingent on certain conditions being met.
    Action Initialization: The init_actions method establishes a series of timed tasks to be executed by the agent in
        operations like telemetry and heartbeat.
    Periodic Operation Execution: In the start_agent method, the agent begins by validating the state of the
        application, actives the application if needed, and then initiates the workers and actions. The run method
        operates the agent by starting the worker manager and executing the necessary actions according to the schedule
        set up by the action handler.
    Response Handling: Agent handles responses from the Nuvla API, processes received jobs, updates the telemetry
        information, and sends heartbeats using the process_response, process_jobs, telemetry, and heartbeat methods, respectively.

The class attributes represent various components of the system including the Nuvla client, Container Orchestration
Engine (COE) client, worker manager, action handler, and the queues for telemetry and VPN data.
The WorkerManagerclass supervises worker initialization and operation, whereasAction
"""
import json
import jsonpatch
import logging
import sys
import time
from functools import cached_property
from queue import Queue
from threading import Event

from nuvla.api.models import CimiResponse

from nuvlaedge.agent.common.util import nuvla_support_new_container_stats
from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.job import Job, JobLauncher
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.timed_actions import ActionHandler, TimedAction
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.file_operations import write_file
from nuvlaedge.common.data_gateway import data_gateway_client
from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.agent.workers.peripheral_manager import PeripheralManager
from nuvlaedge.agent.workers.commissioner import Commissioner
from nuvlaedge.agent.workers.telemetry import TelemetryPayloadAttributes, Telemetry
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.nuvla.resources import State
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.manager import WorkerManager
from nuvlaedge.agent.settings import AgentSettings
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.orchestrator.factory import get_coe_client
from nuvlaedge.models import model_diff


logger: logging.Logger = get_nuvlaedge_logger(__name__)
_status_module_name: str = 'Agent'


class Agent:
    """
    An Agent class handles the operations of the NuvlaEdge agent, including initialization, assert
    current state, registering various workers, initializing periodic actions and running the agent.
    The Agent class interacts with the Nuvla API and the Container Orchestration Engine (COE) to
    collect data and perform tasks.

    Attributes:
        settings: `AgentSettings` - The settings object containing agent configuration.
        _exit: `Event` - The event object used to signal the agent to exit.
        _nuvla_client: `NuvlaClientWrapper` - A wrapper for the Nuvla API library specialized in NuvlaEdge.
        _coe_engine: `DockerClient` or `KubernetesClient` - The container orchestration engine.
        worker_manager: `WorkerManager` - The manager responsible for managing agent workers.
        action_handler: `ActionHandler` - Handles timed actions for heartbeat and telemetry.
        status_handler: `NuvlaEdgeStatusHandler` - Handles NuvlaEdge status.
        telemetry_payload: `TelemetryPayloadAttributes` - Static objects that collect telemetry data.
        telemetry_channel: `Queue` - A channel to handle telemetry payloads.
        status_channel: `Queue` - A channel to handle status reports.

    """
    # Periodic actions defaults
    telemetry_period: int = CTE.REFRESH_INTERVAL
    heartbeat_period: int = CTE.HEARTBEAT_INTERVAL

    def __init__(self,
                 exit_event: Event,
                 settings: AgentSettings):
        """
        Initializes an instance of the Agent class.

        Args:
            exit_event (Event): The event object used to signal the agent to exit.
            settings (AgentSettings): The settings object containing agent configuration.

        """
        logging.info(f"Initialising Agent Class with logger name: {__name__}")

        self.settings: AgentSettings = settings

        self._exit: Event = exit_event

        # Wrapper for Nuvla API library specialised in NuvlaEdge
        self._nuvla_client: NuvlaClientWrapper = ...
        # Container orchestration engine: either docker or k8s implementation
        self._coe_engine: COEClient = get_coe_client()

        # Agent worker manager
        self.worker_manager: WorkerManager = WorkerManager()

        # Timed actions for heartbeat and telemetry
        self.action_handler: ActionHandler = ActionHandler([])

        # Agent Status handler
        self.status_handler: NuvlaEdgeStatusHandler = self.settings.status_handler

        # Telemetry sent to nuvla
        self.telemetry_payload: TelemetryPayloadAttributes = TelemetryPayloadAttributes()
        # Telemetry channel connecting the telemetry handler and the agent
        self.telemetry_channel: Queue[TelemetryPayloadAttributes] = Queue(maxsize=10)
        # Status channel connecting any module and the status handler
        self.status_channel: Queue[StatusReport] = self.status_handler.status_channel

        # Report initial status
        NuvlaEdgeStatusHandler.starting(self.status_channel, _status_module_name)

    def _assert_current_state(self) -> State:
        """
        This method has two main functions: assert the state of NuvlaEdge and in the process instantiate a
        new object of NuvlaClientWrapper depending on the inputs provided. Scenarios:
        1. Provided UUID without local session stored. No API keys
            - We assume the state of NuvlaEdge is NEW and proceed with the installation process. Should this
            assumption be wrong, the activation process will throw the corresponding error
        2. Provided UUID with local session stored (See constant files). No API keys
            - Initialise the NuvlaClient with the stored session and then make sure the UUIDs are equal. Throw error
            if not the case
            - Also, retrieve the NuvlaEdge resource from Nuvla and return the state.
        3. Not provided UUID with local session stored. No API keys
            - Same as before but without comparing, just retrieve the information from Nuvla
        4. No UUID and no local session. No API keys
            - Not possible. Throw InsufficientInformationException
        5.  Provided UUID, no local session, API keys
            - Initialise NuvlaClient with API keys and compare remote resource with local UUID. Return the State if they
            match, throw exception if they don't
        6.  Not UUID, no local session, API key
            - Same as before without comparing

        Returns: The State of NuvlaEdge
        Raises: AgentSettingsMissMatch if the UUID's are not equal
        """

        self._nuvla_client = self.settings.nuvla_client

        _state: State = State.NEW

        # This means the agent is at least in ACTIVATED state
        if self._nuvla_client.irs or self._nuvla_client.nuvlaedge_credentials is not None:
            _state = State.value_of(self._nuvla_client.nuvlaedge.state)
        logger.info(f"Starting NuvlaEdge in state {_state}")

        return _state

    def _init_workers(self):
        """
        This method initializes and registers various workers including Commissioner, Telemetry, VPNHandler and others.
        It sets the worker properties such as `period`, `worker_type`, `init_params` and `actions`. The workers are
        added to the worker manager and are set to run at a specified interval.

        The initialization and registration of some workers, like VPNHandler, depend on certain conditions (e.g.,
        VPN server ID being present).

        No parameters required.

        Returns:
            None.

        """
        logger.info("Registering Commissioner")
        self.worker_manager.add_worker(
            period=60,
            worker_type=Commissioner,
            init_params=((), {'coe_client': self._coe_engine,
                              'nuvla_client': self._nuvla_client,
                              'status_channel': self.status_channel,
                              }),
            actions=['run'],
            initial_delay=3
        )

        """ Initialise Telemetry """
        logger.info("Registering Telemetry")
        self.worker_manager.add_worker(
            period=self.telemetry_period,
            worker_type=Telemetry,
            init_params=((), {'coe_client': self._coe_engine,
                              'status_channel': self.status_channel,
                              'report_channel': self.telemetry_channel,
                              'nuvlaedge_uuid': self._nuvla_client.nuvlaedge_uuid,
                              'excluded_monitors': self.settings.nuvlaedge_excluded_monitors,
                              'new_container_stats_supported': nuvla_support_new_container_stats(self._nuvla_client),
                              }),
            actions=['run'],
            initial_delay=8
        )

        """ Initialise VPN Handler """
        # Initialise only if VPN server ID is present on the resource
        logger.info("Registering VPN Handler")
        self.worker_manager.add_worker(
            period=60,
            worker_type=VPNHandler,
            init_params=((), {'coe_client': self._coe_engine,
                              'status_channel': self.status_channel,
                              'nuvla_client': self._nuvla_client,
                              'vpn_extra_conf': self.settings.vpn_config_extra,
                              'vpn_enable_flag': self.settings.nuvlaedge_vpn_client_enable}),
            actions=['run'],
            initial_delay=10
        )

        """ Initialise Peripheral Manager """
        logger.info("Registering Peripheral Manager")
        self.worker_manager.add_worker(
            period=120,
            worker_type=PeripheralManager,
            init_params=((), {'nuvla_client': self._nuvla_client.nuvlaedge_client,
                              'status_channel': self.status_channel,
                              'nuvlaedge_uuid': self._nuvla_client.nuvlaedge_uuid}),
            actions=['run'],
            initial_delay=30
        )

    def _init_actions(self):
        """
        Initialises the periodic actions to be run by the agent
        Returns:

        """
        # Add Heartbeat (If server is compatible)
        self.action_handler.add(
            TimedAction(
                name='heartbeat',
                period=self.heartbeat_period,
                action=self._heartbeat,
                remaining_time=CTE.HEARTBEAT_INTERVAL
            )
        )

        # Add telemetry
        self.action_handler.add(
            TimedAction(
                name='telemetry',
                period=self.telemetry_period,
                action=self._telemetry,
                remaining_time=CTE.REFRESH_INTERVAL
            )
        )

        # Period refreshing action
        self.action_handler.add(
            TimedAction(
                name='update_period',
                period=60,
                action=self._update_periodic_actions,
                remaining_time=60
            )
        )

        # Status report for Worker Manager
        self.action_handler.add(
            TimedAction(
                name='watch_workers',
                period=45,
                action=self._watch_workers,
                remaining_time=45
            )
        )
        # FUTURE: Status report for Job Manager

    def _watch_workers(self):
        """
        Checks the worker status and restarts them if needed
        Returns: None

        """
        logger.info("Checking worker status")
        logger.info(self.worker_manager.summary())

        self.worker_manager.heal_workers()

    def _install_ssh_key(self):
        """
        Installs the SSH key on the COE
        Returns: None

        """
        if self.settings.nuvlaedge_immutable_ssh_pub_key and self.settings.host_home is not None:
            logger.info(f"Installing SSH key... "
                        f"{self.settings.nuvlaedge_immutable_ssh_pub_key} on {self.settings.host_home}")
            self._coe_engine.install_ssh_key(self.settings.nuvlaedge_immutable_ssh_pub_key, self.settings.host_home)

    def start_agent(self):
        """
        Only called once at the start of NuvlaEdge. Controls the initialisation process
        of the agent starting from scratch. If restart of the agent is needed, call run
        Returns: None
        """
        # Find previous installations
        # Run start up process if needed
        logger.info("Initialising Agent...")

        # Install SSH key if provided in the settings
        self._install_ssh_key()

        # Assert current state
        current_state: State = self._assert_current_state()
        logger.info(f"NuvlaEdge initial state {current_state.name}")

        match current_state:
            case State.NEW:
                logger.info("Activating NuvlaEdge...")
                self._nuvla_client.activate()
                logger.info("Success.")

            case State.COMMISSIONED:
                logger.info("NuvlaEdge is commissioned")
                # If the state is commissioned we should try retrieving nuvlabox-status from Nuvla once
                # so there is no need to create a local stored file
                self.telemetry_payload.update(self._nuvla_client.nuvlaedge_status)
                logger.debug(f"Telemetry from Nuvla: \n "
                             f"{self.telemetry_payload.model_dump_json(indent=4, exclude_none=True, by_alias=True)}")

            case State.DECOMMISSIONED | State.DECOMMISSIONING:
                logger.error(f"Force exiting the agent due to wrong state {current_state}")
                sys.exit(1)

        # Before starting up the system and creating actions and workers we can retrieve once from Nuvla the
        # desired period of the actions and adapt the workers in consequence
        self._update_periodic_actions()
        self._init_workers()
        self._init_actions()

    def _gather_status(self, telemetry: TelemetryPayloadAttributes):
        """ Gathers the status from the workers and stores it in the telemetry payload """
        # Gather the status report
        status, notes = self.status_handler.get_status(self._coe_engine)

        logger.info(f"Status gathered: \n{status} \n {json.dumps(notes,indent=4)}")
        telemetry.status = status
        telemetry.status_notes = notes

    # Agent Actions
    def _update_periodic_actions(self):
        logger.info("Updating periodic actions...")
        # Check telemetry period
        if self._nuvla_client.nuvlaedge.refresh_interval != self.telemetry_period:
            logger.info(f"Telemetry period has changed from {self.telemetry_period} to"
                        f" {self._nuvla_client.nuvlaedge.refresh_interval}")
            self.telemetry_period = self._nuvla_client.nuvlaedge.refresh_interval
            # We should keep telemetry action and telemetry worker synchronised.
            self.worker_manager.edit_period(Telemetry, self.telemetry_period)
            self.action_handler.edit_period('telemetry', self.telemetry_period)

        # Check heartbeat period
        if self.heartbeat_period != self._nuvla_client.nuvlaedge.heartbeat_interval:
            logger.info(f"Heartbeat period has changed from {self.heartbeat_period} to"
                        f" {self._nuvla_client.nuvlaedge.heartbeat_interval}")
            self.heartbeat_period = self._nuvla_client.nuvlaedge.heartbeat_interval
            self.action_handler.edit_period('heartbeat', self.heartbeat_period)

    def _telemetry(self) -> dict | None:
        """ This method is responsible for executing the telemetry operation.
        It retrieves the telemetry data from the telemetry channel and updates the telemetry payload. If the telemetry
         channel is empty, it logs a warning and updates the status of the agent. The telemetry data is then sent to
         Nuvla via the NuvlaClientWrapper. If the telemetry data is successfully sent, the telemetry payload is
         updated and saved locally.

        Returns:
            dict | None: The response from the telemetry operation if successful, None otherwise.
        """
        logger.info("Executing telemetry...")

        # If there is no telemetry available there is nothing to do
        if self.telemetry_channel.empty():
            logger.warning("Telemetry class not reporting fast enough to Agent")
            NuvlaEdgeStatusHandler.failing(self.status_channel,
                                           _status_module_name,
                                           "Telemetry not reported fast enough")
            new_telemetry: TelemetryPayloadAttributes = self.telemetry_payload.model_copy(deep=True)
        else:
            # Retrieve telemetry. Maybe we need to consume all in order to retrieve the latest
            new_telemetry: TelemetryPayloadAttributes = self.telemetry_channel.get(block=False)
            logger.debug("Metrics received from Telemetry class")

        # Gather the status report
        self._gather_status(new_telemetry)

        # Calculate the difference from the latest telemetry sent and the new data to reduce package size
        to_send, to_delete = model_diff(self.telemetry_payload, new_telemetry)
        data_to_send: dict = new_telemetry.model_dump(exclude_none=True, by_alias=True, include=to_send)

        response: dict
        try:
            previous_data = self.telemetry_payload.model_dump(exclude_none=True, by_alias=True)
            telemetry_patch = jsonpatch.make_patch(previous_data, data_to_send)
            logger.debug(f"Sending telemetry patch data to Nuvla \n {telemetry_patch}")
            response = self._nuvla_client.telemetry_patch(list(telemetry_patch), attributes_to_delete=list(to_delete))
        except Exception as e:
            logger.warning(f'Failed to send telemetry patch data, sending standard telemetry: {e}', exc_info=True, stack_info=True)
            # Send telemetry via NuvlaClientWrapper
            logger.debug(f"Sending telemetry data to Nuvla \n "
                         f"{new_telemetry.model_dump_json(indent=4, exclude_none=True, by_alias=True, include=to_send)}")
            response = self._nuvla_client.telemetry(data_to_send, attributes_to_delete=list(to_delete))

        # If telemetry is successful save telemetry
        if not response:
            return

        logger.info("Executing telemetry... Success")
        NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)
        self.telemetry_payload = new_telemetry.model_copy(deep=True)
        write_file(self.telemetry_payload, FILE_NAMES.STATUS_FILE)

        # Send telemetry data to MQTT broker
        logger.info("Sending telemetry data to MQTT broker")
        try:
            data_gateway_client.send_telemetry(new_telemetry)
        except Exception as e:
            logger.error(f"Failed to send telemetry data to MQTT broker: {e}")
            NuvlaEdgeStatusHandler.failing(self.status_channel,
                                           _status_module_name,
                                           "Failed to send telemetry data to MQTT broker")

        return response

    def _heartbeat(self) -> dict | None:
        """
        Executes the heartbeat operation against Nuvla
        Returns: List of jobs if Nuvla Requests so
        """
        logger.info("Executing heartbeat...")

        # Usually takes ~10/15 seconds for the commissioner to commission NuvlaEdge for the first time
        # Until that happens, heartbeat operation is not available
        if (self._nuvla_client.nuvlaedge.state != State.COMMISSIONED and
                self._nuvla_client.nuvlaedge.state != 'COMMISSIONED'):

            logger.info(f"NuvlaEdge still not commissioned, cannot send heartbeat. "
                        f"Current state {self._nuvla_client.nuvlaedge.state}")
            return None

        response: dict = self._nuvla_client.heartbeat()

        if response:
            logger.info("Executing heartbeat... Success")
            NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)

        return response

    def _process_response(self, response: dict, operation: str):
        """
        Processes the response received from an operation.

        Args:
            response (CimiResponse): The response object received from the operation.
            operation (str): The operation that was executed.

        """
        start_time: float = time.perf_counter()
        jobs = response.get('jobs', [])
        logger.info(f"{len(jobs)} jobs received from operation: {operation}")
        if jobs:
            self._process_jobs([NuvlaID(j) for j in jobs])
            logger.info(f"Jobs Response process finished in {time.perf_counter() - start_time}")

    @cached_property
    def job_local(self):
        from nuvlaedge.agent.orchestrator.job_local import JobLocal
        return JobLocal(self._nuvla_client.nuvlaedge_client)

    def get_job_launcher(self, job_href) -> JobLauncher:
        if self.settings.nuvlaedge_exec_jobs_in_agent and not self.is_update_job(job_href):
            return self.job_local
        else:
            return self._coe_engine

    def is_update_job(self, job_href):
        action = self._nuvla_client.nuvlaedge_client.get(job_href).data.get('action')
        return action and (action == 'nuvlabox_update' or action == 'nuvlaedge_update')

    def _process_jobs(self, jobs: list[NuvlaID]):
        """
        Process a list of jobs.

        Args:
            jobs: A list of NuvlaID objects representing the jobs to be processed.
        """

        for job_href in jobs:
            logger.info(f"Creating job {job_href}")
            job = Job(self.get_job_launcher(job_href),
                      self._nuvla_client,
                      job_href,
                      self._coe_engine.job_engine_lite_image)
            if not job.do_nothing:
                logger.info(f"Starting job {job_href}")
                job.launch()
            else:
                logger.debug(f"Job {job.job_id} already running, do nothing")

    def stop(self):
        self._exit.set()

    def run(self):
        """
        Runs the agent by starting the worker manager and executing the actions based on the action handler's schedule.

        Returns:
            None

        """
        self.worker_manager.start()

        next_cycle_in = self.action_handler.sleep_time()
        logger.debug(f"Starting agent with action {self.action_handler.next.name} in {next_cycle_in}s")

        while not self._exit.wait(next_cycle_in):
            NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)
            start_cycle: float = time.perf_counter()

            NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)

            next_action = self.action_handler.next

            response = next_action()

            if response:
                self._process_response(response, next_action.name)

            # Account cycle time
            cycle_duration = time.perf_counter() - start_cycle
            logger.debug(f"Action {next_action.name} completed in {cycle_duration:.2f} seconds")
            logger.debug(self.action_handler.actions_summary())

            # Cycle next action time and function
            next_cycle_in = self.action_handler.sleep_time()
            next_action = self.action_handler.next
            logger.debug(self.action_handler.actions_summary())
            logger.info(f"Next action {next_action.name} will be run in {next_cycle_in:.2f} seconds")
