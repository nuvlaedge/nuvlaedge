# -*- coding: utf-8 -*-

""" NuvlaEdge Edge Networking data structure

Gathers all the requirements for status reporting
"""

from nuvlaedge.agent.workers.monitor import BaseDataStructure


class DockerData(BaseDataStructure):
    images: list[dict] | None = []
    volumes: list[dict] | None = []
    networks: list[dict] | None = []
    containers: list[dict] | None = []
    services: list[dict] | None = []
    tasks: list[dict] | None = []
    configs: list[dict] | None = []
    secrets: list[dict] | None = []


class KubernetesData(BaseDataStructure):
    # Namespaced resources

    # configs
    configmaps: list[dict] | None = []
    secrets: list[dict] | None = []

    # storage
    persistentvolumeclaims: list[dict] | None = []

    # network
    services: list[dict] | None = []
    ingresses: list[dict] | None = []

    # workload
    cronjobs: list[dict] | None = []
    jobs: list[dict] | None = []
    statefulsets: list[dict] | None = []
    daemonsets: list[dict] | None = []
    deployments: list[dict] | None = []
    pods: list[dict] | None = []

    # Non-namespaced resources

    images: list[dict] | None = []
    namespaces: list[dict] | None = []
    persistentvolumes: list[dict] | None = []

    # Cluster
    nodes: list[dict] | None = []


def kubernetes_data_attributes():
    return KubernetesData.model_fields.keys()


class COEResourcesData(BaseDataStructure):
    docker: DockerData | None = None
    kubernetes: KubernetesData | None = None
