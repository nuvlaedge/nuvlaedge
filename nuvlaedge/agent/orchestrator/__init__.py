"""
Orchestration base class. To be extended and implemented by docker or kubernetes
"""

from abc import ABC, abstractmethod

from nuvlaedge.agent.common import util


class ContainerRuntimeClient(ABC):
    """
    Base abstract class for the Docker and Kubernetes clients
    """

    CLIENT_NAME: str
    ORCHESTRATOR: str
    ORCHESTRATOR_COE: str

    hostfs = "/rootfs"
    infra_service_endpoint_keyname: str
    join_token_manager_keyname: str
    join_token_worker_keyname: str

    def __init__(self):
        self.client = None
        self.job_engine_lite_component = util.compose_project_name + "-job-engine-lite"
        self.job_engine_lite_image = None
        self.vpn_client_component = util.compose_project_name + '-vpn-client'
        self.ignore_env_variables = ['NUVLAEDGE_API_KEY', 'NUVLAEDGE_API_SECRET']
        self.data_gateway_name = None

    @abstractmethod
    def get_node_info(self):
        """
        Get high level info about the hosting node
        """

    @abstractmethod
    def get_host_os(self):
        """
        Get operating system of the hosting node
        """

    @abstractmethod
    def get_join_tokens(self) -> tuple:
        """
        Get token for joining this node
        """

    @abstractmethod
    def list_nodes(self, optional_filter={}):
        """
        List all the nodes in the cluster
        """

    @abstractmethod
    def get_cluster_info(self, default_cluster_name=None):
        """
        Get information about the cluster
        """

    @abstractmethod
    def get_api_ip_port(self):
        """
        Get the full API endpoint
        """

    @abstractmethod
    def has_pull_job_capability(self):
        """
        Checks if NuvlaEdge supports pull mode for jobs
        """

    @abstractmethod
    def get_node_labels(self):
        """
        Collects the labels from the hosting node
        """

    @staticmethod
    def cast_dict_to_list(key_value_dict):
        """
        Parses a set of key value pairs in a dict, into a list of strings
        :param key_value_dict: something like {'key': value, 'novalue': None, ...}
        :return: [{key: value}, {key: ""}, ...]
        """

        return [{'name': label, 'value': value} for label, value in key_value_dict.items()]

    @abstractmethod
    def is_vpn_client_running(self):
        """
        Checks if the vpn-client component is up and running
        """

    @abstractmethod
    def install_ssh_key(self, ssh_pub_key, host_home):
        """
        Takes an SSH public key and adds it to the host's HOME authorized keys
        (aka ssh_folder)
        """

    @abstractmethod
    def is_nuvla_job_running(self, job_id, job_execution_id):
        """
        Finds if a job is still running
        :param job_id: nuvla ID of the job
        :param job_execution_id: container ID of the job
        """

    @abstractmethod
    def launch_job(self, job_id, job_execution_id, nuvla_endpoint,
                   nuvla_endpoint_insecure=False, api_key=None,
                   api_secret=None, docker_image=None):
        """
        Launches a new job
        :param job_id: nuvla ID of the job
        :param job_execution_id: name of the container/pod
        :param nuvla_endpoint: Nuvla endpoint
        :param nuvla_endpoint_insecure: whether to use TLS or not
        :param api_key: API key credential for the job to access Nuvla
        :param api_secret: secret for the api_key
        :param docker_image: docker image name
        """

    @abstractmethod
    def collect_container_metrics(self):
        """
        Scans all visible containers and reports their resource consumption
        :return:
        """

    @abstractmethod
    def get_installation_parameters(self):
        """
        Scans all the NuvlaEdge components and returns all parameters that are relevant to
         the installation of the NB
        """

    @abstractmethod
    def read_system_issues(self, node_info):
        """
        Checks if the underlying container management system is reporting any errors or
         warnings
        :param node_info: the result of self.get_node_info()
        """

    @abstractmethod
    def get_node_id(self, node_info):
        """
        Retrieves the node ID
        :param node_info: the result of self.get_node_info()
        """

    @abstractmethod
    def get_cluster_id(self, node_info, default_cluster_name=None):
        """
        Gets the cluster ID
        :param node_info: the result of self.get_node_info()
        :param default_cluster_name: default cluster name in case an ID is not found
        """

    @abstractmethod
    def get_cluster_managers(self):
        """
        Retrieves the cluster manager nodes
        """

    @abstractmethod
    def get_host_architecture(self, node_info):
        """
        Retrieves the host system arch
        :param node_info: the result of self.get_node_info()
        """

    @abstractmethod
    def get_hostname(self, node_info=None):
        """
        Retrieves the hostname
        :param node_info: the result of self.get_node_info()
        """

    @abstractmethod
    def get_cluster_join_address(self, node_id):
        """
        Retrieved the IP address of a manager that can be joined for clustering actions
        :param node_id: ID of the node
        """

    @abstractmethod
    def is_node_active(self, node):
        """
        Checks if a cluster node is ready/active
        :param node: Node object, from self.list_nodes()
        """

    @abstractmethod
    def get_container_plugins(self):
        """
        Lists the container plugins installed in the system
        """

    @abstractmethod
    def define_nuvla_infra_service(self, api_endpoint: str,
                                   client_ca=None, client_cert=None, client_key=None) -> dict:
        """
        Defines the infra service structure for commissioning

        :param api_endpoint: endpoint of the Docker/K8s API
        :param client_ca: API endpoint CA
        :param client_cert: API endpoint client certificate
        :param client_key: API endpoint client private key

        :returns dict of the infra service for commissioning
        """

    @abstractmethod
    def get_partial_decommission_attributes(self) -> list:
        """
        Says which attributes to partially decommission in case the node is a worker

        :returns list of attributes
        """

    @abstractmethod
    def infer_if_additional_coe_exists(self, fallback_address: str = None) -> dict:
        """
        Tries to discover if there is another COE running in the host,
        that can be used for deploying apps from Nuvla

        @param fallback_address: fallback IP/FQDN of the NuvlaEdge's infrastructure service
         in case we cannot find one for the additional COE

        @returns COE attributes as a dict, as expected by the Nuvla commissioning:
                 [coe]-endpoint, [coe]-client-ca, [coe]-client-cert and [coe]-client-key
        """

    @abstractmethod
    def get_all_nuvlaedge_components(self) -> list:
        """
        Finds the names of all NuvlaEdge components installed on the edge device

        :return: list of components' names
        """

    @abstractmethod
    def get_client_version(self) -> str:
        """
        Retrieves the version of the operational orchestrator

        :returns version of the orchestrator in string
        """

    @abstractmethod
    def get_current_container_id(self) -> str:
        """
        Get the container id of the current container

        :return: current container id
        """

    @abstractmethod
    def get_nuvlaedge_project_name(self, default_project_name=None) -> str:
        """
        Get the NuvlaEdge project name

        :return: NuvlaEdge project name
        """

    @abstractmethod
    def container_run_command(self, image, name, command: str = None,
                              args: str = None,
                              network: str = None, remove: bool = True,
                              **kwargs) -> str:
        """
        Runs `command` with `args` in a container started from `image` and
        returns output.

        :return: output of running default entrypoint or `command` with
                 optional `args`.
        """

    @abstractmethod
    def container_remove(self, name: str, **kwargs):
        """
        Removes "container" by `name`. Notion of the "container" is COE
        dependent. It is container for Docker and pod (with all the containers
        in it) for K8s.

        :param name:
        """
