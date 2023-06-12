# -*- coding: utf-8 -*-

""" NuvlaEdge Common

List of common attributes for all classes
"""

import json
import logging
import os
import string

from subprocess import PIPE, Popen
from nuvla.api import Api
from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.common import util
from nuvlaedge.agent.orchestrator import ContainerRuntimeClient


class NuvlaEdgeCommon:
    """
    Common set of methods and variables for the NuvlaEdge agent
    """

    docker_socket_file = '/var/run/docker.sock'
    nuvla_endpoint_key = 'NUVLA_ENDPOINT'
    nuvla_endpoint_insecure_key = 'NUVLA_ENDPOINT_INSECURE'
    nuvla_timestamp_format = "%Y-%m-%dT%H:%M:%SZ"

    ssh_pub_key = os.getenv('NUVLAEDGE_IMMUTABLE_SSH_PUB_KEY')
    vpn_interface_name = os.getenv('VPN_INTERFACE_NAME', 'tun')

    swarm_manager_token_file = "swarm-manager-token"
    swarm_worker_token_file = "swarm-worker-token"

    mqtt_broker_port = 1883
    mqtt_broker_keep_alive = 90

    def __init__(self, container_runtime: ContainerRuntimeClient,
                 shared_data_volume: str = "/srv/nuvlaedge/shared"):
        """
        Constructs an Infrastructure object, with a status placeholder

        :param shared_data_volume: shared volume target path
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.hostfs = container_runtime.hostfs
        self.data_volume = shared_data_volume
        self.container_runtime: ContainerRuntimeClient = container_runtime

        self.mqtt_broker_host = self.container_runtime.data_gateway_name

        self.host_user_home_file = f'{self.data_volume}/.host_user_home'
        self.installation_home = self.set_installation_home(FILE_NAMES.HOST_USER_HOME)

        self.nuvlaedge_nuvla_configuration = f'{self.data_volume}/.nuvla-configuration'
        self.nuvla_endpoint, self.nuvla_endpoint_insecure = self.set_nuvla_endpoint()
        # Also store the Nuvla connection details for future restarts
        conf = f"{self.nuvla_endpoint_key}={self.nuvla_endpoint}\n" \
               f"{self.nuvla_endpoint_insecure_key}={str(self.nuvla_endpoint_insecure)}"
        self.save_nuvla_configuration(FILE_NAMES.NUVLAEDGE_NUVLA_CONFIGURATION, conf)

        self.activation_flag = "{}/.activated".format(self.data_volume)
        self.nuvlaedge_status_file = "{}/.nuvlabox-status".format(self.data_volume)

        self.ip_geolocation_file = "{}/.ipgeolocation".format(self.data_volume)
        self.vulnerabilities_file = "{}/vulnerabilities".format(self.data_volume)
        self.previous_net_stats_file = f"{self.data_volume}/.previous_net_stats"

        self.vpn_folder = "{}/vpn".format(self.data_volume)
        if not os.path.isdir(self.vpn_folder):
            os.makedirs(self.vpn_folder)

        self.vpn_ip_file = "{}/ip".format(self.vpn_folder)
        self.vpn_credential = "{}/vpn-credential".format(self.vpn_folder)
        self.vpn_client_conf_file = "{}/nuvlaedge.conf".format(self.vpn_folder)
        self.vpn_key_file = f'{self.vpn_folder}/nuvlaedge-vpn.key'
        self.vpn_csr_file = f'{self.vpn_folder}/nuvlaedge-vpn.csr'
        self.vpn_config_extra = self.set_vpn_config_extra()

        self.peripherals_dir = "{}/.peripherals".format(self.data_volume)

        self.swarm_node_cert = f"{self.hostfs}/var/lib/docker/swarm/certificates/swarm-node.crt"

        self.nuvlaedge_id = self.set_nuvlaedge_id()

        self.container_stats_json_file = f"{self.data_volume}/docker_stats.json"

    def set_vpn_config_extra(self) -> str:
        """
        If env var VPN_CONFIG_EXTRA is set, update vpn configuration.
        If not set, use the saved value from the shared volume.

        :return: extra config as a string
        """
        extra_config_file = f'{FILE_NAMES.VPN_FOLDER}/.extra_config'

        extra_config = os.getenv('VPN_CONFIG_EXTRA')
        if extra_config is not None:
            extra_config = extra_config.replace(r'\n', '\n')
            try:
                util.atomic_write(extra_config_file, extra_config)
            except OSError:
                self.logger.exception('Failed to write VPN extra config file')
            return extra_config

        try:
            with open(extra_config_file) as f:
                return f.read()
        except FileNotFoundError:
            pass
        except OSError:
            self.logger.exception('Failed to read VPN extra config file')

        return ''

    @staticmethod
    def set_installation_home(host_user_home_file: str) -> str:
        """
        Finds the path for the HOME dir used during installation

        :param host_user_home_file: location of the file where the previous installation home value was saved
        :return: installation home path
        """
        if os.path.exists(host_user_home_file):
            with open(host_user_home_file) as userhome:
                return userhome.read().strip()
        else:
            return os.environ.get('HOST_HOME')

    def set_nuvla_endpoint(self) -> tuple:
        """
        Defines the Nuvla endpoint based on the environment

        :return: clean Nuvla endpoint and whether it is insecure or not -> (str, bool)
        """
        nuvla_endpoint_raw = os.environ["NUVLA_ENDPOINT"] if "NUVLA_ENDPOINT" in os.environ else "nuvla.io"
        nuvla_endpoint_insecure_raw = os.environ[
            "NUVLA_ENDPOINT_INSECURE"] if "NUVLA_ENDPOINT_INSECURE" in os.environ else False
        try:
            with open(FILE_NAMES.NUVLAEDGE_NUVLA_CONFIGURATION) as nuvla_conf:
                local_nuvla_conf = nuvla_conf.read().split()

            nuvla_endpoint_line = list(filter(lambda x: x.startswith(self.nuvla_endpoint_key), local_nuvla_conf))
            if nuvla_endpoint_line:
                nuvla_endpoint_raw = nuvla_endpoint_line[0].split('=')[-1]

            nuvla_endpoint_insecure_line = list(filter(lambda x: x.startswith(self.nuvla_endpoint_insecure_key),
                                                       local_nuvla_conf))
            if nuvla_endpoint_insecure_line:
                nuvla_endpoint_insecure_raw = nuvla_endpoint_insecure_line[0].split('=')[-1]
        except FileNotFoundError:
            self.logger.debug(
                'Local Nuvla configuration does not exist yet - first time running the NuvlaEdge Engine...')
        except IndexError as e:
            self.logger.debug(
                f'Unable to read Nuvla configuration from {FILE_NAMES.NUVLAEDGE_NUVLA_CONFIGURATION}: {str(e)}')

        while nuvla_endpoint_raw[-1] == "/":
            nuvla_endpoint_raw = nuvla_endpoint_raw[:-1]

        if isinstance(nuvla_endpoint_insecure_raw, str):
            if nuvla_endpoint_insecure_raw.lower() == "false":
                nuvla_endpoint_insecure_raw = False
            else:
                nuvla_endpoint_insecure_raw = True
        else:
            nuvla_endpoint_insecure_raw = bool(nuvla_endpoint_insecure_raw)

        return nuvla_endpoint_raw.replace("https://", ""), nuvla_endpoint_insecure_raw

    @staticmethod
    def save_nuvla_configuration(file_path, content):
        if not os.path.exists(file_path):
            util.atomic_write(file_path, content)

    def _get_nuvlaedge_id_from_environment(self):
        nuvlaedge_id = os.getenv('NUVLAEDGE_UUID', os.getenv('NUVLABOX_UUID'))
        if not nuvlaedge_id:
            self.logger.info('NuvlaEdge uuid not available as environment variable')
        else:
            self.logger.info('NuvlaEdge uuid found in environment variables')
        return nuvlaedge_id

    def _get_nuvlaedge_id_from_api_session(self):
        nuvlaedge_id = None
        error_msg = 'Failed to get NuvlaEdge uuid from api session'
        try:
            api = self.api()
            nuvlaedge_id = api.get(api.current_session()).data['identifier']
        except Exception as e:
            self.logger.error(f'{error_msg}: {e}')
        else:
            if nuvlaedge_id:
                self.logger.info('NuvlaEdge uuid found in api session')
            else:
                self.logger.error(error_msg)
        return nuvlaedge_id

    def _get_nuvlaedge_id_from_context_file(self):
        nuvlaedge_id = None
        try:
            with FILE_NAMES.CONTEXT.open('r') as file:
                nuvlaedge_id = json.load(file)['id']
        except Exception as e:
            self.logger.error(f'Failed to read NuvlaEdge uuid from context file '
                              f'{FILE_NAMES.CONTEXT}: {str(e)}')
        else:
            if nuvlaedge_id:
                self.logger.info('NuvlaEdge uuid found in context file')
            else:
                self.logger.error('Failed to get NuvlaEdge uuid from context file')
        return nuvlaedge_id

    def set_nuvlaedge_id(self) -> str:
        """
        Discovers the NuvlaEdge ID either from a previous run or from env or alternatively from the API session

        :return: clean NuvlaEdge ID as a str
        """

        def get_uuid(href):
            return href.split('/')[-1] if href else href

        env_nuvlaedge_id = self._get_nuvlaedge_id_from_environment()
        session_nuvlaedge_id = self._get_nuvlaedge_id_from_api_session()
        context_nuvlaedge_id = self._get_nuvlaedge_id_from_context_file()

        if (context_nuvlaedge_id and env_nuvlaedge_id
                and get_uuid(context_nuvlaedge_id) != get_uuid(env_nuvlaedge_id)):
            raise RuntimeError(f'You are trying to install a new NuvlaEdge {env_nuvlaedge_id} even though a '
                               f'previous NuvlaEdge installation ({context_nuvlaedge_id}) still exists in the system! '
                               f'You can either delete the previous installation (removing all data volumes) or '
                               f'fix the NUVLAEDGE_UUID environment variable to match the old {context_nuvlaedge_id}')

        if (context_nuvlaedge_id and session_nuvlaedge_id
                and get_uuid(context_nuvlaedge_id) != get_uuid(session_nuvlaedge_id)):
            self.logger.warning(f'NuvlaEdge from context file ({context_nuvlaedge_id}) '
                                f'do not match session identifier ({session_nuvlaedge_id})')

        if (env_nuvlaedge_id and session_nuvlaedge_id
                and get_uuid(env_nuvlaedge_id) != get_uuid(session_nuvlaedge_id)):
            self.logger.warning(f'NuvlaEdge from environment variable ({env_nuvlaedge_id}) '
                                f'do not match session identifier ({session_nuvlaedge_id})')

        if context_nuvlaedge_id:
            self.logger.info(f'Using NuvlaEdge uuid from context file: {context_nuvlaedge_id}')
            nuvlaedge_id = context_nuvlaedge_id
        elif env_nuvlaedge_id:
            self.logger.info(f'Using NuvlaEdge uuid from environment variable: {env_nuvlaedge_id}')
            nuvlaedge_id = env_nuvlaedge_id
        elif session_nuvlaedge_id:
            self.logger.info(f'Using NuvlaEdge uuid from api session: {session_nuvlaedge_id}')
            nuvlaedge_id = session_nuvlaedge_id
        else:
            raise RuntimeError('NUVLAEDGE_UUID not provided')

        if not nuvlaedge_id.startswith("nuvlaedge/") and not nuvlaedge_id.startswith("nuvlabox/"):
            nuvlaedge_id = 'nuvlabox/{}'.format(nuvlaedge_id)

        return nuvlaedge_id

    @staticmethod
    def get_api_keys():
        nuvlaedge_api_key = os.environ.get("NUVLAEDGE_API_KEY")
        nuvlaedge_api_secret = os.environ.get("NUVLAEDGE_API_SECRET")
        if nuvlaedge_api_key:
            del os.environ["NUVLAEDGE_API_KEY"]
        if nuvlaedge_api_secret:
            del os.environ["NUVLAEDGE_API_SECRET"]

        return nuvlaedge_api_key, nuvlaedge_api_secret

    def api(self):
        """ Returns an Api object """

        return Api(endpoint='https://{}'.format(self.nuvla_endpoint),
                   insecure=self.nuvla_endpoint_insecure, reauthenticate=True, compress=True)

    def push_event(self, data):
        """
        Push an event resource to Nuvla

        :param data: JSON payload
        :return:
        """

        try:
            self.api().add('event', data)
        except Exception as e:
            self.logger.error(f'Unable to push event to Nuvla: {data}. Reason: {str(e)}')

    def authenticate(self, api_instance, api_key, secret_key):
        """ Creates a user session """

        self.logger.info('Authenticate with "{}"'.format(api_key))
        self.logger.info(api_instance.login_apikey(api_key, secret_key))

        return api_instance

    @staticmethod
    def shell_execute(cmd):
        """ Shell wrapper to execute a command

        :param cmd: command to execute
        :return: all outputs
        """

        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        return {'stdout': stdout, 'stderr': stderr, 'returncode': p.returncode}

    def write_json_to_file(self, file_path: str, content: dict, mode: str = 'w') -> bool:
        """
        Write JSON content into a file

        :param file_path: path of the file to be written
        :param content: JSON content
        :param mode: mode in which to open the file for writing
        :return: True if file was written with success. False otherwise
        """
        try:
            util.atomic_write(file_path, json.dumps(content), mode=mode)
        except Exception as e:
            self.logger.exception(f'Exception in write_json_to_file: {e}')
            return False

        return True

    @staticmethod
    def read_json_file(file_path: str) -> dict:
        """
        Reads a JSON file. Error should be caught by the calling module

        :param file_path: path of the file to be read
        :return: content of the file, as a dict
        """
        with open(file_path) as f:
            return json.load(f)



    def get_operational_status(self):
        """ Retrieves the operational status of the NuvlaEdge from the .status file """

        try:
            with FILE_NAMES.STATUS_FILE.open('r') as file:
                operational_status = file.readlines()[0].replace('\n', '').upper()
        except FileNotFoundError:
            self.logger.warning("Operational status could not be found")
            operational_status = "UNKNOWN"
        except IndexError:
            self.logger.warning("Operational status has not been correctly set")
            operational_status = "UNKNOWN"
            self.set_local_operational_status(operational_status)

        return operational_status

    def get_operational_status_notes(self) -> list:
        """
        Retrieves the operational status notes of the NuvlaEdge from the .status_notes
        file
        """

        notes = []
        try:
            with FILE_NAMES.STATUS_NOTES.open('r') as file:
                notes = file.read().splitlines()
        except Exception as e:
            self.logger.warning(f"Error while reading operational status notes: {str(e)}")

        return notes

    @staticmethod
    def set_local_operational_status(operational_status):
        """ Write the operational status into the .status file

        :param operational_status: status of the NuvlaEdge
        """
        util.atomic_write(FILE_NAMES.STATUS_FILE, operational_status)

    @staticmethod
    def write_vpn_conf(values):
        """ Write VPN configuration into a file

        :param values: map of values for the VPN conf template
        """
        tpl = string.Template("""client

dev ${vpn_interface_name}
dev-type tun
nobind

# Certificate Configuration
# CA certificate
<ca>
${vpn_ca_certificate}
${vpn_intermediate_ca_is}
${vpn_intermediate_ca}
</ca>

# Client Certificate
<cert>
${vpn_certificate}
</cert>

# Client Key
<key>
${nuvlaedge_vpn_key}
</key>

# Shared key
<tls-crypt>
${vpn_shared_key}
</tls-crypt>

remote-cert-tls server

verify-x509-name "${vpn_common_name_prefix}" name-prefix

script-security 2
up /opt/nuvlaedge/scripts/vpn-client/get_ip.sh

auth-nocache
auth-retry nointeract

ping 60
ping-restart 120
compress lz4

${vpn_endpoints_mapped}

${vpn_extra_config}
""")

        util.atomic_write(FILE_NAMES.VPN_CLIENT_CONF_FILE, tpl.substitute(values))
