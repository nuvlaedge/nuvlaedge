""" NuvlaEdge ip geolation data

Gathers all the requirements for status reporting
"""
from nuvlaedge.agent.monitor import BaseDataStructure


class VulnerabilitiesSummary(BaseDataStructure):
    """ Vulnerabilities summary data structure """
    total: int | None = None
    affected_products: list | None = None
    average_score: float | None = None


class VulnerabilitiesData(BaseDataStructure):
    """ GlobalData structure for vulnerabilities """
    summary: VulnerabilitiesSummary | None = None
    items: list | None = None
