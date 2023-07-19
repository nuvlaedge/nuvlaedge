"""
Concrete COE client factory.
"""

import os

from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient


def get_coe_client() -> COEClient:
    """
    Returns the concrete COE client based on the underlying target COE.
    :return: instance of a COEClient
    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        return KubernetesClient()
    else:
        return DockerClient()
