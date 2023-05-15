import os
import random
import requests
import socket
import string
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from nuvlaedge.system_manager.common import utils

KUBERNETES_SERVICE_HOST = os.getenv('KUBERNETES_SERVICE_HOST')
if KUBERNETES_SERVICE_HOST:
    from kubernetes import client, config
    ORCHESTRATOR = 'kubernetes'
else:
    import docker
    ORCHESTRATOR = 'docker'


class ContainerRuntime(ABC):
    """
    Base abstract class for the Docker and Kubernetes clients
    """

    @abstractmethod
    def __init__(self, logging):
        self.client = None
        self.logging = logging

    @abstractmethod
    def list_internal_components(self, base_label=utils.base_label):
        """ Gets all the containers that compose the NuvlaEdge Engine
        :param base_label: label to be used in the filter
        """
        pass

    @abstractmethod
    def fetch_container_logs(self, component, since, tail=30):
        """ Gets the container logs

        :param component: container or pod
        :param since: since when
        :param tail: how many lines to fetch
        """
        pass

    @abstractmethod
    def get_component_name(self, component):
        """ Return the component name

        :param component: container or pod
        """
        pass

    @abstractmethod
    def get_component_id(self, component):
        """ Return the component ID

        :param component: container or pod
        """
        pass

    @abstractmethod
    def get_current_container_id(self) -> str:
        """
        Get the container id of the current container

        :return: current container id
        """
        pass

    @abstractmethod
    def get_node_info(self):
        """ Get high level info about the hosting node
        """
        pass

    @abstractmethod
    def get_ram_capacity(self):
        """ Return the memory capacity for the node, as reported by the Container client
        """
        pass

    @abstractmethod
    def is_version_compatible(self):
        """ Checks if the container runtime engine has a version equal to or higher than the minimum requirements
        """
        pass

    @abstractmethod
    def is_coe_enabled(self, check_local_node_state=False):
        """ Check if the COE (clustering) is enabled. For K8s this is always True
        """
        pass

    @abstractmethod
    def infer_on_stop_docker_image(self):
        """ On stop, the SM launches the NuvlaEdge cleaner, called on-stop, and which is also launched in paused mode
        at the beginning of the NB lifetime.

        Here, we find that service and infer its Docker image for later usage.
        """
        pass

    @abstractmethod
    def launch_nuvlaedge_on_stop(self, on_stop_docker_image):
        """ Launches the on-stop graceful shutdown

        :param on_stop_docker_image: Docker image to be launched
        """
        pass

    @abstractmethod
    def get_node_id(self):
        """ Returns the node ID
        """
        pass

    @abstractmethod
    def list_nodes(self, optional_filter={}):
        """
        List all the nodes in the cluster
        """
        pass

    @abstractmethod
    def get_cluster_managers(self):
        """ Retrieves the cluster manager nodes
        """
        pass

    @abstractmethod
    def read_system_issues(self, node_info):
        """ Reports back the system errors and warnings, as reported by the container runtime engines
        """
        pass

    @abstractmethod
    def set_nuvlaedge_node_label(self, node_id=None):
        """ Gets detailed information about the node's spec

        :param node_id: Node ID
        """
        pass

    @abstractmethod
    def restart_credentials_manager(self):
        """ Restarts the NB component responsible for managing the API credentials
        """
        pass

    @abstractmethod
    def find_nuvlaedge_agent_container(self):
        """ Finds and returns the NuvlaEdge component
        """
        pass

    @abstractmethod
    def list_all_containers_in_this_node(self):
        """ List all the containers running in this node
        """
        pass

    @abstractmethod
    def count_images_in_this_host(self):
        """ Counts the number of Docker images in this host
        """
        pass

    @abstractmethod
    def get_version(self):
        """ Gets the version of the underlying COE
        """
        pass


class Kubernetes(ContainerRuntime):
    """
    Kubernetes client
    """

    def __init__(self, logging):
        super().__init__(logging)

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
        self.agent_dns = f'agent.{self.namespace}'
        self.my_component_name = 'nuvlaedge-engine-core'

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
            self.logging.error("Your Kubelet version is too old: {}. MIN REQUIREMENTS: Kubelet v{}.{} or newer"
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
        self.logging.info(f'The {self.credentials_manager_component} will be automatically restarted by Kubelet '
                          f'within the next 5 minutes')

        return

    def find_nuvlaedge_agent_container(self):
        search_label = f'component={self.my_component_name}'
        main_pod = self.client.list_namespaced_pod(namespace=self.namespace,
                                                   label_selector=search_label).items

        if len(main_pod) == 0:
            msg = f'There are no pods running with the label {search_label}'
            self.logging.error(msg)
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


class Docker(ContainerRuntime):
    """
    Docker client
    """

    def __init__(self, logging):
        super().__init__(logging)
        self.client = docker.from_env()
        self.minimum_version = 18
        self.lost_quorum_hint = 'possible that too few managers are online'
        self.credentials_manager_component = utils.compose_project_name + "-compute-api"

        self.orchestrator = 'docker'
        self.agent_dns = utils.compose_project_name + "-agent"
        self.my_component_name = utils.compose_project_name + '-system-manager'
        self.dg_encrypt_options = self.load_data_gateway_network_options()

    def load_data_gateway_network_options(self) -> dict:
        """
        Loads the Data Gateway options from disk first, and then from env.
        If Network already exists, issue warning.

        :return: network creation options [dict]
        """
        new = os.getenv('DATA_GATEWAY_NETWORK_ENCRYPTION')
        if not new:
            if os.path.exists(utils.nuvlaedge_shared_net_unencrypted):
                return {}
            else:
                return {"encrypted": "True"}

        try:
            self.find_network(utils.nuvlaedge_shared_net)
            self.logging.warning(f'Since {utils.nuvlaedge_shared_net} already exists, the provided '
                                 f'DATA_GATEWAY_NETWORK_ENCRYPTION [{new}] will not be immediately applied. '
                                 f'Reason: cannot update an existing network.')
        except docker.errors.NotFound:
            pass

        if new.lower() == 'false':
            Path(utils.nuvlaedge_shared_net_unencrypted).touch()
            return {}

        return {"encrypted": "True"}

    def find_network(self, name: str) -> object:
        """
        Finds a Docker network by name

        :param name: name or ID of the network
        :return: Docker Network object
        """
        return self.client.networks.get(name)

    def list_internal_components(self, base_label=utils.base_label):
        return self.client.containers.list(filters={"label": base_label})

    def fetch_container_logs(self, component, since, tail=30):
        # component = container object
        return self.client.api.logs(component.id,
                                    timestamps=True,
                                    tail=tail,
                                    since=since).decode('utf-8')

    def get_component_name(self, component):
        return component.name

    def get_component_id(self, component):
        return component.id

    def get_node_info(self):
        return self.client.info()

    def get_ram_capacity(self):
        return self.get_node_info()['MemTotal']/1024/1024

    def is_version_compatible(self):
        docker_major_version = int(self.get_version())

        if docker_major_version < self.minimum_version:
            self.logging.error("Your Docker version is too old: {}. MIN REQUIREMENTS: Docker {} or newer"
                           .format(docker_major_version, self.minimum_version))
            return False

        return True

    def is_coe_enabled(self, check_local_node_state=False):
        if not self.client.info()['Swarm'].get('NodeID'):
            return False

        if self.get_node_info().get('Swarm', {}).get('LocalNodeState', 'inactive').lower() == "inactive":
            return False

        return True

    def infer_on_stop_docker_image(self):
        on_stop_container_name = utils.compose_project_name + "-on-stop"

        try:
            container = self.client.containers.get(on_stop_container_name)
        except docker.errors.NotFound:
            # default to dev image
            return 'nuvladev/on-stop:main'
        except Exception as e:
            self.logging.error(f"Unable to search for container {on_stop_container_name}. Reason: {str(e)}")
            return None

        try:
            if container.status.lower() == "paused":
                return container.attrs['Config']['Image']
        except (AttributeError, KeyError) as e:
            self.logging.error(f'Unable to infer Docker image for {on_stop_container_name}: {str(e)}')

        return None

    def _get_container_id_from_cgroup(self):
        try:
            with open('/proc/self/cgroup', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            self.logging.debug(f'Failed to get container id from cgroup: {e}')

    def _get_container_id_from_cpuset(self):
        try:
            with open('/proc/1/cpuset', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            self.logging.debug(f'Failed to get container id from cpuset: {e}')

    def _get_container_id_from_hostname(self):
        try:
            return socket.gethostname().strip()
        except Exception as e:
            self.logging.debug(f'Failed to get container id from hostname: {e}')

    def get_current_container(self):
        get_id_functions = [self._get_container_id_from_hostname,
                            self._get_container_id_from_cpuset,
                            self._get_container_id_from_cgroup]
        for get_id_function in get_id_functions:
            container_id = get_id_function()
            if container_id:
                try:
                    return self.client.containers.get(container_id)
                except Exception as e:
                    self.logging.debug(f'Failed to get container with id "{container_id}": {e}')
            else:
                self.logging.debug(f'No container id found for "{get_id_function.__name__}"')
        raise RuntimeError('Failed to get current container')

    def get_current_container_id(self) -> str:
        return self.get_current_container().id

    @staticmethod
    def get_compose_project_name_from_labels(labels, default='nuvlaedge'):
        return labels.get('com.docker.compose.project', default)

    def launch_nuvlaedge_on_stop(self, on_stop_docker_image):
        error_msg = 'Cannot launch NuvlaEdge On-Stop graceful shutdown. ' \
                    'If decommissioning, container resources might be left behind'

        if not on_stop_docker_image:
            on_stop_docker_image = self.infer_on_stop_docker_image()
            if not on_stop_docker_image:
                self.logging.warning(f'{error_msg}: Docker image not found for NuvlaEdge On-Stop service')
                return

        myself_labels = {}
        try:
            myself_labels = self.get_current_container().labels
        except Exception as e:
            message = f'Failed to find the current container by id: {e}'
            self.logging.warning(message)

        project_name = self.get_compose_project_name_from_labels(myself_labels)

        random_identifier = ''.join(random.choices(string.ascii_uppercase, k=5))
        now = datetime.strftime(datetime.utcnow(), '%d-%m-%Y_%H%M%S')
        on_stop_container_name = f"{project_name}-on-stop-{random_identifier}-{now}"

        label = {
            "nuvlaedge.on-stop": "True"
        }
        self.client.containers.run(on_stop_docker_image,
                                   name=on_stop_container_name,
                                   labels=label,
                                   environment=[f'PROJECT_NAME={project_name}'],
                                   volumes={
                                       '/var/run/docker.sock': {
                                           'bind': '/var/run/docker.sock',
                                           'mode': 'ro'
                                       }
                                   },
                                   detach=True)

    def get_node_id(self):
        return self.get_node_info().get("Swarm", {}).get("NodeID")

    def list_nodes(self, optional_filter={}):
        return self.client.nodes.list(filters=optional_filter)

    def get_cluster_managers(self):
        remote_managers = self.get_node_info().get('Swarm', {}).get('RemoteManagers')
        cluster_managers = []
        if remote_managers and isinstance(remote_managers, list):
            cluster_managers = [rm.get('NodeID') for rm in remote_managers]

        return cluster_managers

    def read_system_issues(self, node_info):
        errors = []
        warnings = []
        if node_info.get('Swarm', {}).get('Error'):
            errors.append(node_info.get('Swarm', {}).get('Error'))

        if node_info.get('Warnings'):
            warnings += node_info.get('Warnings')

        return errors, warnings

    def set_nuvlaedge_node_label(self, node_id=None):
        if not node_id:
            node_id = self.get_node_id()
        default_err_msg = f'Unable to set NuvlaEdge node label for {node_id}'

        try:
            node = self.client.nodes.get(node_id)
        except docker.errors.APIError as e:
            if self.lost_quorum_hint in str(e):
                # quorum is lost
                msg = 'Quorum is lost. This node will not support Service and Cluster management'
                self.logging.warning(msg)
                err, warn = self.read_system_issues(self.get_node_info())
                err_msg = err[0] if err else msg
                return False, err_msg

            return False, default_err_msg
        try:
            node_spec = node.attrs['Spec']
        except KeyError as e:
            self.logging.error(f'Cannot get node Spec for {node_id}: {str(e)}')
            return False, default_err_msg

        node_labels = node_spec.get('Labels', {})
        if utils.node_label_key not in node_labels.keys() and isinstance(node_spec, dict):
            node_labels[utils.node_label_key] = 'True'
            node_spec['Labels'] = node_labels
            self.logging.info(f'Updating this node ({node_id}) with label {utils.node_label_key}')
            node.update(node_spec)

        return True, None

    def restart_credentials_manager(self):
        try:
            self.client.api.restart(self.credentials_manager_component, timeout=30)
        except docker.errors.NotFound:
            self.logging.exception(f"Container {self.credentials_manager_component} is not running. Nothing to do...")

    def find_nuvlaedge_agent_container(self):
        try:
            current_container = self.get_current_container()
            project_name = self.get_compose_project_name_from_labels(current_container.labels)
        except Exception as e:
            self.logging.warning(f'Failed to get current container. Cannot find agent container. {e}')
            return None, 'Cannot find Agent container'

        filters = {'label': ['nuvlaedge.component=True',
                             'com.docker.compose.service=agent',
                             f'com.docker.compose.project={project_name}']}
        try:
            return self.client.containers.list(filters=filters)[0], None
        except IndexError:
            message = 'Agent container not found'
            self.logging.warning(message)
            return None, message

    def list_all_containers_in_this_node(self):
        return self.client.containers.list(all=True)

    def count_images_in_this_host(self):
        return self.get_node_info().get("Images")

    def get_version(self):
        return self.client.version()["Components"][0]["Version"].split(".")[0].replace('v', '')


# --------------------
class Containers:
    """ Common set of methods and variables for the NuvlaEdge system-manager
    """
    def __init__(self, logging):
        """ Constructs a Container object
        """
        self.docker_socket_file = '/var/run/docker.sock'

        if ORCHESTRATOR == 'kubernetes':
            self.container_runtime = Kubernetes(logging)
        else:
            if os.path.exists(self.docker_socket_file):
                self.container_runtime = Docker(logging)
            else:
                raise Exception(f'Orchestrator is "{ORCHESTRATOR}", but file {self.docker_socket_file} is not present')
