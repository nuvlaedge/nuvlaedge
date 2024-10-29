import json
import logging
from pathlib import Path
from pprint import pformat
from typing import Optional

from nuvla.api.models import CimiResource
from dataclasses import dataclass

from nuvla.api import Api as NuvlaApi
from requests import Response

from nuvlaedge.agent.common.util import get_irs, from_irs
from nuvlaedge.agent.nuvla.resources import (NuvlaID,
                                             NuvlaEdgeResource,
                                             NuvlaEdgeStatusResource,
                                             CredentialResource,
                                             InfrastructureServiceResource,
                                             AutoUpdateNuvlaEdgeTrackedResource,
                                             AutoNuvlaEdgeResource,
                                             AutoNuvlaEdgeStatusResource,
                                             AutoInfrastructureServiceResource,
                                             AutoCredentialResource)
from ..settings import NuvlaApiKeyTemplate, NuvlaEdgeSession
from nuvlaedge.common.constant_files import FILE_NAMES, LEGACY_FILES
from nuvlaedge.common.file_operations import read_file, write_file
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger

logger: logging.Logger = get_nuvlaedge_logger(__name__)


class SessionValidationError(Exception):
    """ An exception raised when the session structure is not as expected. """
    ...


@dataclass(frozen=True)
class NuvlaEndPoints:
    base_path: str = '/api/'
    session: str = base_path + 'session/'

    nuvlaedge: str = base_path + 'nuvlabox/'
    nuvlaedge_status: str = base_path + 'nuvlabox-status/'


def format_host(host: str) -> str:
    if host.startswith('https://') or host.startswith('http://'):
        return host

    return f'https://{host}'


class NuvlaClientWrapper:
    """
    Provides a wrapper around the Nuvla API client for interacting with NuvlaEdge resources.

    Attributes:
        MIN_SYNC_TIME (int): The minimum time interval for updating resources (default is 60 seconds)
        NUVLAEDGE_STATUS_REQUIRED_FIELDS (str):
        NUVLAEDGE_REQUIRED_FIELDS (str):
        VPN_CREDENTIAL_FILTER (str): template used to search for the VPN credential within the NuvlaEdge associated
         credentials

        _host (str): The hostname of the Nuvla API server
        _insecure (bool): Whether to verify the SSL certificate of the Nuvla API server
        _nuvlaedge_uuid (NuvlaID): The ID of the NuvlaEdge resource

        _resources (dict[str, any]): A dictionary containing the NuvlaEdge resources handled by the client

        nuvlaedge_client (NuvlaApi): The Nuvla API client for interacting with NuvlaEdge resources

        _headers (dict): HTTP headers to be sent with requests

        nuvlaedge_credentials (NuvlaApiKeyTemplate | None): The API keys for authenticating with NuvlaEdge

        _nuvlaedge_status_uuid (NuvlaID | None): The ID of the NuvlaEdge status resource

    """
    MIN_SYNC_TIME: int = 60  # Resource min update time
    FULL_RESOURCE_SYNC_TIME: int = 60*15  # Synchronise the whole resource from Nuvla to prevent errors

    NUVLAEDGE_STATUS_REQUIRED_FIELDS: set = {'node-id'}
    NUVLAEDGE_REQUIRED_FIELDS: set = {'id',
                                      'state',
                                      'host-level-management-api-key',
                                      'nuvlabox-status',
                                      'refresh-interval',
                                      'heartbeat-interval'
                                      'infrastructure-service-group',
                                      'credential-api-key',
                                      'ssh-keys',
                                      'vpn-server-id'}

    VPN_CREDENTIAL_FILTER: str = ('method="create-credential-vpn-nuvlabox" and '
                                  'vpn-common-name="{nuvlaedge_uuid}" and '
                                  'parent="{vpn_server_id}"')

    def __init__(self, host: str, insecure: bool, nuvlaedge_uuid: NuvlaID):
        """
        Initialize the NuvlaEdgeClient object with the provided parameters.

        Args:
            host (str): The host URL of the NuvlaEdge instance.
            insecure (bool): Indicates whether to verify the SSL certificate of the host.
            nuvlaedge_uuid (NuvlaID): The UUID of the NuvlaEdge instance.

        """
        self._host: str = format_host(host)
        self._insecure: bool = insecure

        # Dictionary containing the NuvlaEdge resources handled by the client
        # nuvlaedge, nuvlaedge-status, vpn-credential, vpn-server
        self._resources: dict[str, any] = {}

        # Create a different session for each type of resource handled by NuvlaEdge. e.g: nuvlabox, job, deployment
        self.nuvlaedge_client: NuvlaApi = NuvlaApi(endpoint=self._host,
                                                   insecure=insecure,
                                                   reauthenticate=True,
                                                   compress=True)

        self._headers: dict = {}
        self.irs: str | None = None
        self.nuvlaedge_credentials: NuvlaApiKeyTemplate | None = None

        self._nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid
        self._nuvlaedge_status_uuid: NuvlaID | None = None

    def set_nuvlaedge_uuid(self, uuid: NuvlaID):
        self._nuvlaedge_uuid = uuid

    @property
    def nuvlaedge_uuid(self) -> NuvlaID:
        return self._nuvlaedge_uuid

    @property
    def host(self) -> str:
        return self._host

    @property
    def endpoint(self) -> str:
        return self._host

    @property
    def nuvlaedge_status_uuid(self) -> NuvlaID:
        """
        Property for the UUID of the NuvlaEdge status.

        This property retrieves the 'nuvlaedge_status_uuid' in a lazy-loading manner. If the
        'nuvlaedge_status_uuid' is not yet initialized (i.e., None), it fills the value by accessing
        the 'nuvlabox_status' from the 'nuvlaedge' object and assigns it to '_nuvlaedge_status_uuid'.

        Returns:
            NuvlaID: The UUID of the NuvlaEdge status.
        """
        if not self._nuvlaedge_status_uuid:
            self._nuvlaedge_status_uuid = self.nuvlaedge.nuvlabox_status
        return self._nuvlaedge_status_uuid

    @property
    def nuvlaedge(self) -> NuvlaEdgeResource:
        """
        NuvlaEdge property that synchronizes with the NuvlaEdgeResource at a minimum specified interval.

        This property returns the current NuvlaEdgeResource instance. If the time elapsed since
        the last synchronization is longer than the minimum sync time, it triggers a new
        synchronization before returning the instance.

        Returns:
            NuvlaEdgeResource: The current NuvlaEdgeResource instance.
        """
        _res_name = 'nuvlaedge'
        if not self._is_resource_available(_res_name):
            self._init_resource(_res_name, AutoNuvlaEdgeResource, self._nuvlaedge_uuid)
        return self._resources.get(_res_name)

    @property
    def nuvlaedge_status(self) -> NuvlaEdgeStatusResource:
        _res_name = 'nuvlaedge-status'
        if not self._is_resource_available(_res_name):
            self._init_resource(_res_name, AutoNuvlaEdgeStatusResource, self.nuvlaedge_status_uuid)
        return self._resources.get(_res_name)

    @property
    def vpn_credential(self) -> CredentialResource | None:
        if self.nuvlaedge.vpn_server_id is None:
            # This is a safety check. VPN server resource should only be requested if the NuvlaEdge has a VPN server
            logger.warning(f"VPN server not found in NuvlaEdge {self.nuvlaedge_uuid}. This point should not be reached")
            return None

        _res_name = 'vpn-credential'
        if not self._is_resource_available(_res_name):
            self._init_resource(_res_name, AutoCredentialResource, NuvlaID(''),
                                nuvlaedge_id=self._nuvlaedge_uuid,
                                vpn_server_id=self.nuvlaedge.vpn_server_id)

        return self._resources.get(_res_name)

    @property
    def vpn_server(self) -> InfrastructureServiceResource | None:
        if self.nuvlaedge.vpn_server_id is None:
            # This is a safety check. VPN server resource should only be requested if the NuvlaEdge has a VPN server
            logger.warning(f"VPN server not found in NuvlaEdge {self.nuvlaedge_uuid}. This point should not be reached")
            return None

        _res_name = 'vpn-server'
        if not self._is_resource_available(_res_name):
            self._init_resource(_res_name, AutoInfrastructureServiceResource, self.nuvlaedge.vpn_server_id)
        return self._resources.get(_res_name)

    def _is_resource_available(self, res_name: str) -> bool:
        return res_name in self._resources and self._resources.get(res_name) is not None

    def _init_resource(self,
                       res_name: str,
                       res_type: type[AutoUpdateNuvlaEdgeTrackedResource],
                       res_id: NuvlaID,
                       **kwargs):
        logger.debug(f"Initializing resource {res_name} with id {res_id}{kwargs}")
        self._resources[res_name] = res_type(nuvla_client=self.nuvlaedge_client,
                                             resource_id=res_id,
                                             **kwargs)
        self._resources[res_name].force_update()

    def login_nuvlaedge(self) -> bool:
        key, secret = from_irs(self.nuvlaedge_uuid, self.irs)
        login_response: Response = self.nuvlaedge_client.login_apikey(key, secret)

        if login_response.status_code in [200, 201]:
            logger.debug("Log in successful")
            return True
        else:
            logger.warning(f"Error logging in: {login_response}")
            return False

    def activate(self):
        """ Activates the NuvlaEdge, saves the returned api-keys and logs in.
        If we already have api-keys, logs in.
        This method will raise any exception should anything fail. This is a compulsory step for the NuvlaEdge without
         which the system cannot work.

        """
        logger.info("Activating NuvlaEdge...")
        credentials = self.nuvlaedge_client._cimi_post(f'{self.nuvlaedge_uuid}/activate')
        self.irs = get_irs(self.nuvlaedge_uuid, credentials['api-key'], credentials['secret-key'])
        logger.info(f'Activation successful, received credential ID: {credentials["api-key"]}, logging in')

        self.save_current_state_to_file()
        # Then log in to access NuvlaEdge resources
        if not self.login_nuvlaedge():
            logger.warning("Could not log in after activation. NuvlaEdge will not work properly.")

        # Finally, force update the NuvlaEdge resource to get the latest state
        self.nuvlaedge.force_update()

    def commission(self, payload: dict):
        """ Executes nuvlaedge resource commissioning operation in the Nuvla endpoint

        Args:
            payload (dict): content of the commissioning operation

        Returns: a dictionary the response of the server to the commissioning operation

        """
        logger.debug(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid} with payload \n{json.dumps(payload, indent=4)}...")
        try:
            response: dict = self.nuvlaedge_client._cimi_post(resource_id=f"{self.nuvlaedge_uuid}/commission",
                                                              json=payload)
            logger.debug(f"Commissioning response: {response}")
            if response:
                self.nuvlaedge.force_update()
            else:
                logger.warning(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid} with Payload {payload}... Failed")
            return response
        except Exception as e:
            logger.warning(f"Error commissioning NuvlaEdge with Payload {payload}: {e}")

    def heartbeat(self) -> dict:
        """ Executes nuvlaedge resource heartbeat operation in the Nuvla endpoint

        Returns: a CimiResponse instance with the response of the server which includes any possible
            jobs queued for this NuvlaEdge

        """
        try:
            response: dict = self.nuvlaedge_client._cimi_post(f"{self.nuvlaedge_uuid}/heartbeat")
            return response
        except Exception as e:
            logger.warning(f"Heartbeat to {self.nuvlaedge_uuid} failed with error: {e}")

    def telemetry(self, new_status: dict, attributes_to_delete: list[str]) -> dict:
        """ Sends telemetry metrics to the nuvlaedge-status resource using edit(put) operation

        Args:
            new_status: metrics that have changed from the last telemetry
            attributes_to_delete: attributes no longer present in the metrics

        Returns: a dict with the data of the response of the server including jobs queued for this NuvlaEdge

        """
        logger.debug(f"Sending telemetry data to Nuvla: \n"
                     f"Changed fields: {new_status}\n"
                     f"Deleted fields: {attributes_to_delete}")
        response: CimiResource = self.nuvlaedge_client.edit(self.nuvlaedge_status_uuid,
                                                            data=new_status,
                                                            select=attributes_to_delete)
        logger.debug(f"Response received from telemetry report: {response.data}")
        return response.data

    def telemetry_patch(self, telemetry_jsonpatch: list, attributes_to_delete: list[str]) -> dict:
        """Sends telemetry metrics to the nuvlaedge-status resource.

        Args:
            telemetry_jsonpatch: telemetry data in JSON Patch format
            attributes_to_delete: attributes no longer present in the metrics

        Returns: a dict with the data of the response of the server including
                 jobs queued for this NuvlaEdge
        """
        self._log_debug_telemetry_jsonpatch(telemetry_jsonpatch,
                                            attributes_to_delete)

        response: CimiResource = self.nuvlaedge_client.edit_patch(
            self.nuvlaedge_status_uuid,
            data=telemetry_jsonpatch,
            select=attributes_to_delete)
        logger.debug("Response received from telemetry patch report: %s",
                     response.data)
        return response.data

    @staticmethod
    def _log_debug_telemetry_jsonpatch(telemetry_jsonpatch: list,
                                       attributes_to_delete: list[str]):
        logger.debug("Sending telemetry patch data to Nuvla: \n %s",
                     telemetry_jsonpatch)
        logger.debug("Attributes no longer present in the metrics: \n %s",
                     attributes_to_delete)

        if logger.level == logging.DEBUG and len(telemetry_jsonpatch) > 0 and \
                'op' in telemetry_jsonpatch[0] and 'path' in telemetry_jsonpatch[0]:
            ops_paths = [(x['op'], x['path'])
                         for x in sorted(telemetry_jsonpatch,
                                         key=lambda x: (x['op'], x['path']))]
            logger.debug('Telemetry patch data ops and paths:\n%s',
                         pformat(ops_paths))
            logger.debug("Telemetry patch data size: %s",
                         len(bytes(json.dumps(telemetry_jsonpatch), 'utf-8')))

    def save_current_state_to_file(self):
        """ Saves the current state of the NuvlaEdge client to a file.

        This method serializes the current state of the NuvlaEdge client, including the host, SSL verification setting,
        NuvlaEdge credentials, and NuvlaEdge UUIDs, into a NuvlaEdgeSession object. The serialized session is then written
        to a file for future use.

        The file used to store the session is defined by the FILE_NAMES.NUVLAEDGE_SESSION constant.

        Raises:
            Any exceptions raised by the `write_file` function will be propagated up.

        """
        serial_session = NuvlaEdgeSession(
            irs=self.irs,
            endpoint=self._host,
            insecure=self._insecure,
            credentials=self.nuvlaedge_credentials,
            nuvlaedge_uuid=self.nuvlaedge_uuid,
            nuvlaedge_status_uuid=self._nuvlaedge_status_uuid
        )

        write_file(serial_session, FILE_NAMES.NUVLAEDGE_SESSION)

        # To provide support for legacy (<2.14) NuvlaEdge agents, we also save the session to the legacy location,
        # both .activated and .context files
        if Path(LEGACY_FILES.ACTIVATION_FLAG.parent).exists() and self.nuvlaedge_credentials:
            legacy_credentials = {"api-key": self.nuvlaedge_credentials.key,
                                  "secret-key": self.nuvlaedge_credentials.secret}
            write_file(legacy_credentials, LEGACY_FILES.ACTIVATION_FLAG)
        if Path(LEGACY_FILES.CONTEXT.parent).exists():
            legacy_context = {"id": self.nuvlaedge_uuid}
            write_file(legacy_context, LEGACY_FILES.CONTEXT)

    def find_nuvlaedge_id_from_nuvla_session(self) -> Optional[NuvlaID]:
        try:
            nuvlaedge_id = self.nuvlaedge_client.get(self.nuvlaedge_client.current_session()).data['identifier']
            self._nuvlaedge_uuid = nuvlaedge_id
            return NuvlaID(nuvlaedge_id)
        except Exception as e:
            logger.warning(f"Could not find id with with error: {e}")
            return None

    # TODO: Used only by security module. Switch it to settings.py/_create_client_from_settings()
    @classmethod
    def from_session_store(cls, file: Path | str):
        """ Creates a NuvlaEdgeClient object from a saved session file

        Args:
            file: path to saved session file

        Returns:
            NuvlaEdgeClient object

        """
        _stored_session = None
        try:
            _stored_session = read_file(file, decode_json=True)
            session: NuvlaEdgeSession = NuvlaEdgeSession.model_validate(_stored_session)
        except Exception as ex:
            logger.warning(f'Could not validate session \n{_stored_session} \nwith error : {ex}')
            raise SessionValidationError(f'Could not validate session \n{_stored_session} \nwith error : {ex}')

        _client = cls(host=session.endpoint, insecure=session.insecure, nuvlaedge_uuid=session.nuvlaedge_uuid)
        _client.irs = session.irs
        _client.nuvlaedge_credentials = session.credentials

        # Compute IRS from credentials
        if session.credentials and not session.irs:
            _client.irs = get_irs(session.nuvlaedge_uuid, session.credentials.key, session.credentials.secret)
            _client.save_current_state_to_file()

        _client.login_nuvlaedge()

        # If uuid is none in session, retrieve it from the API
        if not _client.nuvlaedge_uuid and _client.nuvlaedge_credentials is not None:
            logger.info("NuvlaEdge UUID not found in session, retrieving from API...")
            _client._nuvlaedge_uuid = _client.find_nuvlaedge_id_from_nuvla_session()
            logger.info(f"NuvlaEdge UUID not found in session, retrieving from API... {_client._nuvlaedge_uuid}")
            if _client.nuvlaedge_uuid:
                _client.irs = get_irs(_client.nuvlaedge_uuid, session.credentials.key, session.credentials.secret)
                _client.save_current_state_to_file()

        return _client
