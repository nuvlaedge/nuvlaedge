"""
Concrete COE client factory.
"""

import os

from nuvlaedge.agent.orchestrator import COEClient


def get_coe_client() -> COEClient:
    """
    Returns either a KubernetesClient or a DockerClient based on the environment.

    Returns:
        KubernetesClient | DockerClient: The client object based on the environment.

    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient
        return KubernetesClient()
    else:
        from nuvlaedge.agent.orchestrator.docker import DockerClient
        return DockerClient()
