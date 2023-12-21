"""
    VulnerabilitiesMonitor.py
"""
import os
import json

from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.agent.workers.monitor.data.vulnerabilities_data import (VulnerabilitiesData,
                                                     VulnerabilitiesSummary)
from nuvlaedge.common.file_operations import read_file


@monitor('vulnerabilities_monitor')
class VulnerabilitiesMonitor(Monitor):
    """ Vulnerabilities monitor class """
    def __init__(self, name: str, telemetry, enable_monitor: bool):
        super().__init__(name, VulnerabilitiesData, enable_monitor)

        if not telemetry.edge_status.vulnerabilities:
            telemetry.edge_status.vulnerabilities = self.data

    @staticmethod
    def retrieve_security_vulnerabilities() -> dict | None:
        """ Reads vulnerabilities from the security scans, from a file in the shared volume

            :return: contents of the file
        """
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

    def populate_nb_report(self, nuvla_report: dict):
        if self.data.summary and self.data.items:
            nuvla_report['vulnerabilities'] = self.data.dict(by_alias=True)
