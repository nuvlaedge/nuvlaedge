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
    '''testing only'''
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
    
    net_mask = "24"
    ports_range = "-p-"
    alternate_modbus_port = "5020"
    if alternate_modbus_port:
        ports_range = "-p " + alternate_modbus_port

    logger.info("Scanning open ports...")

    # FIXME we could determine which port to target based on the configuration of the nmap script?
    # Saves scanning all those open ports?
    # the default gateway for kubernetes is the CNI gateway. All kubernetes pods will be in this namespace...
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        host = host + "/" + net_mask # set the host to CIDR range
        # check if a MY_HOST_NODE_IP has been defined
        if os.getenv('MY_HOST_NODE_IP'):
            host = host + ' ' + os.getenv('MY_HOST_NODE_IP')
        logging.info('The host list in k8s has been set to:\n%s',host)
        # FIX ME testing only
        nmap_replace_port("/usr/share/nmap/scripts/" + \
            modbus_nse, "port_or_service(502,", "port_or_service(" + alternate_modbus_port + ",")
        host = host + " 185.19.31.148"

    command = \
        "nmap --script {} --script-args='modbus-discover.aggressive=true' {} {} -T4 -oX {} > /dev/null"\
        .format(modbus_nse,
                ports_range,
                host,
                xml_file)

    logger.info('Generated command:\n%s',command) # FIXME

    os.system(command)

    logger.info('Completed...') # FIXME

    return xml_file

def manage_modbus_peripherals(ip_address):
    """ Takes care of posting or deleting the respective
    NB peripheral resources from Nuvla
    :param ip_address:
    """

    # local file naming convention:
    #    modbus.{port}.{interface}.{identifier}

    # Ask the NB agent for all modbus peripherals matching this pattern
    logger.info(f'Starting modbus scan on {ip_address}')
    xml_file = scan_open_ports(ip_address)

    parser = NmapOutputXMLParser(xml_file)
    parser.parse()

    all_modbus_devices = parser.get_modbus_details()
    discovered_devices: dict = {}
    if ip_address not in all_modbus_devices:
        logger.warning(f'No Modbus Info found for host : {ip_address}')
        return discovered_devices

    for per in all_modbus_devices[ip_address]:
        port = per.get("port", "nullport")
        interface = per.get("interface", "nullinterface")
        identifiers = per.get("identifiers").copy()
        del per["identifiers"]
        for ident in identifiers:
            _id = ident['key']
            per['classes'] = ident['classes']
            per['vendor'] = ident['vendor']
            per['name'] = ident['name']
            identifier = "modbus.{}.{}.{}".format(port, interface, _id)
            # Redefine the identifier
            per['identifier'] = identifier
            discovered_devices[identifier] = per.copy()

    logger.info(f"discovered devices:\n {discovered_devices}")

    return discovered_devices


def main():
    global logger

    parse_arguments_and_initialize_logging('Modbus Peripheral')

    logger = logging.getLogger(__name__)

    gateway_ip = get_default_gateway_ip()

    modbus_peripheral: Peripheral = Peripheral('modbus')

    modbus_peripheral.run(manage_modbus_peripherals, ip_address=gateway_ip)


if __name__ == '__main__':
    main()
