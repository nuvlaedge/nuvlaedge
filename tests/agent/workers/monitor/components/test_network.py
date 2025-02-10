# -*- coding: utf-8 -*-
import os
import time
import unittest
from random import SystemRandom
from typing import List, Dict, Any

import requests
from mock import Mock, patch, MagicMock

from nuvlaedge.agent.workers.monitor.components import network as monitor
from nuvlaedge.agent.workers.monitor.data.network_data import NetworkInterface, NetworkingData, IP


def generate_random_ip_address():
    rand_bits = SystemRandom().getrandbits(8)
    it_str: List[str] = [str(rand_bits) for _ in range(4)]
    return ".".join(it_str)


atomic_write: str = 'nuvlaedge.common.file_operations.write_file'


class TestNetworkMonitor(unittest.TestCase):
    file_operations_read: str = "nuvlaedge.agent.workers.monitor.components.network.read_file"
    _path_json: str = 'json.loads'

    def setUp(self):
        self.network_monitor = monitor.NetworkMonitor("test_monitor", Mock(), Mock())

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
                monitor.NetworkMonitor("file", Mock(), True)
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


    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    def test_set_local_data_from_route_empty_routes(self, mock_read_traffic_data):
        mock_read_traffic_data.return_value = []
        self.network_monitor._set_local_data_from_route([])
        self.assertEqual(self.network_monitor.data.interfaces, {})

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    def test_set_local_data_from_route_default_gw(self, mock_read_traffic_data):
        mock_read_traffic_data.return_value = []
        routes = [{'dst': 'default', 'dev': 'eth0', 'prefsrc': '192.168.1.1'}]
        self.network_monitor._set_local_data_from_route(routes)
        self.assertEqual(self.network_monitor.data.default_gw, 'eth0')

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    def test_set_local_data_from_route_skip_route(self, mock_read_traffic_data):
        mock_read_traffic_data.return_value = []
        routes = [{'dst': '127.0.0.1', 'dev': 'lo', 'prefsrc': '127.0.0.1'}]
        self.network_monitor._set_local_data_from_route(routes)
        self.assertEqual(self.network_monitor.data.interfaces, {})

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    def test_set_local_data_from_route_add_interface(self, mock_read_traffic_data):
        mock_read_traffic_data.return_value = []
        routes = [{'dst': '192.168.1.0/24', 'dev': 'eth0', 'prefsrc': '192.168.1.2'}]
        self.network_monitor._set_local_data_from_route(routes)
        self.assertIn('eth0', self.network_monitor.data.interfaces)
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].iface_name, 'eth0')
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].ips[0].address, '192.168.1.2')

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    def test_set_local_data_from_route_update_traffic(self, mock_read_traffic_data):
        mock_read_traffic_data.return_value = [
            {"interface": "eth0", "bytes-transmitted": 1000, "bytes-received": 2000}
        ]
        routes = [{'dst': '192.168.1.0/24', 'dev': 'eth0', 'prefsrc': '192.168.1.2'}]
        self.network_monitor._set_local_data_from_route(routes)
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].tx_bytes, 1000)
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].rx_bytes, 2000)

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._get_default_gw_locally')
    def test_set_local_data_from_address_no_addresses(self, mock_get_default_gw, mock_read_traffic_data):
        mock_get_default_gw.return_value = 'eth0'
        mock_read_traffic_data.return_value = []
        self.network_monitor._set_local_data_from_address([])
        self.assertEqual(self.network_monitor.data.interfaces, {})

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._get_default_gw_locally')
    def test_set_local_data_from_address_with_addresses(self, mock_get_default_gw, mock_read_traffic_data):
        mock_get_default_gw.return_value = 'eth0'
        mock_read_traffic_data.return_value = [
            {"interface": "eth0", "bytes-transmitted": 1000, "bytes-received": 2000}
        ]
        addresses = [
            {
                "ifname": "eth0",
                "addr_info": [
                    {"local": "192.168.1.2", "family": "inet"},
                    {"local": "fe80::1", "family": "inet6"}
                ]
            }
        ]
        self.network_monitor._set_local_data_from_address(addresses)
        self.assertIn('eth0', self.network_monitor.data.interfaces)
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].iface_name, 'eth0')
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].ips[0].address, '192.168.1.2')
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].ips[1].address, 'fe80::1')
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].tx_bytes, 1000)
        self.assertEqual(self.network_monitor.data.interfaces['eth0'].rx_bytes, 2000)

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.read_traffic_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._get_default_gw_locally')
    def test_set_local_data_from_address_no_ip_address(self, mock_get_default_gw, mock_read_traffic_data):
        mock_get_default_gw.return_value = 'eth0'
        mock_read_traffic_data.return_value = []
        addresses = [
            {
                "ifname": "eth0",
                "addr_info": []
            }
        ]
        self.network_monitor._set_local_data_from_address(addresses)
        self.assertNotIn('eth0', self.network_monitor.data.interfaces)

    @patch('nuvlaedge.agent.workers.monitor.components.network.util.execute_cmd')
    def test_get_default_gw_locally_success(self, mock_execute_cmd):
        mock_execute_cmd.return_value = {"stdout": b"default via 192.168.1.1 dev eth0"}
        result = self.network_monitor._get_default_gw_locally()
        self.assertEqual(result, "eth0")

    @patch('nuvlaedge.agent.workers.monitor.components.network.util.execute_cmd')
    def test_get_default_gw_locally_no_output(self, mock_execute_cmd):
        mock_execute_cmd.return_value = {"stdout": b""}
        result = self.network_monitor._get_default_gw_locally()
        self.assertEqual(result, "")

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._set_local_data_from_address')
    @patch('nuvlaedge.agent.workers.monitor.components.network.util.execute_cmd')
    def test_set_local_data_host_mode(self, mock_execute_cmd, mock_set_local_data_from_address):
        os.environ['NUVLAEDGE_AGENT_NET_MODE'] = 'host'
        mock_execute_cmd.return_value = {"returncode": 0, "stdout": b'[]'}
        mock_set_local_data_from_address.return_value = None

        self.network_monitor.set_local_data()
        mock_execute_cmd.assert_called_once_with(['ip', '-j', 'address'], method_flag=False)
        mock_set_local_data_from_address.assert_called_once_with([])

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._parse_ip_output')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor._set_local_data_from_route')
    def test_set_local_data_container_mode(self, mock_set_local_data_from_route, mock_parse_ip_output):
        os.environ['NUVLAEDGE_AGENT_NET_MODE'] = ''

        # Create a mock for COEClient
        mock_coe_client = Mock()
        mock_coe_client.container_run_command.return_value = '[]'
        mock_parse_ip_output.return_value = []  # Mock the parsed output as an empty list
        mock_set_local_data_from_route.return_value = None

        # Replace the coe_client object with the mock
        self.network_monitor.coe_client = mock_coe_client

        self.network_monitor.set_local_data()

        # Perform assertions on the mock
        mock_coe_client.container_remove.assert_called_once_with(self.network_monitor.iproute_container_name)
        mock_coe_client.container_run_command.assert_called_once_with(
            image=self.network_monitor._ip_route_image,
            name=self.network_monitor.iproute_container_name,
            args='-j route',
            entrypoint='ip',
            network='host'
        )
        mock_set_local_data_from_route.assert_called_once_with([])

    @patch('nuvlaedge.agent.workers.monitor.components.network.util.execute_cmd')
    def test_set_local_data_host_mode_failure(self, mock_execute_cmd):
        os.environ['NUVLAEDGE_AGENT_NET_MODE'] = 'host'
        mock_execute_cmd.return_value = {"returncode": 1, "stderr": b'error'}

        result = self.network_monitor.set_local_data()
        self.assertEqual(result, '')
        mock_execute_cmd.assert_called_once_with(['ip', '-j', 'address'], method_flag=False)


    def test_is_skip_route(self):
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor("", Mock(), True)

        self.assertTrue(test_ip_monitor.is_skip_route({}, {}))

    # -------------------- VPN data tests -------------------- #

    def test_set_vpn_data(self):
        vpn_file = Mock()
        status = Mock()
        mock_telemetry = Mock()
        mock_telemetry.get_vpn_ip = "ASDFASF"
        status.iface_data = None
        test_ip_monitor: monitor.NetworkMonitor = \
            monitor.NetworkMonitor(vpn_file, mock_telemetry, status)

        it_ip: str = generate_random_ip_address()
        with patch('nuvlaedge.agent.workers.commissioner.VPNHandler.get_vpn_ip') as mock_get_vpn_ip:
            mock_get_vpn_ip.side_effect = [it_ip]
            test_ip_monitor.set_vpn_data()
            self.assertEqual(test_ip_monitor.data.ips.vpn, it_ip)

        test_ip_monitor.data.ips.vpn = ''
        with patch('nuvlaedge.agent.workers.commissioner.VPNHandler.get_vpn_ip') as mock_get_vpn_ip:
            mock_get_vpn_ip.side_effect = [""]
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

    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.set_public_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.set_local_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.set_vpn_data')
    @patch('nuvlaedge.agent.workers.monitor.components.network.NetworkMonitor.set_swarm_data')
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
        with patch('os.listdir') as mock_ls:
            mock_ls.side_effect = FileNotFoundError
            test_ip_monitor.read_traffic_data()

            # if sys path does not exist, get {}
            self.assertEqual(test_ip_monitor.read_traffic_data(), [],
                             'Got net info even though /sys path cannot be found')

            mock_ls.reset_mock(side_effect=True)

            # if previous net file cannot be found, or is malformed, don't load it
            with patch(self.file_operations_read) as mock_read:
                mock_read.side_effect = [None, MagicMock()]
                mock_ls.return_value = []  # no interfaces, get []
                self.assertEqual(test_ip_monitor.read_traffic_data(), [],
                                 'Got net info even though no interfaces were found')

            with patch(self.file_operations_read) as mock_read:
                # if there are interfaces
                mock_ls.return_value = ['iface1', 'iface2']
                # try to open but if it fails, get []
                mock_read.side_effect = [None, None,
                                         None, None, MagicMock()]
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
            with patch(self.file_operations_read) as mock_read:
                # 4 readers because open tx and rx per interface (2x2)
                mock_read.side_effect = [None, '1', '2', '3', '4', MagicMock()]

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
            with patch(self.file_operations_read) as mock_read:
                # 4 readers because open tx and rx per interface (2x2)
                mock_read.side_effect = [None, '10', '10', '20', '20', MagicMock()]

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
            with patch(self.file_operations_read) as mock_read:
                # 4 readers because open tx and rx per interface (2x2)
                mock_read.side_effect = [None, '0', '1', '2', '3', MagicMock()]
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
            with patch(self.file_operations_read) as mock_read:
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
                # 4 readers because open tx and rx per interface (2x2)
                mock_read.side_effect = [previous_net_stats,
                                         '0', '0', '1', '1', MagicMock()]

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
