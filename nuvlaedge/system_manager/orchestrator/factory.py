"""
Factory for System Manager Orchestrator
"""

import os

from nuvlaedge.system_manager.orchestrator import COEClient


def get_coe_client() -> COEClient:
    """
    Returns either a KubernetesClient or a DockerClient based on the environment.

    Returns:
        KubernetesClient | DockerClient: The client object based on the environment.

    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        from nuvlaedge.system_manager.orchestrator.kubernetes import Kubernetes
        return Kubernetes()
    else:
        from nuvlaedge.system_manager.orchestrator.docker import Docker
        return Docker()
