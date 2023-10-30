#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""NuvlaEdge Peripheral Manager Modbus

This service takes care of the discovery and overall
management of Modbus peripherals that are attached to
the NuvlaEdge.

It provides:
 - automatic discovery and reporting of Modbus peripherals
 - data gateway capabilities for Modbus (see docs)
 - modbus2mqtt on demand
"""

import socket
import struct
import os
import logging
import fileinput
import sys
import asyncio
import ipaddress
import subprocess

from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.common.nmap_output_xml_parser import NmapOutputXMLParser

logger = logging.getLogger(__name__)


def get_default_gateway_ip():
    """ Get the default gateway IP

    :returns IP of the default gateway
    """

    logger.info("Retrieving gateway IP...")

    with open("/proc/net/route") as route:
        for line in route:
            fields = line.strip().split()
            if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                continue

            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))

def nmap_replace_port(file, search_exp, replace_exp):
    '''
    Use this to change the port number in the nmap modbus script
    We keep this as a reminder that this may need to be done in the future.
    '''

    for line in fileinput.input(file, inplace=1):
        if search_exp in line:
            line = line.replace(search_exp,replace_exp)
        sys.stdout.write(line)

def scan_open_ports(host, modbus_nse="modbus-discover.nse", xml_file="/tmp/nmap_scan.xml"):
    """ Uses nmap to scan all the open ports in the NuvlaEdge.
        Writes the output into an XML file.

    :param host: IP of the host to be scanned
    :param modbus_nse: nmap NSE script for modbus service discovery
    :param xml_file: XML filename where to write the nmap output

    :returns XML filename where to write the nmap output
    """

    ports_range = "-p-"
    # alternate_modbus_port = ""
    # if alternate_modbus_port:
      #   ports_range = "-p " + alternate_modbus_port
        # nmap_replace_port("/usr/share/nmap/scripts/" + \
          #   modbus_nse, "port_or_service(502,", "port_or_service(" + alternate_modbus_port + ",")

    logger.info("Scanning open ports...")

    command = \
        "nmap --script {} --script-args='modbus-discover.aggressive=true' {} {} -T4 -oX {} > /dev/null"\
        .format(modbus_nse,
                ports_range,
                host,
                xml_file)

    logger.debug(f'Generated command:\n{command}')

    os.system(command)

    return xml_file

def manage_modbus_peripherals(ip_address):
    """ Takes care of posting or deleting the respective
    NB peripheral resources from Nuvla
    :param ip_address:
    """

    # local file naming convention:
    #    modbus.{port}.{interface}.{identifier}

    # Ask the NB agent for all modbus peripherals matching this pattern
    # probably the kubernetes stuff should go here?
    # why not?

    logger.info(f'Starting modbus scan on {ip_address}')
    xml_file = scan_open_ports(ip_address)

    parser = NmapOutputXMLParser(xml_file)
    parser.parse()

    all_modbus_devices = parser.get_modbus_details()
    logger.debug(f"All modbus devices:\n {all_modbus_devices}")

    discovered_devices: dict = {}

    for returned_ip_address in all_modbus_devices.keys():
        for per in all_modbus_devices[returned_ip_address]:
            port = per.get("port", "nullport")
            interface = per.get("interface", "nullinterface")
            identifiers = per.get("identifiers").copy()
            del per["identifiers"]
            for ident in identifiers:
                _id = ident['key']
                per['classes'] = ident['classes']
                per['vendor'] = ident['vendor']
                per['name'] = ident['name']
                per['testhost'] = returned_ip_address
                identifier = "host {}:{} interface {} id {}".format(returned_ip_address, port, interface, _id)
                # Redefine the identifier
                per['identifier'] = identifier
                discovered_devices[identifier] = per.copy()

    logger.debug(f"discovered devices:\n {discovered_devices}")

    return discovered_devices

def determine_ip_addresses_old(list_of_ip_addresses):
    """Determine the list of IP addresses to be scanned."""

    command = "ip -4 -br a s"
    logger.debug(f'IP address command:\n{command}')

    known_ip_addresses = os.system(command)

    logger.debug(f"Known IP addresses:\n {known_ip_addresses}")

    if os.getenv('KUBERNETES_SERVICE_HOST') and os.getenv('MY_HOST_NODE_IP'):
        list_of_ip_addresses = list_of_ip_addresses + ' ' + os.getenv('MY_HOST_NODE_IP')

    logging.debug(f'The list of IP addresses has been set to:\n{list_of_ip_addresses}')

    return list_of_ip_addresses


def determine_ip_addresses(list_of_ip_addresses):
    """
    Determine the list of IP addresses to be scanned on the host.

    Input: list_of_ip_addresses which is the default gateway

    This function will detect all the IP addresses and remove non-routable 
    IP addresses and networks.
    This may need to be adjusted according to how customers deploy modbus
    """
    command="ip -4 -br a s | awk -F \" \" '{print $3}'"

    try:
        ip_list = subprocess.run(["sh", "-c", command], timeout=5, \
            capture_output=True, check=True, encoding="UTF-8")
    except FileNotFoundError as exc:
        logging.error(f"Process failed because the executable could not be found.\n{exc}")
    except subprocess.CalledProcessError as exc:
        logging.error(
            f"Process failed because did not return a successful return code. "
            f"Returned {exc.returncode}\n{exc}"
        )
    except subprocess.TimeoutExpired as exc:
        logging.error(f"Process timed out.\n{exc}")

    for ip_add in ip_list.stdout.splitlines():
        if ipaddress.ip_network(ip_add, strict=False):
            if not ipaddress.ip_network(ip_add, strict=False).is_private:
                logging.info(f"IP address {ip_add} is routable!")
                list_of_ip_addresses = list_of_ip_addresses + ip_add
        else:
            if not ipaddress.ip_address(ip_add).is_private:
                logging.info(f"IP address {ip_add} is routable!")
                list_of_ip_addresses = list_of_ip_addresses + ip_add
    if os.getenv('KUBERNETES_SERVICE_HOST') and os.getenv('MY_HOST_NODE_IP'):
        list_of_ip_addresses = list_of_ip_addresses + ' ' + os.getenv('MY_HOST_NODE_IP')
        
    return list_of_ip_addresses


async def main():
    global logger

    parse_arguments_and_initialize_logging('Modbus Peripheral')

    logger = logging.getLogger(__name__)

    gateway_ip = get_default_gateway_ip()

    modbus_peripheral: Peripheral = Peripheral('modbus')

    # do the ip address thing here?
    
    list_of_ip_addresses = determine_ip_addresses(gateway_ip)
    
    await modbus_peripheral.run(manage_modbus_peripherals, ip_address=list_of_ip_addresses)
    

def entry():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
