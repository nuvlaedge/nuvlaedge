# -*- coding: utf-8 -*-

""" Check system requirements for the NuvlaEdge Engine """

import multiprocessing
import logging
import shutil
import os

from nuvlaedge.system_manager.common import utils
from nuvlaedge.system_manager.common.coe_client import Containers


SKIP_MINIMUM_REQUIREMENTS = False
if 'SKIP_MINIMUM_REQUIREMENTS' in os.environ and \
        str(os.environ.get('SKIP_MINIMUM_REQUIREMENTS', "false")).lower() == "true":
    SKIP_MINIMUM_REQUIREMENTS = True


class SystemRequirements(Containers):
    """ The SystemRequirements contains all the methods and
    definitions for checking whether a device is physically capable of
    hosting the NuvlaEdge Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs an SystemRequirements object """

        self.log = logging.getLogger(__name__)
        super().__init__(self.log)

        self.minimum_requirements = {
            "cpu": 1,
            "ram": 480,
            "disk": 2
        }

        self.not_met = []

    def check_cpu_requirements(self) -> bool:
        """ Check the device for the CPU requirements according to the
         recommended ones

         :returns True if there's enough CPU, False otherwise
         """

        cpu_count = int(multiprocessing.cpu_count())

        if cpu_count < self.minimum_requirements["cpu"]:
            msg = f'Your device only provides {cpu_count} CPUs. MIN REQUIREMENTS: {self.minimum_requirements["cpu"]}'
            self.log.error(msg)
            self.not_met.append(msg)
            return False
        else:
            return True

    def check_ram_requirements(self) -> bool:
        """ Check the device for the RAM requirements according to the
         recommended ones

         :returns True if there's enough RAM, False otherwise
         """

        total_ram = round(self.coe_client.get_ram_capacity(), 2)

        if total_ram < self.minimum_requirements["ram"]:
            msg = f'Your device only provides {total_ram} MBs of memory. ' \
                  f'MIN REQUIREMENTS: {self.minimum_requirements["ram"]} MBs'
            self.log.error(msg)
            self.not_met.append(msg)
            return False
        else:
            return True

    def check_disk_requirements(self) -> bool:
        """ Check the device for the disk requirements according to the
         recommended ones

         :returns True if there's enough disk, False otherwise
         """

        total_disk = round(shutil.disk_usage("/")[0]/1024/1024/1024)

        if total_disk < self.minimum_requirements["disk"]:
            msg = f'Your device only provides {total_disk} GBs of disk. ' \
                  f'MIN REQUIREMENTS: {self.minimum_requirements["disk"]} GBs'
            self.log.error(msg)
            self.not_met.append(msg)
            return False
        else:
            return True

    def check_all_hw_requirements(self) -> bool:
        """ Runs all checks

        :returns True if all checks pass, False otherwise
        """
        meets_cpu_req = self.check_cpu_requirements()
        meets_ram_req = self.check_ram_requirements()
        meets_disk_req = self.check_disk_requirements()

        return meets_disk_req and meets_ram_req and meets_cpu_req


class SoftwareRequirements(Containers):
    """ The SoftwareRequirements contains all the methods and
    definitions for checking whether a device has all the Software
    dependencies and configurations required by the NuvlaEdge Engine

    Attributes:

    """

    def __init__(self):
        """ Constructs the class """

        self.log = logging.getLogger(__name__)
        self.not_met = []
        super().__init__(self.log)

    def check_sw_requirements(self):
        """ Checks all the SW requirements """
        if not self.coe_client.is_version_compatible():
            msg = f'The COE ({self.coe_client.orchestrator}) version installed ' \
                  f'in your system ({self.coe_client.get_version()}) is too old. ' \
                  f'Need version {self.coe_client.minimum_version} or higher.'
            self.not_met.append(msg)

        if self.not_met:
            return False

        return True

    def check_sw_optional_requirements(self):
        msgs = []

        if self.coe_client.orchestrator == 'docker' and not self.coe_client.is_coe_enabled():
            msgs.append((utils.status_operational, 'Docker Swarm mode is not enabled.'))

        return msgs
