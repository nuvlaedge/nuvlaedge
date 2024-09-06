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


class COEResourcesData(BaseDataStructure):
    docker: DockerData | None = None
    # kubernetes: KubernetesData | None = None
