import base64
import datetime
import logging
import os
import socket
import time
from subprocess import run, PIPE, TimeoutExpired
from typing import List, Optional, Dict
import requests
import re
import yaml

import docker
import docker.errors
from docker.models.containers import Container

from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.agent.common import util
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.utils import format_datetime_for_nuvla

logger: logging.Logger = get_nuvlaedge_logger(__name__)

docker_socket_file_default = CTE.DOCKER_SOCKET_FILE_DEFAULT


class InferIPError(Exception):
    ...


class DockerClient(COEClient):
    """
    Docker client
    """

    CLIENT_NAME = 'Docker'
    ORCHESTRATOR = 'docker'
    ORCHESTRATOR_COE = 'swarm'

    infra_service_endpoint_keyname = 'swarm-endpoint'
    join_token_manager_keyname = 'swarm-token-manager'
    join_token_worker_keyname = 'swarm-token-worker'

    def __init__(self):
        super().__init__()
        self.client = docker.from_env()
        self.lost_quorum_hint = 'possible that too few managers are online'
        self.data_gateway_name = "data-gateway"
        self._current_image = None
        self.job_engine_lite_image = os.getenv('NUVLAEDGE_JOB_ENGINE_LITE_IMAGE') or self.current_image

        self.last_node_info: float = 0.0
        self._node_info: dict = {}

    def list_raw_resources(self, resource_type) -> list[dict] | None:

        def get_keys(*keys):
            def f(d):
                return ' '.join([str(d.get(k, '')) for k in keys])
            return f

        api = self.client.api
        match resource_type:
            case 'images':
                images = sorted(api.images(), key=get_keys('Created', 'Id'))
                for i in images:
                    repo_tags = i.get('RepoTags') or []
                    repo_digests = i.get('RepoDigests') or []
                    repo_tags.sort()
                    repo_digests.sort()
                    if repo_tags:
                        repo_tag = repo_tags[0].split(':', 1)
                        i['Repository'] = repo_tag[0]
                        if len(repo_tag) > 1:
                            i['Tag'] = repo_tag[1]
                    elif repo_digests:
                        i['Repository'] = repo_digests[0].split('@', 1)[0]

                return images
            case 'volumes':
                return sorted(api.volumes().get('Volumes', []), key=get_keys('CreatedAt', 'Name'))
            case 'networks':
                return sorted(api.networks(), key=get_keys('Created', 'Id'))
            case 'containers':
                containers = sorted(api.containers(all=True, size=True), key=get_keys('Created', 'Id'))
                for c in containers:
                    c.get('Mounts', []).sort(key=get_keys('Destination'))
                    c.get('Ports', []).sort(key=get_keys('PrivatePort'))
                    names = c.get('Names', [])
                    names.sort()
                    if names:
                        c['Name'] = names[0].lstrip('/')
                return containers
            case 'services':
                return sorted(api.services(status=True), key=get_keys('CreatedAt', 'ID'))
            case 'tasks':
                return sorted(api.tasks(), key=get_keys('CreatedAt', 'ID'))
            case 'configs':
                return sorted(api.configs(), key=get_keys('CreatedAt', 'ID'))
            case 'secrets':
                return sorted(api.secrets(), key=get_keys('CreatedAt', 'ID'))

        logger.error(f'COE resource type "{resource_type}" is not supported')
        return None

    @property
    def node_info(self):
        """
            Retrieves information about the node from the Docker API.

            This method caches the node information for subsequent calls within a 1-second interval,
            in order to avoid making unnecessary requests to the Docker API.

            Returns:
                dict: A dictionary containing information about the node.

            Example:
                {'Architecture': 'x86_64', 'OperatingSystem': 'Linux', '...'}
        """
        # Do not call Docker API for successive uses of node information (1 second)
        if time.time() - self.last_node_info > 1:
            self._node_info = self.client.info()
            self.last_node_info = time.time()
        return self._node_info

    def get_client_version(self) -> str:
        """
        Returns the version of the client.

        Returns:
            str: The version of the client.

        """
        return self.client.version()['Version']

    def get_node_info(self):
        """
        Retrieves the information of the node.

        Returns:
            The information of the node.

        """
        return self.node_info

    def get_host_os(self):
        """
        Returns the operating system and kernel version of the host.

        Returns:
            str: The operating system and kernel version of the host.
        """
        node_info = self.node_info
        return f"{node_info['OperatingSystem']} {node_info['KernelVersion']}"

    def get_join_tokens(self) -> tuple:
        """
        Method to get the join tokens for manager and worker nodes in a Swarm cluster.

        Returns:
            tuple: A tuple containing the join token for manager and worker nodes respectively.
                   If the join tokens are not available or if there is an API error, returns None.

        """
        try:
            if self.client.swarm.attrs:
                return self.client.swarm.attrs['JoinTokens']['Manager'], \
                    self.client.swarm.attrs['JoinTokens']['Worker']
        except docker.errors.APIError as e:
            if self.lost_quorum_hint in str(e):
                # quorum is lost
                logger.warning('Quorum is lost. This node will no longer support Service and Cluster management')

        return None, None

    def list_nodes(self, optional_filter: dict = None):
        """
        Args:
            optional_filter: A dictionary specifying optional filtering for the list of nodes. The keys in the dictionary represent the filtering criteria and the values represent the corresponding
        * filter values.

        Returns:
            A list of nodes that match the given optional filtering criteria.
        """
        return self.client.nodes.list(filters=optional_filter)

    def get_cluster_info(self, default_cluster_name=None):
        """
        Args:
            default_cluster_name: Optional. The default name of the cluster. If not provided, it will use the default value None.

        Returns:
            A dictionary containing cluster information. The dictionary has the following keys:
                - 'cluster-id': The ID of the cluster.
                - 'cluster-orchestrator': The orchestrator used by the cluster.
                - 'cluster-managers': A list of IDs of cluster managers.
                - 'cluster-workers': A list of IDs of cluster workers.

        Note:
            This method retrieves information about the cluster. If the control is available or the current node is one
             of the cluster managers, it will return the cluster information. Otherwise, an empty dictionary is returned
        """
        node_info = self.node_info
        swarm_info = node_info['Swarm']

        if swarm_info.get('ControlAvailable') or self.get_node_id(node_info) in self.get_cluster_managers():
            cluster_id = swarm_info.get('Cluster', {}).get('ID')
            managers = []
            workers = []
            for manager in self.list_nodes(optional_filter={'role': 'manager'}):
                if manager not in managers and manager.attrs.get('Status', {}).get('State', '').lower() == 'ready':
                    managers.append(manager.id)

            for worker in self.list_nodes(optional_filter={'role': 'worker'}):
                if worker not in workers and worker.attrs.get('Status', {}).get('State', '').lower() == 'ready':
                    workers.append(worker.id)

            return {
                'cluster-id': cluster_id,
                'cluster-orchestrator': self.ORCHESTRATOR_COE,
                'cluster-managers': managers,
                'cluster-workers': workers
            }
        else:
            return {}

    def find_compute_api_external_port(self) -> str:
        """
        Find the external port of the compute API container.

        Returns:
            The external port of the compute API container as a string.
            If the container is not found or the port cannot be inferred, an empty string is returned.
        """
        try:
            container = self._get_component_container(util.compute_api_service_name)
        except (docker.errors.NotFound, docker.errors.APIError, TimeoutError) as ex:
            logger.debug(f'Compute API container not found {ex}')
            return ''

        try:
            return container.ports['5000/tcp'][0]['HostPort']
        except (KeyError, IndexError) as ex:
            logger.warning(f'Cannot infer ComputeAPI external port, container attributes not properly formatted: {ex}')
        return ''

    def get_api_ip_port(self):
        """

        Get the IP address and port of the NuvlaEdge API.

        Returns:
            Tuple: A tuple containing the IP address and the port of the NuvlaEdge API.

        """
        node_info = self.node_info
        compute_api_external_port = self.find_compute_api_external_port()
        ip = node_info.get("Swarm", {}).get("NodeAddr")
        if not ip:
            # then probably this isn't running in Swarm mode
            try:
                ip = None
                with open(f'{self.hostfs}/proc/net/tcp') as ipfile:
                    ips = ipfile.readlines()
                    for line in ips[1:]:
                        cols = line.strip().split(' ')
                        if cols[1].startswith('00000000') or cols[2].startswith('00000000'):
                            continue
                        hex_ip = cols[1].split(':')[0]
                        ip = f'{int(hex_ip[len(hex_ip) - 2:], 16)}.' \
                             f'{int(hex_ip[len(hex_ip) - 4:len(hex_ip) - 2], 16)}.' \
                             f'{int(hex_ip[len(hex_ip) - 6:len(hex_ip) - 4], 16)}.' \
                             f'{int(hex_ip[len(hex_ip) - 8:len(hex_ip) - 6], 16)}'
                        break
                if not ip:
                    raise InferIPError('Cannot infer IP')
            except (IOError, InferIPError, IndexError):
                ip = '127.0.0.1'
            else:
                # Double check - we should never get here
                if not ip:
                    logger.warning("Cannot infer the NuvlaEdge API IP!")
                    return None, compute_api_external_port

        return ip, compute_api_external_port

    def has_pull_job_capability(self):
        return True

    def get_node_labels(self):
        """
        Obtains the labels assigned to the current Docker swarm node.

        Returns:
            A list of labels assigned to the node.

        Raises:
            KeyError: If the `node_info` dictionary does not contain the "Swarm" or "NodeID" keys.
            docker.errors.APIError: If there is an error accessing the Docker API.
            docker.errors.NullResource: If the `node_id` is not found or is NULL.

        Note:
            If the error message contains the phrase "node is not a swarm manager", then no labels are returned.

        """
        try:
            node_id = self.node_info["Swarm"]["NodeID"]
            node_labels = self.client.api.inspect_node(node_id)["Spec"]["Labels"]
        except (KeyError, docker.errors.APIError, docker.errors.NullResource) as e:
            if "node is not a swarm manager" not in str(e).lower():
                logger.debug(f"Cannot get node labels: {str(e)}")
            return []

        return self.cast_dict_to_list(node_labels)

    def is_vpn_client_running(self):
        """
        Checks if the VPN client is currently running.

        Returns:
            bool: True if the VPN client is running, False otherwise.
        """
        it_vpn_container = self._get_component_container(util.vpn_client_service_name)
        return it_vpn_container.status == 'running'

    def install_ssh_key(self, ssh_pub_key, host_home):
        """
        Args:
            ssh_pub_key: The SSH public key to be installed on the remote host.
            host_home: The home directory of the user on the remote host.

        Returns:
            bool: Returns `True` if the SSH key installation was successful, otherwise returns `False`.

        """
        ssh_folder = '/tmp/ssh'
        cmd = "-c 'echo -e \"${SSH_PUB}\" >> %s'" % f'{ssh_folder}/authorized_keys'

        self.client.containers.run(self.current_image,
                                   remove=True,
                                   entrypoint='sh',
                                   command=cmd,
                                   environment={
                                       'SSH_PUB': ssh_pub_key
                                   },
                                   volumes={
                                       f'{host_home}/.ssh': {
                                           'bind': ssh_folder
                                       }})

        return True

    def is_nuvla_job_running(self, job_id, job_execution_id) -> bool:
        """
        Checks if a specified Nuvla job is currently running.

        This method retrieves the data of a container associated with the provided job_execution_id
        and checks its status. If the container status is 'running' or 'restarting', the method logs
        necessary details and returns True, indicating that the job is running. If the status is 'created',
        the method removes the existing container and logs a warning. If the container is not found,
        then it stopped by itself and is assumed to be running. The method logs any exceptions encountered
        during the execution.

        Args:
            job_id (str): The ID of the job to be checked.
            job_execution_id (str): The ID of the job execution to be checked.

        Returns:
            bool:
            Returns True if the Nuvla job identified by job_id and job_execution_id is running.
            Returns False otherwise, if the container is either stopped, removed or killed.

        Raises:
            docker.errors.NotFound:
                Raised when the docker container of a job_execution_id is not found.
            Exception:
                Raised when an unexpected error occurs. Logs an error message with the job_id and the exception encountered.
        """
        try:
            job_container = self.client.containers.get(job_execution_id)
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f'Cannot handle job {job_id}. Reason: {str(e)}')
            # assume it is running so we don't mess anything
            return True

        try:
            if job_container.status.lower() in ['running', 'restarting']:
                logger.info(f'Job {job_id} is already running in container {job_container.name}')
                return True
            elif job_container.status.lower() in ['created', 'exited']:
                logger.warning(f'Job {job_id} was created but not started. Removing it and starting a new one')
                job_container.remove()
            else:
                # then it is stopped or dead. force kill it and re-initiate
                job_container.kill()
        except AttributeError:
            # assume it is running so we don't mess anything
            return True
        except docker.errors.NotFound:
            # then it stopped by itself...maybe it ran already and just finished
            # let's not do anything just in case this is a late coming job. In the next
            # telemetry cycle, if job is there again, then we run it because this
            # container is already gone
            return True

        return False

    def _get_component_container_by_service_name(self, service_name):
        """
        This function gets the component container associated with a specific service name.

        It first retrieves the project name using the `get_nuvlaedge_project_name` method,
        and creates a list of labels associated with the desired service and project. It then
        uses this list of labels to filter the available containers and retrieves all that match.

        If no matching containers are found, it raises a `docker.errors.NotFound` exception.
        If more than one matching containers are found, it logs a warning and returns the first one.

        Args:
            service_name (str): The name of the service for which the component container should be retrieved.

        Returns:
            docker.models.containers.Container: The Docker Container instance that matches the service name.

        Raises:
            docker.errors.NotFound: If no container associated with the specified labels is found.
        """
        project_name = self.get_nuvlaedge_project_name()
        labels = [util.base_label,
                  f'com.docker.compose.service={service_name}',
                  f'com.docker.compose.project={project_name}']
        filters = {'label': labels}
        containers = self.list_containers(filters=filters, all=True)
        containers_count = len(containers)
        if containers_count < 1:
            raise docker.errors.NotFound(f'Container with the following labels not found: {labels}')
        elif containers_count > 1:
            logger.warning(f'More than one component container found for service name "{service_name}" '
                           f'and project name "{project_name}": {containers}')
        return containers[0]

    def _get_component_container(self, service_name, container_name=None):
        """
        This method is used to get the Docker container for a specific service.

        If the specific container name is not provided, the container name is composed by appending the service name after the compose project name.
        Subsequently, it attempts to retrieve the Docker container using the client's 'get' method and handles any 'NotFound' and 'APIError' exceptions.
        It logs the error message if it fails to find the container by its name and tries to find the container using '_get_component_container_by_service_name' method.
        If it still fails, it logs the error message again and lets the exception propagate further.

        Args:
            service_name (str): The name of the service. A container for this service will be fetched.
            container_name (str, optional): The specific name of the container we are looking for. Defaults to None, which means the container name is generated by appending the service_name after the compose project name.

        Returns:
            docker.models.containers.Container: The container object if found.

        Raises:
            docker.errors.NotFound: If the specified Docker container is not found.
            docker.errors.APIError: If an API error occurred while trying to access Docker.
        """
        if not container_name:
            container_name = util.compose_project_name + '-' + service_name

        try:
            return self.client.containers.get(container_name)
        except (docker.errors.NotFound, docker.errors.APIError) as e:
            logger.debug(f'Failed to find {service_name} container by name ({container_name}). '
                         f'Trying by project and service name: {e}')

        try:
            return self._get_component_container_by_service_name(service_name)
        except (docker.errors.NotFound, docker.errors.APIError) as e:
            logger.debug(f'Failed to find {service_name} container by project and service name: {e}')
            raise

    def _create_container(self, **create_kwargs):
        """
        Args:
            **create_kwargs: Any keyword arguments needed to create the container.

        Returns:
            The created container.

        """
        try:
            return self.client.containers.create(**create_kwargs)
        except docker.errors.ImageNotFound:
            self.client.images.pull(create_kwargs['image'])
            return self.client.containers.create(**create_kwargs)

    def launch_job(self, job_id, job_execution_id, nuvla_endpoint,
                   nuvla_endpoint_insecure=False, api_key=None, api_secret=None,
                   docker_image=None, cookies=None):
        """
        Launches a job on the local node using the specified Docker image. Takes into account
        various parameters to configure the Docker container. It also handles errors during
        the container creation and starting process.

        Args:
            job_id (str): Unique identifier of the job to be launched.
            job_execution_id (str): Unique identifier of the job execution.
            nuvla_endpoint (str): Endpoint for the Nuvla API.
            nuvla_endpoint_insecure (bool, optional): If true, the Nuvla endpoint is insecure. Defaults to False.
            api_key (str, optional): API Key for the Nuvla API. Defaults to None.
            api_secret (str, optional): API Secret for the Nuvla API. Defaults to None.
            docker_image (str, optional): Docker image to be used for the job. Defaults to None.
            cookies(str, optional): Nuvla Session cookie. Defaults to None.
        Raises:
            Exception: If there's an error during the container creation or starting process.

        Returns:
            None
        """
        image = docker_image if docker_image else self.job_engine_lite_image
        if not image:
            image = util.fallback_image
            logger.error('Failed to find docker image name to execute job. Fallback image will be used')

        # Get the compute-api network
        local_net = None
        try:
            compute_api = self._get_component_container(util.compute_api_service_name)
            local_net = list(compute_api.attrs['NetworkSettings']['Networks'].keys())[0]
        except Exception as e:
            logger.debug(f'Cannot infer compute-api network for local job {job_id}: {e}')

        # Get environment variables and volumes from job-engine-lite container
        volumes = {
            docker_socket_file_default: {
                'bind': docker_socket_file_default,
                'mode': 'rw'
            }
        }

        authentication = ""
        if api_key and api_secret:
            authentication = (f'--api-key {api_key} '
                              f'--api-secret {api_secret} ')

        command = (f'-- /app/job_executor.py '
                   f'--api-url https://{nuvla_endpoint} '
                   f'{authentication}'
                   f'--nuvlaedge-fs {FILE_NAMES.root_fs} '
                   f'--job-id {job_id}')

        if nuvla_endpoint_insecure:
            command += ' --api-insecure'

        environment = {k: v for k, v in os.environ.items()
                       if k.startswith('NE_IMAGE_') or k.startswith('JOB_')}

        if cookies:
            environment["JOB_COOKIES"] = cookies

        logger.info(f'Starting job "{job_id}" with docker image "{image}" and command: "{command}"')

        create_kwargs = dict(
            image=image,
            command=command,
            name=job_execution_id,
            hostname=job_execution_id,
            auto_remove=True,
            detach=True,
            network=local_net,
            volumes=volumes,
            environment=environment
        )
        try:
            try:
                container = self._create_container(**create_kwargs)
            except Exception as e:
                create_kwargs['image'] = self.current_image if image != self.current_image else util.fallback_image

                logger.error(f'Failed to create container to execute job "{job_id}" with image "{image}": {e}. \n'
                             f'Retrying with image "{create_kwargs["image"]}" as fallback.')

                container = self._create_container(**create_kwargs)

        except Exception as e:
            logger.critical(f'Failed to create container to execute job "{job_id}": {e}')
            try:
                self.client.api.remove_container(job_execution_id, force=True)
            except Exception as ex:
                logger.debug(
                    f'Failed to remove container {job_execution_id} which might have been partially created: {ex}')
            raise

        try:
            # for some jobs (like clustering), it is better if the job container is also in the default bridge network,
            # so it doesn't get affected by network changes in the NuvlaEdge.
            self.client.api.connect_container_to_network(job_execution_id, 'bridge')
        except Exception as e:
            logger.warning(f'Could not attach {job_execution_id} to bridge network: {str(e)}')

        try:
            resp = container.start()
            logger.info(f'Job "{job_id}" started with response: {resp}')
        except Exception as ex:
            logger.warning(f"Error when starting container for job {job_id}", exc_info=True)
            container.remove(force=True)
            raise

    @staticmethod
    def collect_container_metrics_cpu(container_stats: dict, metrics: dict, old_version=False):
        """
        Args:
            container_stats (dict): A dictionary containing container statistics.
            old_version (bool, optional): If True, only the CPU usage percentage is added.
                If False, a tuple containing the CPU usage percentage and the number of online CPUs is added.
                Defaults to False.
            metrics (dict): A dictionary containing the metrics data which needs to be populated

        """
        cs = container_stats
        cpu_percent = float('nan')

        try:
            online_cpus_alt = len(cs["cpu_stats"]["cpu_usage"].get("percpu_usage", []))
            online_cpus = cs["cpu_stats"].get('online_cpus', online_cpus_alt)

            cpu_delta = \
                float(cs["cpu_stats"]["cpu_usage"]["total_usage"]) - \
                float(cs["precpu_stats"]["cpu_usage"]["total_usage"])
            system_delta = \
                float(cs["cpu_stats"]["system_cpu_usage"]) - \
                float(cs["precpu_stats"]["system_cpu_usage"])

            if system_delta > 0.0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            logger.warning('Failed to get CPU usage for container '
                           f'{cs.get("id", "?")[:12]} ({cs.get("name")}): {e}')
            return

        if old_version:
            metrics['cpu-percent'] = f'{round(cpu_percent):.2f}'
        else:
            metrics['cpu-usage'] = cpu_percent
            metrics['cpu-capacity'] = online_cpus

    @staticmethod
    def collect_container_metrics_mem(cstats: dict, metrics: dict, old_version=False):
        """
        Calculates the Memory consumption for a give container

        Args:
            cstats: A dictionary containing container metrics data.
            metrics: A dictionary containing the metrics data which needs to be populated.
            old_version: If True, memory percent is added along with mem-usage-limit.
            If False, memory usage and memory limit are added in terms of bytes.

        Returns:
            A tuple with the memory percentage, memory usage, and memory limit of the container.

        """
        try:
            # Get total mem usage and subtract cached memory
            if cstats["memory_stats"]["stats"].get('rss'):
                mem_usage = (float(cstats["memory_stats"]["stats"]["rss"]))
            else:
                mem_usage = (float(cstats["memory_stats"]["usage"]) -
                             float(cstats["memory_stats"]["stats"]["file"]))
            mem_limit = float(cstats["memory_stats"]["limit"])
        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            mem_usage = mem_limit = 0.00
            logger.warning('Failed to get Memory consumption for container '
                           f'{cstats.get("id", "?")[:12]} ({cstats.get("name")}): {e}')
        if old_version:
            metrics['mem-usage-limit'] = (f'{round(mem_usage / 1024 / 1024, 1)}MiB / '
                                          f'{round(mem_limit / 1024 / 1024, 1)}MiB')
            metrics['mem-percent'] = str(round(mem_usage / mem_limit * 100, 2)) if mem_limit > 0 else 0.0
        else:
            metrics['mem-usage'] = mem_usage
            metrics['mem-limit'] = mem_limit

    @staticmethod
    def collect_container_metrics_net(cstats: dict, metrics: dict, old_version=False):
        """
        Collects network metrics for a container.

        Args:
            cstats (dict): A dictionary containing container statistics.
            metrics (dict): A dictionary containing the metrics data which needs to be populated.
            old_version (bool, optional): If True, only the network input and output are added in MB.
            If False, the network input and output are added separately in bytes. Defaults to False.

        Returns:
            tuple: A tuple containing the network input and network output in MB.

        """
        net_in = net_out = 0.0
        try:
            if "networks" in cstats:
                net_in = sum(cstats["networks"][iface]["rx_bytes"]
                             for iface in cstats["networks"])
                net_out = sum(cstats["networks"][iface]["tx_bytes"]
                              for iface in cstats["networks"])
        except (IndexError, KeyError, ValueError) as e:
            logger.warning('Failed to get Network consumption for container '
                           f'{cstats.get("id", "?")[:12]} ({cstats.get("name")}): {e}')

        if old_version:
            metrics['net-in-out'] = (f'{round(net_in / 1000 / 1000, 1)}MB / '
                                     f'{round(net_out / 1000 / 1000, 1)}MB')
        else:
            metrics['net-in'] = net_in
            metrics['net-out'] = net_out

    @staticmethod
    def collect_container_metrics_block(cstats: dict, metrics: dict, old_version=False):
        """
        Calculates the block consumption for a give container

        Args:
            cstats (dict): Dictionary containing container statistics.
            metrics (dict): Dictionary containing the metrics data which needs to be populated.
            old_version (bool, optional): If True, only the block usage (In) and block usage (Out) are added in MB.
            If False, the block usage (In) and block usage (Out) are added separately in bytes. Defaults to False.

        Returns:
            tuple: Tuple containing the block usage (Out) and block usage (In) for the container.

        Note:
            The block usage is calculated by dividing the value of "io_service_bytes_recursive" in the "blkio_stats"
            dictionary by 1000 and then by 1000 again to convert bytes to megabytes.

        """
        blk_out = blk_in = 0.0

        io_bytes_recursive = cstats.get("blkio_stats", {}).get("io_service_bytes_recursive", [])
        if io_bytes_recursive:
            try:
                blk_in = float(io_bytes_recursive[0]["value"])
            except (IndexError, KeyError, TypeError, ValueError) as e:
                logger.warning('Failed to get block usage (In) for container '
                               f'{cstats.get("id", "?")[:12]} ({cstats.get("name")}): {e}')
            try:
                blk_out = float(io_bytes_recursive[1]["value"])
            except (IndexError, KeyError, TypeError, ValueError) as e:
                logger.warning('Failed to get block usage (Out) for container '
                               f'{cstats.get("id", "?")[:12]} ({cstats.get("name")}): {e}')

        if old_version:
            metrics['blk-in-out'] = (f'{round(blk_in / 1000 / 1000, 1)}MB / '
                                     f'{round(blk_out / 1000 / 1000, 1)}MB')
        else:
            metrics['disk-in'] = blk_in
            metrics['disk-out'] = blk_out

    def list_containers(self, *args, **kwargs):
        """
        Bug: Sometime the Docker Python API fails to get the list of containers with the exception:
        'requests.exceptions.HTTPError: 404 Client Error: Not Found'
        This is due to docker listing containers and then inspecting them one by one.
        If in the meantime a container has been removed, it fails with the above exception.
        As a workaround, the list operation is retried if an exception occurs.
        """
        tries = 0
        max_tries = 3

        if 'ignore_removed' not in kwargs:
            kwargs['ignore_removed'] = True

        while True:
            try:
                return self.client.containers.list(*args, **kwargs)
            except requests.exceptions.HTTPError:
                tries += 1
                logger.warning(f'Failed to list containers. Try {tries}/{max_tries}.')
                if tries >= max_tries:
                    raise

    def get_containers_stats(self):
        """
        Retrieves the statistics of all containers.

        Returns:
            A list of tuples, where each tuple contains the container object
            and its respective statistics.

        Raises:
            None.

        """
        containers_stats = []
        for container in self.list_containers():
            try:
                containers_stats.append((container, container.stats(stream=False)))
            except Exception as e:
                logger.warning('Failed to get stats for container '
                               f'{container.short_id} ({container.name}): {e}')
        return containers_stats

    def collect_container_metrics(self, old_version=False) -> List[Dict]:
        """

        Collects metrics for each container in the system.

        Returns a list of dictionaries, where each dictionary represents the metrics for a specific container.
        The dictionary will contain the following keys:

        # FIXME: these are old keys and need to be updated.
        - 'id': The ID of the container.
        - 'name': The name of the container.
        - 'container-status': The current status of the container.
        - 'cpu-percent': The CPU usage percentage for the container, rounded to two decimal places.
        - 'mem-usage-limit': The memory usage and limit for the container in MiB, formatted as "{usage}MiB / {limit}MiB".
        - 'mem-percent': The memory usage percentage for the container, rounded to two decimal places.
        - 'net-in-out': The network usage for the container in MB, formatted as "{in}MB / {out}MB".
        - 'blk-in-out': The block device usage for the container in MB, formatted as "{in}MB / {out}MB".
        - 'restart-count': The number of times the container has been restarted. If not available, it will be set to 0.

        """
        containers_metrics = []

        for container, stats in self.get_containers_stats():
            container_metric = {
                'id': container.id,
                'name': container.name,
                'restart-count': (int(container.attrs["RestartCount"])
                                  if "RestartCount" in container.attrs else 0),
            }
            if old_version:
                container_metric['container-status'] = container.attrs["State"]["Status"]
            else:
                container_metric['state'] = container.attrs["State"]["Status"]
                created = datetime.datetime.fromisoformat(container.attrs["Created"])
                container_metric['created-at'] = format_datetime_for_nuvla(created)
                started = datetime.datetime.fromisoformat(container.attrs["State"]["StartedAt"])
                container_metric['started-at'] = format_datetime_for_nuvla(started)
                container_metric['image'] = container.attrs['Config']['Image']
                container_metric['status'] = container.status
                nano_cpus = container.attrs.get('HostConfig', {}).get('NanoCpus', 0)
                container_metric['cpu-limit'] = (nano_cpus / 1000000000) or None

            # CPU
            self.collect_container_metrics_cpu(stats, container_metric, old_version)
            # RAM
            self.collect_container_metrics_mem(stats, container_metric, old_version)
            # NET
            self.collect_container_metrics_net(stats, container_metric, old_version)
            # DISK
            self.collect_container_metrics_block(stats, container_metric, old_version)

            containers_metrics.append(container_metric)

        return containers_metrics

    @staticmethod
    def _get_container_id_from_cgroup():
        """
        Get the container ID from the cgroup.

        Returns:
            The container ID extracted from the cgroup.

        """
        try:
            with open('/proc/self/cgroup', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cgroup: {e}')

    @staticmethod
    def _get_container_id_from_cpuset():
        """
        Get the container ID from the cpuset file.

        Returns:
            str: The container ID.

        """
        try:
            with open('/proc/1/cpuset', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cpuset: {e}')

    @staticmethod
    def _get_container_id_from_mountinfo():
        """
        Get the container ID from the mountinfo file.

        Returns:
            str: The container ID.

        """
        try:
            with open('/proc/self/mountinfo', 'r') as f:
                results = re.findall(r'.*containers/[^/]+', f.read())
                results = [r for r in results if '/rootfs/' not in r]
                return results[0].split('/')[-1]
        except Exception as e:
            logger.debug(f'Failed to get container id from mountinfo: {e}')

    @staticmethod
    def _get_container_id_from_hostname():
        """
        Get the container ID from the hostname.
        This static method is used to extract the container ID from the hostname. It utilizes the `socket.gethostname()`
         function to fetch the hostname and then strips any whitespace characters from it. In case of any errors or exceptions
         encountered during the process, it logs a debug message using the `logger` object indicating the failure.
        Returns:
            str: The container ID extracted from the hostname.

        """
        try:
            return socket.gethostname().strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from hostname: {e}')

    @staticmethod
    def _get_container_name_from_env():
        try:
            return os.environ['COMPOSE_PROJECT_NAME'] + '-agent'
        except Exception as e:
            logger.debug(f'Failed to get container name from environment: {e}')

    def get_current_container(self):
        """
        Get the current container.

        This method attempts to determine the ID of the current container by calling a list of ID retrieval functions. It then uses the ID to retrieve the corresponding container object from
        * the client.

        Returns:
            A container object representing the current container.

        """
        get_id_functions = [self._get_container_id_from_hostname,
                            self._get_container_id_from_cpuset,
                            self._get_container_id_from_cgroup,
                            self._get_container_id_from_mountinfo,
                            self._get_container_name_from_env]
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

    @staticmethod
    def get_config_files_from_labels(labels) -> List[str]:
        return labels.get('com.docker.compose.project.config_files', '').split(',')

    @staticmethod
    def get_working_dir_from_labels(labels) -> List[str]:
        return labels.get('com.docker.compose.project.working_dir', '')

    @staticmethod
    def get_container_env_variables(container, exclude: list[str] = None):
        env_vars = container.attrs.get('Config', {}).get('Env', [])
        if exclude is None:
            exclude = []
        return [env for env in env_vars if env.split('=')[0] not in exclude]

    def get_installation_parameters(self):
        """
        Return installation parameters based on the current container and its environment.

        Returns:
            dict: A dictionary containing the following installation parameters:
                - 'project-name': The name of the project.
                - 'working-dir': The working directory.
                - 'config-files': A list of unique configuration files.
                - 'environment': A list of unique environment variables.

                If all parameters are missing, None is returned.
        Raises:
            RuntimeError: If the current container cannot be found by ID.
        """
        try:
            myself = self.get_current_container()
        except RuntimeError:
            message = 'Failed to find the current container by id. Cannot proceed'
            logger.error(message)
            raise

        last_update = myself.attrs.get('Created', '')
        working_dir = self.get_working_dir_from_labels(myself.labels)
        config_files = self.get_config_files_from_labels(myself.labels)
        project_name = self.get_compose_project_name_from_labels(myself.labels)

        environment = self.get_container_env_variables(myself, self.ignore_env_variables)

        nuvlaedge_containers = self.get_all_nuvlaedge_containers()
        nuvlaedge_containers = list(filter(lambda x: x.id != myself.id, nuvlaedge_containers))
        for container in nuvlaedge_containers:
            c_labels = container.labels
            if self.get_compose_project_name_from_labels(c_labels, '') == project_name and \
                    self.get_working_dir_from_labels(c_labels) == working_dir:
                if container.attrs.get('Created', '') > last_update:
                    last_update = container.attrs.get('Created', '')
                    config_files = self.get_config_files_from_labels(c_labels)
                environment += self.get_container_env_variables(container, self.ignore_env_variables)

        unique_config_files = list(filter(None, set(config_files)))
        unique_env = list(filter(None, set(environment)))

        installation_parameters = {}
        if working_dir:
            installation_parameters['working-dir'] = working_dir
        if project_name:
            installation_parameters['project-name'] = project_name
        if unique_config_files:
            installation_parameters['config-files'] = unique_config_files
        if unique_env:
            installation_parameters['environment'] = unique_env

        return installation_parameters if installation_parameters else None

    def read_system_issues(self, node_info):
        errors = []
        warnings = []
        if node_info.get('Swarm', {}).get('Error'):
            errors.append(node_info.get('Swarm', {}).get('Error'))

        if node_info.get('Warnings'):
            warnings += node_info.get('Warnings')

        return errors, warnings

    def get_node_id(self, node_info):
        return node_info.get("Swarm", {}).get("NodeID")

    def get_cluster_id(self, node_info, default_cluster_name=None):
        return node_info.get('Swarm', {}).get('Cluster', {}).get('ID')

    def get_cluster_managers(self):
        remote_managers = self.node_info.get('Swarm', {}).get('RemoteManagers')
        cluster_managers = []
        if remote_managers and isinstance(remote_managers, list):
            cluster_managers = [rm.get('NodeID') for rm in remote_managers]

        return cluster_managers

    def get_host_architecture(self, node_info):
        return node_info["Architecture"]

    def get_hostname(self, node_info=None):
        return node_info["Name"]

    def get_cluster_join_address(self, node_id):
        for manager in self.node_info.get('Swarm', {}).get('RemoteManagers'):
            if node_id == manager.get('NodeID', ''):
                try:
                    return manager['Addr']
                except KeyError:
                    logger.warning(f'Unable to infer cluster-join-address attribute: {manager}')

        return None

    def is_node_active(self, node):
        if node.attrs.get('Status', {}).get('State', '').lower() == 'ready':
            return node.id

        return None

    def get_container_plugins(self):
        all_plugins = self.client.plugins.list()

        enabled_plugins = []
        for plugin in all_plugins:
            if plugin.enabled:
                enabled_plugins.append(plugin.name)

        return enabled_plugins

    def define_nuvla_infra_service(self,
                                   api_endpoint: str,
                                   client_ca=None,
                                   client_cert=None,
                                   client_key=None) -> dict:

        try:
            infra_service = self.infer_if_additional_coe_exists()
        except Exception as e:
            # this is a non-critical step, so we should never fail because of it
            logger.warning(f'Exception while trying to find additional COE: {e}')
            infra_service = {}

        if api_endpoint:
            infra_service["swarm-endpoint"] = api_endpoint

            if client_ca and client_cert and client_key:
                infra_service["swarm-client-ca"] = client_ca
                infra_service["swarm-client-cert"] = client_cert
                infra_service["swarm-client-key"] = client_key
        else:
            infra_service["swarm-endpoint"] = 'local'
            infra_service["swarm-client-ca"] = client_ca or 'null'
            infra_service["swarm-client-cert"] = client_cert or 'null'
            infra_service["swarm-client-key"] = client_key or 'null'

        return infra_service

    def get_partial_decommission_attributes(self) -> list:
        return ['swarm-token-manager',
                'swarm-token-worker',
                'swarm-client-key',
                'swarm-client-ca',
                'swarm-client-cert',
                'swarm-endpoint']

    def get_k3s_commissioning_info(self) -> dict:
        """
        Checks specifically if k3s is installed

        :param k3s_address: endpoint address for the kubernetes API
        :return: commissioning-ready kubernetes infra
        """
        vpn_ip = VPNHandler.get_vpn_ip()
        k3s_address = vpn_ip or self.get_api_ip_port()[0]

        k3s_cluster_info = {}
        k3s_conf = f'{self.hostfs}/etc/rancher/k3s/k3s.yaml'
        if not os.path.isfile(k3s_conf) or not k3s_address:
            return k3s_cluster_info

        with open(k3s_conf) as kubeconfig:
            try:
                k3s = yaml.safe_load(kubeconfig)
            except yaml.YAMLError:
                return k3s_cluster_info

        k3s_port = k3s['clusters'][0]['cluster']['server'].split(':')[-1]
        k3s_cluster_info['kubernetes-endpoint'] = f'https://{k3s_address}:{k3s_port}'
        try:
            ca = k3s["clusters"][0]["cluster"]["certificate-authority-data"]
            cert = k3s["users"][0]["user"]["client-certificate-data"]
            key = k3s["users"][0]["user"]["client-key-data"]
            k3s_cluster_info['kubernetes-client-ca'] = base64.b64decode(ca).decode()
            k3s_cluster_info['kubernetes-client-cert'] = base64.b64decode(cert).decode()
            k3s_cluster_info['kubernetes-client-key'] = base64.b64decode(key).decode()
        except Exception as e:
            logger.warning(f'Unable to lookup k3s certificates: {str(e)}')
            return {}

        return k3s_cluster_info

    def infer_if_additional_coe_exists(self, fallback_address=None) -> dict:
        # Check if there is a k8s installation available as well
        k8s_apiserver_process = 'kube-apiserver'
        k8s_cluster_info = {}

        cmd = f'grep -R "{k8s_apiserver_process}" {self.hostfs}/proc/*/comm'

        try:
            result = run(cmd, stdout=PIPE, stderr=PIPE, timeout=5,
                         encoding='UTF-8', shell=True).stdout
        except TimeoutExpired as e:
            logger.warning(f'Could not infer if Kubernetes is also installed on the host: {str(e)}')
            return k8s_cluster_info

        if not result:
            # try k3s
            try:
                return self.get_k3s_commissioning_info()
            except Exception as ex:
                logger.debug(f'No K3s found, assuming K8s {ex}')
                return k8s_cluster_info

        process_args_file = result.split(':')[0].rstrip('comm') + 'cmdline'
        try:
            with open(process_args_file) as pid_file_cmdline:
                k8s_apiserver_args = pid_file_cmdline.read()
        except FileNotFoundError:
            return k8s_cluster_info

        # cope with weird characters
        k8s_apiserver_args = k8s_apiserver_args.replace('\x00', '\n').splitlines()
        args_list = list(map(lambda x: x.lstrip('--'), k8s_apiserver_args[1:]))

        # convert list to dict
        try:
            args = {args_list[i].split('=')[0]: args_list[i].split('=')[-1] for i in range(0, len(args_list))}
        except IndexError:
            # should never get into this exception, but keep it anyway, just to be safe
            logger.warning(f'Unable to infer k8s cluster info from api-server arguments {args_list}')
            return k8s_cluster_info

        arg_address = "advertise-address"
        arg_port = "secure-port"
        arg_ca = "client-ca-file"
        arg_cert = "kubelet-client-certificate"
        arg_key = "kubelet-client-key"

        try:
            k8s_endpoint = f'https://{args[arg_address]}:{args[arg_port]}' \
                if not args[arg_address].startswith("http") else f'{args[arg_address]}:{args[arg_port]}'

            with open(f'{self.hostfs}{args[arg_ca]}') as ca:
                k8s_client_ca = ca.read()

            with open(f'{self.hostfs}{args[arg_cert]}') as cert:
                k8s_client_cert = cert.read()

            with open(f'{self.hostfs}{args[arg_key]}') as key:
                k8s_client_key = key.read()

            k8s_cluster_info.update({
                'kubernetes-endpoint': k8s_endpoint,
                'kubernetes-client-ca': k8s_client_ca,
                'kubernetes-client-cert': k8s_client_cert,
                'kubernetes-client-key': k8s_client_key
            })
        except (KeyError, FileNotFoundError) as e:
            logger.warning(f'Cannot destructure or access certificates from k8s api-server arguments {args}. {str(e)}')
            return {}

        return k8s_cluster_info

    def get_nuvlaedge_project_name(self, default_project_name=None) -> Optional[str]:
        try:
            current_container = self.get_current_container()
            return self.get_compose_project_name_from_labels(current_container.labels)
        except Exception as e:
            logger.warning(f'Failed to get docker compose project name: {e}')
        return default_project_name

    def get_all_nuvlaedge_containers(self):
        filter_labels = [util.base_label]
        project_name = self.get_nuvlaedge_project_name()

        if project_name:
            filter_labels.append(f'com.docker.compose.project={project_name}')

        filters = {'label': filter_labels}

        return self.list_containers(filters=filters, all=True)

    def get_all_nuvlaedge_components(self) -> list:
        return [c.name for c in self.get_all_nuvlaedge_containers()]

    def container_run_command(self, image, name, command: str = None,
                              args: str = None,
                              network: str = None, remove: bool = True,
                              **kwargs) -> str:
        entrypoint = kwargs.get('entrypoint', None)
        if not command:
            command = args
        try:
            output: bytes = self.client.containers.run(
                image,
                command=command,
                entrypoint=entrypoint,
                name=name,
                remove=remove,
                network=network)
            return output.decode('utf-8')
        except (docker.errors.ImageNotFound,
                docker.errors.ContainerError,
                docker.errors.APIError) as ex:
            message = getattr(ex, 'explanation', getattr(ex, 'stderr'))
            logger.error("Failed running container '%s' from '%s': %s",
                         name, image, message)

    def container_remove(self, name: str, **kwargs):
        try:
            cont: Container = self.client.containers.get(name)
            if cont.status == 'running':
                cont.stop()
            cont.remove()
        except docker.errors.NotFound:
            pass
        except Exception as ex:
            logger.warning('Failed removing %s container.', exc_info=ex)

    def compute_api_is_running(self) -> bool:
        """
        Check if the compute-api endpoint is up and running

        :return: True or False
        """

        compute_api_url = f'https://{util.compute_api}:{util.COMPUTE_API_INTERNAL_PORT}'
        logger.debug(f'Trying to reach compute API using {compute_api_url} address')

        try:
            if self._get_component_container(util.compute_api_service_name).status != 'running':
                return False
        except (docker.errors.NotFound, docker.errors.APIError, TimeoutError) as ex:
            logger.debug(f"Compute API container not found {ex}")
            return False

        try:
            requests.get(compute_api_url, timeout=3)
        except requests.exceptions.SSLError:
            # this is expected. It means it is up, we just weren't authorized
            logger.debug("Compute API up and running with security")
        except (requests.exceptions.ConnectionError, TimeoutError) as ex:
            # Can happen if the Compute API takes longer than normal on start
            logger.info(f'Compute API not ready yet: {ex}')
            return False

        return True

    @staticmethod
    def get_current_image_from_env():
        registry = os.getenv('NE_IMAGE_REGISTRY', '')
        organization = os.getenv('NE_IMAGE_ORGANIZATION', 'sixsq')
        repository = os.getenv('NE_IMAGE_REPOSITORY', 'nuvlaedge')
        tag = os.getenv('NE_IMAGE_TAG', 'latest')
        name = os.getenv('NE_IMAGE_NAME', f'{organization}/{repository}')
        return f'{registry}{name}:{tag}'

    @property
    def current_image(self) -> str:
        if not self._current_image:
            try:
                current_id = self.get_current_container_id()
                container = self.client.containers.get(current_id)
                self._current_image = container.attrs['Config']['Image']
            except Exception as e:
                self._current_image = self.get_current_image_from_env()
                logger.error(f"Current container image not found: {str(e)}. "
                             f"Using fallback (built from environment): {self._current_image}")
        return self._current_image
