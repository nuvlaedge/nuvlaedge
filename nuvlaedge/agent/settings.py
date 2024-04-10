import json
from argparse import ArgumentParser, Namespace
import logging
from typing import Optional

from pydantic import Field, field_validator, validator

from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings


DEFAULT_AGENT_SETTINGS_FILE = 'nuvlaedge'


class InsufficientSettingsProvided(Exception):
    """
    Exception raised when insufficient settings are provided.

    This exception is raised when the required settings are not provided or are incomplete.
    """
    ...


class AgentSettingsMissMatch(Exception):
    """ An exception raised when there is a mismatch in the agent settings. """
    ...


class AgentSettings(NuvlaEdgeBaseSettings):
    """
    AgentSettings class represents the settings for the NuvlaEdge agent.

    Attributes:
        nuvlaedge_uuid (Optional[NuvlaID]): The UUID of the NuvlaEdge instance.
        host_home (str): The home directory of the host machine.

        compose_project_name (str): The name of the compose project. Default value is "nuvlaedge".
        nuvlaedge_log_level (str): The log level for NuvlaEdge. Default value is "INFO".
        nuvlaedge_thread_monitors (bool): Flag to enable or disable thread monitors. Default value is False.
        vpn_interface_name (str): The name of the VPN interface. Default value is 'vpn'.
        nuvla_endpoint (str): The Nuvla API endpoint. Default value is 'nuvla.io'.
        nuvla_endpoint_insecure (bool): Flag to enable or disable insecure connection to Nuvla endpoint. Default value is False.
        shared_data_volume (str): The path to the shared data volume. Default value is "/var/lib/nuvlaedge/".
        ne_image_tag (Optional[str]): The tag for the NuvlaEdge image. Default value is None.

        nuvlaedge_api_key (Optional[str]): The API key for NuvlaEdge.
        nuvlaedge_api_secret (Optional[str]): The API secret for NuvlaEdge.
        nuvlaedge_excluded_monitors (Optional[str]): The excluded monitors for NuvlaEdge.
        nuvlaedge_immutable_ssh_pub_key (Optional[str]): The immutable SSH public key for NuvlaEdge.
        vpn_config_extra (Optional[str]): Extra VPN configuration for NuvlaEdge.

        nuvlaedge_job_engine_lite_image (Optional[str]): The image for the NuvlaEdge job engine lite.
        ne_image_registry (Optional[str]): The registry for the NuvlaEdge image.
        ne_image_organization (Optional[str]): The organization for the NuvlaEdge image.
        ne_image_repository (Optional[str]): The repository for the NuvlaEdge image.
        ne_image_installer (Optional[str]): The installer for the NuvlaEdge image.

        nuvlaedge_compute_api_enable (Optional[int]): Flag to enable or disable NuvlaEdge compute API.
        nuvlaedge_vpn_client_enable (Optional[int]): Flag to enable or disable NuvlaEdge VPN client.
        nuvlaedge_job_enable (Optional[int]): Flag to enable or disable NuvlaEdge job engine.
        compute_api_port (Optional[int]): The port for the compute API.

    Methods:
        validate_image_tag(cls, v): Validates the image tag for NuvlaEdge.
        non_empty_srr(cls, v): Validates that a string field is not empty.
        validate_fields(self): Validates the fields of the AgentSettings instance.

    """
    # Required
    nuvlaedge_uuid:                     Optional[NuvlaID] = None
    host_home:                          str = Field(..., alias="HOME")

    # Required with default values
    compose_project_name:               str = "nuvlaedge"
    nuvlaedge_log_level:                str = "INFO"
    vpn_interface_name:                 str = 'vpn'
    nuvla_endpoint:                     str = 'nuvla.io'
    nuvla_endpoint_insecure:            bool = False
    shared_data_volume:                 str = "/var/lib/nuvlaedge/"

    # Optional
    nuvlaedge_thread_monitors:          Optional[bool] = False
    nuvlaedge_api_key:                  Optional[str] = None
    nuvlaedge_api_secret:               Optional[str] = None
    nuvlaedge_excluded_monitors:        Optional[str] = None
    nuvlaedge_immutable_ssh_pub_key:    Optional[str] = None
    vpn_config_extra:                   Optional[str] = None

    # Dev configuration
    nuvlaedge_job_engine_lite_image:    Optional[str] = None
    ne_image_registry:                  Optional[str] = None
    ne_image_organization:              Optional[str] = None
    ne_image_repository:                Optional[str] = None
    ne_image_installer:                 Optional[str] = None
    ne_image_tag:                       Optional[str] = None  # Default value provided by compose

    # Below variables are not directly used by agent but are here
    # to be sent to Nuvla, so they are not lost when updating NE
    nuvlaedge_compute_api_enable:       Optional[int] = None
    nuvlaedge_vpn_client_enable:        Optional[int] = None
    nuvlaedge_job_enable:               Optional[int] = None
    compute_api_port:                   Optional[int] = None

    # New
    nuvlaedge_logging_directory:        Optional[str] = None
    nuvlaedge_debug:                    bool = False
    disable_file_logging:               bool = False

    @field_validator('nuvlaedge_uuid', mode='after')
    def nameless_uuid(cls, v):
        if v is not None and not v.startswith('nuvlabox/'):
            return NuvlaID(f"nuvlabox/{v}")
        return v

    @field_validator('vpn_config_extra', mode='after')
    def clean_config_extra(cls, v):
        if v is not None and v != "":
            return v.replace(r'\n', '\n')
        return v


__agent_settings: AgentSettings | None = None


def parse_cmd_line_args() -> Namespace | None:

    parser: ArgumentParser = ArgumentParser(description="NuvlaEdge agent",
                                            exit_on_error=False)
    parser.add_argument('-l', '--log-level', dest='log_level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO', help='Log level')
    parser.add_argument('-d', '--debug', dest='debug',
                        action='store_const', const='DEBUG',
                        help='Set log level to debug')
    try:
        return parser.parse_args()
    except Exception as ex:
        logging.error(f"Errors parsing command line: {ex}")
        return None


def get_cmd_line_settings(env_settings: AgentSettings) -> AgentSettings:
    cmd_settings: Namespace | None = parse_cmd_line_args()
    if cmd_settings is None:
        return env_settings

    if cmd_settings.debug:
        env_settings.nuvlaedge_debug = (cmd_settings.debug == 'true' or
                                        cmd_settings.debug is True or
                                        cmd_settings.debug == "True")

    if cmd_settings.log_level:
        env_settings.nuvlaedge_log_level = cmd_settings.log_level
    return env_settings


def get_agent_settings() -> AgentSettings:
    global __agent_settings
    if __agent_settings is not None:
        return __agent_settings

    env_settings = AgentSettings()
    __agent_settings = get_cmd_line_settings(env_settings)

    return __agent_settings


if __name__ == '__main__':
    print(get_agent_settings().model_dump_json(indent=4))
