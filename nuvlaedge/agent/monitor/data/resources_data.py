"""
    NuvlaEdge data structure for resources
"""
from pydantic import Field

from nuvlaedge.agent.monitor import BaseDataStructure


# Base class to report CPU, Memory and Disks data status
# that contain some common parameters
class ResourceBase(BaseDataStructure):
    """ Common structure for resource report """
    topic: str | None = None
    raw_sample: str | None = Field(None, alias='raw-sample')


class CPUDataStructure(ResourceBase):
    """ CPU data structure """
    capacity: int | None = None
    load: float | None = None
    load_1: float | None = Field(None, alias='load-1')
    load_5: float | None = Field(None, alias='load-5')
    context_switches: int | None = Field(None, alias='context-switches')
    interrupts: int | None = None
    software_interrupts: int | None = Field(None, alias='software-interrupts')
    system_calls: int | None = Field(None, alias='system-calls')


class MemoryDataStructure(ResourceBase):
    """ RAM data structure """
    capacity: int | None = None
    used: int | None = None


# ======================== Conditional resource structures ======================== #
class DiskDataStructure(ResourceBase):
    """ Storage data structure """
    device: str | None = None
    capacity: int | None = None
    used: int | None = None


class ResourcesData(BaseDataStructure):
    """ Resource wrapper data structure """
    # Basic compute resources
    disks: list[DiskDataStructure] | None = None
    cpu: CPUDataStructure | None = None
    ram: MemoryDataStructure | None = None
