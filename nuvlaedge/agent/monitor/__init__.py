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

from pydantic import BaseModel


class Monitor(ABC, Thread):
    """
    Serves as a base class to facilitate and structure the telemetry gathering
    along the device.
    """
    def __init__(self, name: str, data_type: Type, enable_monitor: bool,
                 thread_period: int = 10):
        super().__init__()
        # Define default thread attributes
        self.daemon = True
        self.thread_period: int = thread_period

        # TODO: FUTURE: Standardize system conf propagation
        if os.environ.get('NE_THREAD_MONITORS', 'False') == 'False':
            self.is_thread: bool = False
        else:
            self.is_thread: bool = True

        self.name: str = name
        self.data: data_type = data_type(telemetry_name=name)

        # Logging system
        self.logger: logging.Logger = logging.getLogger(name)

        # Enable flag
        self._enabled_monitor: bool = enable_monitor
        self.updated: bool = False

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

    def run(self) -> None:
        while True:
            self.update_data()
            self.updated = True

            time.sleep(self.thread_period)


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
    def dict(self, exclude_none: bool = True, **kwargs):
        return super().dict(exclude_none=exclude_none, **kwargs)

    class Config:
        """ Configuration class for base telemetry data """
        allow_population_by_field_name = True
        alias_generator = underscore_to_hyphen
        validate_assignment = True
