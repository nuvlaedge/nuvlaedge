import json
import logging
import time
from pathlib import Path

from nuvla.api.models import CimiResponse, CimiCollection, CimiResource
from pydantic import BaseModel
from dataclasses import dataclass

from nuvla.api import Api as NuvlaApi
from requests import Response

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
    endpoint: str
    verify: bool

    credentials: NuvlaApiKeyTemplate | None

    nuvlaedge_uuid: NuvlaID
    nuvlaedge_status_uuid: NuvlaID | None


class NuvlaClientWrapper:
    MIN_SYNC_TIME: int = 3600  # Resource min update time

    def __init__(self, host: str, verify: bool, nuvlaedge_uuid: NuvlaID):

        self._host: str = host
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
        self.nuvlaedge_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.job_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.deployment_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)

        self._headers: dict = {}
        self.nuvlaedge_credentials: NuvlaApiKeyTemplate | None = None

        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid
        self.nuvlaedge_status_uuid: NuvlaID | None = None

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

        self.nuvlaedge_credentials = NuvlaApiKeyTemplate.model_validate(credentials)
        logger.info(f'Activation successful, received credential ID: {self.nuvlaedge_credentials.key}, logging in')

        self.login_nuvlaedge()

    def commission(self, payload: dict):
        logger.info(f"Commissioning NuvlaEdge {self.nuvlaedge_uuid}")
        try:
            self.nuvlaedge_client._cimi_post(f"{self.nuvlaedge_uuid}/commission", json=payload)

        except Exception as e:
            logger.warning(f"Cannot commission NuvlaEdge with Payload {payload}: {e}")

    def heartbeat(self):
        logger.debug("Sending heartbeat")
        try:
            response: CimiResponse = self.nuvlaedge_client._cimi_post(f"{self.nuvlaedge_uuid}/heartbeat")
            return response
        except Exception as e:
            logger.warning(f"Heartbeat to {self.nuvlaedge_uuid} failed with error: {e}")

    def telemetry(self, new_status: dict, attributes_to_delete: list[str]):
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
            self.__vpn_credential_resource = CredentialResource.model_validate(creds.resources[0])
            self.__vpn_credential_time = time.perf_counter()
        else:
            logger.info("No VPN credential found in NuvlaEdge, Yet?")

    def sync_vpn_server(self):
        """

        Returns:

        """
        if not self.nuvlaedge.vpn_server_id:
            logger.warning("Cannot retrieve the vpn server resource for a NuvlaEdge without Server ID defined")
            return

        response: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge.vpn_server_id)
        if response.data:
            self.__vpn_server_resource = InfrastructureServiceResource.model_validate_json(response.data)
            self.__vpn_server_time = time.perf_counter()

    def sync_peripherals(self):
        ...

    def sync_nuvlaedge(self):
        """

        Returns:

        """
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_uuid)
        if resource.data:
            self.__nuvlaedge_resource = NuvlaEdgeResource.model_validate_json(resource.data)
            self.__nuvlaedge_sync_time = time.perf_counter()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def sync_nuvlaedge_status(self):
        resource: CimiResource = self.nuvlaedge_client.get(self.nuvlaedge_status_uuid)
        if resource.data:
            self.__nuvlaedge_status_resource = NuvlaEdgeStatusResource.model_validate_json(resource.data)
            self.__status_sync_time = time.perf_counter()
        else:
            logger.error("Error retrieving NuvlaEdge resource")

    def save(self, file: Path | str):

        if isinstance(file, str):
            file = Path(file)
        serial_session = NuvlaEdgeSession(
            endpoint=self._host,
            verify=self._verify,
            credentials=NuvlaApiKeyTemplate(key='keyme', secret='secretme'),
            nuvlaedge_uuid=self.nuvlaedge_uuid
        )

        with file.open('w') as f:
            json.dump(serial_session.model_dump(exclude_none=True, by_alias=True), f, indent=4)

    @classmethod
    def from_session_store(cls, file: Path | str):
        if isinstance(file, str):
            file = Path(file)
        with file.open('r') as f:
            session: NuvlaEdgeSession = NuvlaEdgeSession.model_validate_json(json.load(f))

        return cls(host=session.endpoint, verify=session.verify, nuvlaedge_uuid=session.nuvlaedge_uuid)

    @classmethod
    def from_nuvlaedge_credentials(cls, host: str, verify: bool, credentials: NuvlaApiKeyTemplate):
        client = cls(host=host, verify=verify, nuvlaedge_uuid=NuvlaID(""))
        client.nuvlaedge_credentials = credentials
        client.login_nuvlaedge()
        client.nuvlaedge_uuid = client.nuvlaedge.id
        return client

    @classmethod
    def from_agent_settings(cls, settings: AgentSettings):

        return cls(host=settings.nuvla_endpoint,
                   verify=not settings.nuvla_endpoint_insecure,
                   nuvlaedge_uuid=settings.nuvlaedge_uuid)
