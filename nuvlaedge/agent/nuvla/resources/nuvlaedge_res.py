import json
import logging

from nuvla.api import Api
from pydantic import field_validator
from strenum import UppercaseStrEnum
from enum import auto
from typing import Optional

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from .nuvla_id import NuvlaID
from .base import AutoUpdateNuvlaEdgeTrackedResource, NuvlaResourceBase


logger: logging.Logger = get_nuvlaedge_logger(__name__)


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
        raise ValueError(f"'{cls.__name__}' enum not found for '{value}'")


class NuvlaEdgeResource(NuvlaResourceBase):
    """
    Class representing a NuvlaEdge resource.

    Attributes:
        state (Optional[State]): The state of the NuvlaEdge resource.
        refresh_interval (Optional[int]): The refresh interval for the resource.
        heartbeat_interval (Optional[int]): The heartbeat interval for the resource.
        version (Optional[int]): The version of the resource.
        owner (Optional[NuvlaID]): The owner of the resource.
        vpn_server_id (Optional[NuvlaID]): The VPN server ID associated with the resource.
        capabilities (Optional[list[str]]): The capabilities of the resource.
        infrastructure_service_group (Optional[NuvlaID]): The infrastructure service group ID associated with the resource.
        nuvlabox_status (Optional[NuvlaID]): The NuvlaBox status ID associated with the resource.
        credential_api_key (Optional[NuvlaID]): The credential API key associated with the resource.
        host_level_management_api_key (Optional[NuvlaID]): The host level management API key associated with the resource.

    Class Methods:
        cast_str_to_state(cls, v): Helper method to cast a string value to a State value.

    """
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


class AutoNuvlaEdgeResource(NuvlaEdgeResource,
                            AutoUpdateNuvlaEdgeTrackedResource):
    ...
