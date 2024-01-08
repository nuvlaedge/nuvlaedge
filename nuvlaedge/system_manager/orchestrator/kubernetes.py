import os
import logging
import time

from nuvlaedge.system_manager.orchestrator import COEClient
from nuvlaedge.system_manager.common import utils


if os.getenv('KUBERNETES_SERVICE_HOST'):
    from kubernetes import client, config


logger = logging.getLogger(__name__)


class Kubernetes(COEClient):
    """
    Kubernetes client
    """

    def __init__(self):
        super().__init__()

        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.client_apps = client.AppsV1Api()
        self.namespace = os.getenv('MY_NAMESPACE', 'nuvlaedge')
        self.host_node_name = os.getenv('MY_HOST_NODE_NAME')
        self.minimum_major_version = '1'
        self.minimum_minor_version = '20'
        self.minimum_version = f'{self.minimum_major_version}.{self.minimum_minor_version}'
        self.credentials_manager_component = 'kubernetes-credentials-manager'
        self.orchestrator = 'kubernetes'
        self.agent_dns = f'nuvlaedge.agent.{self.namespace}'
        self.my_component_name = 'nuvlaedge-engine-core'
        self.current_image = os.getenv('NUVLAEDGE_IMAGE') or self.current_image

    def list_internal_components(self, base_label=utils.base_label):
        # for k8s, components = pods
        return self.client.list_namespaced_pod(namespace=self.namespace, label_selector=base_label).items

    def fetch_container_logs(self, component, since, tail=30):
        # component = pod object
        pod_logs = []
        if since:
            since = int(time.time() - since)
        for container in component.spec.containers:
            log = self.client.read_namespaced_pod_log(namespace=self.namespace,
                                                      name=component.metadata.name,
                                                      container=container.name,
                                                      tail_lines=tail,
                                                      timestamps=True,
                                                      since_seconds=since).splitlines()

            log_with_name = f"\n [{container.name}] ".join(log)

            final_logs = f' [{container.name}] {log_with_name}\n'
            pod_logs.append(final_logs.splitlines())

        return pod_logs

    def get_component_name(self, component):
        return component.metadata.name

    def get_component_id(self, component):
        return component.metadata.uid

    def get_node_info(self):
        if self.host_node_name:
            return self.client.read_node(self.host_node_name)

        return None

    def get_ram_capacity(self):
        return int(self.get_node_info().status.capacity.get('memory', '0').rstrip('Ki'))/1024

    def is_version_compatible(self):
        kubelet_version = self.get_version()

        kubelet_simplified_version = int(''.join(kubelet_version.lstrip('v').split('.')[0:2]))
        kubelet_minimum_version = int(self.minimum_major_version + self.minimum_minor_version)

        if kubelet_simplified_version < kubelet_minimum_version:
            logger.error("Your Kubelet version is too old: {}. MIN REQUIREMENTS: Kubelet v{}.{} or newer"
                               .format(kubelet_version, self.minimum_major_version, self.minimum_minor_version))

            return False

        return True

    def is_coe_enabled(self, check_local_node_state=False):
        return True

    def infer_on_stop_docker_image(self):
        # This component is not implemented for k8s (no need at the moment)
        return None

    def launch_nuvlaedge_on_stop(self, on_stop_docker_image):
        # not needed for k8s
        pass

    def get_node_id(self):
        return self.get_node_info().metadata.name

    def list_nodes(self, optional_filter={}):
        return self.client.list_node().items

    def get_cluster_managers(self):
        managers = []
        for n in self.list_nodes():
            for label in n.metadata.labels:
                if 'node-role' in label and 'master' in label:
                    managers.append(n.metadata.name)

        return managers

    def read_system_issues(self, node_info):
        errors = []
        warnings = []
        # TODO: is there a way to get any system errors from the k8s API?
        # The cluster-info dump reports a lot of stuff but is all verbose

        return errors, warnings

    def set_nuvlaedge_node_label(self, node_id=None):
        # no need to do this in k8s
        return True, None

    def restart_credentials_manager(self):
        # the credentials manager is a container running in the nuvlaedge-engine-core pod, alongside other containers,
        # and thus cannot be restarted individually.

        # we cannot restart the whole pod because that would bring all containers down, including this one
        # so we just wait for Kubelet to automatically restart it
        logger.info(f'The {self.credentials_manager_component} will be automatically restarted by Kubelet '
                          f'within the next 5 minutes')

    def find_nuvlaedge_agent_container(self):
        search_label = f'component={self.my_component_name}'
        main_pod = self.client.list_namespaced_pod(namespace=self.namespace,
                                                   label_selector=search_label).items

        if len(main_pod) == 0:
            msg = f'There are no pods running with the label {search_label}'
            logger.error(msg)
            return None, msg
        else:
            this_pod = main_pod[0]

        for container in this_pod.status.container_statuses:
            if container.name == utils.compose_project_name + '-agent':
                return container, None

        return None, f'Cannot find agent container within main NuvlaEdge Engine pod with label {search_label}'

    def list_all_containers_in_this_node(self):
        pods_here = self.client.list_pod_for_all_namespaces(field_selector=f'spec.nodeName={self.host_node_name}').items

        containers = []
        for pod in pods_here:
            containers += pod.status.container_statuses

        return containers

    def count_images_in_this_host(self):

        return len(self.get_node_info().status.images)

    def get_version(self):
        return self.get_node_info().status.node_info.kubelet_version

    def get_current_container_id(self) -> str:
        # TODO
        return ''