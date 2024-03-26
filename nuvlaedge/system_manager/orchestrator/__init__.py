from abc import ABC, abstractmethod

from nuvlaedge.common.constants import CTE
from nuvlaedge.system_manager.common import utils


class COEClient(ABC):
    """
    Abstract base class for the Container Orchestration Engine (COE) clients.

    To be subclassed and implemented by clients to the concrete COE
    implementations, such as Docker, Kubernetes, and alike.
    """
    orchestrator = ''
    minimum_version = ''
    dg_encrypt_options = {}

    @abstractmethod
    def __init__(self):
        self.client = None

        self.current_image = CTE.FALLBACK_IMAGE

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