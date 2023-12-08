import logging

from pydantic import field_validator
from strenum import UppercaseStrEnum
from enum import auto
from typing import Optional

from pydantic import GetCoreSchemaHandler

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

    @classmethod
    def value_of(cls, value):
        for k, v in cls.__members__.items():
            if k == value:
                return v
        else:
            raise ValueError(f"'{cls.__name__}' enum not found for '{value}'")


class NuvlaEdgeResource(NuvlaResourceBase):
    state:                          Optional[State] = None
    refresh_interval:               Optional[int] = None
    heartbeat_interval:             Optional[int] = None

    version:                        Optional[int] = None
    owner:                          Optional[NuvlaID] = None
    vpn_server_id:                  Optional[NuvlaID] = None
    capabilities:                   Optional[list[str]] = None

    infrastructure_service_group:   Optional[NuvlaID] = None

    nuvlabox_status:                Optional[NuvlaID] = None
    credential_api_key:             Optional[NuvlaID] = None

    host_level_management_api_key:  Optional[NuvlaID] = None

    @field_validator('state', mode='before')
    def cast_str_to_state(cls, v):
        if isinstance(v, str):
            return State.value_of(v)
