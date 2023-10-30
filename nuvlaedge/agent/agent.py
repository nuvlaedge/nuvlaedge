"""
This class gathers the main properties of the agent component of the NuvlaEdge engine.
Also controls the execution flow and provides utilities to the children dependencies
"""

import logging
import os
from copy import copy
from threading import Event, Thread

from nuvla.api.models import CimiResource, CimiResponse

from nuvlaedge.broker.file_broker import FileBroker
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.timed_actions import TimedAction
from nuvlaedge.peripherals.peripheral_manager import PeripheralManager

from nuvlaedge.agent.activate import Activate
from nuvlaedge.agent.common import util
from nuvlaedge.agent.infrastructure import Infrastructure
from nuvlaedge.agent.job import Job
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.orchestrator.factory import get_coe_client
from nuvlaedge.agent.telemetry import Telemetry
from nuvlaedge.agent.common.thread_handler import (is_thread_creation_needed,
                                                   create_start_thread)


class Agent:
    """
    Parent agent class in charge of gathering all the subcomponents and synchronize them
    """
    # Default shared volume location
    _DATA_VOLUME: str = "/srv/nuvlaedge/shared"

    # Event timeout controller
    agent_event: Event = Event()

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        # Class logger
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.debug('Instantiating Agent class')

        # Main NuvlaEdge data
        self.past_status_time: str = ''

        self.excluded_monitors = os.environ.get('NUVLAEDGE_EXCLUDED_MONITORS', '')

        self._activate = None
        self._coe_client = None
        self._infrastructure = None
        self._telemetry = None
        self._peripheral_manager = None

        self.infrastructure_thread = None
        self.telemetry_thread = None
        self.peripherals_thread = None

    @property
    def peripheral_manager(self) -> PeripheralManager:
        """
        Class responsible for handling peripheral reports and posting them to Nuvla
        """
        if not self._peripheral_manager:
            self.logger.info('Instantiating PeripheralManager class')
            self._peripheral_manager = PeripheralManager(
                FileBroker(),
                self.telemetry.api(),
                self.telemetry.nuvlaedge_id)
        return self._peripheral_manager

    @property
    def coe_client(self) -> COEClient:
        """ Class containing COE functions (docker or kubernetes) """
        if not self._coe_client:
            self.logger.info('Instantiating COE class')
            self._coe_client = get_coe_client()
        return self._coe_client

    @property
    def activate(self) -> Activate:
        """
        Class responsible for activating and controlling previous nuvla
        installations
        """
        if not self._activate:
            self.logger.info('Instantiating Activate class')
            self._activate = Activate(self.coe_client,
                                      self._DATA_VOLUME)
        return self._activate

    @property
    def infrastructure(self) -> Infrastructure:
        """ Intermediary class which provides and interface to communicate with nuvla """
        if not self._infrastructure:
            self.logger.info('Instantiating Infrastructure class')
            self._infrastructure = Infrastructure(self.coe_client,
                                                  self._DATA_VOLUME,
                                                  telemetry=self.telemetry)
            self.initialize_infrastructure()
        return self._infrastructure

    @property
    def telemetry(self) -> Telemetry:
        """ Telemetry updater class """
        if not self._telemetry:
            self.logger.info('Instantiating Telemetry class')
            self._telemetry = Telemetry(self.coe_client,
                                        self._DATA_VOLUME,
                                        self.nuvlaedge_status_id,
                                        self.excluded_monitors)
        return self._telemetry

    def activate_nuvlaedge(self) -> None:
        """
        Creates an "activate" object class and uses it to check the previous status
        of the NuvlaEdge. If it was activated before, it gathers the previous status.
        If not, it activates the device and again gathers the status
        """

        self.logger.info(f'Nuvla endpoint: {self.activate.nuvla_endpoint}')
        self.logger.info(
            f'Nuvla connection insecure: {str(self.activate.nuvla_endpoint_insecure)}')

        while True:
            can_activate, user_info = self.activate.activation_is_possible()
            if can_activate or user_info:
                break
            else:
                self.logger.info(
                    f'Activation not yet possible {can_activate}-{user_info}')

            self.agent_event.wait(timeout=3)

        if not user_info:
            self.logger.info('NuvlaEdge not yet activated, proceeding')
            self.activate.activate()

        # Gather resources post-activation
        nuvlaedge_resource_data, _ = self.activate.update_nuvlaedge_resource()
        self.logger.info(f'NuvlaEdge status id {self.nuvlaedge_status_id}')

    def get_nuvlaedge(self) -> CimiResource:
        return self.activate.get_nuvlaedge()

    @property
    def nuvlaedge_resource(self) -> CimiResource:
        if not self.activate.nuvlaedge_resource:
            self.get_nuvlaedge()
        return self.activate.nuvlaedge_resource

    @property
    def nuvlaedge_operations(self) -> dict:
        return self.nuvlaedge_resource.operations

    @property
    def nuvlaedge_status_id(self) -> str:
        return self.nuvlaedge_resource.data.get(CTE.NUVLAEDGE_STATUS_RES_NAME)

    @property
    def nuvlaedge_updated_date(self) -> str:
        return self.nuvlaedge_resource.data.get('updated')

    @property
    def is_heartbeat_supported_server_side(self) -> bool:
        return 'heartbeat' in self.nuvlaedge_operations

    def initialize_infrastructure(self) -> None:
        """
        Initializes the infrastructure class

        Returns: None
        """
        if not self.infrastructure.installation_home:
            self.logger.warning('Host user home directory not defined.'
                                'This might impact future SSH management actions')
        else:
            util.atomic_write(self.infrastructure.host_user_home_file,
                              self.infrastructure.installation_home,
                              encoding='UTF-8')
            self.infrastructure.set_immutable_ssh_key()

    def initialize_agent(self) -> bool:
        """
        This method sequentially initializes al the NuvlaEdge main components.

        Returns: True if the initialization is successful.  False, otherwise

        """
        # 1. Proceed with the initialization of the NuvlaEdge
        self.activate_nuvlaedge()
        return True

    def _log_jobs(self, response, source=''):
        try:
            jobs_count = len(response.data.get("jobs", []))
            self.logger.info(f'{jobs_count} jobs received in the {source} response')
        except Exception as e:
            self.logger.debug(f'Failed to log jobs count: {e}')

    def send_heartbeat(self, update_periods=None) -> dict:
        """
        Send heartbeat

        Args:
            update_periods: function to call to update periods

        Returns: a dict with the response from Nuvla
        """
        if not self.is_heartbeat_supported_server_side:
            self.logger.info('Heartbeat not supported by Nuvla server. Skipping heartbeat')
            return {}

        response: CimiResponse = self.telemetry.api().operation(
            self.nuvlaedge_resource, 'heartbeat')

        self._log_jobs(response, 'heartbeat')

        doc_last_updated = response.data.get('doc-last-updated')
        if doc_last_updated and doc_last_updated != self.nuvlaedge_updated_date:
            self.get_nuvlaedge()
            if update_periods:
                update_periods(self.nuvlaedge_resource.data)

        return response.data

    def send_telemetry(self) -> dict:
        """
        Updates the NuvlaEdge Status according to the local status file

        Returns: a dict with the response from Nuvla
        """
        self.logger.debug(f'send_telemetry(, '
                          f'{self.telemetry}, {self.nuvlaedge_status_id},'
                          f' {self.past_status_time})')

        # Calculate differences NE-Nuvla status
        status, _del_attr = self.telemetry.diff(self.telemetry.status_on_nuvla,
                                                self.telemetry.status)
        status_current_time = self.telemetry.status.get('current-time', '')
        del_attr: list = []
        self.logger.debug(f'send_telemetry: status_current_time = {status_current_time} '
                          f'_delete_attributes = {_del_attr}  status = {status}')

        if not status_current_time:
            status = {'status-notes': ['NuvlaEdge Telemetry is starting']}
            self.telemetry.status.update(status)
        else:
            if status_current_time <= self.past_status_time:
                status = {
                    'status-notes': status.get('status-notes', []) + [
                        'NuvlaEdge telemetry is falling behind'],
                    'status': 'DEGRADED'
                }
                self.telemetry.status.update(status)
            else:
                del_attr = _del_attr

        if del_attr:
            self.logger.info(f'Deleting the following attributes from NuvlaEdge Status: '
                             f'{", ".join(del_attr)}')

        try:
            response: CimiResponse = self.telemetry.api().edit(
                self.nuvlaedge_status_id,
                data=status,
                select=del_attr)

            self.telemetry.status_on_nuvla.update(status)

            self._log_jobs(response, 'telemetry')

        except Exception as e:
            self.logger.error(f'Unable to send telemetry to Nuvla: {e}')
            raise

        self.past_status_time = copy(status_current_time)

        return response.data

    def run_pull_jobs(self, job_list):
        """
        Handles the pull jobs one by one, sequentially
        Args:
            job_list: list of job IDs
        """
        for job_id in job_list:
            job: Job = Job(self.coe_client,
                           self._DATA_VOLUME,
                           job_id,
                           self.infrastructure.coe_client.job_engine_lite_image)

            if not job.do_nothing:

                try:
                    job.launch()
                except Exception as ex:
                    # catch all
                    self.logger.error(f'Cannot process job {job_id}. Reason: {str(ex)}')

    def handle_pull_jobs(self, response: dict):
        """
        Reads the response from the heartbeat and executes the jobs received from Nuvla
        Args:
            response: Heartbeat received response

        Returns:

        """
        pull_jobs: list = response.get('jobs', [])
        if not isinstance(pull_jobs, list):
            self.logger.warning(f'Jobs received on format not compatible: {response.get("jobs")}')
            return

        if pull_jobs:
            self.logger.info(f'Processing following jobs in pull mode: {pull_jobs}')

            Thread(
                target=self.run_pull_jobs,
                args=(pull_jobs,),
                daemon=True).start()

        else:
            self.logger.debug('No pull jobs to run')

    def run_single_cycle(self, action: TimedAction):
        """
        Controls the main functionalities of the agent:
            1. Sending heartbeat
            2. Running pull jobs

        Args:
            action: Action to be executed in the cycle

        Returns: None

        """

        if action.name == 'telemetry':
            if is_thread_creation_needed('Telemetry', self.telemetry_thread,
                                         log_not_alive=(logging.DEBUG, 'Recreating {} thread.'),
                                         log_alive=(logging.WARNING, 'Thread {} taking too long to complete')):
                self.telemetry_thread = create_start_thread(
                    name='Telemetry',
                    target=self.telemetry.update_status)

            if is_thread_creation_needed('PeripheralManager', self.peripherals_thread):
                self.peripherals_thread = create_start_thread(
                    name='PeripheralManager',
                    target=self.peripheral_manager.run)

        response: dict = action()
        if response:
            self.handle_pull_jobs(response)

        if is_thread_creation_needed('Infrastructure', self.infrastructure_thread):
            self.infrastructure_thread = create_start_thread(
                name='Infrastructure',
                target=self.infrastructure.run)
