""" NuvlaEdge container monitor """

import logging
import os

from docker import errors as docker_err

from nuvlaedge.common.constants import CTE

from nuvlaedge.agent.workers.monitor.data.orchestrator_data import (DeploymentData,
                                                                    ClusterStatusData,
                                                                    ContainerStatsDataOld,
                                                                    ContainerStatsData)
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.utils import get_certificate_expiry, format_datetime_for_nuvla

logger: logging.Logger = get_nuvlaedge_logger(__name__)


@monitor('container_stats_monitor')
class ContainerStatsMonitor(Monitor):
    """
    Provides asynchronous information gathering about containers.

    """
    def __init__(self, name: str, telemetry, enable_monitor: bool, period: int = 60):
        super().__init__(name, DeploymentData, enable_monitor, period)

        self.coe_client: COEClient = telemetry.coe_client

        self.nuvlaedge_id: str = telemetry.nuvlaedge_uuid
        self.swarm_node_cert_path: str = CTE.SWARM_NODE_CERTIFICATE

        self.data.containers = {}

        self._old_container_stats_version = not telemetry.new_container_stats_supported

    def refresh_container_info(self) -> None:
        """
            Gathers container statistics from the orchestrator and stores it into
            local data variable
        """
        it_containers: list = self.coe_client.collect_container_metrics(self._old_container_stats_version)
        self.data.containers = {}
        for i in it_containers:
            if self._old_container_stats_version:
                it_cont: ContainerStatsDataOld = ContainerStatsDataOld.model_validate(i)
                self.data.containers[it_cont.id] = it_cont
            else:
                it_cont: ContainerStatsData = ContainerStatsData.model_validate(i)
                self.data.containers[it_cont.id] = it_cont

    def get_cluster_manager_attrs(self, managers: list, node_id: str) -> tuple:
        """
        If this node is a manager, tries to get the WHOLE list of nodes in the cluster

        :param managers: existing cluster managers
        :param node_id: this node's ID
        :return: tuple of (bool, list), to say if this node is a manager, and the whole
        list of cluster nodes
        """
        cluster_nodes = []
        if node_id not in managers:
            return False, cluster_nodes

        try:
            all_cluster_nodes = self.coe_client.list_nodes()
        except docker_err.APIError as ex:
            self.logger.error(f'Cannot get Docker cluster nodes: {str(ex)}')
        else:
            for node in all_cluster_nodes:
                active_node_id = self.coe_client.is_node_active(node)
                if not active_node_id:
                    continue
                if active_node_id not in cluster_nodes:
                    try:
                        cluster_nodes.append(node.id)
                    except AttributeError:
                        continue

            return True, cluster_nodes
        return False, []

    def update_cluster_data(self):
        """
        Gets and sets all the cluster attributes for the nuvlaedge-status

        """

        node = self.coe_client.get_node_info()
        node_id = self.coe_client.get_node_id(node)
        cluster_id = self.coe_client.get_cluster_id(
            node,
            f'cluster_{self.nuvlaedge_id}')
        labels = self.coe_client.get_node_labels()

        cluster_managers = self.coe_client.get_cluster_managers()

        self.data.cluster_data = ClusterStatusData()

        if node_id:
            self.data.cluster_data.node_id = node_id
            self.data.cluster_data.orchestrator = self.coe_client.ORCHESTRATOR_COE
            self.data.cluster_data.cluster_node_role = 'worker'

        if cluster_id:
            self.data.cluster_data.cluster_id = cluster_id

        if cluster_managers:
            self.data.cluster_data.cluster_managers = cluster_managers
            if node_id:
                join_addr = self.coe_client.get_cluster_join_address(node_id)
                if join_addr:

                    self.data.cluster_data.cluster_join_address = join_addr

        if labels:
            self.data.cluster_data.cluster_node_labels = labels

        is_manager, cluster_nodes = self.get_cluster_manager_attrs(cluster_managers,
                                                                   node_id)
        if is_manager:
            self.data.cluster_data.cluster_node_role = 'manager'

        if len(cluster_nodes) > 0:
            self.data.cluster_data.cluster_nodes = cluster_nodes

    def get_swarm_certificate_expiration_date(self) -> str | None:
        """
        If the docker swarm certs can be found, try to infer their expiration date
        """
        if not os.path.isfile(self.swarm_node_cert_path):
            return None
        expiry_datetime = get_certificate_expiry(self.swarm_node_cert_path)
        return format_datetime_for_nuvla(expiry_datetime) if expiry_datetime else None

    def update_data(self):
        self.refresh_container_info()
        version: str = self.coe_client.get_client_version()

        if self.coe_client.ORCHESTRATOR == 'docker':
            self.data.docker_server_version = version
        else:
            self.data.kubelet_version = version

        self.update_cluster_data()

        self.data.swarm_node_cert_expiry_date = \
            self.get_swarm_certificate_expiration_date()

    def populate_telemetry_payload(self):
        self.telemetry_data.resources = {
            'container-stats': [x.dict(by_alias=True) for x in self.data.containers.values()]}

        if self.data.docker_server_version:
            self.telemetry_data.docker_server_version = self.data.docker_server_version

        if self.data.kubelet_version:
            self.telemetry_data.kubelet_version = self.data.kubelet_version

        if self.data.cluster_data:
            self.telemetry_data.update(self.data.cluster_data.dict(
                by_alias=True, exclude_none=True))

        if self.data.swarm_node_cert_expiry_date:
            self.telemetry_data.swarm_node_cert_expiry_date = self.data.swarm_node_cert_expiry_date
