import logging
import os
from pathlib import Path


class BaseFileConstants(object):
    @property
    def root_fs(self) -> Path:
        return self._root_fs

    def __init__(self, root_fs: str):
        self._root_fs: str = root_fs

    def __getattribute__(self, item) -> Path:
        if item in ['_root_fs', 'root_fs']:
            return Path(object.__getattribute__(self, item))

        return Path(f'{self._root_fs}/{object.__getattribute__(self, item)}')


class LegacyFileConstants(BaseFileConstants):
    # Legacy file locations
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
    VPN_IP_FILE = VPN_FOLDER + 'ip'
    VPN_CLIENT_CONF_FILE = VPN_FOLDER + 'nuvlaedge.conf'
    VPN_CREDENTIAL = VPN_FOLDER + 'vpn-credential'
    VPN_CSR_FILE = VPN_FOLDER + 'nuvlaedge-vpn.csr'
    VPN_KEY_FILE = VPN_FOLDER + 'nuvlaedge-vpn.key'


class FileConstants(BaseFileConstants):

    def __init__(self, root_fs: str):
        super().__init__(root_fs)
        if not self.root_fs.exists() and not bool(os.getenv('TOX_TESTENV', False)):
            self.root_fs.mkdir()

    # Basic file locations
    NUVLAEDGE_SESSION = 'nuvlaedge_session.json'
    NUVLAEDGE_COMMISSION_DATA = 'commission.json'
    TELEMETRY_DATA = 'telemetry.json'

    # Monitoring utils
    PREVIOUS_NET_STATS_FILE = '.previous_net_stats'
    HOST_USER_HOME = '.host_user_home'
    VULNERABILITIES_FILE = 'vulnerabilities'

    # Keep track of the last commissioned data
    COMMISSIONING_FILE = 'commission_data.json'
    CA = 'ca.pem'
    CERT = 'cert.pem'
    KEY = 'key.pem'

    # VPN
    VPN_FOLDER = 'vpn/'
    VPN_IP_FILE = VPN_FOLDER + 'ip'
    VPN_CLIENT_CONF_FILE = VPN_FOLDER + 'nuvlaedge.conf'
    VPN_CREDENTIAL = VPN_FOLDER + 'vpn-credential.json'
    VPN_HANDLER_CONF = VPN_FOLDER + 'client-vpn-conf.json'
    VPN_SERVER_FILE = VPN_FOLDER + 'vpn-server.json'
    VPN_CSR_FILE = VPN_FOLDER + 'nuvlaedge-vpn.csr'
    VPN_KEY_FILE = VPN_FOLDER + 'nuvlaedge-vpn.key'

    # Peripherals
    PERIPHERALS_FOLDER = '.peripherals/'
    LOCAL_PERIPHERAL_DB = PERIPHERALS_FOLDER + 'local_peripherals.json'
    NETWORK_PERIPHERAL = PERIPHERALS_FOLDER + 'network'
    BLUETOOTH_PERIPHERAL = PERIPHERALS_FOLDER + 'bluetooth'
    MODBUS_PERIPHERAL = PERIPHERALS_FOLDER + 'modbus'
    GPU_PERIPHERAL = PERIPHERALS_FOLDER + 'gpu'

    # System manager status and status notes report
    STATUS_FILE = '.status'
    STATUS_NOTES = '.status_notes'


# Nuvlaedge configuration
FILE_NAMES = FileConstants(os.getenv('SHARED_DATA_VOLUME', '/var/lib/nuvlaedge/'))
LEGACY_FILES = LegacyFileConstants(os.getenv('OLD_SHARED_DATA_VOLUME', '/srv/nuvlaedge/shared/'))
