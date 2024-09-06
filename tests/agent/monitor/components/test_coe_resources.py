# -*- coding: utf-8 -*-

import unittest
from mock import Mock

from nuvlaedge.agent.workers.monitor.components.coe_resources import COEResourcesMonitor
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus


def list_raw_resources(resource_type):
    return [{'id': '1', 'name': f'{resource_type}-1'},
            {'id': '2', 'name': f'{resource_type}-2'}]


class TestCOEResourcesMonitor(unittest.TestCase):

    def test_coe_resource_monitor(self):
        telemetry = Mock()
        telemetry.edge_status = EdgeStatus()
        test_monitor = COEResourcesMonitor('test_monitor', telemetry, True)
        test_monitor.coe_client.list_raw_resources = list_raw_resources

        test_monitor.coe_client.ORCHESTRATOR = 'not_docker'
        test_monitor.update_data()
        self.assertIsNone(test_monitor.data.docker)

        test_monitor.coe_client.ORCHESTRATOR = 'docker'
        test_monitor.update_data()
        self.assertIsNotNone(test_monitor.data.docker)

        nb_report: dict = {}
        test_monitor.populate_nb_report(nb_report)
        expected_data = {
            'docker': {
                'images': [{'id': '1', 'name': 'images-1'},
                           {'id': '2', 'name': 'images-2'}],
                'volumes': [{'id': '1', 'name': 'volumes-1'},
                            {'id': '2', 'name': 'volumes-2'}],
                'networks': [{'id': '1', 'name': 'networks-1'},
                             {'id': '2', 'name': 'networks-2'}],
                'containers': [{'id': '1', 'name': 'containers-1'},
                               {'id': '2', 'name': 'containers-2'}]}}
        self.assertEqual(nb_report['coe-resources'], expected_data)

        self.assertIs(telemetry.edge_status.coe_resources, test_monitor.data)
