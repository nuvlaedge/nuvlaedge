import json
import logging
import time
from pathlib import Path

from nuvla.api.models import CimiResponse, CimiCollection, CimiResource
from pydantic import BaseModel
from dataclasses import dataclass

from nuvla.api import Api as NuvlaApi
from requests import Response

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.nuvla.resources import (NuvlaID,
                                             NuvlaEdgeResource,
                                             NuvlaEdgeStatusResource,
                                             CredentialResource,
                                             InfrastructureServiceResource,
                                             AutoUpdateNuvlaEdgeTrackedResource,
                                             AutoNuvlaEdgeResource,
                                             AutoNuvlaEdgeStatusResource,
                                             AutoInfrastructureServiceResource)
from nuvlaedge.agent.settings import AgentSettings
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.file_operations import read_file, write_file


logger: logging.Logger = get_nuvlaedge_logger(__name__)


@dataclass(frozen=True)
class NuvlaEndPoints:
    base_path: str = '/api/'
    session: str = base_path + 'session/'

    nuvlaedge: str = base_path + 'nuvlabox/'
    nuvlaedge_status: str = base_path + 'nuvlabox-status/'


class NuvlaApiKeyTemplate(BaseModel, frozen=True):
    key: str
    secret: str
    href: str = "session-template/api-key"


class NuvlaEdgeSession(NuvlaEdgeBaseModel):
    endpoint:               str
    verify:                 bool

    credentials:            NuvlaApiKeyTemplate | None = None

    nuvlaedge_uuid:         NuvlaID
    nuvlaedge_status_uuid:  NuvlaID | None = None


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
        _verify (bool): Whether to verify the SSL certificate of the Nuvla API server
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

    def __init__(self, host: str, verify: bool, nuvlaedge_uuid: NuvlaID):
        """
        Initialize the NuvlaEdgeClient object with the provided parameters.

        Args:
            host (str): The host URL of the NuvlaEdge instance.
            verify (bool): Indicates whether to verify the SSL certificate of the host.
            nuvlaedge_uuid (NuvlaID): The UUID of the NuvlaEdge instance.

        """
        self._host: str = format_host(host)
        self._verify: bool = verify

        # Dictionary containing the NuvlaEdge resources handled by the client
        # nuvlaedge, nuvlaedge-status, vpn-credential, vpn-server
        self._resources: dict[str, any] = {}

        # Create a different session for each type of resource handled by NuvlaEdge. e.g: nuvlabox, job, deployment
        self.nuvlaedge_client: NuvlaApi = NuvlaApi(endpoint=self._host,
                                                   insecure=not verify,
                                                   reauthenticate=True)
        # self.job_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.deployment_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)

        self._headers: dict = {}
        self.nuvlaedge_credentials: NuvlaApiKeyTemplate | None = None

        self._nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid
        self._nuvlaedge_status_uuid: NuvlaID | None = None

    @property
    def nuvlaedge_uuid(self) -> NuvlaID:
        return self._nuvlaedge_uuid

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

    def _is_resource_available(self, res_name: str):
        return res_name in self._resources and self._resources.get(res_name) is not None

    def _init_resource(self,
                       res_name: str,
                       res_type: type[AutoUpdateNuvlaEdgeTrackedResource],
                       res_id: NuvlaID,
                       **kwargs):
        logger.info(f"Initializing resource {res_name} with id {res_id}{kwargs}")
        self._resources[res_name] = res_type(nuvla_client=self.nuvlaedge_client,
                                             resource_id=res_id,
                                             **kwargs)
        self._resources[res_name].force_update()

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
            self._init_resource(_res_name, AutoNuvlaEdgeStatusResource, self._nuvlaedge_uuid)
        return self._resources.get(_res_name)

    @property
    def vpn_credential(self) -> CredentialResource | None:
        if self.nuvlaedge.vpn_server_id is None:
            # This is a safety check. VPN server resource should only be requested if the NuvlaEdge has a VPN server
            logger.warning(f"VPN server not found in NuvlaEdge {self.nuvlaedge_uuid}. This point should not be reached")
            return None

        _res_name = 'vpn-credential'
        if not self._is_resource_available(_res_name):
            self._init_resource(_res_name, CredentialResource, NuvlaID(''),
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

    def login_nuvlaedge(self):
        login_response: Response = self.nuvlaedge_client.login_apikey(self.nuvlaedge_credentials.key,
                                                                      self.nuvlaedge_credentials.secret)

        if login_response.status_code in [200, 201]:
            logger.info("Log in successful")
        else:
            logger.info(f"Error logging in: {login_response}")

    def activate(self):
        """ Activates the NuvlaEdge, saves the returned api-keys and logs in.
        If we already have api-keys, logs in.
        This method will raise any exception should anything fail. This is a compulsory step for the NuvlaEdge without
         which the system cannot work.

        """

        credentials = self.nuvlaedge_client._cimi_post(f'{self.nuvlaedge_uuid}/activate')
        logger.info(f"Credentials received from activation: {credentials}")
        self.nuvlaedge_credentials = NuvlaApiKeyTemplate(key=credentials['api-key'],
                                                         secret=credentials['secret-key'])
        logger.info(f'Activation successful, received credential ID: {self.nuvlaedge_credentials.key}, logging in')
        # Firstly, save the key pair to file
        self._save_current_state_to_file()

        # Then log in to access NuvlaEdge resources
        self.login_nuvlaedge()

        # Finally, force update the NuvlaEdge resource to get the latest state
        self.nuvlaedge.force_update()

    def commission(self, payload: dict):
        """ Executes nuvlaedge resource commissioning operation in the Nuvla endpoint

        Args:
            payload (dict): content of the commissioning operation

        Returns: a dictionary the response of the server to the commissioning operation

        """
        logger.info(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid} with payload {payload}")
        try:
            response: dict = self.nuvlaedge_client._cimi_post(resource_id=f"{self.nuvlaedge_uuid}/commission",
                                                              json=payload)
            if response:
                self.nuvlaedge.force_update()

            return response
        except Exception as e:
            logger.warning(f"Cannot commission NuvlaEdge with Payload {payload}: {e}")

    def heartbeat(self) -> dict:
        """ Executes nuvlaedge resource heartbeat operation in the Nuvla endpoint

        Returns: a CimiResponse instance with the response of the server which includes any possible
            jobs queued for this NuvlaEdge

        """
        logger.info("Sending heartbeat")
        try:
            if not self.nuvlaedge_client.is_authenticated():
                self.login_nuvlaedge()
            response: dict = self.nuvlaedge_client._cimi_post(f"{self.nuvlaedge_uuid}/heartbeat")
            return response
        except Exception as e:
            logger.warning(f"Heartbeat to {self.nuvlaedge_uuid} failed with error: {e}")

    def telemetry(self, new_status: dict, attributes_to_delete: list[str]) -> dict:
        """ Sends telemetry metrics to the nuvlaedge-status resource using edit(put) operation

        Args:
            new_status: metrics that have changed from the last telemetry
            attributes_to_delete: attributes no longer present in the metrics

        Returns: a CimiResponse instance with the response of the server including jobs queued for this NuvlaEdge

        """
        response: CimiResource = self.nuvlaedge_client.edit(self.nuvlaedge_status_uuid,
                                                            data=new_status,
                                                            select=attributes_to_delete)
        logger.debug(f"Response received from telemetry report: {response.data}")
        return response.data

    def _save_current_state_to_file(self):
        """ Saves the current state of the NuvlaEdge client to a file.

        This method serializes the current state of the NuvlaEdge client, including the host, SSL verification setting,
        NuvlaEdge credentials, and NuvlaEdge UUIDs, into a NuvlaEdgeSession object. The serialized session is then written
        to a file for future use.

        The file used to store the session is defined by the FILE_NAMES.NUVLAEDGE_SESSION constant.

        Raises:
            Any exceptions raised by the `write_file` function will be propagated up.

        """
        serial_session = NuvlaEdgeSession(
            endpoint=self._host,
            verify=self._verify,
            credentials=self.nuvlaedge_credentials,
            nuvlaedge_uuid=self.nuvlaedge_uuid,
            nuvlaedge_status_uuid=self._nuvlaedge_status_uuid
        )

        write_file(serial_session, FILE_NAMES.NUVLAEDGE_SESSION)

    @classmethod
    def from_session_store(cls, file: Path | str):
        """ Creates a NuvlaEdgeClient object from a saved session file

        Args:
            file: path to saved session file

        Returns:
            NuvlaEdgeClient object

        """
        session_store = read_file(file, decode_json=True)
        if session_store is None:
            return None
        try:
            session: NuvlaEdgeSession = NuvlaEdgeSession.model_validate(session_store)
        except Exception as ex:
            logger.warning(f'Could not validate session \n{session_store} \nwith error : {ex}')
            return None

        temp_client = cls(host=session.endpoint, verify=session.verify, nuvlaedge_uuid=session.nuvlaedge_uuid)
        temp_client.nuvlaedge_credentials = session.credentials
        temp_client.login_nuvlaedge()
        return temp_client

    @classmethod
    def from_nuvlaedge_credentials(cls, host: str, verify: bool, nuvlaedge_uuid: str, credentials: NuvlaApiKeyTemplate):
        """ Creates a NuvlaEdgeClient object from the API keys

        It retrieves the nuvlaedge resource from the log-in session

        Args:
            host: Nuvla endpoint
            verify: whether to the endpoint is secured or not
            nuvlaedge_uuid: nuvlaedge id
            credentials: api key pair

        Returns: a NuvlaEdgeClient object

        """
        client = cls(host=host, verify=verify, nuvlaedge_uuid=NuvlaID(nuvlaedge_uuid))
        client.nuvlaedge_credentials = credentials
        client.login_nuvlaedge()
        client.login_nuvlaedge()
        return client

    @classmethod
    def from_agent_settings(cls, settings: AgentSettings):
        """ Creates a NuvlaEdgeClient object from the Agent settings

        Args:
            settings: configuration of the NuvlaEdge which should include,
               - endpoint
               - verify
               - nuvlaedge_uuid

        Returns: a NuvlaEdgeClient object

        """
        return cls(host=settings.nuvla_endpoint,
                   verify=not settings.nuvla_endpoint_insecure,
                   nuvlaedge_uuid=settings.nuvlaedge_uuid)
