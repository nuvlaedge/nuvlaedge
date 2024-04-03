""" Module for temperature data structures """
from nuvlaedge.agent.workers.monitor import BaseDataStructure


class TemperatureZone(BaseDataStructure):
    """ Temperature zone structure description """
    thermal_zone: str | None = None
    value: float | None = None


# Temperature data structure
class TemperatureData(BaseDataStructure):
    """ Wrapper for temperature zones """
    temperatures: list[dict] | None = None
