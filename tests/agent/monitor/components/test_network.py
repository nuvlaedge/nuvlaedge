# -*- coding: utf-8 -*-
import json
import time
import unittest
from random import SystemRandom
from typing import List, Dict, Any
from pathlib import Path

import requests
from docker import errors as docker_err
from mock import Mock, mock_open, patch, MagicMock

from nuvlaedge.agent.monitor.components import network as monitor
from nuvlaedge.agent.monitor.data.network_data import NetworkInterface, NetworkingData, IP
from nuvlaedge.agent.monitor.edge_status import EdgeStatus


def generate_random_ip_address():
    rand_bits = SystemRandom().getrandbits(8)
    it_str: List[str] = [str(rand_bits) for _ in range(4)]
    return ".".join(it_str)


atomic_write: str = 'nuvlaedge.agent.common.util.atomic_write'


class TestNetworkMonitor(unittest.TestCase):
    built_open: str = "builtins.open"
    _path_json: str = 'json.loads'

    def test_constructor(self):
        it_telemetry = Mock()
        it_telemetry.edge_status.iface_data = None
        monitor.NetworkMonitor('geo_test', it_telemetry, True)
        self.assertIsInstance(
            it_telemetry.edge_status.iface_data,
            NetworkingData)

    # -------------------- Public data tests -------------------- #
    def test_set_public_data(self):
        # Test Public IP update rate
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("file", Mock(), Mock())
        test_ip_monitor.last_public_ip = time.time()
        test_ip_monitor.set_public_data()
        self.assertFalse(test_ip_monitor.data.ips.public)

        #
        status = Mock()
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("file", Mock(), status)
        self.assertFalse(test_ip_monitor.data.ips.public)
        test_ip_monitor.set_public_data()
        self.assertIsNotNone(test_ip_monitor.data.ips.public)

        # Test exception clause
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("file", Mock(), Mock())
        test_ip_monitor._REMOTE_IPV4_API = "empty"
        test_ip_monitor.set_public_data()
        self.assertIsNotNone(test_ip_monitor.data.ips.public)

    def test_set_public_data_should_raise_timeout(self):
        # Test timeout
        with patch('requests.get') as get:
            get.side_effect = requests.Timeout
            test_ip_monitor: monitor.NetworkMonitor = \
                monitor.NetworkMonitor("file", Mock(), EdgeStatus())
            test_ip_monitor.set_public_data()
            self.assertFalse(test_ip_monitor.data.ips.public)

    # -------------------- Local data tests -------------------- #
    def test_parse_host_ip_json(self):
        # Base test
        it_ip: str = generate_random_ip_address()
        test_attribute: Dict[str, Any] = {
            "dev": "eth0",
            "prefsrc": it_ip
        }
        status = Mock()
        status.iface_data = None
        it_1 = Mock()
        it_1.coe_client.client.containers.list.return_value = []
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("file", it_1, status)
        expected_result: NetworkInterface = \
            NetworkInterface(iface_name="eth0", ips=[IP(address=it_ip)])
        self.assertEqual(test_ip_monitor.parse_host_ip_json(test_attribute),
                         expected_result)

        # Non-complete attributes tests
        test_attribute.pop("dev")
        self.assertIsNone(test_ip_monitor.parse_host_ip_json(test_attribute))

        test_attribute["dev"] = "eth0"
        test_attribute.pop("prefsrc")
        self.assertIsNone(test_ip_monitor.parse_host_ip_json(test_attribute))

    def test_gather_host_route(self):
        it_1 = Mock()
        m = Mock()
        m.return_value = ''
        it_1.coe_client.container_run_command = m
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", it_1, True)
        self.assertEqual('', test_ip_monitor._gather_host_ip_route())

    def test_set_local_data(self):
        # Test no available route IP's
        runtime_mock = Mock()
        cont_mock = Mock()
        cont_mock.labels = {'com.docker.compose.project': 'nuvlaedge_test'}
        runtime_mock.client.containers.list.return_value = [cont_mock]
        tel_mock = Mock()
        tel_mock.coe_client = runtime_mock
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", tel_mock, Mock())
        with patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.'
                   '_gather_host_ip_route') as test_gather:
            test_gather.return_value = None
            test_ip_monitor.set_local_data()
            self.assertFalse(test_ip_monitor.data.ips.local)

        # Test Skip routes
        with patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.'
                   'is_skip_route') as test_skip, \
                patch(self._path_json) as json_dict:
            json_dict.return_value = [{'Test': None}]
            test_skip.return_value = True
            test_ip_monitor.set_local_data()
            self.assertFalse(test_ip_monitor.data.ips.local)

        status = Mock()
        status.iface_data = None
        it_1 = Mock()
        it_1.coe_client.client.containers.list.return_value = []
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", it_1, status)
        mock_gather = Mock()
        mock_gather = b''
        test_ip_monitor.coe_client.container_run_command.return_value = mock_gather
        test_ip_monitor.set_local_data()
        self.assertFalse(test_ip_monitor.data.ips.local)

        # Test readable route
        it_1 = Mock()
        it_1.coe_client.client.containers.list.return_value = []
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", it_1, True)
        test_ip_monitor.is_skip_route = Mock(return_value=True)
        test_ip_monitor._gather_host_ip_route = Mock(return_value='{}')
        test_ip_monitor.set_local_data()
        self.assertEqual(test_ip_monitor.data.ips.local, '')

        with patch(self._path_json) as json_dict:
            test_ip_monitor: monitor.NetworkMonitor = \
                monitor.NetworkMonitor("", Mock(), True)
            test_ip_monitor.is_skip_route = Mock(return_value=False)
            test_ip_monitor._gather_host_ip_route = Mock(return_value='{}')
            it_address: str = generate_random_ip_address()
            json_dict.return_value = [{'dst': 'default',
                                       'dev': 'eth0',
                                       'prefsrc': it_address}]
            test_ip_monitor.set_local_data()
            self.assertEqual(test_ip_monitor.data.ips.local, it_address)

        # Test traffic readings
        with patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.'
                   'read_traffic_data') as test_traffic, \
                patch(self._path_json) as json_dict:
            json_dict.return_value = None
            test_traffic.return_value = [{'a': 'a'}]
            test_ip_monitor: monitor.NetworkMonitor = \
                monitor.NetworkMonitor("", Mock(), True)
            test_ip_monitor.set_local_data()
            self.assertFalse(test_ip_monitor.data.ips.local)

        # Test multi routes&ips per interface
        with patch(self._path_json) as json_dict:
            test_ip_monitor: monitor.NetworkMonitor = \
                monitor.NetworkMonitor("", Mock(), True)
            test_ip_monitor._gather_host_ip_route = Mock(return_value='{}')
            addr1: str = generate_random_ip_address()
            addr2: str = generate_random_ip_address()
            json_dict.return_value = [{'dst': 'default',
                                       'dev': 'eth0',
                                       'prefsrc': addr1},
                                      {'dst': 'default',
                                       'dev': 'eth0',
                                       'prefsrc': addr2},
                                      {'dst': 'default',
                                       'dev': 'eth0',
                                       'prefsrc': addr1}]
            test_ip_monitor.set_local_data()
            self.assertEqual(test_ip_monitor.data.interfaces['eth0'].ips,
                             [IP(address=addr1), IP(address=addr2)])

    def test_is_skip_route(self):
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", Mock(), True)

        self.assertTrue(test_ip_monitor.is_skip_route({}))

    # -------------------- VPN data tests -------------------- #

    @patch.object(Path, 'exists')
    @patch.object(Path, 'stat')
    def test_set_vpn_data(self, mock_stat, mock_exists):
        vpn_file = Mock()
        status = Mock()
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor(vpn_file, Mock(), status)

        it_ip: str = generate_random_ip_address()
        mock_stat.return_value.st_size = 1
        mock_exists.return_value = True
        with patch.object(Path, 'open', mock_open(read_data=it_ip)):
            test_ip_monitor.set_vpn_data()
            self.assertEqual(test_ip_monitor.data.ips.vpn, it_ip)

        test_ip_monitor.data.ips.vpn = ''
        mock_stat.return_value.st_size = 0
        mock_exists.return_value = True
        with patch.object(Path, 'open', mock_open(read_data="")):
            test_ip_monitor.set_vpn_data()
            self.assertFalse(test_ip_monitor.data.ips.vpn)

    # -------------------- Swarm data tests -------------------- #
    def test_set_swarm_data(self):
        runtime_mock = Mock()
        r_ip: str = generate_random_ip_address()
        status = Mock()
        status.iface_data = None
        runtime_mock.coe_client.get_api_ip_port.return_value = (r_ip, 0)
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", runtime_mock, status)
        test_ip_monitor.set_swarm_data()
        self.assertEqual(test_ip_monitor.data.ips.swarm, r_ip)

        runtime_mock.coe_client.get_api_ip_port.return_value = ('', '')
        test_ip_monitor.set_swarm_data()
        self.assertFalse(test_ip_monitor.data.ips.swarm)

        runtime_mock.coe_client.get_api_ip_port.return_value = None
        with self.assertRaises(TypeError):
            test_ip_monitor.set_swarm_data()

    @patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.set_public_data')
    @patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.set_local_data')
    @patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.set_vpn_data')
    @patch('nuvlaedge.agent.monitor.components.network.NetworkMonitor.set_swarm_data')
    def test_update_data(self, pub, local, vpn, swarm):
        runtime_mock = Mock()
        # r_ip: str = generate_random_ip_address()
        status = Mock()
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", runtime_mock, status)
        test_ip_monitor.update_data()

        # Check public is called
        self.assertEqual(pub.call_count, 1)
        self.assertEqual(local.call_count, 1)
        self.assertEqual(vpn.call_count, 1)
        self.assertEqual(swarm.call_count, 1)

    @patch(atomic_write)
    def test_read_traffic_data(self, atomic_write_mock):

        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", Mock(), True)
        with patch(self._path_json) as mock_json_loads, patch('os.listdir') as mock_ls:
            mock_ls.side_effect = FileNotFoundError
            test_ip_monitor.read_traffic_data()

            # if sys path does not exist, get {}
            self.assertEqual(test_ip_monitor.read_traffic_data(), [],
                             'Got net info even though /sys path cannot be found')

            mock_ls.reset_mock(side_effect=True)

            # if previous net file cannot be found, or is malformed, don't load it
            with patch(self.built_open, mock_open()) as mock_tel_open:
                mock_tel_open.side_effect = [FileNotFoundError, MagicMock()]
                mock_ls.return_value = []  # no interfaces, get []
                self.assertEqual(test_ip_monitor.read_traffic_data(), [],
                                 'Got net info even though no interfaces were found')
                mock_json_loads.assert_not_called()

            with patch(self.built_open, mock_open()) as mock_tel_open:
                # if there are interfaces
                mock_ls.return_value = ['iface1', 'iface2']
                # try to open but if it fails, get []
                mock_tel_open.side_effect = [FileNotFoundError, FileNotFoundError,
                                             NotADirectoryError, MagicMock()]
                self.assertEqual(
                    test_ip_monitor.read_traffic_data(),
                    [],
                    'Got net info even though interfaces files cannot be read')

            # the first time it runs, there are no previous net stats
            self.assertEqual(test_ip_monitor.first_net_stats, {},
                             'First net stats is not empty before first run')

            expected_first_net_stats = {
                'iface1': {
                    "bytes-transmitted": 2,
                    "bytes-received": 1,
                    "bytes-transmitted-carry": 0,
                    "bytes-received-carry": 0
                },
                'iface2': {
                    "bytes-transmitted": 4,
                    "bytes-received": 3,
                    "bytes-transmitted-carry": 0,
                    "bytes-received-carry": 0
                }
            }
            with patch(self.built_open, mock_open()) as mock_tel_open:
                # 4 readers because open tx and rx per interface (2x2)
                mock_tel_open.side_effect = [FileNotFoundError,
                                             mock_open(read_data='1').return_value,
                                             mock_open(read_data='2').return_value,
                                             mock_open(read_data='3').return_value,
                                             mock_open(read_data='4').return_value,
                                             MagicMock()]

                # first time is all 0
                self.assertEqual(
                    test_ip_monitor.read_traffic_data(),
                    [
                        {
                            'interface': 'iface1',
                            'bytes-transmitted': 0,
                            'bytes-received': 0},
                        {
                            'interface': 'iface2',
                            'bytes-transmitted': 0,
                            'bytes-received': 0}
                    ],
                    'Failed to get net stats')

                self.assertEqual(
                    test_ip_monitor.first_net_stats,
                    expected_first_net_stats,
                    'Unable to set first_net_stats after first run')

            # now that first_net_stats exists, if system counter are still going,
            # get the diff and return values
            with patch(self.built_open) as mock_tel_open:
                # 4 readers because open tx and rx per interface (2x2)
                mock_tel_open.side_effect = [FileNotFoundError,
                                             mock_open(read_data='10').return_value,
                                             mock_open(read_data='10').return_value,
                                             mock_open(read_data='20').return_value,
                                             mock_open(read_data='20').return_value,
                                             MagicMock()]

                # current-first+carry=x -> 20-4+0-16
                self.assertEqual(test_ip_monitor.read_traffic_data(), [
                    {'interface': 'iface1', 'bytes-transmitted': 8,
                     'bytes-received': 9},
                    {'interface': 'iface2', 'bytes-transmitted': 16,
                     'bytes-received': 17}
                ],
                                 'Failed to get net stats on a 2nd run')
                # first_net_stats is not changed anymore
                self.assertEqual(test_ip_monitor.first_net_stats,
                                 expected_first_net_stats,
                                 'first_net_stats were changed when they should not have')

            # when system counters are reset, the reads are smaller than the first ones
            with patch(self.built_open) as mock_tel_open:
                # 4 readers because open tx and rx per interface (2x2)
                mock_tel_open.side_effect = [FileNotFoundError,
                                             mock_open(read_data='0').return_value,
                                             mock_open(read_data='1').return_value,
                                             mock_open(read_data='2').return_value,
                                             mock_open(read_data='3').return_value,
                                             MagicMock()]
                # assuming once more previous_stats don't exist, we should get the
                # reading as is
                self.assertEqual(test_ip_monitor.read_traffic_data(), [
                    {'interface': 'iface1', 'bytes-transmitted': 1,
                     'bytes-received': 0},
                    {'interface': 'iface2', 'bytes-transmitted': 3,
                     'bytes-received': 2}
                ],
                                 'Failed to get net stats after counter reset')
                # first_net_stats is NOW changed because of reset
                new_first_stats = {
                    'iface1': {
                        "bytes-transmitted": 1,
                        "bytes-received": 0,
                        "bytes-transmitted-carry": 0,
                        "bytes-received-carry": 0
                    },
                    'iface2': {
                        "bytes-transmitted": 3,
                        "bytes-received": 2,
                        "bytes-transmitted-carry": 0,
                        "bytes-received-carry": 0
                    }
                }
                self.assertEqual(test_ip_monitor.first_net_stats, new_first_stats,
                                 'first_net_stats did not change after system '
                                 'counters reset')

            # finally, if previous stats exist, and counters are reset, get their value
            # + current readings
            with patch(self.built_open) as mock_tel_open:
                previous_net_stats = {
                    'iface1': {
                        "bytes-transmitted": 1,
                        "bytes-received": 1
                    },
                    'iface2': {
                        "bytes-transmitted": 2,
                        "bytes-received": 2
                    }
                }
                mock_json_loads.return_value = previous_net_stats
                # 4 readers because open tx and rx per interface (2x2)
                mock_tel_open.side_effect = [
                    mock_open(read_data=json.dumps(previous_net_stats)).return_value,
                    mock_open(read_data='0').return_value,
                    mock_open(read_data='0').return_value,
                    mock_open(read_data='1').return_value,
                    mock_open(read_data='1').return_value,
                    MagicMock()]

                # result is the sum of previous + current
                self.assertEqual(
                    test_ip_monitor.read_traffic_data(),
                    [
                        {'interface': 'iface1',
                         'bytes-transmitted': 1,
                         'bytes-received': 1},
                        {'interface': 'iface2',
                         'bytes-transmitted': 3,
                         'bytes-received': 3}
                    ],
                    'Failed to get net stats after counter reset, having previous'
                    ' net stats')

                # first_net_stats is NOW changed because of reset, considering
                # previous stats
                new_first_stats = {
                    'iface1': {
                        "bytes-transmitted": 0,
                        "bytes-received": 0,
                        "bytes-transmitted-carry": 1,
                        "bytes-received-carry": 1
                    },
                    'iface2': {
                        "bytes-transmitted": 1,
                        "bytes-received": 1,
                        "bytes-transmitted-carry": 2,
                        "bytes-received-carry": 2
                    }
                }
                self.assertEqual(test_ip_monitor.first_net_stats, new_first_stats,
                                 'first_net_stats did not change after system counters '
                                 'reset, having previous stats')

    def test_populate_nb_report(self):
        runtime_mock = Mock()
        status = Mock()
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", runtime_mock, status)
        test_body: dict = {}
        # No data- return none
        test_ip_monitor.populate_nb_report(test_body)
        self.assertNotIn('ip', test_body)

        test_ip_monitor.data.ips.vpn = "VPN_IP"
        self.assertEqual("VPN_IP", test_ip_monitor.populate_nb_report(test_body))
        self.assertIn('ip', test_body)
        self.assertIn('resources', test_body)
        #
        test_ip_monitor.data.ips.vpn = ''
        test_ip_monitor.data.ips.public = "PUB"
        self.assertEqual('PUB', test_ip_monitor.populate_nb_report(test_body))

        # Test local IP report
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", runtime_mock, status)
        test_body: dict = {}
        it_name = 'test_1'
        it_rand_ip = generate_random_ip_address()

        test_ip_monitor.data.interfaces = {}
        self.assertIsNone(test_ip_monitor.populate_nb_report(test_body))

        test_ip_monitor.data.interfaces = {
            'test_1': NetworkInterface(iface_name=it_name,
                                       default_gw=True,
                                       ips=[IP(address=it_rand_ip)])}
        test_ip_monitor.data.ips.local = it_rand_ip
        self.assertEqual(it_rand_ip, test_ip_monitor.populate_nb_report(test_body))
        self.assertEqual(test_body['ip'], it_rand_ip)
        self.assertEqual(len(test_body['network']['interfaces']), 1)
        self.assertEqual(len(test_body['network']['interfaces'][0]['ips']), 1)
        self.assertEqual(test_body['network']['interfaces'][0]['interface'], it_name)
        self.assertEqual(test_body['network']['interfaces'][0]['ips'][0]['address'], it_rand_ip)

        test_ip_monitor.data.ips.local = ''
        self.assertIsNone(test_ip_monitor.populate_nb_report(test_body))

        # Test Swarm IP report
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", runtime_mock, status)
        test_body: dict = {}
        test_ip_monitor.populate_nb_report(test_body)
        test_ip_monitor.data.ips.swarm = 'SWARM'
        self.assertEqual('SWARM', test_ip_monitor.populate_nb_report(test_body))
        self.assertEqual('SWARM', test_body['ip'])
