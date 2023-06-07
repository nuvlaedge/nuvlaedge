""" Module for Power report structure definition """
from nuvlaedge.agent.monitor import BaseDataStructure


class PowerEntry(BaseDataStructure):
    """ Single power report structure """
    metric_name: str | None
    energy_consumption: float | None
    unit: str | None


class PowerData(BaseDataStructure):
    """ Complete power report map"""
    power_entries: dict[str, PowerEntry] | None
