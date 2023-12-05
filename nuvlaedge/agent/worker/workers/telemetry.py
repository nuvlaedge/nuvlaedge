"""

"""
import json
import logging
import threading
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from nuvlaedge.agent.monitor.edge_status import EdgeStatus
from nuvlaedge.agent.monitor.components import get_monitor, active_monitors
from nuvlaedge.agent.monitor import Monitor
from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import Status
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.agent.common.thread_handler import is_thread_creation_needed


logger: logging.Logger = logging.getLogger(__name__)


class TelemetryPayloadAttributes(NuvlaEdgeStaticModel):
    status:                         Optional[Status] = None
    status_notes:                   Optional[list[str]] = None
    current_time:                   Optional[datetime] = None

    # NuvlaEdge System configuration
    components:                     Optional[dict] = None
    nuvlabox_api_endpoint:          Optional[str] = None
    nuvlabox_engine_version:        Optional[str] = None
    installation_parameters:        Optional[list] = None
    host_user_home:                 Optional[str] = None

    # Metrics
    resources:                      Optional[dict] = None
    last_boot:                      Optional[datetime] = None
    gpio_pins:                      Optional[dict] = None
    vulnerabilities:                Optional[dict] = None
    inferred_location:              Optional[list[float]] = None
    network:                        Optional[dict] = None
    temperatures:                   Optional[dict] = None

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
    swarm_node_cert_expiry_date:    Optional[str] = None
    cluster_join_address:           Optional[str] = None
    orchestrator:                   Optional[str] = None
    container_plugins:              Optional[str] = None
    kubelet_version:                Optional[str] = None

    _update_lock: threading.Lock = threading.Lock()

    def update(self, data: dict[str, any] | BaseModel):
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_none=True)

        for k, v in data.items():
            if hasattr(self, k):
                with self._update_lock:
                    self.__setattr__(k, v)


class Telemetry:

    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 telemetry_payload: TelemetryPayloadAttributes,
                 excluded_monitors):
        logger.debug("Initialising Telemetry")

        self.coe_client = coe_client
        self.nuvla_client = nuvla_client

        """ Static variable from where the agent retrieves the information agent """
        self.telemetry_payload: TelemetryPayloadAttributes = telemetry_payload

        """ Data variable where the monitors dump their readings """
        self.edge_status: EdgeStatus = EdgeStatus()

        """ Monitors modular system initialisation """
        self.excluded_monitors: list[str] = excluded_monitors.replace("'", "").split(',')
        logger.info(f'Excluded monitors received in Telemetry: {self.excluded_monitors}')
        self.monitor_list: dict[str, Monitor] = {}
        # self.initialize_monitors()

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

    def collect_monitor_metrics(self, telemetry: TelemetryPayloadAttributes):
        """

        Args:
            telemetry:

        Returns:

        """
        # Retrieve monitoring data
        for it_monitor in self.monitor_list.values():
            temp_dict = {}
            try:
                if it_monitor.updated:
                    it_monitor.populate_nb_report(temp_dict)
                else:
                    logger.info(f'Data not updated yet in monitor {it_monitor.name}')
            except Exception as ex:
                logger.exception(f'Error retrieving data from monitor {it_monitor.name}.', ex)
                continue

            telemetry.update(temp_dict)

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

    def run(self):
        logger.info("Collection monitor metrics...")
        self.check_monitors_health()

        collected_telemetry = self.telemetry_payload.model_copy(deep=True)
        self.collect_monitor_metrics(collected_telemetry)

        if collected_telemetry != self.telemetry_payload:
            self.telemetry_payload.update(collected_telemetry)
        self.telemetry_payload.current_time = datetime.utcnow().isoformat().split('.')[0] + 'Z'
        logger.info(f"Metrics collected at time {self.telemetry_payload.current_time}")
