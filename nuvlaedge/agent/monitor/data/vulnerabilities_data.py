""" NuvlaEdge ip geolation data

Gathers all the requirements for status reporting
"""
from nuvlaedge.agent.monitor import BaseDataStructure


class VulnerabilitiesSummary(BaseDataStructure):
    """ Vulnerabilities summary data structure """
    total: int | None
    affected_products: list | None
    average_score: float | None


class VulnerabilitiesData(BaseDataStructure):
    """ GlobalData structure for vulnerabilities """
    summary: VulnerabilitiesSummary | None
    items: list | None
