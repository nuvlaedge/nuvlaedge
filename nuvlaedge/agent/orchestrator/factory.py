"""
Orchestration factory
"""

import os

from nuvlaedge.agent.orchestrator import ContainerRuntimeClient
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient


def get_container_runtime() -> ContainerRuntimeClient:
    """
    Instantiate the right container runtime client based on the underlying COE
    :return: instance of a ContainerRuntimeClient
    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        return KubernetesClient()
    else:
        return DockerClient()
