"""
    NuvlaEdge data structure for resources
"""
from pydantic import Field

from nuvlaedge.agent.monitor import BaseDataStructure


# Base class to report CPU, Memory and Disks data status
# that contain some common parameters
class ResourceBase(BaseDataStructure):
    """ Common structure for resource report """
    topic: str | None
    raw_sample: str | None = Field(alias='raw-sample')


class CPUDataStructure(ResourceBase):
    """ CPU data structure """
    capacity: int | None
    load: float | None
    load_1: float | None = Field(alias='load-1')
    load_5: float | None = Field(alias='load-5')
    context_switches: int | None = Field(alias='context-switches')
    interrupts: int | None
    software_interrupts: int | None = Field(alias='software-interrupts')
    system_calls: int | None = Field(alias='system-calls')


class MemoryDataStructure(ResourceBase):
    """ RAM data structure """
    capacity: int | None
    used: int | None


# ======================== Conditional resource structures ======================== #
class DiskDataStructure(ResourceBase):
    """ Storage data structure """
    device: str | None
    capacity: int | None
    used: int | None


class ResourcesData(BaseDataStructure):
    """ Resource wrapper data structure """
    # Basic compute resources
    disks: list[DiskDataStructure] | None
    cpu: CPUDataStructure | None
    ram: MemoryDataStructure | None
