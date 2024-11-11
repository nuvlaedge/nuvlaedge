import logging
import os
import time
from typing import Dict, List, Union

from nuvlaedge.common.utils import format_datetime_for_nuvla
from nuvlaedge.agent.common import util
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger

if os.getenv('KUBERNETES_SERVICE_HOST'):
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException

log: logging.Logger = get_nuvlaedge_logger(__name__)


JOB_TTL_SECONDS_AFTER_FINISHED = 60 * 2
JOB_BACKOFF_LIMIT = 0
DEFAULT_IMAGE_PULL_POLICY = "Always"

NANOCORES = 1000000000
KIB_TO_BYTES = 1024

class TimeoutException(Exception):
    ...


class KubernetesClient(COEClient):
    """
    Kubernetes client
    """

    CLIENT_NAME = 'Kubernetes'
    ORCHESTRATOR = 'kubernetes'
    ORCHESTRATOR_COE = ORCHESTRATOR

    infra_service_endpoint_keyname = 'kubernetes-endpoint'
    join_token_manager_keyname = 'kubernetes-token-manager'
    join_token_worker_keyname = 'kubernetes-token-worker'

    WAIT_SLEEP_SEC = 2

    # FIXME: This needs to be parameterised.
    NE_DB_ROOT_HOSTPATH = '/var/lib/nuvlaedge'
    NE_DB_CONTAINER_PATH = str(FILE_NAMES.root_fs)

    DEFAULT_IMAGE_PULL_POLICY = "Always"

    def __init__(self):
        super().__init__()
        config.load_incluster_config()
        self.client = client.CoreV1Api()
        self.client_apps = client.AppsV1Api()
        self.client_batch_api = client.BatchV1Api()
        self.namespace = \
            self.get_nuvlaedge_project_name(util.default_project_name)
        self.job_engine_lite_image = \
            os.getenv('NUVLAEDGE_JOB_ENGINE_LITE_IMAGE') or self.current_image
        self.host_node_ip = os.getenv('MY_HOST_NODE_IP')
        self.host_node_name = os.getenv('MY_HOST_NODE_NAME')
        self.vpn_client_component = \
            os.getenv('NUVLAEDGE_VPN_COMPONENT_NAME', 'vpn-client')
        self.job_image_pull_policy = os.getenv('JOB_IMAGE_PULL_POLICY', DEFAULT_IMAGE_PULL_POLICY)
        self.data_gateway_name = f"data-gateway.{self.namespace}"

    def list_raw_resources(self, resource_type) -> list[dict] | None:
        return None

    @staticmethod
    def get_image_pull_policy(image_pull_policy):
        """
        Check if the image pull policy is valid
        If not, return a sane value of IfNotPresent
        """

        valid_pull_policies = ["Always", "IfNotPresent", "Never"]

        if image_pull_policy in valid_pull_policies:
            return image_pull_policy

        log.warning(f'The image pull policy was set to an invalid string: {image_pull_policy}'
                    f'Using "{DEFAULT_IMAGE_PULL_POLICY}" instead.')
        return DEFAULT_IMAGE_PULL_POLICY

    def get_node_info(self, node_name=None) -> Union[client.V1Node, None]:
        node_name = node_name or self.host_node_name
        if node_name:
            try:
                return self.client.read_node(node_name)
            except AttributeError:
                log.warning(f'Cannot infer node information for node "{node_name}"')

        return None

    def get_host_os(self):
        node = self.get_node_info(self.host_node_name)
        if node:
            return f"{node.status.node_info.os_image} {node.status.node_info.kernel_version}"

        return None

    def get_join_tokens(self) -> tuple:
        # NOTE: I don't think we can get the cluster join token from the API
        # it needs to come from the cluster mgmt tool (i.e. k0s, k3s, kubeadm, etc.)
        return ()

    def list_nodes(self, optional_filter: dict = None):
        return self.client.list_node().items

    def list_deployments(self):

        deployment_list = []

        temp_result = self.client_apps.list_namespaced_deployment(self.namespace)

        for deployment in temp_result.items:
            logging.debug(f"pod name -->>  {deployment.metadata.name}")
            deployment_list += [deployment.metadata.name]

        return deployment_list

    def get_cluster_info(self, default_cluster_name=None):
        node_info = self.get_node_info()

        cluster_id = self.get_cluster_id(node_info, default_cluster_name)

        nodes = self.list_nodes()
        managers = []
        workers = []
        for n in nodes:
            workers.append(n.metadata.name)
            for label in n.metadata.labels:
                if 'node-role' in label and 'master' in label:
                    workers.pop()
                    managers.append(n.metadata.name)
                    break

        return {
            'cluster-id': cluster_id,
            'cluster-orchestrator': self.ORCHESTRATOR_COE,
            'cluster-managers': managers,
            'cluster-workers': workers
        }

    def get_api_ip_port(self):
        if self.host_node_ip:
            return self.host_node_ip, 6443

        all_endpoints = self.client.list_endpoints_for_all_namespaces().items

        try:
            endpoint = list(filter(lambda x: x.metadata.name.lower() == 'kubernetes', all_endpoints))[0]
        except IndexError:
            log.error('There are no "kubernetes" endpoints where to get the API IP and port from')
            return None, None

        ip_port = None
        for subset in endpoint.subsets:
            for addr in subset.addresses:
                if addr.ip:
                    self.host_node_ip = addr.ip
                    break

            for port in subset.ports:
                if f'{port.name}/{port.protocol}' == 'https/TCP':
                    ip_port = port.port
                    break

            if self.host_node_ip and ip_port:
                return self.host_node_ip, ip_port

        return None, None

    def has_pull_job_capability(self):
        if self.job_engine_lite_image:
            return True
        return False

    def get_node_labels(self):
        node = self.get_node_info()
        node_labels = node.metadata.labels

        return self.cast_dict_to_list(node_labels)

    def is_vpn_client_running(self):
        vpn_pod = self.client.list_pod_for_all_namespaces(label_selector=f"component={self.vpn_client_component}").items

        if len(vpn_pod) < 1:
            return False

        for res in vpn_pod:
            for container in res.status.container_statuses:
                if container.name == self.vpn_client_component and container.ready:
                    return True

        return False

    def install_ssh_key(self, ssh_pub_key, host_home):
        name = 'nuvlaedge-ssh-installer'
        ssh_folder = '/tmp/ssh'
        try:
            existing_pod = self.client.read_namespaced_pod(namespace=self.namespace, name=name)
        except ApiException as e:
            if e.status != 404: # If 404, this is good, we can proceed
                raise
        else:
            if existing_pod.status.phase.lower() not in ['succeeded', 'running']:
                log.warning(f'Found old {name} with state {existing_pod.status.phase}. Trying to relaunch it...')
                self.client.delete_namespaced_pod(namespace=self.namespace, name=name)
            else:
                log.info(f'SSH key installer "{name}" has already been launched in the past. Skipping this step')
                return False

        entrypoint = ["sh"]
        cmd = ["-c", "echo -e \"${SSH_PUB}\" >> %s" % f'{ssh_folder}/authorized_keys']
        volume_name = f'{name}-volume'
        pod_body = client.V1Pod(
            kind='Pod',
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1PodSpec(
                node_name=self.host_node_name,
                volumes=[
                    client.V1Volume(
                        name=volume_name,
                        host_path=client.V1HostPathVolumeSource(
                            path=f'{host_home}/.ssh'
                        )
                    )
                ],
                restart_policy='Never',
                containers=[
                    client.V1Container(
                        name=name,
                        image=self.current_image,
                        env=[
                            client.V1EnvVar(
                                name='SSH_PUB',
                                value=ssh_pub_key
                            )
                        ],
                        volume_mounts=[
                            client.V1VolumeMount(
                                name=volume_name,
                                mount_path=ssh_folder
                            )
                        ],
                        command=entrypoint,
                        args=cmd
                    )
                ]
            )
        )

        self.client.create_namespaced_pod(namespace=self.namespace, body=pod_body)

        return True

    def is_nuvla_job_running(self, job_id, job_execution_id):
        try:
            job = self.client.read_namespaced_pod(namespace=self.namespace, name=job_execution_id)
        except ApiException as e:
            if e.status == 404:
                return False
            log.error(f'Cannot handle job {job_id}. Reason: {str(e)}')
            # assume it is running so we don't mess anything
            return True

        try:
            if job.status.phase.lower() == 'running':
                log.info(f'Job {job_id} is already running in pod {job.metadata.name}, with UID {job.metadata.uid}')
                return True
            if job.status.phase.lower() == 'pending':
                log.warning(f'Job {job_id} was created and still pending')
                # TODO: maybe we should run a cleanup for pending jobs after X hours
            else:
                if job.status.phase.lower() == 'succeeded':
                    log.info(f'Job {job_id} has already finished successfully. Deleting the pod...')
                # then it is probably UNKNOWN or in an undesired state
                self.client.delete_namespaced_pod(namespace=self.namespace, name=job_execution_id)
        except AttributeError:
            # assume it is running so we don't mess anything
            return True
        except ApiException as e:
            # this exception can only happen if we tried to delete the pod and couldn't
            # log it and don't let another job come in
            log.error(f'Failed to handle job {job_id} due to pod management error: {str(e)}')
            return True

        return False

    def launch_job(self, job_id, job_execution_id, nuvla_endpoint,
                   nuvla_endpoint_insecure=False, api_key=None, api_secret=None,
                   docker_image=None, cookies=None, **kwargs):

        authentication = ""
        if api_key and api_secret:
            authentication = (f'--api-key {api_key} '
                              f'--api-secret {api_secret} ')

        cmd = '/app/job_executor.py'
        args = f'--api-url https://{nuvla_endpoint} ' \
               f'{authentication} ' \
               f'--nuvlaedge-fs {FILE_NAMES.root_fs} ' \
               f'--job-id {job_id}'

        if nuvla_endpoint_insecure:
            args += ' --api-insecure'

        image = docker_image if docker_image else self.job_engine_lite_image

        environment = {k: v for k, v in os.environ.items()
                       if k.startswith('NE_IMAGE_') or k.startswith('JOB_')}

        if cookies:
            environment["JOB_COOKIES"] = cookies

        log.info(f'Launch Nuvla job {job_id} using {image} with: {cmd} {args}')

        job = self._job_executor_job_def(image, job_execution_id, cmd, args, environment)

        namespace = self._namespace(**kwargs)
        log.debug('Run job %s in namespace %s', job.to_str(), namespace)
        try:
            self.client_batch_api.create_namespaced_job(namespace, job)
        except Exception as ex:
            log.error('Failed starting job %s in namespace %s', job.to_str(),
                      namespace, exc_info=ex)
            raise ex

    def collect_container_metrics(self, _: bool = False) -> List[Dict]:
        """
        Collect container metrics.
        :param _:
        :return: List of container metrics
        """
        # TODO: Generalize this method to be able to collect and compute
        #  metrics for all containers running on all nodes, not just the one
        #  where the agent is running.
        node_name = self.host_node_name

        node_info = self.get_node_info(node_name)
        if node_info:
            node_capacity = node_info.status.capacity
            node_cpu_capacity = int(node_capacity['cpu'])
            node_mem_capacity_b = (int(node_capacity['memory'].rstrip('Ki'))
                                   * KIB_TO_BYTES)
        else:
            raise Exception('Failed getting node info.')

        try:
            pods = self.client.list_pod_for_all_namespaces(
                field_selector=f'spec.nodeName={node_name}'
            )
        except ApiException as ex:
            log.error('Failed listing pods for all namespaces: %s',
                      ex, exc_info=ex)
            return []
        pods_per_ns = {f'{p.metadata.namespace}/{p.metadata.name}': p
                       for p in pods.items}

        try:
            pod_metrics_list = \
                client.CustomObjectsApi().list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "pods")
        except ApiException as ex:
            log.error('Failed listing pod metrics: %s', ex)
            return []
        out = []
        for pod in pod_metrics_list.get('items', []):
            short_identifier = f"{pod['metadata']['namespace']}/{pod['metadata']['name']}"
            if short_identifier not in pods_per_ns:
                continue

            for cstats in pod.get('containers', []):
                try:
                    metrics = self._container_metrics(
                        pods_per_ns[short_identifier],
                        cstats,
                        node_cpu_capacity,
                        node_mem_capacity_b)
                    out.append(metrics)
                except Exception as ex:
                    log.error('Failed collecting metrics for container %s in pod %s: %s',
                              cstats['name'], pod['metadata']['name'], ex)

        return out

    def _container_metrics(self, pod: client.V1Pod, cstats: dict,
                           node_cpu_capacity: int, node_mem_capacity_b: int):
        """
        Compiles and returns container metrics.

        :param pod: The Kubernetes Pod object containing the container.
        :type pod: client.V1Pod
        :param cstats: The container statistics.
        :type cstats: dict
        :param node_cpu_capacity: The CPU capacity of the node in cores.
        :type node_cpu_capacity: int
        :param node_mem_capacity_b: The memory capacity of the node in bytes.
        :type node_mem_capacity_b: int
        :return: A dictionary containing the container metrics.
        :rtype: dict
        """

        pod_name = pod.metadata.name
        container_name = cstats['name']

        # Metadata
        metrics = {
            'name': f"{pod_name}/{container_name}"
        }
        for cstat in pod.status.container_statuses:
            if cstat.name == container_name:
                metrics['id'] = cstat.container_id
                metrics['image'] = cstat.image
                metrics['restart-count'] = int(cstat.restart_count or 0)
                for k, v in cstat.state.to_dict().items():
                    if v:
                        metrics['state'] = k
                        metrics['status'] = k
                        if k == 'running':
                            metrics['created-at'] = format_datetime_for_nuvla(
                                pod.metadata.creation_timestamp)
                            metrics['started-at'] = format_datetime_for_nuvla(
                                cstat.state.running.started_at)
                        elif k == 'terminated':
                            pass
                            # TODO: expose these metrics
                            # metrics['finished-at'] = format_datetime_for_nuvla(
                            #     cstat.state.terminated.finished_at)
                            # metrics['exit-code'] = cstat.state.terminated.exit_code
                            # metrics['reason'] = cstat.state.terminated.reason
                        elif k == 'waiting':
                            pass
                            # TODO: expose these metrics
                            # metrics['reason'] = cstat.state.waiting.reason
                        break

        # CPU
        metrics['cpu-capacity'] = node_cpu_capacity
        container_cpu_usage = int(cstats['usage']['cpu'].rstrip('n'))
        metrics['cpu-usage'] = \
            (container_cpu_usage / (node_cpu_capacity * NANOCORES)) * 100

        # MEM
        metrics['mem-limit'] = node_mem_capacity_b
        metrics['mem-usage'] = (
                int(cstats['usage']['memory'].rstrip('Ki')) * KIB_TO_BYTES)

        # FIXME: implement net and disk metrics collection.
        self._container_metrics_net(metrics)
        self._container_metrics_block(metrics)

        return metrics

    def get_installation_parameters(self) -> dict:
        nuvlaedge_deployments = \
            self.client_apps.list_namespaced_deployment(
                namespace=self.namespace, label_selector=util.base_label).items

        environment = self._extract_environment_variables(nuvlaedge_deployments)
        unique_env = list(filter(None, set(environment)))

        return {'project-name': self.namespace,
                'environment': unique_env}

    def _extract_environment_variables(self, deployments) -> list:
        environment = []
        for dep in deployments:
            for container in dep.spec.template.spec.containers:
                if container.env:
                    environment.extend(self._process_container_env(container.env))
        return environment

    @staticmethod
    def _process_container_env(env) -> list:
        return [f'{env_var.name}={env_var.value}' for env_var in env 
                if not hasattr(env_var, 'value_from')]

    def read_system_issues(self, node_info):
        errors = []
        warnings = []
        # TODO: is there a way to get any system errors from the k8s API?
        # The cluster-info dump reports a lot of stuff but is all verbose

        return errors, warnings

    def get_node_id(self, node_info):
        return node_info.metadata.name

    def get_cluster_id(self, node_or_cluster_info_not_used,
                       default_cluster_name=None):
        # FIXME: https://github.com/kubernetes/kubernetes/issues/44954 It's not
        #        possible to get K8s cluster name or id.
        log.warning('Unable to get K8s cluster id. See https://github.com/kubernetes/kubernetes/issues/44954')
        return default_cluster_name

    def get_cluster_managers(self):
        managers = []
        for n in self.list_nodes():
            for label in n.metadata.labels:
                if 'node-role' in label and 'master' in label:
                    managers.append(n.metadata.name)

        return managers

    def get_host_architecture(self, node_info):
        return node_info.status.node_info.architecture

    def get_hostname(self, node_info=None):
        return self.host_node_name

    def get_client_version(self):
        # IMPORTANT: this is only implemented for this k8s client class
        return self.get_node_info().status.node_info.kubelet_version

    def get_kubelet_version(self):
        # IMPORTANT: this is only implemented for this k8s client class
        return self.get_node_info().status.node_info.kubelet_version

    def get_cluster_join_address(self, node_id):
        # NOT IMPLEMENTED for k8s installations
        pass

    def is_node_active(self, node):
        if any(list(map(lambda n: n.type == 'Ready' and n.status == 'True', node.status.conditions))):
            return node.metadata.name

        return None

    def get_container_plugins(self):
        # TODO
        # doesn't seem to be available from the API
        return None

    def define_nuvla_infra_service(self, api_endpoint: str, client_ca=None,
                                   client_cert=None, client_key=None) -> dict:
        if api_endpoint:
            infra_service = {
                "kubernetes-endpoint": api_endpoint
            }

            if client_ca and client_cert and client_key:
                infra_service["kubernetes-client-ca"] = client_ca
                infra_service["kubernetes-client-cert"] = client_cert
                infra_service["kubernetes-client-key"] = client_key

            return infra_service
        return {}

    def get_partial_decommission_attributes(self) -> list:
        # TODO: implement.
        return []

    def infer_if_additional_coe_exists(self, fallback_address: str=None) -> dict:
        # For k8s installations, we might want to see if there's also Docker running alongside
        # TODO: implement if deemed needed. I don't think discovery of other
        #       COE is needed (KS).
        return {}

    def get_all_nuvlaedge_components(self) -> list:

        return self.list_deployments()

    def _namespace(self, **kwargs):
        return kwargs.get('namespace', self.namespace)

    def _wait_pod_in_phase(self, namespace: str, name: str, phase: str, wait_sec=60):
        ts_stop = time.time() + wait_sec
        while True:
            pod: client.V1Pod = self.client.read_namespaced_pod(name, namespace)
            if phase == pod.status.phase:
                return
            log.info(f'Waiting pod {phase}: {namespace}:{name} till {ts_stop}')
            if ts_stop <= time.time():
                raise TimeoutException(f'Pod is not {phase} after {wait_sec} sec')
            time.sleep(self.WAIT_SLEEP_SEC)

    def _wait_pod_deleted(self, namespace: str, name: str, wait_sec=60):
        ts_stop = time.time() + wait_sec
        while True:
            try:
                self.client.read_namespaced_pod(name, namespace)
            except ApiException as ex:
                if ex.reason == 'Not Found':
                    return
            log.info(f'Deleting pod: {namespace}:{name} till {ts_stop}')
            if ts_stop <= time.time():
                raise TimeoutException(f'Pod is still not deleted after {wait_sec} sec')
            time.sleep(self.WAIT_SLEEP_SEC)

    @staticmethod
    def _to_k8s_obj_name(name: str) -> str:
        return name.replace('_', '-').replace('/', '-')

    def _container_def(self, image, name,
                       volume_mounts: List[client.V1VolumeMount] | None,
                       command: str = None,
                       image_pull_policy: str = DEFAULT_IMAGE_PULL_POLICY,
                       args: str = None,
                       env: dict = None) -> client.V1Container:

        args = args.split() if args else None
        command = command.split() if command else None

        parsed_env = None
        if env:
            parsed_env = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]

        return client.V1Container(image=image,
                                  name=name,
                                  env=parsed_env,
                                  command=command,
                                  volume_mounts=volume_mounts,
                                  image_pull_policy=self.get_image_pull_policy(image_pull_policy),
                                  args=args)

    @staticmethod
    def _pod_spec(container: client.V1Container,
                  network: str = None,
                  volumes: List[client.V1Volume] = None,
                  **kwargs) -> client.V1PodSpec:
        return client.V1PodSpec(containers=[container],
                                host_network=(network == 'host'),
                                restart_policy=kwargs.get('restart_policy'),
                                volumes=volumes)

    @staticmethod
    def _pod_template_spec(name: str,
                           pod_spec: client.V1PodSpec) -> client.V1PodTemplateSpec:
        return client.V1PodTemplateSpec(spec=pod_spec,
                                        metadata=client.V1ObjectMeta(name=name))

    def _ne_db_hostpath(self):
        return os.path.join(self.NE_DB_ROOT_HOSTPATH,
                            self.get_nuvlaedge_project_name(util.default_project_name),
                            'data')

    def _volume_mount_ne_db(self) -> (client.V1Volume, client.V1VolumeMount):
        volume_name = 'ne-db'
        host_path = self._ne_db_hostpath()
        log.info("Binding host path %s to volume %s", host_path, volume_name)
        pod_volume = client.V1Volume(
            name=volume_name,
            host_path=client.V1HostPathVolumeSource(path=host_path))

        container_volume_mount = client.V1VolumeMount(name=volume_name,
                                                      mount_path=self.NE_DB_CONTAINER_PATH,
                                                      read_only=True)

        return pod_volume, container_volume_mount

    def _pod_def(self, image, name,
                 command: str = None,
                 args: str = None,
                 network: str = None,
                 mount_ne_db: bool = False,
                 image_pull_policy: str = DEFAULT_IMAGE_PULL_POLICY,
                 env: dict = None,
                 **kwargs) -> client.V1Pod:

        pod_spec = self._pod_spec_with_container(image, name,
                                                 command, args,
                                                 network, mount_ne_db,
                                                 image_pull_policy=image_pull_policy,
                                                 env=env,
                                                 **kwargs)
        return client.V1Pod(
            metadata=client.V1ObjectMeta(name=name, annotations={}),
            spec=pod_spec)

    def _pod_spec_with_container(self, image: str, name: str,
                                 command: str = None,
                                 args: str = None,
                                 network: str = None,
                                 mount_ne_db: bool = False,
                                 image_pull_policy: str = DEFAULT_IMAGE_PULL_POLICY,
                                 env: dict = None,
                                 **kwargs):

        container_volume_mounts, pod_volumes = None, None
        if mount_ne_db:
            ne_db_volume, ne_db_volume_mount = self._volume_mount_ne_db()
            container_volume_mounts = [ne_db_volume_mount]
            pod_volumes = [ne_db_volume]

        container = self._container_def(image, name,
                                        volume_mounts=container_volume_mounts,
                                        command=command,
                                        image_pull_policy=image_pull_policy,
                                        args=args,
                                        env=env)

        return self._pod_spec(container,
                              network=network,
                              volumes=pod_volumes,
                              **kwargs)

    def _job_def(self, image, name,
                 command: str = None,
                 args: str = None,
                 network: str = None,
                 mount_ne_db: bool = False,
                 image_pull_policy: str = DEFAULT_IMAGE_PULL_POLICY,
                 env: dict = None,
                 **kwargs) -> client.V1Job:

        pod_spec = self._pod_spec_with_container(image, name,
                                                 command, args,
                                                 network, mount_ne_db,
                                                 image_pull_policy=image_pull_policy,
                                                 env=env,
                                                 **kwargs)

        job_spec = client.V1JobSpec(template=self._pod_template_spec(name, pod_spec))

        job_spec.backoff_limit = kwargs.get('backoff_limit', JOB_BACKOFF_LIMIT)

        job_spec.ttl_seconds_after_finished = kwargs.get(
            'ttl_seconds_after_finished', JOB_TTL_SECONDS_AFTER_FINISHED)

        return client.V1Job(api_version="batch/v1",
                            kind="Job",
                            metadata=client.V1ObjectMeta(name=name),
                            spec=job_spec)

    def _job_executor_job_def(self, image, name, cmd, args, env=None) -> client.V1Job:
        return self._job_def(image, self._to_k8s_obj_name(name),
                             command=cmd, args=args,
                             mount_ne_db=True,
                             restart_policy='Never',
                             image_pull_policy=self.job_image_pull_policy,
                             env=env)

    def container_run_command(self, image, name,
                              command: str = None,
                              args: str = None,
                              network: str = None,
                              remove: bool = True,
                              no_output=False,
                              **kwargs) -> str:
        name = self._to_k8s_obj_name(name)

        # To comply with docker, try to retrieve entrypoint when there is
        # no command (k8s entrypoint) defined
        command = command or kwargs.get('entrypoint')
        image_pull_policy = kwargs.get('image_pull_policy', DEFAULT_IMAGE_PULL_POLICY)

        pod = self._pod_def(image, name,
                            command=command,
                            args=args,
                            network=network,
                            image_pull_policy=image_pull_policy,
                            **kwargs)

        namespace = self._namespace(**kwargs)

        log.info('Run pod %s in namespace %s', pod.to_str(), namespace)
        try:
            self.client.create_namespaced_pod(namespace, pod)
            if no_output:
                return ''
        except ApiException as ex:
            log.error('Failed to create %s:%s: %s', namespace, name, ex, exc_info=ex)
            return ''
        try:
            self._wait_pod_in_phase(namespace, name, 'Running')
        except TimeoutException as ex:
            log.warning(ex)
            return ''
        output = self.client.read_namespaced_pod_log(
            name,
            namespace,
            _preload_content=False,
            timestamps=False).data.decode('utf8')
        if remove:
            self.container_remove(name, **kwargs)
        return output

    def container_remove(self, name: str, **kwargs):
        """
        Interprets `name` as the name of the pod and removes it (which
        effectively removes all the containers in the pod).

        :param name:
        :param kwargs:
        :return:
        """
        name = self._to_k8s_obj_name(name)
        namespace = self._namespace(**kwargs)
        try:
            log.info(f'Deleting pod {namespace}:{name}')
            self.client.delete_namespaced_pod(name, namespace)
            self._wait_pod_deleted(namespace, name)
        except ApiException as ex:
            log.warning('Failed removing pod %s in %s: %s', name, namespace, ex.reason)
        except TimeoutException as ex_timeout:
            log.warning('Timeout waiting for pod to be deleted: %s', ex_timeout)

    def _container_metrics_net(self, metrics: dict):
        # FIXME: implement. Not clear how to get Rx/Tx metrics.
        metrics['net-in'] = 0
        metrics['net-out'] = 0
        return metrics

    def _container_metrics_block(self, metrics: dict):
        # FIXME: implement. Not clear how to get the block IO.
        metrics['blk-in'] = 0
        metrics['blk-out'] = 0
        return metrics

    def get_current_container_id(self) -> str:
        # TODO
        return ''

    def get_nuvlaedge_project_name(self, default_project_name=None) -> str:
        return os.getenv('MY_NAMESPACE', default_project_name)

    @property
    def current_image(self) -> str:
        return os.getenv('NUVLAEDGE_IMAGE')
