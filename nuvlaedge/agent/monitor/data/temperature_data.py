""" Module for temperature data structures """
from nuvlaedge.agent.monitor import BaseDataStructure


class TemperatureZone(BaseDataStructure):
    """ Temperature zone structure description """
    thermal_zone: str | None
    value: float | None


# Temperature data structure
class TemperatureData(BaseDataStructure):
    """ Wrapper for temperature zones """
    temperatures: dict[str, TemperatureZone] | None
