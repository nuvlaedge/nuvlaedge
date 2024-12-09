"""
    VulnerabilitiesMonitor.py
"""
import logging
import os
import json

from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.agent.workers.monitor.data.vulnerabilities_data import (VulnerabilitiesData,
                                                     VulnerabilitiesSummary)
from nuvlaedge.common.file_operations import read_file, file_exists_and_not_empty
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger

logger: logging.Logger = get_nuvlaedge_logger(__name__)


@monitor('vulnerabilities_monitor')
class VulnerabilitiesMonitor(Monitor):
    """ Vulnerabilities monitor class """
    def __init__(self, name: str, telemetry, enable_monitor: bool, period: int = 60):
        super().__init__(name, VulnerabilitiesData, enable_monitor, period)

    @staticmethod
    def retrieve_security_vulnerabilities() -> dict | None:
        """ Reads vulnerabilities from the security scans, from a file in the shared volume

            :return: contents of the file
        """
        if not file_exists_and_not_empty(FILE_NAMES.VULNERABILITIES_FILE):
            # Added redundant check for file existence to prevent warning message. Log message in debug level
            logger.debug(f"File {FILE_NAMES.VULNERABILITIES_FILE} does not exist or is empty")
            return None

        return read_file(FILE_NAMES.VULNERABILITIES_FILE, True)

    def update_data(self):
        vulnerabilities = self.retrieve_security_vulnerabilities()

        if vulnerabilities:
            it_summary: VulnerabilitiesSummary = VulnerabilitiesSummary()

            scores = \
                [v.get('vulnerability-score', -1) for v in vulnerabilities if v.get('vulnerability-score', -1) != -1]

            it_summary.total = len(vulnerabilities)

            it_summary.affected_products = list(set(map(
                lambda v: v.get('product', 'unknown'), vulnerabilities)))

            if len(scores) > 0:
                it_summary.average_score = round(sum(scores) / len(scores), 2)

            self.data.summary = it_summary
            self.data.items = sorted(
                vulnerabilities,
                key=lambda v: v.get('vulnerability-score', 0), reverse=True)[0:100]

    def populate_telemetry_payload(self):
        if self.data.summary and self.data.items:
            self.telemetry_data.vulnerabilities = self.data.dict(by_alias=True)
