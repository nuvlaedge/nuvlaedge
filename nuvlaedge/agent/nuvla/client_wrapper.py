import json
import logging
from pathlib import Path
from pydantic import BaseModel
from dataclasses import dataclass

from nuvla.api import Api as NuvlaApi

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
    def __init__(self, host: str, verify: bool, nuvlaedge_uuid: NuvlaID):

        self._host: str = host
        self._verify: bool = verify

        self.__nuvlaedge_resource: NuvlaEdgeResource = NuvlaEdgeResource(id=nuvlaedge_uuid)
        self.__nuvlaedge_status_resource: NuvlaEdgeStatusResource | None = None

        # Create a different session for each type of resource handled by NuvlaEdge. e.g: nuvlabox, job, deployment
        self.nuvlaedge_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.job_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)
        # self.deployment_client: NuvlaApi = NuvlaApi(endpoint=host, insecure=not verify, persist_cookie=False)

        self._headers: dict = {}
        self.nuvlaedge_credentials: NuvlaApiKeyTemplate | None = None

        self.nuvlaedge_uuid: NuvlaID = nuvlaedge_uuid
        self.nuvlaedge_status_uuid: NuvlaID | None = None

        self.paths: NuvlaEndPointPaths = NuvlaEndPointPaths()

    def login_nuvlaedge(self):
        ...

    def activate(self):
        ...

    def commission(self):
        ...

    def heartbeat(self):
        ...

    def telemetry(self):
        ...

    def add_peripherals(self, peripherals: list):
        ...

    def remove_peripherals(self, peripherals: list):
        ...

    def sync_peripherals(self):
        ...

    def sync_nuvlaedge(self):
        ...

    def sync_nuvlaedge_status(self):
        ...

    def save(self, file: Path | str):

        if isinstance(file, str):
            file = Path(file)
        serial_session = NuvlaEdgeSession(
            endpoint=self._host,
            verify=self._verify,
            credentials=self.nuvlaedge_credentials,
            nuvlaedge_uuid=self.nuvlaedge_uuid
        )

        with file.open('w') as f:
            json.dump(serial_session.dict(exclude_none=True, by_alias=True), f, indent=4)

    @classmethod
    def from_session_store(cls, file: Path | str):
        if isinstance(file, str):
            file = Path(file)
        session: NuvlaEdgeSession = NuvlaEdgeSession.parse_file(path=file)

        return cls(host=session.endpoint, verify=session.verify, nuvlaedge_uuid=session.nuvlaedge_uuid)


__nuvla_client: NuvlaClientWrapper | None = NuvlaClientWrapper('nuvla', False, NuvlaID('nuvlabox/asdfas'))


def get_nuvla_client(host: str = '', verify: bool = None, nuvlaedge_uuid: str = ''):
    global __nuvla_client

    if __nuvla_client is not None:
        return __nuvla_client

    __nuvla_client = NuvlaClientWrapper(host, verify, NuvlaID(nuvlaedge_uuid))
    return __nuvla_client


def get_client_from_session(session_file: Path):
    global __nuvla_client

    if __nuvla_client is not None:
        return __nuvla_client

    with session_file.open('r') as f:
        logger.info("Opening file...")

