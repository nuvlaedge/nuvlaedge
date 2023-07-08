#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest
import socket
from pathlib import Path

import paho.mqtt.client as mqtt

import tests.agent.utils.fake as fake
from nuvlaedge.agent.common import nuvlaedge_common
from nuvlaedge.agent.orchestrator.factory import get_coe_client
from nuvlaedge.agent.telemetry import Telemetry


class TelemetryTestCase(unittest.TestCase):

    agent_telemetry_open = 'nuvlaedge.agent.telemetry.open'
    atomic_write = 'nuvlaedge.agent.common.util.atomic_write'

    @mock.patch('nuvlaedge.agent.telemetry.Telemetry.initialize_monitors')
    def setUp(self, mock_monitor_initializer):
        fake_nuvlaedge_common = fake.Fake.imitate(nuvlaedge_common.NuvlaEdgeCommon)
        setattr(fake_nuvlaedge_common, 'coe_client', mock.MagicMock())
        setattr(fake_nuvlaedge_common, 'container_stats_json_file', 'fake-stats-file')
        setattr(fake_nuvlaedge_common, 'vpn_ip_file', 'fake-vpn-file')
        Telemetry.__bases__ = (fake_nuvlaedge_common,)

        self.shared_volume = "mock/path"
        self.nuvlaedge_status_id = "nuvlabox-status/fake-id"

        self.obj = Telemetry(get_coe_client(),
                             self.shared_volume,
                             self.nuvlaedge_status_id)

        # monkeypatching
        self.obj.mqtt_broker_host = 'fake-data-gateway'
        self.obj.mqtt_broker_port = 1
        self.obj.mqtt_broker_keep_alive = True
        self.obj.swarm_node_cert = 'swarm-cert'
        self.obj.nuvla_timestamp_format = "%Y-%m-%dT%H:%M:%SZ"
        self.obj.installation_home = '/home/fake-user'
        self.obj.nuvlaedge_id = 'nuvlabox/fake-id'
        self.obj.nuvlaedge_engine_version = '2.1.0'
        self.obj.hostfs = '/rootfs'
        self.obj.vulnerabilities_file = 'vuln'
        self.obj.ip_geolocation_file = 'geolocation'
        self.obj.previous_net_stats_file = 'prev-net'
        self.obj.nuvlaedge_status_file = '.status'
        self.obj.vpn_ip_file = '.ip'
        self.obj.nvidia_software_power_consumption_model = {
            "ina3221x": {
                "channels": 3,
                "boards": {
                    "agx_xavier": {
                        "i2c_addresses": ["1-0040", "1-0041"],
                        "channels_path": ["1-0040/iio:device0", "1-0041/iio:device1"]
                    },
                    "nano": {
                        "i2c_addresses": ["6-0040"],
                        "channels_path": ["6-0040/iio:device0"]
                    },
                    "tx1": {
                        "i2c_addresses": ["1-0040"],
                        "channels_path": ["1-0040/iio:device0"]
                    },
                    "tx1_dev_kit": {
                        "i2c_addresses": ["1-0042", "1-0043"],
                        "channels_path": ["1-0042/iio:device2", "1-0043/iio:device3"]
                    },
                    "tx2": {
                        "i2c_addresses": ["0-0040", "0-0041"],
                        "channels_path": ["0-0040/iio:device0", "0-0041/iio:device1"]
                    },
                    "tx2_dev_kit": {
                        "i2c_addresses": ["0-0042", "0-0043"],
                        "channels_path": ["0-0042/iio:device2", "0-0043/iio:device3"]
                    }
                }
            }
        }
        ###
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # make sure attrs are set and NuvlaEdgeCommon is inherited
        self.assertIsNotNone(self.obj.status_default,
                             'Telemetry status not initialized')
        self.assertIsNotNone(self.obj.coe_client,
                             'NuvlaEdgeCommon not inherited')
        self.assertEqual(self.obj.status_default, self.obj.status,
                         'Failed to initialized status structures')
        self.assertIsInstance(self.obj.mqtt_telemetry, mqtt.Client)

    @mock.patch('nuvlaedge.agent.telemetry.active_monitors')
    @mock.patch('nuvlaedge.agent.telemetry.get_monitor')
    def test_initialize_monitors(self, get_mock, act_mock):
        get_mock.return_value = mock.Mock()
        self.obj.initialize_monitors()

    @mock.patch('os.system')
    def test_send_mqtt(self, mock_system):
        self.obj.mqtt_telemetry = mock.MagicMock()
        self.obj.mqtt_telemetry.disconnect.return_value = None

        # if socket.timeout, just return none
        self.obj.mqtt_telemetry.connect.side_effect = socket.timeout
        self.assertIsNone(self.obj.send_mqtt(''),
                          'Failed to react to socket timeout while sending data to MQTT broker')
        self.obj.mqtt_telemetry.disconnect.assert_not_called()
        mock_system.assert_not_called()

        # if ConnectionRefusedError or socket.gaierror, disconnect and return None
        self.obj.mqtt_telemetry.connect.side_effect = ConnectionRefusedError
        self.assertIsNone(self.obj.send_mqtt(''),
                          'Failed to react to ConnectionRefusedError while sending data to MQTT broker')
        self.obj.mqtt_telemetry.disconnect.assert_called_once()
        mock_system.assert_not_called()

        self.obj.mqtt_telemetry.connect.side_effect = socket.gaierror
        self.assertIsNone(self.obj.send_mqtt(''),
                          'Failed to react to socket.gaierror while sending data to MQTT broker')
        self.assertEqual(self.obj.mqtt_telemetry.disconnect.call_count, 2,
                         'MQTT disconnect should have been called twice by now')
        mock_system.assert_not_called()

        # otherwise, send ONLY NB status to broker
        mock_system.return_value = None
        self.obj.mqtt_telemetry.connect.reset_mock(side_effect=True)
        self.obj.mqtt_telemetry.connect.return_value = None
        self.assertIsNone(self.obj.send_mqtt(''),
                          'Failed to send NuvlaEdge status to MQTT broker')
        mock_system.assert_called_once()

        # and if all metrics are passed, send them ALL
        mock_system.reset_mock() # reset counter
        self.assertIsNone(self.obj.send_mqtt('', cpu='cpu', ram='ram', disks=['disk1'], energy='e1'),
                          'Failed to send multiple metrics to MQTT broker')
        self.assertEqual(mock_system.call_count, 5,
                         'Should have sent data to MQTT broker 5 times (1 per given metric)')

    @mock.patch.object(Telemetry, 'set_status_operational_status')
    @mock.patch.object(Telemetry, 'send_mqtt')
    def test_get_status(self, mock_send_mqtt, mock_set_status_operational_status):
        self.obj.coe_client.get_node_info.return_value = fake.MockDockerNode()
        self.obj.coe_client.get_host_os.return_value = 'os'
        self.obj.coe_client.get_host_architecture.return_value = 'arch'
        self.obj.coe_client.get_hostname.return_value = 'hostname'
        self.obj.coe_client.get_container_plugins.return_value = ['plugin']

        # these functions are already tested elsewhere
        mock_set_status_operational_status.return_value = \
            mock_send_mqtt.return_value = None

        self.obj.status_default['resources'] = {
            'cpu': {
                'raw-sample': None},
            'ram': {
                'raw-sample': None},
            'disks': []
        }
        status_for_nuvla, all_status = self.obj.get_status()

        # all "Gets" were called
        mock_send_mqtt.assert_called_once_with(status_for_nuvla, None, None, [])

        # all_status contains additional fields
        additional_fields = ["cpu-usage", "cpu-load", "disk-usage", "memory-usage", "cpus", "memory", "disk"]
        self.assertTrue(all(k in all_status for k in additional_fields),
                        'Failed to set additional status attributes for all_status, during get_status')

    def test_diff(self):
        # new values added, get new value and nothing to delete
        new = {'a': 1, 'b': 2}
        old = {'a': 1}
        expected = ({'b': 2}, set())
        self.assertEqual(self.obj.diff(old, new), expected,
                         'Failed to diff for new values')

        # no changes, nothing to return
        new = {'a': 1}
        old = {'a': 1}
        expected = ({}, set())
        self.assertEqual(self.obj.diff(old, new), expected,
                         'Failed to diff when there are no changes')

        # values modified, return them
        new = {'a': 2}
        old = {'a': 1}
        expected = ({'a': 2}, set())
        self.assertEqual(self.obj.diff(old, new), expected,
                         'Failed to diff for modified values')

        # values have disappeared, return deleted key list
        new = {}
        old = {'a': 1}
        expected = ({}, set('a'))
        self.assertEqual(self.obj.diff(old, new), expected,
                         'Failed to diff for obsolete values (deleted)')

        # all mixed
        new = {'a': 1, 'b': 2, 'c': False, 'd': [1, 2, 3]}
        old = {'a': 1, 'old': 'bye', 'c': True, 'd': [1, 2]}
        expected = ({'b': 2, 'c': False, 'd': [1, 2, 3]}, {'old'})
        self.assertEqual(self.obj.diff(old, new), expected,
                         'Failed to diff')

    @mock.patch.object(Telemetry, 'diff')
    @mock.patch.object(Telemetry, 'get_status')
    def test_update_status(self, mock_get_status, mock_diff):
        previous_status = self.obj.status.copy()
        new_status = {**previous_status, **{'new-value': 'fake-value'}}
        all_status = {**new_status, **{'extra': 'value'}}
        mock_get_status.return_value = (new_status, all_status)
        mock_diff.return_value = ({'new-value': 'fake-value'}, set())

        # make sure the right status is updated and saved
        with mock.patch(self.agent_telemetry_open) as mock_open, \
             mock.patch(self.atomic_write): # TODO: Patch not needed but file cleanup is required
            mock_open.return_value.write.return_value = None
            self.assertIsNone(self.obj.update_status(),
                              'Failed to update status')

        self.assertEqual(self.obj.status, new_status,
                         'NuvlaEdge status was not updated in memory')

        minimum_payload_keys = {'current-time', 'id', 'new-value'}
        self.assertEqual(minimum_payload_keys & set(new_status.keys()), minimum_payload_keys,
                         'Failed to set minimum payload for updating nuvlabox-status in Nuvla')

        _, delete_attrs = self.obj.diff(new_status, self.obj.status)
        self.assertEqual(delete_attrs, set(),
                         'Saying there are attrs to delete when there are none')

    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'stat')
    def test_get_vpn_ip(self, mock_stat, mock_exists):
        # if vpn file does not exist or is empty, get None
        mock_exists.return_value = False
        self.assertIsNone(self.obj.get_vpn_ip(),
                          'Returned VPN IP when VPN file does not exist')
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 0
        self.assertIsNone(self.obj.get_vpn_ip(),
                          'Returned VPN IP when VPN file is empty')

        # otherwise, read the file and return the IP
        mock_stat.return_value.st_size = 1
        # with mock.patch(self.agent_telemetry_open, mock.mock_open(read_data='1.1.1.1')):

        with mock.patch.object(Path, 'open', mock.mock_open(read_data='1.1.1.1')):
            self.assertEqual(self.obj.get_vpn_ip(), '1.1.1.1',
                             'Failed to get VPN IP')
