"""

"""
import json
import logging
from queue import Queue, Full
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus
from nuvlaedge.agent.workers.monitor.components import get_monitor, active_monitors
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import Status
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.common.thread_handler import is_thread_creation_needed


logger: logging.Logger = logging.getLogger(__name__)


class TelemetryPayloadAttributes(NuvlaEdgeStaticModel):
    status:                         Optional[Status] = None
    status_notes:                   Optional[list[str]] = None
    current_time:                   Optional[str] = None

    # NuvlaEdge System configuration
    components:                     Optional[list[str]] = None
    nuvlabox_api_endpoint:          Optional[str] = None
    nuvlabox_engine_version:        Optional[str] = None
    installation_parameters:        Optional[dict] = None
    host_user_home:                 Optional[str] = None

    # Metrics
    resources:                      Optional[dict] = None
    last_boot:                      Optional[str] = None
    gpio_pins:                      Optional[dict] = None
    vulnerabilities:                Optional[dict] = None
    inferred_location:              Optional[list[float]] = None
    network:                        Optional[dict] = None
    temperatures:                   Optional[list] = None

    # System Configuration
    operating_system:               Optional[str] = None
    architecture:                   Optional[str] = None
    ip:                             Optional[str] = None
    hostname:                       Optional[str] = None
    docker_server_version:          Optional[str] = None

    # Cluster information
    node_id:                        Optional[str] = None
    cluster_id:                     Optional[str] = None
    cluster_managers:               Optional[list[str]] = None
    cluster_nodes:                  Optional[list[str]] = None
    cluster_node_role:              Optional[str] = None
    cluster_node_labels:            Optional[list[dict]] = None
    swarm_node_cert_expiry_date:    Optional[str] = None
    cluster_join_address:           Optional[str] = None
    orchestrator:                   Optional[str] = None
    container_plugins:              Optional[list[str]] = None
    kubelet_version:                Optional[str] = None


def model_diff(reference: BaseModel, target: BaseModel) -> tuple[set[str], set[str]]:
    """
    Compares two Pydantic base classes and returns a tuple of the fields present in the target and not equal to the f
    fields present in the reference. And another set with the fields that are present in the reference but not in the
    target
    Args:
        reference:
        target:

    Returns:

    """
    to_send: set = set()
    for field, value in iter(target):
        if value != getattr(reference, field):
            to_send.add(field)
    to_delete = reference.model_fields_set - target.model_fields_set
    return to_send, to_delete


class Telemetry:

    def __init__(self,
                 coe_client: COEClient,
                 report_channel: Queue[TelemetryPayloadAttributes],
                 nuvlaedge_uuid: NuvlaID,
                 excluded_monitors):
        logger.debug("Initialising Telemetry")

        self.coe_client = coe_client
        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid

        """ Local variable to track changes on the telemetry """
        self._local_telemetry: TelemetryPayloadAttributes = TelemetryPayloadAttributes()

        """ Channel to communicate with the Agent"""
        self.report_channel: Queue[TelemetryPayloadAttributes] = report_channel

        """ Data variable where the monitors dump their readings """
        self.edge_status: EdgeStatus = EdgeStatus()

        """ Monitors modular system initialisation """
        self.excluded_monitors: list[str] = excluded_monitors.replace("'", "").split(',') if excluded_monitors else []
        logger.info(f'Excluded monitors received in Telemetry: {self.excluded_monitors}')
        self.monitor_list: dict[str, Monitor] = {}
        self.initialize_monitors()

    def initialize_monitors(self):
        """
        Auxiliary function to extract some control from the class initialization
        It gathers the available monitors and initializes them saving the reference into
        the monitor_list attribute of Telemetry
        """
        for mon in active_monitors:
            if mon.rsplit('_', 1)[0] in self.excluded_monitors:
                continue
            self.monitor_list[mon] = (get_monitor(mon)(mon, self, True))

    def collect_monitor_metrics(self):
        """

        Returns:

        """
        # Retrieve monitoring data
        temp_dict = {}
        for it_monitor in self.monitor_list.values():
            try:
                if it_monitor.updated:
                    it_monitor.populate_nb_report(temp_dict)
                else:
                    logger.info(f'Data not updated yet in monitor {it_monitor.name}')
            except Exception as ex:
                logger.exception(f'Error retrieving data from monitor {it_monitor.name}.', ex)
                continue

        self._local_telemetry.update(temp_dict)

    def check_monitors_health(self):
        for monitor_name, it_monitor in self.monitor_list.items():
            logger.debug(f'Monitor: {it_monitor.name} - '
                         f'Threaded: {it_monitor.is_thread} - '
                         f'Alive: {it_monitor.is_alive()}')

            if it_monitor.is_thread:
                if is_thread_creation_needed(
                        monitor_name,
                        it_monitor,
                        log_not_alive=(logging.INFO, 'Recreating {} thread.'),
                        log_alive=(logging.DEBUG, 'Thread {} is alive'),
                        log_not_exist=(logging.INFO, 'Creating {} thread.')):
                    monitor = get_monitor(monitor_name)(monitor_name, self, True)
                    monitor.start()
                    self.monitor_list[monitor_name] = monitor

            else:
                it_monitor.run_update_data(monitor_name=monitor_name)

        monitor_process_duration = {k: v.last_process_duration for k, v in self.monitor_list.items()}
        logger.debug(f'Monitors processing duration: {json.dumps(monitor_process_duration, indent=4)}')

    def sync_status_to_telemetry(self):
        """
        Synchronises EdgeStatus object with Telemetry Data.
        TODO: This needs rework so the monitors automatically report their data into a TelemetryPayload

        Returns: None

        """

        # Iterate EdgeStatus attributes
        for attr, value in iter(self.edge_status):
            if isinstance(value, BaseModel):
                # Dump the model
                data = value.model_dump(exclude_none=True, by_alias=True)

                # Clean the empty objects such as dict = {}, list = [], str = '', etc (Not accepted by Nuvla)
                data = {k: v for k, v in data.items() if v}
                if data:
                    self._local_telemetry.update(data)

        # Clean the model from empty fields

    def run(self):
        logger.info("Collecting monitor metrics...")
        """ Retrieve data from monitors (If not threaded) and check threaded monitors health"""
        self.check_monitors_health()
        self.collect_monitor_metrics()
        logger.info("Translating telemetry data")
        """ Retrieve data from metrics and system information class (EdgeStatus)  and conform the telemetry payload """
        self.sync_status_to_telemetry()

        """ We make sure at least one field changes so telemetry is always sent. Current Time for synchronization """
        self._local_telemetry.current_time = datetime.utcnow().isoformat().split('.')[0] + 'Z'

        try:
            logger.debug(f"Writing telemetry to Agent Queue"
                         f" {self._local_telemetry.model_dump_json(indent=4, exclude_none=True, by_alias=True)}")
            self.report_channel.put(self._local_telemetry, block=False)

        except Full:
            logger.warning("Telemetry Queue is full, agent not consuming data...")
