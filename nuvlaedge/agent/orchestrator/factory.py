"""
Concrete COE client factory.
"""

import os

from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient


def get_coe_client() -> KubernetesClient | DockerClient:
    """
    Returns either a KubernetesClient or a DockerClient based on the environment.

    Returns:
        KubernetesClient | DockerClient: The client object based on the environment.

    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        return KubernetesClient()
    else:
        return DockerClient()
