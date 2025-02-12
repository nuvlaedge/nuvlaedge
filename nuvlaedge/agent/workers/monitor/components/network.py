# -*- coding: utf-8 -*-
""" NuvlaEdge IP address monitoring class.

This class is devoted to finding and reporting IP addresses of the Host,
Docker Container, and VPN along with their corresponding interface names.
It also reports and handles the IP geolocation system.

"""
import json
import logging
import os
import time

import requests

from nuvlaedge.common.constants import CTE
from ..components import monitor
from nuvlaedge.agent.common import util
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.data.network_data import (NetworkingData,
                                                               NetworkInterface,
                                                               IP, IPType)
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.workers.vpn_handler import VPNHandler
from nuvlaedge.common.file_operations import read_file, write_file


_IP_TYPE_CONVERSION: dict[str, IPType] = {
    "inet": "v4",
    "inet6": "v6"
}

@monitor('network_monitor')
class NetworkMonitor(Monitor):
    """
    Handles the retrieval of IP networking data.
    """
    _REMOTE_IPV4_API: str = "https://api.ipify.org?format=json"
    _IP_COMMAND_ARGS: str = '-j route'
    _IP_BASE_COMMAND: str = 'ip'
    _IP_ADDRESS_ARGS: str = '-j address'
    _PUBLIC_IP_UPDATE_RATE: int = 3600
    _NUVLAEDGE_COMPONENT_LABEL_KEY: str = util.base_label

    def __init__(self, name: str, telemetry, enable_monitor=True, period: int = 60):
        super().__init__(name, NetworkingData, enable_monitor, period)
        # list of network interfaces
        self.updaters: list = [self.set_public_data,
                               self.set_local_data,
                               self.set_swarm_data,
                               self.set_vpn_data]

        self.host_fs: str = CTE.HOST_FS
        self.first_net_stats: dict = {}
        self.previous_net_stats_file: str = FILE_NAMES.PREVIOUS_NET_STATS_FILE

        self.coe_client: COEClient = telemetry.coe_client
        self.excluded_field = {"type"} if not telemetry.ip_type_supported else set()

        self._ip_route_image: str = self.coe_client.current_image

        self.engine_project_name: str = self.get_engine_project_name()

        self.iproute_container_name: str = f'{self.engine_project_name}-iproute'

        self.last_public_ip: float = 0.0


    def get_engine_project_name(self) -> str:
        return self.coe_client.get_nuvlaedge_project_name(util.default_project_name)

    def set_public_data(self) -> None:
        """
        Reads the IP from the GeoLocation systems.
        """
        if time.time() - self.last_public_ip < self._PUBLIC_IP_UPDATE_RATE:
            return
        try:
            it_v4_response: requests.Response = requests.get(
                self._REMOTE_IPV4_API, timeout=5)

            if it_v4_response.status_code == 200:
                self.data.ips.public = \
                    json.loads(it_v4_response.content.decode("utf-8")).get("ip")
                self.last_public_ip = time.time()

        except requests.Timeout as ex:
            reason: str = f'Connection to server timed out: {ex}'
            self.logger.error(f'Cannot retrieve public IP: {reason}')
        except Exception as e:
            self.logger.error(f'Cannot retrieve public IP: {e}')

    def parse_host_ip_json(self, iface_data: dict) -> NetworkInterface | None:
        """
        Receives a dict with the information of a host interface and returns a
        BaseModel data class of NetworkInterface.

        @param iface_data: Single interface data entry.
        @return: NetworkInterface class
        """
        try:
            is_default_gw = iface_data.get('dst', '') == 'default'
            return NetworkInterface(iface_name=iface_data['dev'],
                                    ips=[IP(address=iface_data['prefsrc'])],
                                    default_gw=is_default_gw)
        except KeyError as err:
            self.logger.warning(f'Interface key not found {err}')
            return None

    @staticmethod
    def is_already_registered(interfaces: dict[str, NetworkInterface], it_route: dict) -> bool:
        it_name = it_route.get('dev', '')
        it_ip = IP(address=it_route.get('prefsrc', ''))
        return it_name in interfaces.keys() \
            and it_ip in interfaces[it_name].ips

    def is_skip_route(self, interfaces: dict[str, NetworkInterface], it_route: dict) -> bool:
        """
        Assess whether the IP route is a loopback or the interface is already
        registered

        Args:
            interfaces: current list of interfaces
            it_route: single IP route report in

        Returns:
            True if the route is to be skipped
        """
        is_loop: bool = it_route.get('dst', '127.').startswith('127.')
        is_already_registered: bool = self.is_already_registered(interfaces, it_route)
        not_complete: bool = 'prefsrc' not in it_route

        return is_loop or is_already_registered or not_complete

    @staticmethod
    def _parse_ip_output(ip_str: str) -> dict | list | None:
        """
        Parses the output of the IP command and returns a dictionary
        with the information of the interfaces and their corresponding
        IP addresses.

        Args:
            ip_str: Output of the IP command

        Returns:
            dict with the interfaces and their IP addresses
        """
        try:
            return json.loads(ip_str)
        except json.decoder.JSONDecodeError as ex:
            logging.warning(f'Failed parsing IP info: {ex}')

    def read_traffic_data(self) -> list:
        """ Gets the list of net ifaces and corresponding rxbytes and txbytes

            :returns [{"interface": "iface1", "bytes-transmitted": X,
            "bytes-received": Y}, {"interface": "iface2", ...}]
        """

        sysfs_net = f"{self.host_fs}/sys/class/net"

        try:
            ifaces = os.listdir(sysfs_net)
        except FileNotFoundError:
            self.logger.warning("Cannot find network information for this device")
            return []

        previous_net_stats = read_file(self.previous_net_stats_file, True, False)
        if not previous_net_stats:
            previous_net_stats = {}

        net_stats = []
        for interface in ifaces:
            stats = f"{sysfs_net}/{interface}/statistics"
            rx_bytes_str = read_file(f"{stats}/rx_bytes")
            tx_bytes_str = read_file(f"{stats}/tx_bytes")
            if rx_bytes_str is None or tx_bytes_str is None:
                continue
            rx_bytes = int(rx_bytes_str)
            tx_bytes = int(tx_bytes_str)

            # we compute the net stats since the beginning of the NB lifetime
            # and our counters reset on every NB restart
            if interface in self.first_net_stats:
                if rx_bytes < self.first_net_stats[interface].get('bytes-received', 0) \
                        or tx_bytes < \
                        self.first_net_stats[interface].get('bytes-transmitted', 0):

                    # then the system counters were reset
                    self.logger.warning(f'Host network counters seem to have been reset for network interface '
                                        f'{interface}')

                    if interface in previous_net_stats:
                        # in this case, because the numbers no longer correlate,
                        # we need to add up to the previous reported value
                        rx_bytes_report = previous_net_stats[interface].get(
                            'bytes-received', 0) + rx_bytes
                        tx_bytes_report = previous_net_stats[interface].get(
                            'bytes-transmitted', 0) + tx_bytes
                    else:
                        rx_bytes_report = rx_bytes
                        tx_bytes_report = tx_bytes

                    self.first_net_stats[interface] = {
                        "bytes-transmitted": tx_bytes,
                        "bytes-received": rx_bytes,
                        "bytes-transmitted-carry": previous_net_stats.get(interface,
                                                                          {}).get(
                            'bytes-transmitted', 0),
                        "bytes-received-carry": previous_net_stats.get(interface, {}).get(
                            'bytes-received', 0),
                    }
                else:
                    # then counters are still going. In this case we just need to do
                    #
                    # current - first + carry
                    rx_bytes_report = rx_bytes - \
                                      self.first_net_stats[interface].get(
                                          'bytes-received', 0) + \
                                      self.first_net_stats[interface].get(
                                          'bytes-received-carry', 0)
                    tx_bytes_report = \
                        tx_bytes - \
                        self.first_net_stats[interface].get('bytes-transmitted', 0) + \
                        self.first_net_stats[interface].get('bytes-transmitted-carry', 0)

            else:
                rx_bytes_report = previous_net_stats.get(interface, {}).get(
                    'bytes-received', 0)
                tx_bytes_report = previous_net_stats.get(interface, {}).get(
                    'bytes-transmitted', 0)

                self.first_net_stats[interface] = {
                    "bytes-transmitted": tx_bytes,
                    "bytes-received": rx_bytes,
                    "bytes-transmitted-carry": tx_bytes_report,
                    "bytes-received-carry": rx_bytes_report
                }

            previous_net_stats[interface] = {
                "bytes-transmitted": tx_bytes_report,
                "bytes-received": rx_bytes_report
            }

            net_stats.append({
                "interface": interface,
                "bytes-transmitted": tx_bytes_report,
                "bytes-received": rx_bytes_report
            })

        write_file(previous_net_stats, self.previous_net_stats_file, encoding='UTF-8')

        return net_stats

    def set_local_data(self):
        """
                Gathers a json type string containing the host local network routing if
                the container run is run successfully
                Returns:
                    str as the output of the command (can be empty).
                """
        network_mode = os.environ.get('NUVLAEDGE_AGENT_NET_MODE', '')
        if network_mode and network_mode == 'host':
            command = [self._IP_BASE_COMMAND]
            command.extend(self._IP_ADDRESS_ARGS.split(' '))
            self.logger.debug(f'Scanning local IP with command: {command}')
            result = util.execute_cmd(command, method_flag=False)
            if result.get('returncode', -1) != 0:
                self.logger.error(f'Failed to get local IP route: {result.get("stderr")}')
                return ''
            ip_ad_data = self._parse_ip_output(result.get('stdout'))
            return self._set_local_data_from_address(ip_ad_data)

        else:
            self.coe_client.container_remove(self.iproute_container_name)
            self.logger.debug(f'Scanning local IP with IP route image {self._ip_route_image}')
            result = self.coe_client.container_run_command(
                image=self._ip_route_image,
                name=self.iproute_container_name,
                args=self._IP_COMMAND_ARGS,
                entrypoint=self._IP_BASE_COMMAND,
                network='host')

            self.logger.debug(f'ip_route: {result}')
            ip_route_data = self._parse_ip_output(result)
            return self._set_local_data_from_route(ip_route_data)

    def _get_default_gw_locally(self) -> str:
        cmd = [self._IP_BASE_COMMAND, "route", "show", "default"]
        result = util.execute_cmd(cmd, method_flag=False)
        gw = result["stdout"]
        if gw:
            gw = gw.decode("utf-8").strip().split()
            return gw[-1] if gw else ''
        return ""

    def _set_local_data_from_address(self, addresses: list):
        self.logger.debug(f"Local IP address data: {json.dumps(addresses, indent=4)}")

        self.data.default_gw = self._get_default_gw_locally()
        self.logger.debug(f"Default gateway: {self.data.default_gw}")

        traffic: dict = {t.get("interface"): t for t in self.read_traffic_data()}

        interfaces: dict = {}

        for iface_data in addresses:
            iface_name = iface_data.get("ifname")
            iface_addr = iface_data.get("addr_info", [])
            if not iface_addr:
                self.logger.debug(f"Interface {iface_name} has no IP address")
                continue

            iface = NetworkInterface(
                iface_name=iface_name,
                default_gw=iface_name == self.data.default_gw)


            for addr in iface_addr:
                ip = addr.get("local", None)
                ip_type = addr.get("family", None)
                if not ip or not ip_type:
                    continue

                if iface.default_gw and ip_type == 'inet':
                    self.data.ips.local = ip

                iface.ips.append(IP(address=ip, type=_IP_TYPE_CONVERSION[ip_type]))


            iface_traffic: dict[str, any] = traffic.get(iface_name, {})
            if iface_traffic:
                iface.tx_bytes = int(iface_traffic.get('bytes-transmitted', ''))
                iface.rx_bytes = int(iface_traffic.get('bytes-received', ''))

            interfaces[iface_name] = iface

        self.data.interfaces = interfaces

    def _set_local_data_from_route(self, routes: list) -> None:
        """
        Runs the auxiliary container that reads the host network interfaces and parses the
        output return
        """
        if not routes:
            return

        interfaces = {}
        for route in routes:
            it_name = route.get('dev')
            it_ip = route.get('prefsrc')

            # Handle special cases
            if route.get('dst', 'not_def') == 'default':
                self.data.default_gw = it_name

            if self.is_skip_route(interfaces, route):
                continue

            # Create new interface data structure
            it_iface: NetworkInterface
            if it_name in interfaces:
                it_iface = interfaces[it_name]
            else:
                it_iface = self.parse_host_ip_json(route)
                interfaces[it_name] = it_iface

            if it_iface and it_name and it_ip:
                if it_name == self.data.default_gw:
                    it_iface.default_gw = True

                    if self.data.ips.local != it_ip:
                        self.data.ips.local = it_ip

                ip_address = IP(address=it_ip)
                if ip_address not in interfaces[it_name].ips:
                    interfaces[it_name].ips.append(ip_address)

        # Update traffic data
        it_traffic: list = self.read_traffic_data()

        for iface_traffic in it_traffic:
            it_name: str = iface_traffic.get("interface")
            if it_name in interfaces.keys():
                interfaces[it_name].tx_bytes = \
                    iface_traffic.get('bytes-transmitted', '')
                interfaces[it_name].rx_bytes = \
                    iface_traffic.get('bytes-received', '')

        self.logger.debug(f'interfaces (new): {interfaces}')
        self.data.interfaces = interfaces

    def set_vpn_data(self) -> None:
        """ Discovers the NuvlaEdge VPN IP  """

        vpn_ip = VPNHandler.get_vpn_ip()
        if vpn_ip and self.data.ips.vpn != vpn_ip:
            self.data.ips.vpn = vpn_ip

    def set_swarm_data(self) -> None:
        """ Discovers the host SWARM IP address """
        self.data.ips.swarm = self.coe_client.get_api_ip_port()[0]

    def update_data(self) -> None:
        """
        Iterates over the different interfaces and gathers the data
        """
        for updater in self.updaters:
            updater()

    def populate_telemetry_payload(self):
        """
        Network report structure:
        network: {
            default_gw: str,
            ips: {
                local: str,
                public: str,
                swarm: str,
                vpn: str
                }
            interfaces: [
                {
                    "interface": iface_name
                    "ips": [{
                        "address": "ip_Add"
                    }]
                }
            ]
        }
        """
        # Until server is adapted, we only return a single IP address as
        #  a string following the next priority.
        # 1.- VPN
        # 2.- Default Local Gateway
        # 3.- Public
        # 4.- Swarm
        it_traffic: list = [x.dict(by_alias=True, exclude={'ips', 'default_gw'})
                            for _, x in self.data.interfaces.items()]

        it_report = self.data.dict(by_alias=True, exclude={'interfaces'}, exclude_none=True)


        it_report['interfaces'] = [{'interface': name,
                                    'ips': [ip.dict(exclude=self.excluded_field) for ip in obj.ips]}
                                   for name, obj in self.data.interfaces.items()]

        self.telemetry_data.network = it_report

        if it_traffic:
            self.telemetry_data.resources = {
                'net-stats': it_traffic
            }

        if self.data.ips.vpn:
            self.telemetry_data.ip = str(self.data.ips.vpn)
            return

        if self.data.ips.local:
            self.telemetry_data.ip = str(self.data.ips.local)
            return

        if self.data.ips.public:
            self.telemetry_data.ip = str(self.data.ips.public)
            return

        if self.data.ips.swarm:
            self.telemetry_data.ip = str(self.data.ips.swarm)
