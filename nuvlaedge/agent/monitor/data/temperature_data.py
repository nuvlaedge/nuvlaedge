""" Module for temperature data structures """
from typing import Union, Dict

from nuvlaedge.agent.monitor import BaseDataStructure


class TemperatureZone(BaseDataStructure):
    """ Temperature zone structure description """
    thermal_zone: Union[str, None]
    value: Union[float, None]


# Temperature data structure
class TemperatureData(BaseDataStructure):
    """ Wrapper for temperature zones """
    temperatures: Union[Dict[str, TemperatureZone], None]
