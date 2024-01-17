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
from nuvlaedge.agent.nuvla.resources.credential import CredentialResource
from nuvlaedge.agent.nuvla.resources.infrastructure_service import InfrastructureServiceResource
from nuvlaedge.agent.settings import AgentSettings
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.nuvla.resources.nuvlaedge import NuvlaEdgeResource
from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import NuvlaEdgeStatusResource
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
    NuvlaClientWrapper is a class that provides a wrapper around the Nuvla API client for interacting with NuvlaEdge resources.

    Attributes:
        MIN_SYNC_TIME (int): The minimum time interval for updating resources (default is 60 seconds)

        _host (str): The hostname of the Nuvla API server
        _verify (bool): Whether to verify the SSL certificate of the Nuvla API server
        _nuvlaedge_uuid (NuvlaID): The ID of the NuvlaEdge resource

        _nuvlaedge_resource (NuvlaEdgeResource | None): The cached NuvlaEdge resource instance
        _nuvlaedge_status_resource (NuvlaEdgeStatusResource | None): The cached NuvlaEdge status resource instance
        _vpn_credential_resource (CredentialResource | None): The cached VPN credential resource instance
        _vpn_server_resource (InfrastructureServiceResource | None): The cached VPN server resource instance

        _nuvlaedge_sync_time (float): The last time the NuvlaEdge resource was synced
        _status_sync_time (float): The last time the NuvlaEdge status resource was synced
        _vpn_credential_time (float): The last time the VPN credential resource was synced
        _vpn_server_time (float): The last time the VPN server resource was synced

        nuvlaedge_client (NuvlaApi): The Nuvla API client for interacting with NuvlaEdge resources

        _headers (dict): HTTP headers to be sent with requests

        nuvlaedge_credentials (NuvlaApiKeyTemplate | None): The API keys for authenticating with NuvlaEdge

        _nuvlaedge_status_uuid (NuvlaID | None): The ID of the NuvlaEdge status resource

    """
    MIN_SYNC_TIME: int = 60  # Resource min update time
    NUVLAEDGE_STATUS_REQUIRED_FIELDS: set = {'node-id'}
    NUVLAEDGE_REQUIRED_FIELDS: set = {'nuvlabox-status',
                                      'infrastructure-service-group',
                                      'vpn-server-id'}

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

        self._nuvlaedge_resource: NuvlaEdgeResource | None = None  # NuvlaEdgeResource(id=nuvlaedge_uuid)
        self._nuvlaedge_status_resource: NuvlaEdgeStatusResource | None = None
        self._vpn_credential_resource: CredentialResource | None = None
        self._vpn_server_resource: InfrastructureServiceResource | None = None

        self._nuvlaedge_sync_time: float = 0.0
        self._status_sync_time: float = 0.0
        self._vpn_credential_time: float = 0.0
        self._vpn_server_time: float = 0.0

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
        if time.time() - self._nuvlaedge_sync_time > self.MIN_SYNC_TIME:
            self._sync_nuvlaedge()
        return self._nuvlaedge_resource

    @property
    def nuvlaedge_status(self) -> NuvlaEdgeStatusResource:
        if time.time() - self._status_sync_time > self.MIN_SYNC_TIME:

            # We only need to retrieve the whole NuvlaBox-status resource once on agent start-up. Then, the only
            # field needed to be updated is node-id. Required by Commissioner to trigger the creation of the
            # nuvlaedge infrastructure service. The creation requires the node-id field. TODO: Improve commissioning op
            if not self._nuvlaedge_status_resource:
                self._sync_nuvlaedge_status()
            else:
                self._sync_nuvlaedge_status(select=self.NUVLAEDGE_STATUS_REQUIRED_FIELDS)

        return self._nuvlaedge_status_resource

    @property
    def vpn_credential(self) -> CredentialResource:
        if time.time() - self._vpn_credential_time > self.MIN_SYNC_TIME:
            self._sync_vpn_credential()
        return self._vpn_credential_resource

    @property
    def vpn_server(self) -> InfrastructureServiceResource:
        if time.time() - self._vpn_server_time > self.MIN_SYNC_TIME:
            self._sync_vpn_server()
        return self._vpn_server_resource

    def login_nuvlaedge(self):
        login_response: Response = self.nuvlaedge_client.login_apikey(self.nuvlaedge_credentials.key,
                                                                      self.nuvlaedge_credentials.secret)

        if login_response.status_code in [200, 201]:
            logger.info("Log in successful")
        else:
            logger.info(f"Error logging in: {login_response}")

    def activate(self):
        """
        Activates the NuvlaEdge, saves the returned api-keys and logs in. If we already have api-keys, logs in
        Returns: None
        Raises: ActivationNotPossible if no api-keys are presents and NuvlaEdge activation returns and error
        """

        credentials = self.nuvlaedge_client._cimi_post(f'{self.nuvlaedge_uuid}/activate')
        logger.info(f"Credentials received from activation: {credentials}")
        self.nuvlaedge_credentials = NuvlaApiKeyTemplate(key=credentials['api-key'],
                                                         secret=credentials['secret-key'])
        logger.info(f'Activation successful, received credential ID: {self.nuvlaedge_credentials.key}, logging in')

        self._save_current_state_to_file()
        self.login_nuvlaedge()

    def commission(self, payload: dict):
        """ Executes nuvlaedge resource commissioning operation in the Nuvla endpoint

        Args:
            payload (dict): content of the commissioning operation

        Returns: a dictionary the response of the server to the commissioning operation

        """
        logger.info(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid}")
        try:
            response: dict = self.nuvlaedge_client._cimi_post(resource_id=f"{self.nuvlaedge_uuid}/commission",
                                                              json=payload)
            return response
        except Exception as e:
            logger.warning(f"Cannot commission NuvlaEdge with Payload {payload}: {e}")

    def heartbeat(self) -> CimiResponse:
        """ Executes nuvlaedge resource heartbeat operation in the Nuvla endpoint

        Returns: a CimiResponse instance with the response of the server which includes any possible
            jobs queued for this NuvlaEdge

        """
        logger.info("Sending heartbeat")
        try:
            if not self.nuvlaedge_client.is_authenticated():
                self.login_nuvlaedge()
            res: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_uuid)
            response: CimiResponse = self.nuvlaedge_client.operation(res, 'heartbeat')
            return response
        except Exception as e:
            logger.warning(f"Heartbeat to {self.nuvlaedge_uuid} failed with error: {e}")

    def telemetry(self, new_status: dict, attributes_to_delete: set[str]):
        """ Sends telemetry metrics to the nuvlaedge-status resource using edit(put) operation

        Args:
            new_status: metrics that have changed from the last telemetry
            attributes_to_delete: attributes no longer present in the metrics

        Returns: a CimiResponse instance with the response of the server including jobs queued for this NuvlaEdge

        """
        response: CimiResponse = self.nuvlaedge_client.edit(self.nuvlaedge_status_uuid,
                                                            data=new_status,
                                                            select=attributes_to_delete)
        logger.debug(f"Response received from telemetry report: {response.data}")
        return response

    def _sync_vpn_credential(self):
        """ Retrieves the VPN credential when requested.

        It accesses the VPN credential associated with the NuvlaEdge and updates the local variable
        The VPN credential is created via commissioning, then it can only be accessed after the VPN keys
         are commissioned which creates the credential and the infrastructure service

        We assume NuvlaEdge has only 1 vpn credential associated.

        Returns: None
        """
        vpn_credential_filter = (f'method="create-credential-vpn-nuvlabox" and '
                                 f'vpn-common-name="{self.nuvlaedge_uuid}" and '
                                 f'parent="{self.nuvlaedge.vpn_server_id}"')

        creds: CimiCollection = self.nuvlaedge_client.search(resource_type="credential",
                                                             filter=vpn_credential_filter,
                                                             last=1)

        if creds.count >= 1:
            logger.info("VPN credential found in NuvlaEdge")
            self._vpn_credential_resource = CredentialResource.model_validate(creds.resources[0].data)
            self._vpn_credential_time = time.time()
        else:
            logger.debug("VPN credential not found in Nuvla")

    def _sync_vpn_server(self):
        """ If the NuvlaEdge has VPN enabled, tries to retrieve the VPN infrastructure service resource

        It reads the VPN server ID from nuvlaedge resource and tries to retrieve its content, then it is
        stored locally.

        Returns: None

        """
        if not self.nuvlaedge.vpn_server_id:
            logger.warning("Cannot retrieve the vpn server resource for a NuvlaEdge without Server ID defined")
            return

        response: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge.vpn_server_id)
        if response.data:
            self._vpn_server_resource = InfrastructureServiceResource.model_validate(response.data)
            self._vpn_server_time = time.time()

    def _sync_nuvlaedge(self, select: set = None):
        """ Updates the nuvlaedge resource when requested.

        Parameter select allows for cherry-picking the fields of the resource to synchronise which allows for data
         consumption optimisation reducing unnecessary data transfer

        Args:
            select: set of fields to retrieve when synchronising nuvlaedge resource

        Returns: None

        """
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_uuid, select=select)
        if resource.data:
            self._nuvlaedge_resource = NuvlaEdgeResource.model_validate(resource.data)
            print_me = json.dumps(self._nuvlaedge_resource.model_dump(exclude_none=True,
                                                                      exclude={'operations', 'acl'}),
                                  indent=4)

            logger.info(f"Data retrieved for Nuvlaedge: {print_me}")
            self._nuvlaedge_sync_time = time.time()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def _sync_nuvlaedge_status(self, select: set = None):
        """ Synchronises the nuvlaedge-status resource and saves it locally

        The nuvlaedge-status id is only set when the nuvlaedge is activated. During this operation, the server,
         creates the nuvlaedge-status resource and adds the id to the nuvlaedge resource

        Args:
            select: set of fields to retrieve when synchronising nuvlaedge-status resource

        Returns: None

        """
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_status_uuid, select=select)
        if resource and resource.data:
            self._nuvlaedge_status_resource = NuvlaEdgeStatusResource.model_validate(resource.data)
            self._status_sync_time = time.time()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def _save_current_state_to_file(self):

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

        Returns: a NuvlaEdgeClient object

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
