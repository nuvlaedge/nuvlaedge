"""
Gathers the base NuvlaEdge base information
"""

import datetime
import psutil
from typing import Dict

from nuvlaedge.agent.common import util
from nuvlaedge.agent.monitor import Monitor
from nuvlaedge.agent.monitor.data.nuvlaedge_data import NuvlaEdgeData as NuvlaInfo
from nuvlaedge.agent.monitor.data.nuvlaedge_data import InstallationParametersData
from nuvlaedge.agent.orchestrator import ContainerRuntimeClient
from ..components import monitor


@monitor('nuvlaedge_info_monitor')
class NuvlaEdgeInfoMonitor(Monitor):
    """ NuvlaEdge information monitor class. """
    def __init__(self, name: str, telemetry,
                 enable_monitor: bool = True):
        super().__init__(name, NuvlaInfo, enable_monitor)

        self.runtime_client: ContainerRuntimeClient = telemetry.container_runtime
        self.ne_id: str = telemetry.nb_status_id
        self.ne_engine_version: str = util.extract_nuvlaedge_version(self.runtime_client.get_current_image())
        self.installation_home: str = telemetry.installation_home

        if not telemetry.edge_status.nuvlaedge_info:
            telemetry.edge_status.nuvlaedge_info = self.data

    def update_data(self):
        """
        Updates NuvlaEdge configuration parameters including installation and Nuvla
        information. Also, the components of the NuvlaEdge deployment
        """
        # Update static information
        self.data.id = self.ne_id
        self.data.nuvlaedge_engine_version = self.ne_engine_version
        self.data.installation_home = self.installation_home

        node_info = self.runtime_client.get_node_info()

        self.data.operating_system = self.runtime_client.get_host_os()
        self.data.architecture = self.runtime_client.get_host_architecture(node_info)
        self.data.hostname = self.runtime_client.get_hostname(node_info)
        self.data.last_boot = datetime.datetime.fromtimestamp(psutil.boot_time()).\
            strftime("%Y-%m-%dT%H:%M:%SZ")
        self.data.container_plugins = self.runtime_client.get_container_plugins()

        # installation parameters
        if not self.data.installation_parameters:
            self.data.installation_parameters = InstallationParametersData()

        installation_parameters = self.runtime_client.get_installation_parameters()
        self.data.installation_parameters = InstallationParametersData.parse_obj(installation_parameters)

        # Components running in the current NuvlaEdge deployment
        self.data.components = self.runtime_client.get_all_nuvlaedge_components() or None

    def populate_nb_report(self, nuvla_report: Dict):
        nuvla_report.update(self.data.dict(by_alias=True, exclude_none=True))
