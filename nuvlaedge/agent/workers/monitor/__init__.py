"""
Implementation of the Monitor and BaseDataStructure to be extended by every
component and data structure
"""

import time
import logging
from queue import Queue, Empty
from threading import Thread, Event
from abc import ABC, abstractmethod
from typing import Type, Dict

from pydantic import BaseModel, ConfigDict

from nuvlaedge.agent.nuvla.resources.telemetry_payload import TelemetryPayloadAttributes
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging = get_nuvlaedge_logger(__name__)

def underscore_to_hyphen(field_name: str) -> str:
    """
    Alias generator that takes the field name and converts the underscore into hyphen
    Args:
        field_name: string that contains the name of the field to be processed

    Returns: the alias name with no underscores

    """
    return field_name.replace("_", "-")


class BaseDataStructure(NuvlaEdgeBaseModel):
    """
    Base data structure for providing a common configuration for all the
    structures.
    """
    _telemetry_name: str = "BaseDataStructure"

    def dict(self, exclude_none: bool = True, **kwargs):
        return super().model_dump(exclude_none=exclude_none, **kwargs)

class Monitor(ABC, Thread):
    """
    Serves as a base class to facilitate and structure the telemetry gathering
    along the device.
    """

    def __init__(self,
                 name: str,
                 data_type: Type,
                 enable_monitor: bool = True,
                 thread_period: int = 60):
        super().__init__()
        # Define default thread attributes
        self.daemon = True
        self._period: int = thread_period

        self.report_channel: Queue[TelemetryPayloadAttributes] = Queue(maxsize=1)
        self.telemetry_data: TelemetryPayloadAttributes = TelemetryPayloadAttributes()

        self.name: str = name or self.__class__.__name__
        self.data: data_type = data_type(_telemetry_name=self.name)

        # Logging system
        self.logger: logging.Logger = get_nuvlaedge_logger(self.__class__.__module__)

        # Enable flag
        self._enabled_monitor: bool = enable_monitor
        self.last_process_duration = None
        self._last_update: float = time.time()
        self._exit_event: Event = Event()

    def set_period(self, period: int):
        logger.debug(f"Setting period for monitor {self.name} to {period}")
        self._period = period


    @property
    def enabled_monitor(self):
        """
        Getter for monitor flag

        Returns: bool

        """
        return self._enabled_monitor

    @enabled_monitor.setter
    def enabled_monitor(self, flag: bool):
        """
        Setter for monitor flag
        Args:
            flag: bool
        """
        self._enabled_monitor = flag

    @abstractmethod
    def update_data(self):
        """
        General updater of the data attribute. To be implemented by class
        extension.
        """
        ...

    @abstractmethod
    def populate_telemetry_payload(self):
        """
        Populates the local telemetry payload attribute with the data gathered
        Returns: None

        """

    def send_telemetry_data(self):
        """
        Sends the telemetry data to the report channel
        """
        if self.report_channel.full():
            self.logger.warning(f"Monitor {self.name} telemetry channel data not being consumed on time. "
                                f"Discarding old data.")
            try:
                _ = self.report_channel.get_nowait()
            except Empty:
                # It is highly unlikely that this will happen, but add this protection to prevent from
                # exiting the monitor thread
                self.logger.debug("Channel was empty, no need to discard data")

        self.report_channel.put(self.telemetry_data, block=False)
        self.telemetry_data = TelemetryPayloadAttributes()

    def run_update_data(self, monitor_name=None):
        if not monitor_name:
            monitor_name = self.name

        init_time: float = time.time_ns()
        self._last_update = time.time()
        try:
            self.update_data()
            self.populate_telemetry_payload()
            self.send_telemetry_data()
        except Exception as e:
            self.logger.exception(f'Something went wrong updating monitor {monitor_name}: {e}')
        finally:
            self.last_process_duration = round((time.time_ns() - init_time)/1e9, 4)

    def _compute_wait_time(self, period: int) -> float:
        return period - (time.time() - self._last_update)

    def run(self) -> None:
        # the first time it runs, it should do  it at half the period. This is due to the fact that
        # the first run is executed sequentially on NuvlaEdge startup.

        _wait_time: float = self._compute_wait_time(int(self._period/2))
        if _wait_time < 0:
            _wait_time = 0.0

        while not self._exit_event.wait(timeout=_wait_time):
            self.run_update_data()

            _wait_time = self._compute_wait_time(self._period)
            logger.info(f"Monitor {self.name} waiting for {format(_wait_time, '.2f')} seconds")
            if _wait_time < 0:
                _wait_time = 0.0
                self.logger.warning(f'Monitor {self.name} took too long to complete '
                                    f'({self.last_process_duration} > {self._period})')
