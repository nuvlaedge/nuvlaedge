#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""NuvlaEdge Peripheral Manager Network
This service provides network devices discovery.
"""

import logging
import requests
import os
import xmltodict
import re
import base64

from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging

# Packages for Service Discovery
from ssdpy import SSDPClient
from xml.dom import minidom
from urllib.parse import urlparse
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from zeroconf import ZeroconfServiceTypes, ServiceBrowser, Zeroconf

scanning_interval = 30

logger: logging.Logger = logging.getLogger(__name__)

KUBERNETES_SERVICE_HOST = os.getenv('KUBERNETES_SERVICE_HOST')
namespace = os.getenv('MY_NAMESPACE', 'nuvlaedge')


def get_ssdp_device_xml_as_json(url):
    """
    Requests and parses XML file with information from SSDP
    """

    if not url:
        return {}

    parsed_url = urlparse(url)
    try:
        if not parsed_url.scheme:
            url = f'http://{url}'
    except AttributeError:
        return {}

    try:
        r = requests.get(url)
        device_xml = minidom.parseString(r.content).getElementsByTagName('device')[0]

        device_json = xmltodict.parse(device_xml.toxml())

        return device_json.get('device', {})
    except Exception as e:
        logger.debug(f'Exception {e} parsing xml from {url}')
        logger.warning(f"Cannot get and parse XML for SSDP device info from {url}")
        return {}


def ssdp_manager():
    """
    Manages SSDP discoverable devices (SSDP and UPnP devices)
    """

    client = SSDPClient()
    devices = client.m_search("ssdp:all")
    output = {
        'peripherals': {},
        'xml': {}
    }

    for device in devices:
        try:
            usn = device['usn']
        except KeyError:
            logger.warning(f'SSDP device {device} missinng USN field, and thus is considered not compliant. Ignoring')
            continue

        if ":device:" in usn:
            # normally, USN = "uuid:XYZ::urn:schemas-upnp-org:device:DEVICETYPE:1"
            # if this substring is not there, then we are not interested (it might be a service)
            try:
                device_class = usn.split(':device:')[1].split(':')[0]
            except IndexError:
                logger.exception(f'Failed to infer device class for from USN {usn}')
                continue
        else:
            continue

        try:
            identifier = usn.replace("uuid:", "").split(":")[0]
        except IndexError:
            logger.warning(f'Cannot parse USN {usn}. Continuing with raw USN value as identifier')
            identifier = usn

        if identifier in output['peripherals']:
            # ssdp device has already been identified. This entry might simply be another service/class
            # of the same device let's just see if there's an update to the classes and move on

            existing_classes = output['peripherals'][identifier]['classes']
            if device_class in existing_classes:
                continue
            else:
                output['peripherals'][identifier]['classes'].append(device_class)
        else:
            # new device
            location = device.get('location')
            device_from_location = get_ssdp_device_xml_as_json(location)    # always a dict
            alt_name = usn
            if 'x-friendly-name' in device:
                try:
                    alt_name = base64.b64decode(device.get('x-friendly-name')).decode()
                except Exception as ex:
                    logger.debug('Exception decoding name', ex)

            name = device_from_location.get('friendlyName', alt_name)
            description = device_from_location.get('modelDescription',
                                                   device.get('server', name))

            output['peripherals'][identifier] = {
                'classes': [device_class],
                'available': True,
                'identifier': identifier,
                'interface': 'SSDP',
                'name': name,
                'description': description
            }

            if location:
                output['peripherals'][identifier]['device-path'] = location

            vendor = device_from_location.get('manufacturer')
            if vendor:
                output['peripherals'][identifier]['vendor'] = vendor

            product = device_from_location.get('modelName')
            if product:
                output['peripherals'][identifier]['product'] = product

            serial = device_from_location.get('serialNumber')
            if serial:
                output['peripherals'][identifier]['serial-number'] = serial

    return output['peripherals']


def ws_discovery_manager(ws_daemon):
    """
    Manages WSDiscovery discoverable devices
    """
    manager = {}

    ws_daemon.start()

    services = ws_daemon.searchServices(timeout=6)
    for service in services:
        identifier = str(service.getEPR()).split(':')[-1]
        classes = [ re.split("/|:", str(c))[-1] for c in service.getTypes() ]
        name = " | ".join(classes)
        if identifier not in manager.keys():
            output = {
                "available": True,
                "name": name,
                "description": f"[wsdiscovery peripheral] {str(service.getEPR())} | Scopes: {', '.join([str(s) for s in service.getScopes()])}",
                "classes": classes,
                "identifier": identifier,
                "interface": 'WS-Discovery',
            }

            if len(service.getXAddrs()) > 0:
                output['device-path'] = ", ".join([str(x) for x in service.getXAddrs()])

            manager[identifier] = output

    ws_daemon.stop()

    return manager


class ZeroConfListener:
    all_info = {}
    listening_to = {}

    def remove_service(self, name):
        logger.info(f"[zeroconf] Service {name} removed")
        if name in self.all_info:
            self.all_info.pop(name)

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        logger.info(f"[zeroconf] Service {name} added")
        self.all_info[name] = info

    update_service = add_service


def format_zeroconf_services(services):
    """ Formats the Zeroconf listener services into a Nuvla compliant data format

    :param services: list of zeroconf services from lister, i.e. list = {'service_name': ServiceInfo, ...}
    :return: Nuvla formatted peripheral data
    """

    output = {}

    for service_name, service_data in services.items():
        try:
            identifier = service_data.server

            if identifier not in output:
                output[identifier] = {
                    'name': service_data.server,
                    'description': f'{service_name}:{service_data.port}',
                    'identifier': identifier,
                    'available': True,
                    'interface': "Bonjour/Avahi",
                    'classes': [service_data.type]
                }

            if service_data.type not in output[identifier]['classes']:
                output[identifier]['classes'].append(service_data.type)

            if service_data.parsed_addresses() and 'device-path' not in output[identifier]:
                output[identifier]['device-path'] = service_data.parsed_addresses()[0]

            if service_name not in output[identifier]['description']:
                output[identifier]['description'] += f' | {service_name}:{service_data.port}'

            try:
                properties = service_data.properties
                if properties and isinstance(properties, dict):
                    dict_properties = dict(map(lambda tup:
                                               map(lambda el: el.decode('ascii', errors="ignore"), tup),
                                               properties.items()))

                    # Try to find a limited and predefined list of known useful attributes:

                    # for the device model name:
                    product_name_known_keys = ['model', 'ModelName', 'am', 'rpMd', 'name']
                    matched_keys = list(product_name_known_keys & dict_properties.keys())
                    if matched_keys:
                        output[identifier]['name'] = output[identifier]['product'] = dict_properties[matched_keys[0]]

                    # for additional description
                    if 'uname' in dict_properties:
                        output[identifier]['description'] += f'. OS: {dict_properties["uname"]}'

                    if 'description' in dict_properties:
                        output[identifier]['description'] += f'. Extra description: {dict_properties["description"]}'

                    # for additional classes
                    if 'class' in dict_properties:
                        output[identifier]['class'].append(dict_properties['class'])
            except Exception as ex:
                # this is only to get additional info on the peripheral, if it fails, we can live without it
                logger.debug('Failed gathering extra information from peripheral', ex)

        except Exception as ex:
            logger.exception(f'Unable to categorize Zeroconf peripheral {service_name} with data: {service_data}', ex)
            continue

    return output


def parse_zeroconf_devices(zc, listener):
    """ Manages the Zeroconf listeners and parse the existing broadcasted services

    :param zc: zeroconf object
    :param listener: zeroconf listener instance
    :return: list of peripheral documents
    """

    service_types_available = set(ZeroconfServiceTypes.find())

    old_service_types = set(listener.listening_to) - service_types_available
    new_service_types = service_types_available - set(listener.listening_to)

    for new in new_service_types:
        try:
            listener.listening_to[new] = ServiceBrowser(zc, new, listener)
        except Exception:
            logger.exception(f'Zeroconf exception in ServiceBrowser(zc={zc}, new={new}, listener={listener})')

    for old in old_service_types:
        listener.listening_to[old].cancel()
        logger.info(f'Removing Zeroconf listener for service type {old}: {listener.listening_to.pop(old)}')

    return format_zeroconf_services(listener.all_info)


def network_manager(**kwargs):
    """
    Runs and manages the outputs from the discovery.
    """
    output = {}

    if kwargs['zc_obj']:
        zeroconf_output = parse_zeroconf_devices(kwargs['zc_obj'], kwargs['zc_listener'])
    else:
        zeroconf_output = {}

    ssdp_output = ssdp_manager()
    ws_discovery_output = ws_discovery_manager(kwargs['wsdaemon'])
    output.update(ssdp_output)
    output.update(ws_discovery_output)
    output.update(zeroconf_output)

    return output


async def main():
    global logger
    parse_arguments_and_initialize_logging('Network Peripheral')

    logger = logging.getLogger(__name__)
    logger.info('NETWORK PERIPHERAL MANAGER STARTED')

    network_peripheral: Peripheral = Peripheral('network')
    try:
        zeroconf = Zeroconf()
    except OSError as ex:
        logger.error(f'Zeroconf failed to start and cannot be fixed without a restart: {str(ex)}')
        zeroconf = zeroconf_listener = None
    else:
        zeroconf_listener = ZeroConfListener()

    ws_daemon = WSDiscovery()

    await network_peripheral.run(network_manager, zc_obj=zeroconf, zc_listener=zeroconf_listener, wsdaemon=ws_daemon)
