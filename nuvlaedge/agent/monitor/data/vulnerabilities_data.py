""" NuvlaEdge ip geolation data

Gathers all the requirements for status reporting
"""
from typing import List, Union

from nuvlaedge.agent.monitor import BaseDataStructure


class VulnerabilitiesSummary(BaseDataStructure):
    """ Vulnerabilities summary data structure """
    total: Union[int, None]
    affected_products: Union[List, None]
    average_score: Union[float, None]


class VulnerabilitiesData(BaseDataStructure):
    """ GlobalData structure for vulnerabilities """
    summary: Union[VulnerabilitiesSummary, None]
    items: Union[List, None]
