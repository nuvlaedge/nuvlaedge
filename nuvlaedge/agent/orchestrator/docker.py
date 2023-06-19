import base64
import logging
import os
import socket
from subprocess import run, PIPE, TimeoutExpired
from typing import List, Optional

import docker
import docker.errors
from docker.models.containers import Container

import requests
import yaml

from nuvlaedge.agent.common import util
from nuvlaedge.agent.orchestrator import ContainerRuntimeClient


logger: logging.Logger = logging.getLogger(__name__)


class InferIPError(Exception):
    ...


class DockerClient(ContainerRuntimeClient):
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
        # To initialize job_engine_image
        self.has_pull_job_capability()

    def get_client_version(self) -> str:
        return self.client.version()['Version']

    def get_node_info(self):
        return self.client.info()

    def get_host_os(self):
        node_info = self.get_node_info()
        return f"{node_info['OperatingSystem']} {node_info['KernelVersion']}"

    def get_join_tokens(self) -> tuple:
        try:
            if self.client.swarm.attrs:
                return self.client.swarm.attrs['JoinTokens']['Manager'], \
                       self.client.swarm.attrs['JoinTokens']['Worker']
        except docker.errors.APIError as e:
            if self.lost_quorum_hint in str(e):
                # quorum is lost
                logger.warning('Quorum is lost. This node will no longer support '
                               'Service and Cluster management')

        return ()

    def list_nodes(self, optional_filter={}):
        return self.client.nodes.list(filters=optional_filter)

    def get_cluster_info(self, default_cluster_name=None):
        node_info = self.get_node_info()
        swarm_info = node_info['Swarm']

        if swarm_info.get('ControlAvailable'):
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
        try:
            container = self._get_component_container(util.compute_api_service_name)

        except (docker.errors.NotFound, docker.errors.APIError, TimeoutError) as ex:
            logger.debug(f"Compute API container not found {ex}")
            return ''

        try:
            return container.ports['5000/tcp'][0]['HostPort']

        except (KeyError, IndexError) as ex:
            logger.warning('Cannot infer ComputeAPI external port, container attributes '
                                'not properly formatted', exc_info=ex)
        return ""

    def get_api_ip_port(self):
        node_info = self.get_node_info()
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
                        ip = f'{int(hex_ip[len(hex_ip)-2:],16)}.' \
                             f'{int(hex_ip[len(hex_ip)-4:len(hex_ip)-2],16)}.' \
                             f'{int(hex_ip[len(hex_ip)-6:len(hex_ip)-4],16)}.' \
                             f'{int(hex_ip[len(hex_ip)-8:len(hex_ip)-6],16)}'
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
        try:
            container = self._get_component_container(util.job_engine_service_name)
        except docker.errors.NotFound as e:
            logger.warning(f"Container {self.job_engine_lite_component} not found. Reason: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unable to search for container {self.job_engine_lite_component}. Reason: {str(e)}")
            return False

        try:
            if container.status.lower() == "paused":
                self.job_engine_lite_image = container.attrs['Config']['Image']
                return True
        except (AttributeError, KeyError):
            logger.exception('Failed to get job-engine-lite image')
            return False

        logger.info('job-engine-lite not paused')
        return False

    def get_node_labels(self):
        try:
            node_id = self.get_node_info()["Swarm"]["NodeID"]
            node_labels = self.client.api.inspect_node(node_id)["Spec"]["Labels"]
        except (KeyError, docker.errors.APIError, docker.errors.NullResource) as e:
            if "node is not a swarm manager" not in str(e).lower():
                logger.debug(f"Cannot get node labels: {str(e)}")
            return []

        return self.cast_dict_to_list(node_labels)

    def is_vpn_client_running(self):
        it_vpn_container = self._get_component_container(util.vpn_client_service_name)
        vpn_client_running = it_vpn_container.status == 'running'
        return vpn_client_running

    def install_ssh_key(self, ssh_pub_key, host_home):
        ssh_folder = '/tmp/ssh'
        cmd = "sh -c 'echo -e \"${SSH_PUB}\" >> %s'" % f'{ssh_folder}/authorized_keys'

        self.client.containers.run(self.get_current_image(),
                                   remove=True,
                                   command=cmd,
                                   environment={
                                       'SSH_PUB': ssh_pub_key
                                   },
                                   volumes={
                                       f'{host_home}/.ssh': {
                                           'bind': ssh_folder
                                       }})

        return True

    def is_nuvla_job_running(self, job_id, job_execution_id):
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
                logger.info(f'Job {job_id} is already running in container '
                             f'{job_container.name}')
                return True
            elif job_container.status.lower() in ['created']:
                logger.warning(f'Job {job_id} was created by not started. Removing it '
                                f'and starting a new one')
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
            logger.warning(f'More than one component container found for '
                           f'service name "{service_name}" and project name "{project_name}": {containers}')
        return containers[0]

    def _get_component_container(self, service_name, container_name=None):
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
        
    def launch_job(self, job_id, job_execution_id, nuvla_endpoint,
                   nuvla_endpoint_insecure=False, api_key=None, api_secret=None,
                   docker_image=None):
        # Get the compute-api network
        local_net = None
        try:
            compute_api = self._get_component_container(util.compute_api_service_name)
            local_net = list(compute_api.attrs['NetworkSettings']['Networks'].keys())[0]
        except (docker.errors.NotFound, docker.errors.APIError, IndexError, KeyError, TimeoutError) as e:
            logger.error(f'Cannot infer compute-api network for local job {job_id}: {e}')

        # Get environment variables and volumes from job-engine-lite container
        volumes = {
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock',
                'mode': 'rw'
            }
        }
        volumes_from = []
        environment = []

        try:
            job_engine_lite = self._get_component_container(util.job_engine_service_name)
            environment = job_engine_lite.attrs['Config']['Env']
            volumes = []
            volumes_from = [job_engine_lite.name]
        except (docker.errors.NotFound, docker.errors.APIError, IndexError, KeyError, TimeoutError) as e:
            logger.warning(f'Cannot get env and volumes from job-engine-lite ({job_id}): {e}')

        cmd = f'-- /app/job_executor.py --api-url https://{nuvla_endpoint} ' \
              f'--api-key {api_key} ' \
              f'--api-secret {api_secret} ' \
              f'--job-id {job_id}'

        if nuvla_endpoint_insecure:
            cmd = f'{cmd} --api-insecure'

        logger.info(f'Starting job {job_id} on {self.job_engine_lite_image} image, with command: "{cmd}"')

        img = docker_image if docker_image else self.job_engine_lite_image
        self.client.containers.run(img,
                                   command=cmd,
                                   detach=True,
                                   name=job_execution_id,
                                   hostname=job_execution_id,
                                   remove=True,
                                   network=local_net,
                                   volumes=volumes,
                                   volumes_from=volumes_from,
                                   environment=environment)

        try:
            # for some jobs (like clustering), it is better if the job container is also
            # in the default bridge network, so it doesn't get affected by network changes
            # in the NuvlaEdge
            self.client.api.connect_container_to_network(job_execution_id, 'bridge')
        except docker.errors.APIError as e:
            logger.warning(f'Could not attach {job_execution_id} to bridge network: {str(e)}')

    @staticmethod
    def collect_container_metrics_cpu(container_stats: dict) -> float:
        """
        Calculates the CPU consumption for a give container

        :param container_stats: Docker container statistics
        :return: CPU consumption in percentage
        """
        cs = container_stats
        cpu_percent = float('nan')

        try:
            cpu_delta = \
                float(cs["cpu_stats"]["cpu_usage"]["total_usage"]) - \
                float(cs["precpu_stats"]["cpu_usage"]["total_usage"])
            system_delta = \
                float(cs["cpu_stats"]["system_cpu_usage"]) - \
                float(cs["precpu_stats"]["system_cpu_usage"])

            online_cpus_alt = len(cs["cpu_stats"]["cpu_usage"].get("percpu_usage", []))
            online_cpus = cs["cpu_stats"].get('online_cpus', online_cpus_alt)

            if system_delta > 0.0 and online_cpus > 0:
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            logger.warning('Failed to get CPU usage for container '
                            f'{cs.get("id","?")[:12]} ({cs.get("name")}): {e}')

        return cpu_percent

    @staticmethod
    def collect_container_metrics_mem(cstats: dict) -> tuple:
        """
        Calculates the Memory consumption for a give container

        :param cstats: Docker container statistics
        :return: Memory consumption tuple with percentage, usage and limit
        """
        try:
            # Get total mem usage and subtract cached memory
            if cstats["memory_stats"]["stats"].get('rss'):
                mem_usage = (float(cstats["memory_stats"]["stats"]["rss"]))/1024/1024
            else:
                mem_usage = (float(cstats["memory_stats"]["usage"]) -
                             float(cstats["memory_stats"]["stats"]["file"]))/1024/1024
            mem_limit = float(cstats["memory_stats"]["limit"]) / 1024 / 1024
            if round(mem_limit, 2) == 0.00:
                mem_percent = 0.00
            else:
                mem_percent = round(float(mem_usage / mem_limit) * 100, 2)
        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            mem_percent = mem_usage = mem_limit = 0.00
            logger.warning('Failed to get Memory consumption for container '
                            f'{cstats.get("id","?")[:12]} ({cstats.get("name")}): {e}')

        return mem_percent, mem_usage, mem_limit

    @staticmethod
    def collect_container_metrics_net(cstats: dict) -> tuple:
        """
        Calculates the Network consumption for a give container

        :param cstats: Docker container statistics
        :return: tuple with network bytes IN and OUT
        """
        net_in = net_out = 0.0
        try:
            if "networks" in cstats:
                net_in = sum(cstats["networks"][iface]["rx_bytes"]
                             for iface in cstats["networks"]) / 1000 / 1000
                net_out = sum(cstats["networks"][iface]["tx_bytes"]
                              for iface in cstats["networks"]) / 1000 / 1000
        except (IndexError, KeyError, ValueError) as e:
            logger.warning('Failed to get Network consumption for container '
                            f'{cstats.get("id","?")[:12]} ({cstats.get("name")}): {e}')

        return net_in, net_out

    @staticmethod
    def collect_container_metrics_block(cstats: dict) -> tuple:
        """
        Calculates the block consumption for a give container

        :param cstats: Docker container statistics
        :return: tuple with block bytes IN and OUT
        """
        blk_out = blk_in = 0.0

        io_bytes_recursive = cstats.get("blkio_stats", {}).get("io_service_bytes_recursive", [])
        if io_bytes_recursive:
            try:
                blk_in = float(io_bytes_recursive[0]["value"] / 1000 / 1000)
            except (IndexError, KeyError, TypeError) as e:
                logger.warning('Failed to get block usage (In) for container '
                                f'{cstats.get("id","?")[:12]} ({cstats.get("name")}): {e}')
            try:
                blk_out = float(io_bytes_recursive[1]["value"] / 1000 / 1000)
            except (IndexError, KeyError, TypeError) as e:
                logger.warning('Failed to get block usage (Out) for container '
                                f'{cstats.get("id","?")[:12]} ({cstats.get("name")}): {e}')

        return blk_out, blk_in

    def list_containers(self, *args, **kwargs):
        """
        Bug: Sometime the Docker Python API fails to get the list of containers with the exception:
        'requests.exceptions.HTTPError: 404 Client Error: Not Found'
        This is due to docker listing containers and then inpecting them one by one.
        If in the mean time a container has been removed, it fails with the above exception.
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
        containers_stats = []
        for container in self.list_containers():
            try:
                containers_stats.append((container, container.stats(stream=False)))
            except Exception as e:
                logger.warning('Failed to get stats for container '
                                f'{container.short_id} ({container.name}): {e}')
        return containers_stats

    def collect_container_metrics(self):
        containers_metrics = []

        for container, stats in self.get_containers_stats():
            # CPU
            cpu_percent = \
                self.collect_container_metrics_cpu(stats)
            # RAM
            mem_percent, mem_usage, mem_limit = \
                self.collect_container_metrics_mem(stats)
            # NET
            net_in, net_out = \
                self.collect_container_metrics_net(stats)
            # DISK
            blk_out, blk_in = \
                self.collect_container_metrics_block(stats)

            containers_metrics.append({
                'id': container.id,
                'name': container.name,
                'container-status': container.status,
                'cpu-percent': "%.2f" % round(cpu_percent, 2),
                'mem-usage-limit': ("{}MiB / {}MiB".format(round(mem_usage, 1),
                                                           round(mem_limit, 1))),
                'mem-percent': "%.2f" % mem_percent,
                'net-in-out': "%sMB / %sMB" % (round(net_in, 1), round(net_out, 1)),
                'blk-in-out': "%sMB / %sMB" % (round(blk_in, 1), round(blk_out, 1)),
                'restart-count': (int(container.attrs["RestartCount"])
                                  if "RestartCount" in container.attrs else 0)
            })

        return containers_metrics

    @staticmethod
    def _get_container_id_from_cgroup():
        try:
            with open('/proc/self/cgroup', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cgroup: {e}')

    @staticmethod
    def _get_container_id_from_cpuset():
        try:
            with open('/proc/1/cpuset', 'r') as f:
                return f.read().split('/')[-1].strip()
        except Exception as e:
            logger.debug(f'Failed to get container id from cpuset: {e}')

    @staticmethod
    def _get_container_id_from_hostname():
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

    @staticmethod
    def get_config_files_from_labels(labels) -> List[str]:
        return labels.get('com.docker.compose.project.config_files', '').split(',')

    @staticmethod
    def get_working_dir_from_labels(labels) -> List[str]:
        return labels.get('com.docker.compose.project.working_dir', '')

    def get_installation_parameters(self):
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

        environment = []
        for env_var in myself.attrs.get('Config', {}).get('Env', []):
            if env_var.split('=')[0] in self.ignore_env_variables:
                continue
            environment.append(env_var)

        nuvlaedge_containers = self.get_all_nuvlaedge_containers()
        nuvlaedge_containers = list(filter(lambda x: x.id != myself.id, nuvlaedge_containers))
        for container in nuvlaedge_containers:
            c_labels = container.labels
            if self.get_compose_project_name_from_labels(c_labels, '') == project_name and \
                    self.get_working_dir_from_labels(c_labels) == working_dir:
                if container.attrs.get('Created', '') > last_update:
                    last_update = container.attrs.get('Created', '')
                    config_files = self.get_config_files_from_labels(c_labels)
                environment += container.attrs.get('Config', {}).get('Env', [])

        unique_config_files = list(filter(None, set(config_files)))
        unique_env = list(filter(None, set(environment)))

        if working_dir and project_name and unique_config_files:
            return {'project-name': project_name,
                    'working-dir': working_dir,
                    'config-files': unique_config_files,
                    'environment': unique_env}
        else:
            return None

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
        remote_managers = self.get_node_info().get('Swarm', {}).get('RemoteManagers')
        cluster_managers = []
        if remote_managers and isinstance(remote_managers, list):
            cluster_managers = [rm.get('NodeID') for rm in remote_managers]

        return cluster_managers

    def get_host_architecture(self, node_info):
        return node_info["Architecture"]

    def get_hostname(self, node_info=None):
        return node_info["Name"]

    def get_cluster_join_address(self, node_id):
        for manager in self.get_node_info().get('Swarm', {}).get('RemoteManagers'):
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

    def define_nuvla_infra_service(self, api_endpoint: str,
                                   client_ca=None, client_cert=None, client_key=None) -> dict:
        if not self.compute_api_is_running():
            return {}
        try:
            fallback_address = api_endpoint.replace('https://', '').split(':')[0]
            infra_service = self.infer_if_additional_coe_exists(fallback_address=fallback_address)
        except (IndexError, ConnectionError):
            # this is a non-critical step, so we should never fail because of it
            infra_service = {}

        if api_endpoint:
            infra_service["swarm-endpoint"] = api_endpoint

            if client_ca and client_cert and client_key:
                infra_service["swarm-client-ca"] = client_ca
                infra_service["swarm-client-cert"] = client_cert
                infra_service["swarm-client-key"] = client_key

        return infra_service

    def get_partial_decommission_attributes(self) -> list:
        return ['swarm-token-manager',
                'swarm-token-worker',
                'swarm-client-key',
                'swarm-client-ca',
                'swarm-client-cert',
                'swarm-endpoint']

    def is_k3s_running(self, k3s_address: str) -> dict:
        """
        Checks specifically if k3s is installed

        :param k3s_address: endpoint address for the kubernetes API
        :return: commissioning-ready kubernetes infra
        """
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
            logger.warning(f'Could not infer if Kubernetes is also installed '
                                f'on the host: {str(e)}')
            return k8s_cluster_info

        if not result:
            # try k3s
            try:
                return self.is_k3s_running(fallback_address)
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
            logger.error("Failed running container '%s' from '%s': %s",
                              name, image, ex.explanation)

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

    def get_current_image(self) -> str:
        if self._current_image:
            return self._current_image

        try:
            current_id = self.get_current_container_id()
            container = self.client.containers.get(current_id)
        except docker.errors.NotFound as e:
            logger.warning(f"Current container not found. Reason: {str(e)}")
            return ""

        self._current_image = container.attrs['Config']['Image']
        return self._current_image
