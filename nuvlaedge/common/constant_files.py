import logging
import os
from pathlib import Path


class FileConstants(object):
    HOST_USER_HOME = '.host_user_home'
    NUVLAEDGE_NUVLA_CONFIGURATION = '.nuvla-configuration'
    ACTIVATION_FLAG = '.activated'
    COMMISSIONING_FILE = '.commission'
    STATUS_FILE = '.status'
    STATUS_NOTES = '.status_notes'
    NUVLAEDGE_STATUS_FILE = '.nuvlabox-status'
    IP_FILE = '.ip'
    IP_GEOLOCATION_FILE = '.ipgeolocation'
    VULNERABILITIES_FILE = 'vulnerabilities'
    CA = 'ca.pem'
    CERT = 'cert.pem'
    KEY = 'key.pem'
    CONTEXT = '.context'
    PREVIOUS_NET_STATS_FILE = '.previous_net_stats'
    CONTAINER_STATS_JSON_FILE = 'docker_stats.json'

    # VPN
    VPN_FOLDER = 'vpn/'
    VPN_IP_FILE = 'vpn/ip'
    VPN_CREDENTIAL = 'vpn/vpn-credential'
    VPN_CLIENT_CONF_FILE = 'vpn/nuvlaedge.conf'

    # Peripherals
    PERIPHERALS_FOLDER = '.peripherals/'
    LOCAL_PERIPHERAL_DB = PERIPHERALS_FOLDER + 'local_peripherals.json'
    NETWORK_PERIPHERAL = PERIPHERALS_FOLDER + 'network'
    BLUETOOTH_PERIPHERAL = PERIPHERALS_FOLDER + 'bluetooth'
    MODBUS_PERIPHERAL = PERIPHERALS_FOLDER + 'modbus'
    GPU_PERIPHERAL = PERIPHERALS_FOLDER + 'gpu'

    @property
    def root_fs(self):
        return self._root_fs

    def __init__(self, root_fs: str):
        self._root_fs: str = root_fs

    def __getattribute__(self, item) -> Path:
        if item in ['_root_fs', 'root_fs']:
            return Path(object.__getattribute__(self, item))

        return Path(f'{self._root_fs}/{object.__getattribute__(self, item)}')


FILE_NAMES = FileConstants(os.getenv('SHARED_DATA_VOLUME', '/srv/nuvlaedge/shared/'))
