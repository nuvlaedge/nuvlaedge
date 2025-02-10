# -*- coding: utf-8 -*-

""" NuvlaEdge Edge Networking data structure

Gathers all the requirements for status reporting
"""
from typing import Literal

from pydantic import Field

from nuvlaedge.agent.workers.monitor import BaseDataStructure

IPType = Literal["v4", "v6"]

class IP(BaseDataStructure):
    """
    address: IP addresses
    """
    address: str = ''
    type: IPType = 'v4'

    def __hash__(self):
        return hash(self.address)


class NetworkInterface(BaseDataStructure):
    """
    Pydantic BaseModel definition for Network interfaces. This includes public,
    vpn, and swarm addresses.
        iface_name: network interface name
        ips: List of IP addresses
        default_gw: flag indicating whether the interface is the default for the host
        device or not
    """

    iface_name: str | None = Field(None, alias='interface')
    ips: list[IP] = Field(default_factory=list)
    default_gw: bool = Field(False, alias='default-gw')

    # Interface data traffic control
    tx_bytes: int | None = Field(0, alias='bytes-transmitted')
    rx_bytes: int | None = Field(0, alias='bytes-received')


class IPAddresses(BaseDataStructure):
    """
    public: Public IPv4 and IPv6 addresses
    local: Host device local interface and its corresponding IP addresses
    vpn: VPN IPv4 address provided by OpenVpn server (If present)
    swarm: SWARM node IP address (If present)
    """
    public: str = ''
    swarm: str = ''
    vpn: str = ''
    local: str = ''


class NetworkingData(BaseDataStructure):
    """
    Base model to gather all the IP addresses in the NuvlaEdge device

    """
    default_gw: str | None = None
    interfaces: dict[str, NetworkInterface] = Field(default_factory=dict)
    ips: IPAddresses = IPAddresses()
