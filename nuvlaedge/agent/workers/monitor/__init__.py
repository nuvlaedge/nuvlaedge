"""
Implementation of the Monitor and BaseDataStructure to be extended by every
component and data structure
"""

import os
import time
import logging
from threading import Thread
from abc import ABC, abstractmethod
from typing import Type, Dict

from pydantic import BaseModel, ConfigDict

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


class Monitor(ABC, Thread):
    """
    Serves as a base class to facilitate and structure the telemetry gathering
    along the device.
    """
    def __init__(self, name: str, data_type: Type, enable_monitor: bool,
                 thread_period: int = 60):
        super().__init__()
        # Define default thread attributes
        self.daemon = True
        self.thread_period: int = thread_period

        if os.environ.get('NUVLAEDGE_THREAD_MONITORS', 'False') == 'False':
            self.is_thread: bool = False
        else:
            self.is_thread: bool = True

        self.name: str = name
        self.data: data_type = data_type(telemetry_name=name)

        # Logging system
        self.logger: logging.Logger = get_nuvlaedge_logger(__name__)

        # Enable flag
        self._enabled_monitor: bool = enable_monitor
        self.updated: bool = False
        self.last_process_duration = None

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
    def populate_nb_report(self, nuvla_report: Dict):
        """
            This method fills the nuvla report dictionary with the data corresponding
            to the given monitor class following the current structure of NuvlaAPI
        Args:
            nuvla_report: dictionary to fill with the data structure report
        """
        ...

    def run_update_data(self, monitor_name=None):
        if not monitor_name:
            monitor_name = self.name

        init_time: float = time.perf_counter()
        try:
            self.update_data()
            self.updated = True
        except Exception as e:
            self.logger.exception(f'Something went wrong updating monitor {monitor_name}: {e}')
        finally:
            self.last_process_duration = time.perf_counter() - init_time

    def run(self) -> None:
        while True:
            t0 = time.perf_counter()
            self.run_update_data()
            run_time = time.perf_counter() - t0
            wait_time = self.thread_period - run_time
            if wait_time > 0:
                time.sleep(wait_time)
            else:
                self.logger.warning(f'Monitor {self.name} took too long to complete '
                                    f'({run_time} > {self.thread_period})')


def underscore_to_hyphen(field_name: str) -> str:
    """
    Alias generator that takes the field name and converts the underscore into hyphen
    Args:
        field_name: string that contains the name of the field to be processed

    Returns: the alias name with no underscores

    """
    return field_name.replace("_", "-")


class BaseDataStructure(BaseModel):
    """
    Base data structure for providing a common configuration for all the
    structures.
    """
    """ Configuration class for base telemetry data """
    model_config = ConfigDict(populate_by_name=True,
                              alias_generator=underscore_to_hyphen,
                              validate_assignment=True)

    def dict(self, exclude_none: bool = True, **kwargs):
        return super().model_dump(exclude_none=exclude_none, **kwargs)
