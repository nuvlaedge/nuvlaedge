"""
    NuvlaEdge data structure for resources
"""
from typing import Union, List

from pydantic import Field

from nuvlaedge.agent.monitor import BaseDataStructure


# Base class to report CPU, Memory and Disks data status
# that contain some common parameters
class ResourceBase(BaseDataStructure):
    """ Common structure for resource report """
    topic: Union[str, None]
    raw_sample: Union[str, None] = Field(alias='raw-sample')


class CPUDataStructure(ResourceBase):
    """ CPU data structure """
    capacity: Union[int, None]
    load: Union[float, None]
    load_1: Union[float, None] = Field(alias='load-1')
    load_5: Union[float, None] = Field(alias='load-5')
    context_switches: Union[int, None] = Field(alias='context-switches')
    interrupts: Union[int, None]
    software_interrupts: Union[int, None] = Field(alias='software-interrupts')
    system_calls: Union[int, None] = Field(alias='system-calls')


class MemoryDataStructure(ResourceBase):
    """ RAM data structure """
    capacity: Union[int, None]
    used: Union[int, None]


# ======================== Conditional resource structures ======================== #
class DiskDataStructure(ResourceBase):
    """ Storage data structure """
    device: Union[str, None]
    capacity: Union[int, None]
    used: Union[int, None]


class ResourcesData(BaseDataStructure):
    """ Resource wrapper data structure """
    # Basic compute resources
    disks: Union[List[DiskDataStructure], None]
    cpu: Union[CPUDataStructure, None]
    ram: Union[MemoryDataStructure, None]
