import inspect
import json
import logging
import sys
import time
from queue import Queue
from threading import Event

from nuvla.api.models import CimiResponse

from nuvlaedge.common.constants import CTE
from nuvlaedge.common.timed_actions import ActionHandler, TimedAction
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.utils import file_exists_and_not_empty
from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.agent.workers.peripheral_manager import PeripheralManager
from nuvlaedge.agent.workers.commissioner import CommissioningAttributes, Commissioner
from nuvlaedge.agent.workers.telemetry import TelemetryPayloadAttributes, Telemetry, model_diff
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.nuvla.resources.nuvlaedge import State
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper, NuvlaApiKeyTemplate
from nuvlaedge.agent.manager import WorkerManager
from nuvlaedge.agent.settings import (AgentSettings,
                                      AgentSettingsMissMatch,
                                      InsufficientSettingsProvided)
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient
from nuvlaedge.agent.orchestrator.factory import get_coe_client


logger: logging.Logger = logging.getLogger(__name__)


class Agent:
    def __init__(self,
                 exit_event: Event,
                 settings: AgentSettings):

        logging.debug(f"Initialising Agent Class")

        self.settings: AgentSettings = settings

        self._exit: Event = exit_event

        # Wrapper for Nuvla API library specialised in NuvlaEdge
        self._nuvla_client: NuvlaClientWrapper = ...
        # Container orchestration engine: either docker or k8s implementation
        self._coe_engine: DockerClient | KubernetesClient = get_coe_client()

        # Agent worker manager
        self.worker_manager: WorkerManager = WorkerManager()

        # Timed actions for heartbeat and telemetry
        self.action_handler: ActionHandler = ActionHandler([])

        # Static objects
        self.telemetry_payload: TelemetryPayloadAttributes = TelemetryPayloadAttributes()
        self.telemetry_channel: Queue[TelemetryPayloadAttributes] = Queue(maxsize=10)

        self.commission_payload: CommissioningAttributes = CommissioningAttributes()

    def assert_current_state(self) -> State:
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
        def check_uuid_missmatch(env_uuid, other_uuid):
            """

            Args:
                env_uuid: UUID parsed as an environmental variable
                other_uuid: UUID stored locally or retrieved from API keys

            Returns: None
            Raises: AgentSettingsMissMatch if the UUID's are not equal

            """
            # Check UUID missmatch
            if env_uuid != other_uuid:
                logger.error(f"Parsed UUID {env_uuid} is different from the locally stored "
                             f"{other_uuid} session. You are probably trying to install a "
                             f"new NuvlaEdge, please remove previous volumes and installation files")
                raise AgentSettingsMissMatch(f"Provided NuvlaEdge UUID {env_uuid} must"
                                             f"match the locally stored. Remove previous installation of NuvlaEdge")

        # Stored session found -> Previous installation
        if file_exists_and_not_empty(FILE_NAMES.NUVLAEDGE_SESSION):
            logger.info("Starting NuvlaEdge from previously stored session")
            self._nuvla_client = NuvlaClientWrapper.from_session_store(FILE_NAMES.NUVLAEDGE_SESSION)

            if self.settings.nuvlaedge_uuid:
                check_uuid_missmatch(self.settings.nuvlaedge_uuid, self._nuvla_client.nuvlaedge.id)

            return State.value_of(self._nuvla_client.nuvlaedge.state)

        # API keys log-in
        if self.settings.nuvlaedge_api_key is not None and self.settings.nuvlaedge_api_secret is not None:
            logger.info("Logging in with keys parsed from Environmental variables")
            self._nuvla_client = NuvlaClientWrapper.from_nuvlaedge_credentials(
                host=self.settings.nuvla_endpoint,
                verify=not self.settings.nuvla_endpoint_insecure,
                credentials=NuvlaApiKeyTemplate(key=self.settings.nuvlaedge_api_key,
                                                secret=self.settings.nuvlaedge_api_secret
                                                )
            )

            if self.settings.nuvlaedge_uuid:
                check_uuid_missmatch(self.settings.nuvlaedge_uuid, self._nuvla_client.nuvlaedge.id)
            return self._nuvla_client.nuvlaedge.state

        # If we reached this point we should have a NEW Nuvlaedge, and we need the uuid to start
        if not self.settings.nuvlaedge_uuid:
            raise InsufficientSettingsProvided("No UUID provided and no previous installation found. To continue, "
                                               "create a new NuvlaEdge and configure the Environmental variable "
                                               "NUVLAEDGE_UUID")

        self._nuvla_client = NuvlaClientWrapper.from_agent_settings(self.settings)
        return State.NEW

    def init_workers(self):
        """

        Returns:

        """
        """ Initialise Commissioner"""
        logger.info("Registering Commissioner")
        self.worker_manager.add_worker(
            period=60,
            worker_type=Commissioner,
            init_params=((), {'coe_client': self._coe_engine,
                              'nuvla_client': self._nuvla_client,
                              'vpn_channel': Queue[dict]()
                              }),
            actions=['run'],
            initial_delay=1
        )

        """ Initialise Telemetry """
        logger.info("Registering Telemetry")
        self.worker_manager.add_worker(
            period=60,
            worker_type=Telemetry,
            init_params=((), {'coe_client': self._coe_engine,
                              'report_channel': self.telemetry_channel,
                              'nuvlaedge_uuid': self._nuvla_client.nuvlaedge_uuid,
                              'excluded_monitors': self.settings.nuvlaedge_excluded_monitors
                              }),
            actions=['run']
        )

        """ Initialise VPN Handler """
        # Initialise only if VPN server ID is present on the resource
        # logger.info("Registering VPN Handler")
        # if self._nuvla_client.nuvlaedge.vpn_server_id:
        #     self.worker_manager.add_worker(
        #         period=60,
        #         worker_type=VPNHandler,
        #         init_params=((), {'coe_client': self._coe_engine,
        #                           'nuvla_client': self._nuvla_client,
        #                           'commission_payload': self.commission_payload}),
        #         actions=['run']
        #     )

        """ Initialise Peripheral Manager """
        # logger.info("Registering Peripheral Manager")
        # self.worker_manager.add_worker(
        #     period=120,
        #     worker_type=PeripheralManager,
        #     init_params=((), {'nuvla_client': self._nuvla_client.nuvlaedge_client,
        #                       'nuvlaedge_uuid': self._nuvla_client.nuvlaedge_uuid}),
        #     actions=['run']
        # )

        """ Initialise Job Manager """
        # logger.info("Registering Job Manager")
        pass

    def init_actions(self):
        """
        Initialises the periodic actions to be run by the agent
        Returns:

        """
        """ Add Heartbeat (If server is compatible) """
        self.action_handler.add(
            TimedAction(
                name='heartbeat',
                period=CTE.HEARTBEAT_INTERVAL,
                action=self.heartbeat,
                remaining_time=CTE.HEARTBEAT_INTERVAL
            )
        )

        """ Add telemetry """
        self.action_handler.add(
            TimedAction(
                name='telemetry',
                period=CTE.REFRESH_INTERVAL,
                action=self.telemetry,
                remaining_time=CTE.REFRESH_INTERVAL
            )
        )

        """ Status report for Worker Manager """
        """ Status report for Job Manager """

    def start_agent(self):
        """
        Only called once at the start of NuvlaEdge. Controls the initialisation process
        of the agent starting from scratch. If restart of the agent is needed, call run
        Returns: None
        """
        # Find previous installations
        # Run start up process if needed
        logger.info("Initialising Agent...")

        current_state: State = self.assert_current_state()
        logger.info(f"NuvlaEdge initial state {current_state.name}")

        if current_state == State.NEW:
            logger.info("Activating NuvlaEdge...")
            self._nuvla_client.activate()
            logger.info("Success.")

        if current_state in [State.DECOMMISSIONED, State.DECOMMISSIONING]:
            logger.error(f"Force exiting the agent due to wrong state {current_state}")
            sys.exit(1)

        self.init_workers()
        self.init_actions()

    """ Agent Actions """
    def telemetry(self) -> CimiResponse | None:
        """
        Gather the information from the workers and executes the telemetry operation against Nuvla
        Returns: List of jobs if Nuvla requests so

        """
        logger.info("Executing telemetry")
        if self.telemetry_channel.empty():
            logger.warning("Telemetry class not reporting fast enough to Agent")
            return None

        new_telemetry: TelemetryPayloadAttributes = self.telemetry_channel.get(block=False)

        to_send, to_delete = model_diff(self.telemetry_payload, new_telemetry)
        data_to_send: dict = new_telemetry.model_dump(exclude_none=True, by_alias=True, include=to_send)

        logger.debug(f"Sending telemetry data to Nuvla {json.dumps(data_to_send, indent=4)}")
        response: CimiResponse = self._nuvla_client.telemetry(data_to_send, attributes_to_delete=to_delete)

        return response

    def heartbeat(self) -> CimiResponse | None:
        """
        Executes the heartbeat operation against Nuvla
        Returns: List of jobs if Nuvla Requests so
        """
        logger.info("Executing heartbeat")
        if (self._nuvla_client.nuvlaedge.state != State.COMMISSIONED and
                self._nuvla_client.nuvlaedge.state != 'COMMISSIONED'):

            logger.info(f"NuvlaEdge still not commissioned, cannot send heartbeat. "
                        f"Current state {self._nuvla_client.nuvlaedge.state}")
            return None

        return self._nuvla_client.heartbeat()

    def process_response(self, response: CimiResponse, operation: str):
        jobs = response.data.get('jobs', [])
        logger.info(f"{len(jobs)} received in from {operation}")
        if jobs:
            logger.info("{}")
            self.process_jobs([NuvlaID(j) for j in jobs])

    def process_jobs(self, jobs: list[NuvlaID]):
        ...

    def stop(self):
        self._exit.set()

    def run(self):
        self.worker_manager.start()

        next_cycle_in = self.action_handler.sleep_time()
        logger.info(f"Starting agent with action {self.action_handler.next.name} in {next_cycle_in}s")
        logger.debug(self.action_handler.actions_summary())

        while not self._exit.wait(next_cycle_in):
            start_cycle: float = time.perf_counter()
            next_action = self.action_handler.next
            response = next_action()

            if response:
                self.process_jobs(response)

            # Account cycle time
            cycle_duration = time.perf_counter() - start_cycle
            logger.info(f"Action {next_action.name} completed in {cycle_duration:.2f} seconds")

            # Cycle next action time and function
            next_cycle_in = self.action_handler.sleep_time()
            next_action = self.action_handler.next
            logger.info(self.action_handler.actions_summary())
            logger.info(f"Next action {next_action.name} will be run in {next_cycle_in:.2f} seconds")

