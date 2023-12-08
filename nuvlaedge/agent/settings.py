from typing import Optional

from pydantic import Field, field_validator, model_validator

from nuvlaedge.agent.common.util import extract_nuvlaedge_version
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings


class InsufficientSettingsProvided(Exception):
    ...


class AgentSettingsMissMatch(Exception):
    ...


class AgentSettings(NuvlaEdgeBaseSettings):
    # Required
    nuvlaedge_uuid:                     Optional[NuvlaID] = None
    host_home:                          str = Field(..., alias="HOME")

    # Required with default values
    compose_project_name:               str = "nuvlaedge"
    nuvlaedge_log_level:                str = "INFO"
    nuvlaedge_thread_monitors:          bool = False
    vpn_interface_name:                 str = 'vpn'
    nuvla_endpoint:                     str = 'nuvla.io'
    nuvla_endpoint_insecure:            bool = False
    shared_data_volume:                 str = "/srv/nuvlaedge/shared/"
    ne_image_tag:                       Optional[str] = None  # Default value provided by compose

    # Optional
    nuvlaedge_api_key:                  Optional[str] = None
    nuvlaedge_api_secret:               Optional[str] = None
    nuvlaedge_excluded_monitors:        Optional[str] = None
    nuvlaedge_immutable_ssh_pub_key:    Optional[str] = Field(None, alias='NUVLAEDGE_SSH_PUB_KEY')
    vpn_config_extra:                   Optional[str] = None

    # Dev configuration
    nuvlaedge_job_engine_lite_image:    Optional[str] = None
    ne_image_registry:                  Optional[str] = None
    ne_image_organization:              Optional[str] = None
    ne_image_repository:                Optional[str] = None
    ne_image_installer:                 Optional[str] = None

    # Below variables are not directly used by agent but are here
    # to be sent to Nuvla, so they are not lost when updating NE
    nuvlaedge_compute_api_enable:       Optional[int] = None
    nuvlaedge_vpn_client_enable:        Optional[int] = None
    nuvlaedge_job_enable:               Optional[int] = None
    compute_api_port:                   Optional[int] = None

    @field_validator('ne_image_tag', mode='before')
    def validate_image_tag(cls, v):
        if v is None or v == "":
            return extract_nuvlaedge_version('')
        return v

    @field_validator('*', mode='before')
    def non_empty_srr(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
        return v

    @model_validator(mode='after')
    def validate_fields(self):

        def none_or_empty_str(val: str) -> bool:
            return val is None or val == ""

        if none_or_empty_str(self.nuvlaedge_uuid) and \
           none_or_empty_str(self.nuvlaedge_api_key) and \
           none_or_empty_str(self.nuvlaedge_api_secret):
            raise ValueError("Nor NuvlaEdge UUID or API keys were provided. One of them must be provided on NuvlaEdge")
