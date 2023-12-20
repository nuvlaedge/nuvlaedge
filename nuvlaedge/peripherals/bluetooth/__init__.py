#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""NuvlaEdge Peripheral Manager Bluetooth

This service provides bluetooth device discovery.

"""

import logging
import sys
import os

from typing import List

import bluetooth as bt

from bleak import BleakScanner, BLEDevice, AdvertisementData, BleakClient
from bleak.backends._manufacturers import MANUFACTURERS
from bleak.uuids import uuidstr_to_str

from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging

logger: logging.Logger = logging.getLogger(__name__)


def device_discovery():
    """
    Return all discoverable bluetooth class devices.
    """
    return bt.discover_devices(lookup_names=True, lookup_class=True)


async def ble_device_discovery() -> dict:
    """
    Return all discoverable ble devices
    """
    devices: dict[str, tuple[BLEDevice, AdvertisementData]] = await BleakScanner.discover(timeout=4, return_adv=True)
    ble_devices: dict = {}
    for dev_id, ble_device in devices.items():
        ble_devices[dev_id] = {}
        ble_devices[dev_id]['available'] = True
        ble_devices[dev_id]['interface'] = "Bluetooth-LE"
        ble_devices[dev_id]['identifier'] = dev_id
        ble_devices[dev_id]['classes'] = []
        if ble_device[0].name != "":
            ble_devices[dev_id]['name'] = ble_device[0].name
        ble_devices[dev_id]['address'] = ble_device[0].address
        ble_devices[dev_id]['rssi'] = ble_device[1].rssi
        man_dict = ble_device[1].manufacturer_data
        ble_devices[dev_id]['vendor'] = ''
        for company_id in man_dict.keys():
            if company_id in MANUFACTURERS:
                ble_devices[dev_id]['vendor'] += MANUFACTURERS[company_id] + ', '
        if ble_devices[dev_id]['vendor'] != '':
            ble_devices[dev_id]['vendor'] = ble_devices[dev_id]['vendor'][:-2]
        uuids: List = ble_device[1].service_uuids
        if ble_device[1].platform_data[1] is not None:
            get_info_from_raw_data(ble_device[1].platform_data[1], ble_devices[dev_id])
        fill_service_desc(uuids, ble_devices[dev_id])
        if ble_devices[dev_id]['vendor'] == '':
            del ble_devices[dev_id]['vendor']
    return ble_devices


def get_info_from_raw_data(raw_data: dict, device_info: dict):
    for key, value in raw_data.items():
        if key == 'Class':
            device_info['classes'] = cod_converter(value)
        elif key == 'Name':
            device_info['name'] = value


def fill_service_desc(uuids: List, device_info: dict):
    if device_info['classes']:
        return
    for service_id in uuids:
        service_desc = uuidstr_to_str(service_id)
        if service_desc != "Unknown" and service_desc != device_info['vendor']:
            device_info['classes'].append(service_desc)


def compare_bluetooth(bluetooth, ble):
    output = []

    for device in bluetooth:
        device_id = device[0]
        # if device_id not in ble:
        d = {
            "identifier": device_id,
            "class": device[2],
            "interface": "Bluetooth"
        }
        if device[1] != "":
            d["name"] = device[1]
        output.append(d)

        # elif device[1] and not ble[device_id].get('name'):
        #     ble[device_id]['name'] = device[1]

    return output


def cod_converter(cod_decimal_string):
    """ From a decimal value of CoD, map and retrieve the corresponding major class of a Bluetooth device

    :param cod_decimal_string: numeric string corresponding to the class of device
    :return: list of class(es)
    """

    if not cod_decimal_string or cod_decimal_string == "":
        return []

    cod_decimal_string = int(cod_decimal_string)

    # Major CoDs
    classes = {0: {'major': 'Miscellaneous',
                   'minor': {}},
               1: {
                   'major': 'Computer',
                   'minor': {
                       'bitwise': False,
                       '0': 'Uncategorized',
                       '1': 'Desktop workstation',
                       '2': 'Server-class computer',
                       '3': 'Laptop',
                       '4': 'Handheld PC/PDA (clamshell)',
                       '5': 'Palm-size PC/PDA',
                       '6': 'Wearable computer (watch size)',
                       '7': 'Tablet'}
               },
               2: {
                   'major': 'Phone',
                   'minor': {
                       'bitwise': False,
                       '0': 'Uncategorized',
                       '1': 'Cellular',
                       '2': 'Cordless',
                       '3': 'Smartphone',
                       '4': 'Wired modem or voice gateway',
                       '5': 'Common ISDN access'
                   }
               },
               3: {
                   'major': 'LAN/Network Access Point',
                   'minor': {
                       'bitwise': False,
                       '0': 'Fully available',
                       '1': '1% to 17% utilized',
                       '2': '17% to 33% utilized',
                       '3': '33% to 50% utilized',
                       '4': '50% to 67% utilized',
                       '5': '67% to 83% utilized',
                       '6': '83% to 99% utilized',
                       '7': 'No service available'
                   }
               },
               4: {
                   'major': 'Audio/Video',
                   'minor': {
                       'bitwise': False,
                       '0': 'Uncategorized',
                       '1': 'Wearable Headset Device',
                       '2': 'Hands-free Device',
                       '3': '(Reserved)',
                       '4': 'Microphone',
                       '5': 'Loudspeaker',
                       '6': 'Headphones',
                       '7': 'Portable Audio',
                       '8': 'Car audio',
                       '9': 'Set-top box',
                       '10': 'HiFi Audio Device',
                       '11': 'VCR',
                       '12': 'Video Camera',
                       '13': 'Camcorder',
                       '14': 'Video Monitor',
                       '15': 'Video Display and Loudspeaker',
                       '16': 'Video Conferencing',
                       '17': '(Reserved)',
                       '18': 'Gaming/Toy'
                   }
               },
               5: {
                   'major': 'Peripheral',
                   'minor': {
                       'bitwise': False,
                       'feel': {
                           '0': 'Not Keyboard / Not Pointing Device',
                           '1': 'Keyboard',
                           '2': 'Pointing device',
                           '3': 'Combo keyboard/pointing device'
                       },
                       '0': 'Uncategorized',
                       '1': 'Joystick',
                       '2': 'Gamepad',
                       '3': 'Remote control',
                       '4': 'Sensing device',
                       '5': 'Digitizer tablet',
                       '6': 'Card Reader',
                       '7': 'Digital Pen',
                       '8': 'Handheld scanner for bar-codes, RFID, etc.',
                       '9': 'Handheld gestural input device'
                   }
               },
               6: {
                   'major': 'Imaging',
                   'minor': {
                       'bitwise': True,
                       '4': 'Display',
                       '8': 'Camera',
                       '16': 'Scanner',
                       '32': 'Printer'
                   }
               },
               7: {
                   'major': 'Wearable',
                   'minor': {
                       'bitwise': False,
                       '0': 'Wristwatch',
                       '1': 'Pager',
                       '2': 'Jacket',
                       '3': 'Helmet',
                       '4': 'Glasses'
                   }
               },
               8: {
                   'major': 'Toy',
                   'minor': {
                       'bitwise': False,
                       '0': 'Robot',
                       '1': 'Vehicle',
                       '2': 'Doll / Action figure',
                       '3': 'Controller',
                       '4': 'Game'
                   }
               },
               9: {
                   'major': 'Health',
                   'minor': {
                       'bitwise': False,
                       '0': 'Undefined',
                       '1': 'Blood Pressure Monitor',
                       '2': 'Thermometer',
                       '3': 'Weighing Scale',
                       '4': 'Glucose Meter',
                       '5': 'Pulse Oximeter',
                       '6': 'Heart/Pulse Rate Monitor',
                       '7': 'Health Data Display',
                       '8': 'Step Counter',
                       '9': 'Body Composition Analyzer',
                       '10': 'Peak Flow Monitor',
                       '11': 'Medication Monitor',
                       '12': 'Knee Prosthesis',
                       '13': 'Ankle Prosthesis',
                       '14': 'Generic Health Manager',
                       '15': 'Personal Mobility Device'
                   }
               }}

    major_number = (cod_decimal_string >> 8) & 0x1f
    minor_number = (cod_decimal_string >> 2) & 0x3f

    minor_class_name = None
    minor = {'minor': {}}
    if major_number == 31:
        major = {'major': 'Uncategorized'}
    else:
        major = classes.get(major_number, {'major': 'Reserved'})
        minor = classes.get(major_number, minor)

    minor_class = minor.get('minor', {})
    if minor_class.get('bitwise', False):
        # i.e. imaging
        for key, value in minor_class.items():
            try:
                # if key is an integer, it is good to be evaluated
                minor_key = int(key)
            except ValueError:
                continue
            except Exception as e:
                logger.exception(f"Failed to evaluate minor device class with key {key}: {e}")
                continue

            if minor_number & minor_key:
                minor_class_name = value
                break
    else:
        minor_class_name = minor_class.get(str(minor_number), 'reserved')

    major_class_name = major.get('major')

    peripheral_classes = [major_class_name, minor_class_name]

    if 'feel' in minor_class:
        feel_number = minor_number >> 4
        feel_class_name = minor_class['feel'].get(str(feel_number))
        if feel_class_name:
            peripheral_classes.append(feel_class_name)

    return peripheral_classes


async def bluetooth_manager():

    bluetooth_devices = []
    try:
        bluetooth_devices = device_discovery()
        logger.debug(f'Bluetooth devices: {bluetooth_devices}')
    except Exception as e:
        logger.error(f"Failed to discover BT devices: {e}")
        logger.debug("Exception", exc_info=e)

    ble_devices = {}
    try:
        ble_devices = await ble_device_discovery()
        logger.debug(f'BLE devices: {ble_devices}')
    except Exception as e:
        logger.error(f"Failed to discover BLE devices: {e}")
        error = str(e)
        if error.__contains__('DBus.Error'):
            logger.debug("Restarting bluetooth application because of DBus Error")
            os.execv(sys.executable, ['python'] + sys.argv)
        logger.debug("Exception", exc_info=e)

    if bluetooth_devices or ble_devices:
        logger.info(f'Found {len(bluetooth_devices)} Bluetooth devices and {len(ble_devices)} BLE devices')
    else:
        logger.info('No device found')

    bluetooth = compare_bluetooth(bluetooth_devices, ble_devices)
    output = ble_devices
    if len(bluetooth) > 0:
        for device in bluetooth:
            name = device.get("name", "unknown")
            output[device['identifier']] = {
                "available": True,
                "name": name,
                "classes": cod_converter(device.get("class", "")),
                "identifier": device.get("identifier"),
                "interface": device.get("interface", "Bluetooth"),
            }
    logger.info(f'Final Output {output}')
    return output


def main():
    parse_arguments_and_initialize_logging('Bluetooth Peripheral')

    logger.info('Starting bluetooth manager')

    bluetooth_peripheral: Peripheral = Peripheral(name='bluetooth', async_mode=True)

    bluetooth_peripheral.run(bluetooth_manager)


def entry():
    main()


if __name__ == "__main__":
    main()
