"""

"""
import logging
import threading
import time
from queue import Queue, Empty
from datetime import datetime, UTC

from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.agent.common.thread_handler import is_thread_creation_needed
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.nuvla.resources.telemetry_payload import TelemetryPayloadAttributes
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.workers.monitor.components import get_monitor, active_monitors
from nuvlaedge.agent.workers.monitor import Monitor, BaseDataStructure
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.utils import dump_dict_to_str

logger: logging.Logger = get_nuvlaedge_logger(__name__)
_status_module_name = 'Telemetry'


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

    Note: Make sure to call the run() method to start the telemetry collection process.
    """
    def __init__(self,
                 coe_client: COEClient,
                 status_channel: Queue[StatusReport],
                 nuvlaedge_uuid: NuvlaID,
                 excluded_monitors,
                 coe_resources_supported,
                 new_container_stats_supported,
                 telemetry_period: int = 60):
        """
        Initializes the Telemetry object with the given parameters. It is also in charge of initialising the child
         sub-monitors

        Args:
            coe_client (COEClient): The COEClient object for interacting with the COE API.
            nuvlaedge_uuid (NuvlaID): The NuvlaID object representing the NuvlaEdge UUID.
            excluded_monitors: The list of excluded monitors as a comma-separated string.

        """
        logger.info("Creating Telemetry object...")

        self.coe_client = coe_client
        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid

        # Local variable to track changes on the telemetry
        self._telemetry_lock: threading.Lock = threading.Lock()
        self._local_telemetry: TelemetryPayloadAttributes = TelemetryPayloadAttributes()
        self._last_telemetry: TelemetryPayloadAttributes = TelemetryPayloadAttributes()

        # Monitors should report metrics to this channel
        self.metrics_channel: Queue[BaseDataStructure] = Queue()

        # Channel to report status
        self.status_channel: Queue[StatusReport] = status_channel

        self.coe_resources_supported = coe_resources_supported
        self.new_container_stats_supported = new_container_stats_supported

        # Monitors modular system initialisation
        self.excluded_monitors: list[str] = excluded_monitors.replace("'", "").split(',') if excluded_monitors else []
        if self.excluded_monitors:
            logger.info(f'Excluded monitors received in Telemetry: {self.excluded_monitors}')

        self.monitor_list: dict[str, Monitor] = {}

        self.period: int = telemetry_period
        self._initialize_monitors(telemetry_period)

        NuvlaEdgeStatusHandler.starting(self.status_channel, _status_module_name)

    def set_period(self, period: int):
        self.period = period
        for mon in self.monitor_list.values():
            mon.set_period(period)

    def _initialize_monitors(self, period: int):
        """
        Auxiliary function to extract some control from the class initialization
        It gathers the available monitors and initializes them saving the reference into
        the monitor_list attribute of Telemetry
        """
        for mon in active_monitors:
            if mon.rsplit('_', 1)[0] in self.excluded_monitors:
                logger.info(f'Monitor "{mon}" excluded')
                continue
            monitor = get_monitor(mon)(mon, self, True, period)
            if monitor.enabled_monitor:
                self.monitor_list[mon] = monitor
            else:
                logger.info(f'Monitor "{mon}" disabled')

    def _collect_monitor_metrics(self) -> str:
        """
        Collects monitoring metrics from the monitor list and updates the local telemetry data.

        Returns:
            str: A string containing the report of the monitors that didn't send any metrics in the last period.
        """
        # Retrieve monitoring data
        self._local_telemetry = TelemetryPayloadAttributes()
        _report = ""
        for it_monitor in self.monitor_list.values():
            if not it_monitor.enabled_monitor:
                logger.info("Monitor {} is disabled".format(it_monitor.name))
                continue

            try:
                m_telemetry: TelemetryPayloadAttributes = it_monitor.report_channel.get_nowait()
            except Empty:
                logger.warning(f"Monitor {it_monitor.name} didn't send any metrics in the last {self.period} seconds.")
                _report += f"\tMonitor {it_monitor.name} not sending metrics\n"
                continue
            self._local_telemetry.update(m_telemetry)

        return _report

    def _check_monitors_health(self):
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
                         f'Alive: {it_monitor.is_alive()}')
            if not it_monitor.enabled_monitor:
                logger.info(f'Monitor {it_monitor.name} is disabled, no need to check health')
                continue

            if is_thread_creation_needed(
                    monitor_name,
                    it_monitor,
                    log_not_alive=(logging.INFO, 'Recreating {} thread.'),
                    log_alive=(logging.DEBUG, 'Thread {} is alive'),
                    log_not_exist=(logging.INFO, 'Creating {} thread.')):
                monitor = get_monitor(monitor_name)(monitor_name, self, True)
                monitor.start()
                self.monitor_list[monitor_name] = monitor

        if logger.level <= logging.INFO:
            monitor_process_duration = {k: v.last_process_duration for k, v in self.monitor_list.items()}
            logger.debug(f'Monitors processing duration: {dump_dict_to_str(monitor_process_duration)}')

    @property
    def _local_telemetry_json(self):
        return self._local_telemetry.model_dump_json(exclude_none=True, by_alias=True)

    def run(self):
        NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name)
        logger.debug("Telemetry health check started.")
        self._check_monitors_health()

    def run_once(self):
        logger.info("Gathering metrics from monitors...")
        t_time = time.time()
        for m in self.monitor_list.values():
            m.run_update_data()
            logger.info(f"Metrics from {m.name} updated in {m.last_process_duration}s")
            if m.enabled_monitor:
                m.start()
        logger.info(f"Metrics updated in {time.time() - t_time}")

    def get_telemetry(self) -> TelemetryPayloadAttributes:
        _monitor_report = self._collect_monitor_metrics()
        self._local_telemetry.current_time = datetime.now(UTC).isoformat().split('.')[0] + 'Z'

        NuvlaEdgeStatusHandler.running(self.status_channel, _status_module_name, _monitor_report)
        return self._local_telemetry.model_copy(deep=True)
