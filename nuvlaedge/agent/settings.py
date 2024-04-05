import json
from argparse import ArgumentParser, Namespace
import logging
from typing import Optional

from pydantic import Field, field_validator, validator, BaseModel

from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings
from nuvlaedge.common.file_operations import file_exists_and_not_empty, read_file
from nuvlaedge.common.constant_files import FILE_NAMES


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


class NuvlaApiKeyTemplate(BaseModel, frozen=True):
    key: str
    secret: str
    href: str = "session-template/api-key"


class NuvlaEdgeSession(NuvlaEdgeBaseModel):
    endpoint:               str
    verify:                 bool

    credentials:            NuvlaApiKeyTemplate

    nuvlaedge_uuid:         NuvlaID | None = None
    nuvlaedge_status_uuid:  NuvlaID | None = None


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
    nuvlaedge_uuid_env:                Optional[NuvlaID] = Field(None, alias='NUVLAEDGE_UUID')
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
    nuvlaedge_immutable_ssh_pub_key:    Optional[str] = Field(None, alias='NUVLAEDGE_SSH_PUB_KEY')
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

    _nuvla_client = None
    _nuvlaedge_uuid:                    Optional[NuvlaID] = None
    _stored_session:                    Optional[NuvlaEdgeSession] = None

    def __init__(self, **values):
        super().__init__(**values)
        logging.info("Initialising AgentSettings...")

        _dict_session = read_file(FILE_NAMES.NUVLAEDGE_SESSION, decode_json=True, warn_on_missing=False)
        if _dict_session is not None:
            logging.info(f"Loading NuvlaEdge session from file {FILE_NAMES.NUVLAEDGE_SESSION}")
            self._stored_session = NuvlaEdgeSession.model_validate(_dict_session)
            # Set immutable nuvla endpoint into settings
            self.nuvla_endpoint = self._stored_session.endpoint

        self._create_client_from_settings()

        self._nuvlaedge_uuid = self._assert_nuvlaedge_uuid()

    def _assert_nuvlaedge_uuid(self) -> NuvlaID:
        """
        NuvlaEdge UUID is asserted once when the agent starts and from then on it is immutable.
        Priority:
        1  NuvlaEdge UUID from NuvlaClient:
          1.1 either from saved local session or from Nuvla
          1.2 or inferred from Nuvla if API are provided from
        2. NuvlaEdge UUID from the environment variable
        Returns:
        """

        def get_uuid(href):
            return href.split('/')[-1] if href else href

        nuvla_nuvlaedge_id = None
        env_nuvlaedge_id = self.nuvlaedge_uuid_env
        stored_nuvlaedge_id = self._stored_session.nuvlaedge_uuid if self._stored_session else None
        _found_id = None

        if self._nuvla_client.nuvlaedge_credentials and self._nuvla_client.login_nuvlaedge():
            # NuvlaEdge UUID will always prevail from
            nuvla_nuvlaedge_id = self._nuvla_client.find_nuvlaedge_id_from_nuvla_session()

        if (stored_nuvlaedge_id and env_nuvlaedge_id and
                get_uuid(stored_nuvlaedge_id) != get_uuid(env_nuvlaedge_id)):
            logging.warning(f'You are trying to install a new NuvlaEdge {env_nuvlaedge_id} even '
                            f'though a previous NuvlaEdge installation ({stored_nuvlaedge_id}) '
                            f'still exists in the system! You can either delete the previous '
                            f'installation (removing all data volumes) or fix the NUVLAEDGE_UUID '
                            f'environment variable to match the old {stored_nuvlaedge_id}')

        if (stored_nuvlaedge_id and nuvla_nuvlaedge_id and
                get_uuid(stored_nuvlaedge_id) != get_uuid(nuvla_nuvlaedge_id)):
            logging.warning(f'NuvlaEdge from context file ({stored_nuvlaedge_id}) '
                            f'do not match session identifier ({nuvla_nuvlaedge_id})')

        if nuvla_nuvlaedge_id:
            logging.info("Using NuvlaEdge UUID from Nuvla session")
            _found_id = nuvla_nuvlaedge_id

        elif stored_nuvlaedge_id:
            logging.info("Using NuvlaEdge UUID from stored session file")
            _found_id = stored_nuvlaedge_id

        elif env_nuvlaedge_id:
            logging.info("Using NuvlaEdge UUID from environment variable. Most likely a new installation.")
            _found_id = env_nuvlaedge_id

        else:
            logging.error("We shouldn't have reached this point. NuvlaEdge UUID is required to start the agent")
            raise InsufficientSettingsProvided("NuvlaEdge UUID is required to start the agent")

        if not _found_id.startswith("nuvlabox/") and not _found_id.startswith("nuvlaedge/"):
            return NuvlaID(f"nuvlabox/{_found_id}")

        return _found_id

    def _create_client_from_settings(self):
        from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper

        self._nuvla_client = NuvlaClientWrapper(self.nuvla_endpoint, self.nuvla_endpoint_insecure, self.nuvlaedge_uuid)
        if self.nuvlaedge_api_key and self.nuvlaedge_api_secret:
            logging.info("Nuvla API keys passed as arguments, these will replace local session")
            self._stored_session.credentials = NuvlaApiKeyTemplate(key=self.nuvlaedge_api_key,
                                                                   secret=self.nuvlaedge_api_secret)
            self._nuvla_client.nuvlaedge_credentials = self._stored_session.credentials

        if self._stored_session and self._stored_session.credentials:
            self._nuvla_client.nuvlaedge_credentials = self._stored_session.credentials

    @property
    def nuvlaedge_uuid(self):
        return self.nuvlaedge_uuid_env

    @property
    def nuvla_client(self):
        return self._nuvla_client

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