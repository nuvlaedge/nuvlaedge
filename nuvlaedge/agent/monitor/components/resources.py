# -*- coding: utf-8 -*-
""" NuvlaEdge host resources monitor module """
import json
from subprocess import CompletedProcess
import psutil

from nuvlaedge.agent.common.util import execute_cmd
from nuvlaedge.agent.monitor.data.resources_data import (ResourcesData,
                                                         DiskDataStructure,
                                                         CPUDataStructure,
                                                         MemoryDataStructure)
from nuvlaedge.agent.monitor import Monitor
from ..components import monitor


@monitor('resources_monitor')
class ResourcesMonitor(Monitor):
    """ Resource monitor class. Extracts the host resource utilization """

    _DISK_INFO_COMMAND: list[str] = ["lsblk", "--json", "-o",
                                     "NAME,SIZE,MOUNTPOINT,FSUSED", "-b", "-a"]

    def __init__(self, name: str, telemetry, enable_monitor: bool = True):
        super().__init__(name, ResourcesData, enable_monitor)

        if not telemetry.edge_status.resources:
            telemetry.edge_status.resources = self.data

    @staticmethod
    def get_static_disks() -> list[DiskDataStructure]:
        """
        Gathers the generic disk usage

        Returns: A list containing a DickDataStructure object with the current state
        of the disk

        """
        return [DiskDataStructure.parse_obj({
            'device': 'overlay',
            'capacity': int(psutil.disk_usage('/')[0] / 1024 / 1024 / 1024),
            'used': int(psutil.disk_usage('/')[1] / 1024 / 1024 / 1024)
        })]

    @staticmethod
    def clean_disk_report(report: dict) -> DiskDataStructure | None:
        """
            Receives a dict containing information about a drive or a partition
            and returns a structure report of the node
        Args:
            report: single dict containing information about a drive or partition
        Returns:
            disk data report
        """
        try:
            capacity: int = round(int(report['size']) / 1024 / 1024 / 1024)
            fused = report['fsused'] if report.get('fsused') else 0
            fused = round(int(fused) / 1024 / 1024 / 1024)
            name: str = report.get('name')

            if not capacity or not isinstance(fused, int) or not name:
                return None

            return DiskDataStructure(device=name, capacity=capacity, used=fused)

        except (KeyError, ValueError):
            return None

    def get_disks_usage(self):
        """ Gets disk usage for N partitions """
        it_disk_status: list[DiskDataStructure] = []

        raw_disk_info: CompletedProcess = execute_cmd(self._DISK_INFO_COMMAND)

        if not raw_disk_info or raw_disk_info.returncode != 0 or not raw_disk_info.stdout:
            return self.get_static_disks()

        # Gather list of disks and their children partitions
        lsblk: dict = json.loads(raw_disk_info.stdout)
        devices: list[dict] = lsblk.get('blockdevices', [])

        # Iterate list of drives
        for device in devices:
            partitions: list[dict] = device.get('children', [])

            # Generate drive report data structure
            if not device.get('size') or not device.get('children'):
                continue

            # Iterate list of partitions
            for partition in partitions:
                if not partition.get('mountpoint'):
                    continue
                it_drive = self.clean_disk_report(partition)
                if it_drive:
                    it_disk_status.append(it_drive)

        if it_disk_status:
            return it_disk_status

        return self.get_static_disks()

    def get_disk_resources(self) -> list[DiskDataStructure]:
        """
        Gets the disk usage information and adds a topic name and the raw string for
        report

        Returns: a list of DiskDataStructure pydantic base models

        """
        partial_disk_data: list[DiskDataStructure] = self.get_disks_usage()
        for disk in partial_disk_data:
            if disk:
                disk.raw_sample = json.dumps(disk.dict(exclude_none=True))
                disk.topic = 'disks'

        return partial_disk_data

    @staticmethod
    def get_cpu_data() -> CPUDataStructure:
        """
        Gets CPU information from psutil package

        Returns: current status of the CPU encapsulated in a CPUDataStructure

        """
        it_cpu_data: CPUDataStructure = CPUDataStructure.parse_obj(
            {
                "capacity": int(psutil.cpu_count()),
                "load": float(psutil.getloadavg()[2]),
                "load_1": float(psutil.getloadavg()[0]),
                "load_5": float(psutil.getloadavg()[1]),
                "context_switches": int(psutil.cpu_stats().ctx_switches),
                "interrupts": int(psutil.cpu_stats().interrupts),
                "software_interrupts": int(psutil.cpu_stats().soft_interrupts),
                "system_calls": int(psutil.cpu_stats().syscalls)
            }
        )
        it_cpu_data.raw_sample = json.dumps(it_cpu_data.dict(exclude_none=True))
        it_cpu_data.topic = "cpu"
        return it_cpu_data

    @staticmethod
    def get_memory_data() -> MemoryDataStructure:
        """
        Get RAM memory info from psutil package

        Returns: current memory status encapsulated in a MemoryDataStructure

        """
        it_memory_data: MemoryDataStructure = MemoryDataStructure.parse_obj(
            {
                "capacity": int(round(psutil.virtual_memory()[0] / 1024 / 1024)),
                "used": int(round(psutil.virtual_memory()[3] / 1024 / 1024))
            }
        )
        it_memory_data.raw_sample = json.dumps(it_memory_data.dict(exclude_none=True))
        it_memory_data.topic = 'ram'
        return it_memory_data

    def update_data(self):
        self.data.disks = self.get_disk_resources()
        self.data.cpu = self.get_cpu_data()
        self.data.ram = self.get_memory_data()

    def populate_nb_report(self, nuvla_report: dict):
        if not nuvla_report.get('resources'):
            nuvla_report['resources'] = {}

        nuvla_report['resources']['cpu'] = self.data.cpu.dict(by_alias=True)
        nuvla_report['resources']['ram'] = self.data.ram.dict(by_alias=True)
        nuvla_report['resources']['disks'] = \
            [x.dict(by_alias=True) for x in self.data.disks]
