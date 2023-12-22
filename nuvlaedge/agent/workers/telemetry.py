"""

"""
import json
import logging
from queue import Queue, Full
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus
from nuvlaedge.agent.workers.monitor.components import get_monitor, active_monitors
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import Status
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.common.thread_handler import is_thread_creation_needed


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class TelemetryPayloadAttributes(NuvlaEdgeStaticModel):
    """

    The TelemetryPayloadAttributes class represents the attributes of a telemetry payload for NuvlaEdge.

    Attributes:
        status (Optional[Status]): The status of the NuvlaEdge system.
        status_notes (Optional[list[str]]): Any additional notes about the status.
        current_time (Optional[str]): The current time of the NuvlaEdge system.

        components (Optional[list[str]]): The components of the NuvlaEdge system.
        nuvlabox_api_endpoint (Optional[str]): The API endpoint of the NuvlaBox.
        nuvlabox_engine_version (Optional[str]): The version of the NuvlaBox engine.
        installation_parameters (Optional[dict]): The installation parameters of the NuvlaBox.
        host_user_home (Optional[str]): The home directory of the NuvlaBox host user.

        resources (Optional[dict]): The resources of the NuvlaEdge system.
        last_boot (Optional[str]): The last boot time of the NuvlaEdge system.
        gpio_pins (Optional[dict]): The GPIO pins of the NuvlaEdge system.
        vulnerabilities (Optional[dict]): The vulnerabilities of the NuvlaEdge system.
        inferred_location (Optional[list[float]]): The inferred location of the NuvlaEdge system.
        network (Optional[dict]): The network configuration of the NuvlaEdge system.
        temperatures (Optional[list]): The temperatures of the NuvlaEdge system.

        operating_system (Optional[str]): The operating system of the NuvlaEdge system.
        architecture (Optional[str]): The architecture of the NuvlaEdge system.
        ip (Optional[str]): The IP address of the NuvlaEdge system.
        hostname (Optional[str]): The hostname of the NuvlaEdge system.
        docker_server_version (Optional[str]): The version of the Docker server.

        node_id (Optional[str]): The ID of the cluster node.
        cluster_id (Optional[str]): The ID of the cluster.
        cluster_managers (Optional[list[str]]): The managers of the cluster.
        cluster_nodes (Optional[list[str]]): The nodes of the cluster.
        cluster_node_role (Optional[str]): The role of the cluster node.
        cluster_node_labels (Optional[list[dict]]): The labels of the cluster node.
        swarm_node_cert_expiry_date (Optional[str]): The expiry date of the swarm node certificate.
        cluster_join_address (Optional[str]): The join address of the cluster.
        orchestrator (Optional[str]): The orchestrator used by the cluster.
        container_plugins (Optional[list[str]]): The container plugins used by the cluster.
        kubelet_version (Optional[str]): The version of the kubelet.

    """
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
    Calculate the differences between two models.

    Args:
        reference (BaseModel): The reference model to compare against.
        target (BaseModel): The target model to compare with.

    Returns:
        tuple[set[str], set[str]]: A tuple containing two sets. The first set contains the fields that have different values between the reference and target models. The second set contains
    * the fields that exist in the reference model but not in the target model.
    """
    to_send: set = set()
    for field, value in iter(target):
        if value != getattr(reference, field) and value is not None:
            to_send.add(field)
    to_delete = reference.model_fields_set - target.model_fields_set
    return to_send, to_delete


class Telemetry:
    """
    The Telemetry class is responsible for collecting and synchronizing telemetry data from various monitors and system
     information. It provides methods to initialize monitors, collect monitor metrics, check monitor health, sync
     status to telemetry, and run the telemetry collection process.

    Attributes:
        - coe_client: The COEClient object used to communicate with the COE API.
        - report_channel: The Queue object used to send telemetry data to the agent.
        - nuvlaedge_uuid: The NuvlaID object representing the UUID of the NuvlaEdge instance.
        - excluded_monitors: A list of monitor names that should be excluded from telemetry collection.

    Methods:
        - __init__(self, coe_client: COEClient, report_channel: Queue[TelemetryPayloadAttributes], nuvlaedge_uuid: NuvlaID, excluded_monitors):
        Initializes the Telemetry object with the given COEClient, report channel, NuvlaEdge UUID, and excluded monitors.

        - initialize_monitors(self):
        Auxiliary function to extract some control from the class initialization
        It gathers the available monitors and initializes them saving the reference into
        the monitor_list attribute of Telemetry.

        - collect_monitor_metrics(self):
        Collects monitoring data from the initialized monitors and populates the local telemetry attribute.

        - check_monitors_health(self):
        Checks the health of the initialized monitors. If a monitor is threaded and not alive, it recreates the thread.

        - sync_status_to_telemetry(self):
        Synchronizes the EdgeStatus object with Telemetry Data.

        - run(self):
        Executes the telemetry collection process. It collects monitor metrics, checks monitor health, syncs status to telemetry, and sends the telemetry data to the agent queue.

    Note: Make sure to call the run() method to start the telemetry collection process.
    """
    def __init__(self,
                 coe_client: COEClient,
                 report_channel: Queue[TelemetryPayloadAttributes],
                 status_channel: Queue[StatusReport],
                 nuvlaedge_uuid: NuvlaID,
                 excluded_monitors):
        """
        Initializes the Telemetry object with the given parameters.

        Args:
            coe_client (COEClient): The COEClient object for interacting with the COE API.
            report_channel (Queue[TelemetryPayloadAttributes]): The report channel to communicate with the Agent.
            nuvlaedge_uuid (NuvlaID): The NuvlaID object representing the NuvlaEdge UUID.
            excluded_monitors: The list of excluded monitors as a comma-separated string.

        """
        logger.info(f"Initialising Telemetry with logger name {__name__}")

        self.coe_client = coe_client
        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid

        """ Local variable to track changes on the telemetry """
        self._local_telemetry: TelemetryPayloadAttributes = TelemetryPayloadAttributes()

        """ Channel to communicate with the Agent"""
        self.report_channel: Queue[TelemetryPayloadAttributes] = report_channel

        """ Channel to report status """
        self.status_channel: Queue[StatusReport] = status_channel

        """ Data variable where the monitors dump their readings """
        self.edge_status: EdgeStatus = EdgeStatus()

        """ Monitors modular system initialisation """
        self.excluded_monitors: list[str] = excluded_monitors.replace("'", "").split(',') if excluded_monitors else []
        logger.info(f'Excluded monitors received in Telemetry: {self.excluded_monitors}')
        self.monitor_list: dict[str, Monitor] = {}
        self.initialize_monitors()

        NuvlaEdgeStatusHandler.starting(self.status_channel, 'telemetry')

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
        Collects monitoring metrics from the monitor list and updates the local telemetry data.

        Returns:
            None
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
        """
        Check the health of all monitors in the monitor list.

        This method iterates through each monitor in the monitor list and performs the following tasks:
        - Prints the monitor's name, whether it's threaded, and whether it's alive using the logger.debug() function.
        - If the monitor is threaded and needs to be recreated, it calls the is_thread_creation_needed() method with appropriate parameters for logging. If the method returns True, a new instance
        * of the monitor with the same name is created and started, replacing the old instance in the monitor list.
        - If the monitor is not threaded, it calls the run_update_data() method of the monitor with the monitor_name parameter.
        - After processing all monitors, it creates a dictionary monitor_process_duration that maps each monitor's name to its last process's duration.
        - Finally, it logs the monitor_process_duration dictionary using logger.debug().

        Returns:
            None
        """
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
        """
        Collects monitor metrics, checks threaded monitors health,
        retrieves data from metrics and system information class,
        conforms the telemetry payload, and writes telemetry to the Agent Queue.

        Returns:
            None
        """
        NuvlaEdgeStatusHandler.running(self.status_channel, 'telemetry')

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
            # TODO: Should we empty the channel here?

