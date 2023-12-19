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
class NuvlaEndPointPaths:
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
        nuvlaedge_uuid (NuvlaID): The ID of the NuvlaEdge resource

        __nuvlaedge_resource (NuvlaEdgeResource | None): The cached NuvlaEdge resource instance
        __nuvlaedge_status_resource (NuvlaEdgeStatusResource | None): The cached NuvlaEdge status resource instance
        __vpn_credential_resource (CredentialResource | None): The cached VPN credential resource instance
        __vpn_server_resource (InfrastructureServiceResource | None): The cached VPN server resource instance

        __nuvlaedge_sync_time (float): The last time the NuvlaEdge resource was synced
        __status_sync_time (float): The last time the NuvlaEdge status resource was synced
        __vpn_credential_time (float): The last time the VPN credential resource was synced
        __vpn_server_time (float): The last time the VPN server resource was synced

        nuvlaedge_client (NuvlaApi): The Nuvla API client for interacting with NuvlaEdge resources

        _headers (dict): HTTP headers to be sent with requests

        nuvlaedge_credentials (NuvlaApiKeyTemplate | None): The API keys for authenticating with NuvlaEdge

        _nuvlaedge_status_uuid (NuvlaID | None): The ID of the NuvlaEdge status resource

        _watched_fields (dict[str, set[str]]): The dictionary of watched fields for each resource

    Methods:
        nuvlaedge_status_uuid(self) -> NuvlaID:
            Returns the ID of the NuvlaEdge status resource

        nuvlaedge(self) -> NuvlaEdgeResource:
            Returns the NuvlaEdge resource

        nuvlaedge_status(self) -> NuvlaEdgeStatusResource:
            Returns the NuvlaEdge status resource

        vpn_credential(self) -> CredentialResource:
            Returns the VPN credential resource

        vpn_server(self) -> InfrastructureServiceResource:
            Returns the VPN server resource

        login_nuvlaedge(self) -> None:
            Logs in to the NuvlaEdge API using the API keys

        activate(self) -> None:
            Activates the NuvlaEdge, saves the returned API keys, and logs in

        commission(self, payload: dict) -> dict:
            Sends a commission request to the NuvlaEdge API with the given payload

        heartbeat(self) -> CimiResponse:
            Sends a heartbeat request to the NuvlaEdge API

        telemetry(self, new_status: dict, attributes_to_delete: set[str]) -> CimiResponse:
            Sends a telemetry report to the NuvlaEdge API with the given new status and attributes to delete

        add_peripherals(self, peripherals: list[str]) -> None:
            Adds peripherals to the NuvlaEdge resource

        remove_peripherals(self, peripherals: list[str]) -> None:
            Removes peripherals from the NuvlaEdge resource

        sync_vpn_credential(self) -> None:
            Retrieves the VPN credential from the Nuvla API

        sync_vpn_server(self) -> None:
            Retrieves the VPN server from the Nuvla API

        sync_peripherals(self) -> None:
            Syncs the peripherals of the NuvlaEdge resource

        sync_nuvlaedge(self) -> None:
            Syncs the NuvlaEdge resource from the Nuvla API

        sync_nuvlaedge_status(self) -> None:
            Syncs the NuvlaEdge status resource from the Nuvla API
    """
    MIN_SYNC_TIME: int = 60  # Resource min update time

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

        self.__nuvlaedge_resource: NuvlaEdgeResource | None = None  # NuvlaEdgeResource(id=nuvlaedge_uuid)
        self.__nuvlaedge_status_resource: NuvlaEdgeStatusResource | None = None
        self.__vpn_credential_resource: CredentialResource | None = None
        self.__vpn_server_resource: InfrastructureServiceResource | None = None

        self.__nuvlaedge_sync_time: float = 0.0
        self.__status_sync_time: float = 0.0
        self.__vpn_credential_time: float = 0.0
        self.__vpn_server_time: float = 0.0

        # Create a different session for each type of resource handled by NuvlaEdge. e.g: nuvlabox, job, deployment
        self.nuvlaedge_client: NuvlaApi = NuvlaApi(endpoint=self._host,
                                                   insecure=not verify,
                                                   reauthenticate=True)
        # self.job_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.deployment_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)

        self._headers: dict = {}
        self.nuvlaedge_credentials: NuvlaApiKeyTemplate | None = None

        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid
        self._nuvlaedge_status_uuid: NuvlaID | None = None

        self._watched_fields: dict[str, set[str]] = {}

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
        if time.time() - self.__nuvlaedge_sync_time > self.MIN_SYNC_TIME:
            self.sync_nuvlaedge()
        return self.__nuvlaedge_resource

    @property
    def nuvlaedge_status(self) -> NuvlaEdgeStatusResource:
        if time.time() - self.__status_sync_time > self.MIN_SYNC_TIME:
            self.sync_nuvlaedge_status()
        return self.__nuvlaedge_status_resource

    @property
    def vpn_credential(self) -> CredentialResource:
        if time.time() - self.__vpn_credential_time > self.MIN_SYNC_TIME:
            self.sync_vpn_credential()
        return self.__vpn_credential_resource

    @property
    def vpn_server(self) -> InfrastructureServiceResource:
        if time.time() - self.__vpn_server_time > self.MIN_SYNC_TIME:
            self.sync_vpn_server()
        return self.__vpn_server_resource

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

        self.save()
        self.login_nuvlaedge()

    def commission(self, payload: dict):
        logger.info(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid}")
        try:
            response: dict = self.nuvlaedge_client._cimi_post(resource_id=f"{self.nuvlaedge_uuid}/commission",
                                                              json=payload)
            return response
        except Exception as e:
            logger.warning(f"Cannot commission NuvlaEdge with Payload {payload}: {e}")

    def heartbeat(self) -> CimiResponse:
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
        response: CimiResponse = self.nuvlaedge_client.edit(self.nuvlaedge_status_uuid,
                                                            data=new_status,
                                                            select=attributes_to_delete)
        logger.debug(f"Response received from telemetry report: {response.data}")
        return response

    def add_peripherals(self, peripherals: list):
        ...

    def remove_peripherals(self, peripherals: list):
        ...

    def sync_vpn_credential(self):
        """
        Retrieves the VPN credential if requested.
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
            self.__vpn_credential_resource = CredentialResource.model_validate(creds.resources[0].data)
            self.__vpn_credential_time = time.time()

    def sync_vpn_server(self):
        """

        Returns:

        """
        if not self.nuvlaedge.vpn_server_id:
            logger.warning("Cannot retrieve the vpn server resource for a NuvlaEdge without Server ID defined")
            return

        response: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge.vpn_server_id)
        if response.data:
            self.__vpn_server_resource = InfrastructureServiceResource.model_validate(response.data)
            self.__vpn_server_time = time.time()

    def sync_peripherals(self):
        ...

    def sync_nuvlaedge(self):
        """

        Returns:

        """
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_uuid)
        if resource.data:
            self.__nuvlaedge_resource = NuvlaEdgeResource.model_validate(resource.data)
            print_me = json.dumps(self.__nuvlaedge_resource.model_dump(exclude_none=True,
                                                                       exclude={'operations', 'acl'}),
                                  indent=4)

            logger.info(f"Data retrieved for Nuvlaedge: {print_me}")
            self.__nuvlaedge_sync_time = time.time()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def sync_nuvlaedge_status(self):
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_status_uuid)
        if resource.data:
            self.__nuvlaedge_status_resource = NuvlaEdgeStatusResource.model_validate(resource.data)
            self.__status_sync_time = time.time()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def save(self):

        serial_session = NuvlaEdgeSession(
            endpoint=self._host,
            verify=self._verify,
            credentials=self.nuvlaedge_credentials,
            nuvlaedge_uuid=self.nuvlaedge_uuid,
            nuvlaedge_status_uuid=self._nuvlaedge_status_uuid
        )

        write_file(serial_session.model_dump(exclude_none=True, by_alias=True), FILE_NAMES.NUVLAEDGE_SESSION, indent=4)

    @classmethod
    def from_session_store(cls, file: Path | str):
        session_store = read_file(file, decode_json=True)
        if session_store is None:
            return None
        try:
            session: NuvlaEdgeSession = NuvlaEdgeSession.model_validate(session_store)
        except Exception as ex:
            logger.warning(f'Could not validate session : {ex}')
            return None

        temp_client = cls(host=session.endpoint, verify=session.verify, nuvlaedge_uuid=session.nuvlaedge_uuid)
        temp_client.nuvlaedge_credentials = session.credentials
        temp_client.login_nuvlaedge()
        return temp_client

    @classmethod
    def from_nuvlaedge_credentials(cls, host: str, verify: bool, credentials: NuvlaApiKeyTemplate):
        client = cls(host=host, verify=verify, nuvlaedge_uuid=NuvlaID(""))
        client.nuvlaedge_credentials = credentials
        client.login_nuvlaedge()
        client.nuvlaedge_uuid = client.nuvlaedge.id
        client.login_nuvlaedge()
        return client

    @classmethod
    def from_agent_settings(cls, settings: AgentSettings):

        return cls(host=settings.nuvla_endpoint,
                   verify=not settings.nuvla_endpoint_insecure,
                   nuvlaedge_uuid=settings.nuvlaedge_uuid)
