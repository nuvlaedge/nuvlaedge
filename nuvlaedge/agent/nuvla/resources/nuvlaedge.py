from strenum import UppercaseStrEnum
from enum import auto
from typing import Optional

from pydantic import ValidationError

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase


class State(UppercaseStrEnum):
    NEW = auto()
    ACTIVATED = auto()
    COMMISSIONED = auto()
    DECOMMISSIONED = auto()
    DECOMMISSIONING = auto()

    # Used by NuvlaEdge to identify errors
    UNKNOWN = auto()


class NuvlaEdgeResource(NuvlaResourceBase):
    state:                          Optional[State]
    refresh_interval:               Optional[int]
    heartbeat_interval:             Optional[int]

    version:                        Optional[int]
    owner:                          Optional[NuvlaID]
    vpn_server_id:                  Optional[NuvlaID]
    capabilities:                   Optional[list[str]]

    infrastructure_service_group:   Optional[NuvlaID]
    version:                        Optional[int]

    nuvlabox_status:                Optional[NuvlaID]
    credential_api_key:             Optional[NuvlaID]

    host_level_management_api_key:  Optional[NuvlaID]

