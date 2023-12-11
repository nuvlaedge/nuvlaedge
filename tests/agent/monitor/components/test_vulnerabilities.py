# -*- coding: utf-8 -*-
from typing import Dict
from pathlib import Path

from mock import Mock, patch, mock_open
import unittest

from nuvlaedge.agent.workers.monitor.components.vulnerabilities import VulnerabilitiesMonitor
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus


class TestVulnerabilitiesMonitor(unittest.TestCase):
    openssh_ctr: str = 'OpenSSH 7.6p1 Ubuntu 4ubuntu0.5'

    @patch.object(Path, 'exists')
    def test_retrieve_security_vulnerabilities(self, mock_exists):
        fake_telemetry: Mock = Mock()
        mock_exists.return_value = False
        test_monitor: VulnerabilitiesMonitor = VulnerabilitiesMonitor(
            'vul_mon', fake_telemetry, Mock()
        )
        self.assertIsNone(test_monitor.retrieve_security_vulnerabilities())

        fake_data: str = ":"
        with patch.object(Path, 'open', mock_open(read_data=fake_data)):
            self.assertIsNone(test_monitor.retrieve_security_vulnerabilities())

        fake_data: str = '{"name": "file"}'
        mock_exists.return_value = True
        with patch.object(Path, 'open', mock_open(read_data=fake_data)):
            self.assertEqual(test_monitor.retrieve_security_vulnerabilities(),
                             {'name': 'file'})

    @patch.object(VulnerabilitiesMonitor, 'retrieve_security_vulnerabilities')
    def test_update_data(self, mock_retrieve):
        fake_telemetry: Mock = Mock()
        fake_telemetry.edge_status = EdgeStatus()

        # Test empty vulnerabilities
        mock_retrieve.return_value = None
        test_monitor: VulnerabilitiesMonitor = VulnerabilitiesMonitor(
            'vul_mon', fake_telemetry, Mock())
        test_monitor.update_data()
        self.assertIsNone(test_monitor.data.summary)

        # Test simply vulnerability

        mock_retrieve.return_value = [
            {
                "product": self.openssh_ctr,
                "vulnerability-id": "CVE-2021-28041",
                "vulnerability-score": 7.1
            }
        ]
        test_monitor.update_data()
        self.assertIsNotNone(test_monitor.data.summary)
        expected_out = {
            'items': [{
                "product": self.openssh_ctr,
                "vulnerability-id": "CVE-2021-28041",
                "vulnerability-score": 7.1
            }],
            'summary': {
                'total': 1,
                'affected-products': [self.openssh_ctr],
                'average-score': 7.1
            }
        }
        self.assertEqual(test_monitor.data.dict(by_alias=True), expected_out)

    @patch.object(VulnerabilitiesMonitor, 'retrieve_security_vulnerabilities')
    def test_populate_nb_report(self, mock_retrieve):
        body: Dict = {}
        fake_telemetry: Mock = Mock()
        fake_telemetry.edge_status = EdgeStatus()

        # Test empty vulnerabilities
        mock_retrieve.return_value = None
        test_monitor: VulnerabilitiesMonitor = VulnerabilitiesMonitor(
            'vul_mon', fake_telemetry, Mock())
        test_monitor.update_data()
        test_monitor.populate_nb_report(body)
        self.assertEqual(body, {})

        # Test simply vulnerability
        mock_retrieve.return_value = [
            {
                "product": self.openssh_ctr,
                "vulnerability-id": "CVE-2021-28041",
                "vulnerability-score": 7.1
            }
        ]
        test_monitor.update_data()
        test_monitor.populate_nb_report(body)
        expected_out = {
            'items': [{
                "product": self.openssh_ctr,
                "vulnerability-id": "CVE-2021-28041",
                "vulnerability-score": 7.1
            }],
            'summary': {
                'total': 1,
                'affected-products': [self.openssh_ctr],
                'average-score': 7.1
            }
        }
        self.assertEqual(body['vulnerabilities'], expected_out,
                         'Status vulnerabilities do not match the real ones')