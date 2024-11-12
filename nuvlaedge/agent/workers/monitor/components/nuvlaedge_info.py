"""
Gathers the base NuvlaEdge base information
"""

import datetime
import os

import psutil
from typing import Dict

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.common import util
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.data.nuvlaedge_data import NuvlaEdgeData as NuvlaInfo
from nuvlaedge.agent.workers.monitor.data.nuvlaedge_data import InstallationParametersData
from nuvlaedge.agent.orchestrator import COEClient
from ..components import monitor


@monitor('nuvlaedge_info_monitor')
class NuvlaEdgeInfoMonitor(Monitor):
    """ NuvlaEdge information monitor class. """
    def __init__(self, name: str, telemetry, enable_monitor: bool = True):
        super().__init__(name, NuvlaInfo, enable_monitor)

        self.coe_client: COEClient = telemetry.coe_client

        self.ne_engine_version: str = util.extract_nuvlaedge_version(self.coe_client.current_image)
        self.installation_home: str = self.set_installation_home(FILE_NAMES.HOST_USER_HOME)

        if not telemetry.edge_status.nuvlaedge_info:
            telemetry.edge_status.nuvlaedge_info = self.data

    @staticmethod
    def set_installation_home(host_user_home_file: str) -> str:
        """
        Finds the path for the HOME dir used during installation

        :param host_user_home_file: location of the file where the previous installation
        home value was saved
        :return: installation home path
        """
        if os.path.exists(host_user_home_file):
            with open(host_user_home_file) as user_home:
                return user_home.read().strip()
        else:
            return os.environ.get('HOST_HOME')

    def update_data(self):
        """
        Updates NuvlaEdge configuration parameters including installation and Nuvla
        information. Also, the components of the NuvlaEdge deployment
        """
        # Update static information
        self.data.nuvlabox_engine_version = self.ne_engine_version
        self.data.installation_home = self.installation_home

        node_info = self.coe_client.get_node_info()

        self.data.operating_system = self.coe_client.get_host_os()
        self.data.architecture = self.coe_client.get_host_architecture(node_info)
        self.data.hostname = self.coe_client.get_hostname(node_info)
        self.data.last_boot = datetime.datetime.fromtimestamp(psutil.boot_time()).\
            strftime("%Y-%m-%dT%H:%M:%SZ")
        self.data.container_plugins = self.coe_client.get_container_plugins()

        # installation parameters
        if not self.data.installation_parameters:
            self.data.installation_parameters = InstallationParametersData()

        installation_parameters = self.coe_client.get_installation_parameters()
        if installation_parameters:
            self.data.installation_parameters = InstallationParametersData.model_validate(installation_parameters)

        # Components running in the current NuvlaEdge deployment
        self.data.components = self.coe_client.get_all_nuvlaedge_components() or None

    def populate_nb_report(self, nuvla_report: Dict):
        nuvla_report.update(self.data.dict(by_alias=True, exclude_none=True))
