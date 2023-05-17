""" Module for Power report structure definition """
from typing import Dict, Union

from nuvlaedge.agent.monitor import BaseDataStructure


class PowerEntry(BaseDataStructure):
    """ Single power report structure """
    metric_name: Union[str, None]
    energy_consumption: Union[float, None]
    unit: Union[str, None]


class PowerData(BaseDataStructure):
    """ Complete power report map"""
    power_entries: Union[Dict[str, PowerEntry], None]
