import os
import logging
from pathlib import Path
import socket
import string
from datetime import datetime

import docker
import docker.errors
from nuvlaedge.system_manager.orchestrator import COEClient
from nuvlaedge.system_manager.common import utils
from nuvlaedge.common.constants import CTE


logger = logging.getLogger(__name__)


class Docker(COEClient):
    """
    Docker client
    """

    def __init__(self):
        super().__init__()
        self.client = docker.from_env()
        self.minimum_version = 18
        self.lost_quorum_hint = 'possible that too few managers are online'
        self.credentials_manager_component = utils.compose_project_name + "-compute-api"

        self.orchestrator = 'docker'
        self.agent_dns = utils.compose_project_name + "-agent"
        self.my_component_name = utils.compose_project_name + '-system-manager'
        self.dg_encrypt_options = self.load_data_gateway_network_options()
        self.current_image = self._get_current_image() or self.current_image

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
            logger.warning(f'Since {utils.nuvlaedge_shared_net} already exists, the provided '
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
            logger.error("Your Docker version is too old: {}. MIN REQUIREMENTS: Docker {} or newer"
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
            if container.status.lower() == "paused":
                return container.attrs['Config']['Image']
        except docker.errors.NotFound as e:
            logger.warning(f"Container {on_stop_container_name} not found: {str(e)}")
        except (AttributeError, KeyError) as e:
            logger.warning(f'Unable to infer Docker image for {on_stop_container_name}: {str(e)}')
        except Exception as e:
            logger.warning(f"Unable to search for container {on_stop_container_name}. Reason: {str(e)}")

        return self.current_image

    @staticmethod
    def get_current_image_from_env():
        # TODO: Centrilise COE clients to nuvlaedge level module to prevent cross import from agent to sm and viceversa
        registry = os.getenv('NE_IMAGE_REGISTRY', '')
        organization = os.getenv('NE_IMAGE_ORGANIZATION', 'sixsq')
        repository = os.getenv('NE_IMAGE_REPOSITORY', 'nuvlaedge')
        tag = os.getenv('NE_IMAGE_TAG', 'latest')
        name = os.getenv('NE_IMAGE_NAME', f'{organization}/{repository}')
        return f'{registry}{name}:{tag}'

    def _get_current_image(self):
        try:
            return self.get_current_container().attrs['Config']['Image']
        except docker.errors.NotFound as e:
            logger.error(f"Current container not found. Reason: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get current container. Reason: {str(e)}")

        image = self.get_current_image_from_env()
        logger.error(f'Failed to get current container. Using fallback (built from environment): {image}')
        return image

    def _get_container_id_from_cgroup(self):
        try:
            with open('/proc/self/cgroup', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cgroup: {e}')

    def _get_container_id_from_cpuset(self):
        try:
            with open('/proc/1/cpuset', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cpuset: {e}')

    def _get_container_id_from_hostname(self):
        try:
            return socket.gethostname().strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from hostname: {e}')

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
                    logger.debug(f'Failed to get container with id "{container_id}": {e}')
            else:
                logger.debug(f'No container id found for "{get_id_function.__name__}"')
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
                logger.warning(f'{error_msg}: Docker image not found for NuvlaEdge On-Stop service')
                return

        myself_labels = {}
        try:
            myself_labels = self.get_current_container().labels
        except Exception as e:
            message = f'Failed to find the current container by id: {e}'
            logger.warning(message)

        project_name = self.get_compose_project_name_from_labels(myself_labels)

        random_identifier = ''.join(utils.random_choices(string.ascii_uppercase, 5))
        now = datetime.strftime(datetime.utcnow(), '%d-%m-%Y_%H%M%S')
        on_stop_container_name = f"{project_name}-on-stop-{random_identifier}-{now}"

        label = {
            "nuvlaedge.on-stop": "True"
        }
        self.client.containers.run(on_stop_docker_image,
                                   name=on_stop_container_name,
                                   entrypoint="on-stop",
                                   labels=label,
                                   environment=[f'PROJECT_NAME={project_name}'],
                                   volumes={
                                       CTE.DOCKER_SOCKET_FILE_DEFAULT: {
                                           'bind': CTE.DOCKER_SOCKET_FILE_DEFAULT,
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
                logger.warning(msg)
                err, _ = self.read_system_issues(self.get_node_info())
                err_msg = err[0] if err else msg
                return False, err_msg

            return False, default_err_msg
        try:
            node_spec = node.attrs['Spec']
        except KeyError as e:
            logger.error(f'Cannot get node Spec for {node_id}: {str(e)}')
            return False, default_err_msg

        node_labels = node_spec.get('Labels', {})
        if utils.node_label_key not in node_labels.keys() and isinstance(node_spec, dict):
            node_labels[utils.node_label_key] = 'True'
            node_spec['Labels'] = node_labels
            logger.info(f'Updating this node ({node_id}) with label {utils.node_label_key}')
            node.update(node_spec)

        return True, None

    def restart_credentials_manager(self):
        try:
            self.client.api.restart(self.credentials_manager_component, timeout=30)
        except docker.errors.NotFound:
            logger.exception(f"Container {self.credentials_manager_component} is not running. Nothing to do...")

    def find_nuvlaedge_agent_container(self):
        try:
            current_container = self.get_current_container()
            project_name = self.get_compose_project_name_from_labels(current_container.labels)
        except Exception as e:
            logger.warning(f'Failed to get current container. Cannot find agent container. {e}')
            return None, 'Cannot find Agent container'

        filters = {'label': ['nuvlaedge.component=True',
                             'com.docker.compose.service=agent',
                             f'com.docker.compose.project={project_name}']}
        try:
            return self.client.containers.list(filters=filters)[0], None
        except IndexError:
            message = 'Agent container not found'
            logger.warning(message)
            return None, message

    def list_all_containers_in_this_node(self):
        return self.client.containers.list(all=True)

    def count_images_in_this_host(self):
        return self.get_node_info().get("Images")

    def get_version(self):
        return self.client.version()["Components"][0]["Version"].split(".")[0].replace('v', '')