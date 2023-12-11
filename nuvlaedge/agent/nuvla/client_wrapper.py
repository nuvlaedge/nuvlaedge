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

logger: logging.Logger = logging.getLogger(__name__)


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
    MIN_SYNC_TIME: int = 60  # Resource min update time

    def __init__(self, host: str, verify: bool, nuvlaedge_uuid: NuvlaID):

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

        self.paths: NuvlaEndPointPaths = NuvlaEndPointPaths()

        self._watched_fields: dict[str, set[str]] = {}

    def add_watched_field(self, resource: str, field: str):
        # Check resource exists
        if resource in self._watched_fields:
            self._watched_fields[resource].add(field)
        else:
            self._watched_fields[resource] = set(field)

    def remove_watch_field(self, resource: str, field: str):
        if field in self._watched_fields.get(resource, set()):
            self._watched_fields.get(resource).remove(field)

    @property
    def nuvlaedge_status_uuid(self) -> NuvlaID:
        if not self._nuvlaedge_status_uuid:
            self._nuvlaedge_status_uuid = self.nuvlaedge.nuvlabox_status
        return self._nuvlaedge_status_uuid

    @property
    def nuvlaedge(self) -> NuvlaEdgeResource:
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

        with FILE_NAMES.NUVLAEDGE_SESSION.open('w') as f:
            json.dump(serial_session.model_dump(exclude_none=True, by_alias=True), f, indent=4)

    @classmethod
    def from_session_store(cls, file: Path | str):
        if isinstance(file, str):
            file = Path(file)
        with file.open('r') as f:
            session: NuvlaEdgeSession = NuvlaEdgeSession.model_validate_json(f.read())

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
