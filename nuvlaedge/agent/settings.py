import logging

from argparse import ArgumentParser, Namespace
from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.agent.common.util import get_irs, from_irs
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings
from nuvlaedge.common.file_operations import read_file
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.constants import CTE

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
    model_config = ConfigDict(frozen=True)

    endpoint: str = "https://nuvla.io"
    insecure: bool | None = None
    # To support updates from 2.14.1 to >=2.14.2
    verify: bool | None = None

    # Important Random String
    irs_v2: str | None = Field(None, alias='irs2')
    irs_v1: str | None = Field(None, alias='irs')

    credentials: NuvlaApiKeyTemplate | None = None

    nuvlaedge_uuid: NuvlaID | None = None
    nuvlaedge_status_uuid: NuvlaID | None = None

    @property
    def irs(self):
        return self.irs_v2

    @model_validator(mode='after')
    @classmethod
    def validate_fields(cls, v):
        v.model_config['frozen'] = False

        if v.insecure is None and v.verify is None:
            # Default to secure connection
            v.insecure = False

        if v.insecure is None and v.verify is not None:
            # This should be v.insecure = not v.verify, however, due to a bug in version 2.14.1, verify is set
            # to the opposite of what it should be. This is fixed in version 2.14.2.
            v.insecure = v.verify

        v.model_config['frozen'] = True
        return v


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
        nuvlaedge_exec_jobs_in_agent (Optional[bool]): Execute jobs in agent instead of in a new container.
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
    nuvlaedge_uuid_env: Optional[NuvlaID] = Field(None,
                                                  validation_alias=AliasChoices(
                                                      'NUVLAEDGE_UUID',
                                                      'NUVLABOX_UUID'))
    host_home: str = ""

    # Required with default values
    compose_project_name: str = "nuvlaedge"
    nuvlaedge_log_level: str = "INFO"
    vpn_interface_name: str = 'vpn'
    nuvla_endpoint: str = 'nuvla.io'
    nuvla_endpoint_insecure: bool = False
    shared_data_volume: str = "/var/lib/nuvlaedge/"

    # Optional
    nuvlaedge_thread_monitors: Optional[bool] = False
    nuvlaedge_api_key: Optional[str] = None
    nuvlaedge_api_secret: Optional[str] = None
    nuvlaedge_excluded_monitors: Optional[str] = None
    nuvlaedge_immutable_ssh_pub_key: Optional[str] = None
    nuvlaedge_exec_jobs_in_agent: Optional[bool] = True
    vpn_config_extra: Optional[str] = None

    # Dev configuration
    nuvlaedge_job_engine_lite_image: Optional[str] = None
    ne_image_registry: Optional[str] = None
    ne_image_organization: Optional[str] = None
    ne_image_repository: Optional[str] = None
    ne_image_installer: Optional[str] = None
    ne_image_tag: Optional[str] = None  # Default value provided by compose

    # Below variables are not directly used by agent but are here
    # to be sent to Nuvla, so they are not lost when updating NE
    nuvlaedge_compute_api_enable: Optional[int] = None
    nuvlaedge_vpn_client_enable: Optional[int] = None
    nuvlaedge_job_enable: Optional[int] = None
    compute_api_port: Optional[int] = None

    # New
    nuvlaedge_logging_directory: Optional[str] = None
    nuvlaedge_debug: bool = False
    disable_file_logging: bool = False

    _nuvla_client = None
    _status_handler = None
    _status_report_type = None

    _nuvlaedge_uuid: Optional[NuvlaID] = None
    _stored_session: NuvlaEdgeSession = NuvlaEdgeSession()

    @field_validator('nuvlaedge_thread_monitors', mode='after')
    @classmethod
    def validate_nuvlaedge_thread_monitors(cls, v):
        if isinstance(v, bool):
            return v
        else:
            return False

    def __init__(self, **values):
        super().__init__(**values)
        self.initialise()

    def initialise(self):
        logging.info("Initialising AgentSettings...")

        # Check legacy settings
        # Adds support for updating to NuvlaEdge > 2.13.0
        from nuvlaedge.agent.common.legacy_support import transform_legacy_config_if_needed
        transform_legacy_config_if_needed()

        from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
        self._status_handler = NuvlaEdgeStatusHandler()
        self._status_report_type = StatusReport

        _dict_session = read_file(FILE_NAMES.NUVLAEDGE_SESSION, decode_json=True, warn_on_missing=False)
        if _dict_session is not None:
            logging.info(f"Loading NuvlaEdge session from file {FILE_NAMES.NUVLAEDGE_SESSION}")
            self._stored_session = NuvlaEdgeSession.model_validate(_dict_session)
            # Set immutable nuvla endpoint into settings
            self.nuvla_endpoint = self._stored_session.endpoint

        self._nuvlaedge_uuid = self._find_nuvlaedge_uuid()

        self._create_client_from_settings()

        logging.info("Initialising agent settings for NuvlaEdge: %s", self.nuvlaedge_uuid)

    @staticmethod
    def get_uuid(href):
        return href.split('/')[-1] if href else href

    def _find_nuvlaedge_uuid(self) -> NuvlaID:
        """
        NuvlaEdge UUID is asserted once when the agent starts and from then on it is immutable.
        Priority:
        1  NuvlaEdge UUID from saved local session
        2. NuvlaEdge UUID from the environment variable
        Returns:
        """

        env_nuvlaedge_id = self.nuvlaedge_uuid_env
        stored_nuvlaedge_id = self._stored_session.nuvlaedge_uuid
        _found_id = None

        if (stored_nuvlaedge_id and env_nuvlaedge_id and
                self.get_uuid(stored_nuvlaedge_id) != self.get_uuid(env_nuvlaedge_id)):
            self._status_handler.warning(
                self.status_handler.status_channel,
                "Agent Settings",
                "Trying to start a NuvlaEdge with an env UUID different from the "
                "stored one. Running on stored ID and credentials... ",
                date=datetime.now() + relativedelta(years=1))
            logging.warning(
                f'You are trying to install a new NuvlaEdge {env_nuvlaedge_id} even '
                f'though a previous NuvlaEdge installation ({stored_nuvlaedge_id}) '
                f'still exists in the system! You can either delete the previous '
                f'installation (removing all data volumes) or fix the NUVLAEDGE_UUID '
                f'environment variable to match the old {stored_nuvlaedge_id}')

        if stored_nuvlaedge_id:
            logging.info("Using NuvlaEdge UUID from stored session file")
            _found_id = stored_nuvlaedge_id

        elif env_nuvlaedge_id:
            logging.info("Using NuvlaEdge UUID from environment variable. Most likely a new installation.")
            _found_id = env_nuvlaedge_id

        else:
            msg = "NuvlaEdge UUID is required to start the agent"
            logging.error(msg)
            raise InsufficientSettingsProvided(msg)

        if not _found_id.startswith("nuvlabox/") and not _found_id.startswith("nuvlaedge/"):
            return NuvlaID(f"nuvlabox/{_found_id}")

        return NuvlaID(_found_id)

    def _handle_api_key_secret_from_env(self):
        """
        Handle a special case when the NuvlaEdge credentials are provided as ENV variables.
        These credentials need to replace any local session if the configuration match with the stored session
        and Nuvla after login.
        """
        if self.nuvlaedge_api_key and self.nuvlaedge_api_secret:
            logging.info("Nuvla API keys passed as arguments, these will replace local session if valid")

            irs = get_irs(self.nuvlaedge_uuid, self.nuvlaedge_api_key, self.nuvlaedge_api_secret)
            try:
                login_success = self._nuvla_client.login_nuvlaedge(irs)
                if not login_success:
                    logging.error('Failed to login to Nuvla with the API key and secret provided from the environment')
            except Exception as e:
                logging.exception(f'Login with API key and secret provided from the environment failed with: {e}')
                login_success = False

            if login_success:
                self._nuvla_client.irs = irs
                if self._stored_session.credentials:
                    self._nuvla_client.nuvlaedge_credentials = NuvlaApiKeyTemplate(key=self.nuvlaedge_api_key,
                                                                                   secret=self.nuvlaedge_api_secret)

    def _check_uuid_match_with_nuvla_session(self):
        nuvlaedge_id = self.nuvlaedge_uuid
        nuvla_nuvlaedge_id = self._nuvla_client.find_nuvlaedge_id_from_nuvla_session()
        uuids_match = bool(nuvlaedge_id and nuvla_nuvlaedge_id and
                           self.get_uuid(nuvlaedge_id) == self.get_uuid(nuvla_nuvlaedge_id))
        if not uuids_match:
            self._status_handler.warning(
                self.status_handler.status_channel,
                "AgentSettings", "NuvlaEdge ID missmatch with Nuvla session identifier.")
            logging.warning(f'NuvlaEdge UUID ({nuvlaedge_id}) '
                            f'do not match Nuvla session identifier ({nuvla_nuvlaedge_id})')
        return uuids_match

    def _irs_migration(self):
        # Migration from IRSv1 to IRSv2
        if not self._stored_session.irs_v2 and self._stored_session.irs_v1:
            try:
                data = from_irs(self.nuvlaedge_uuid, self._stored_session.irs_v1, CTE.MACHINE_ID)
                irs2 = get_irs(self.nuvlaedge_uuid, *data)
                self._stored_session = self._stored_session.model_copy(deep=True, update={'irs_v2': irs2})
            except Exception as e:
                logging.exception(f'Failed to migrate IRS from v1 to v2: {e}')

        # Keep IRSv1
        self._nuvla_client.irs_v1 = self._stored_session.irs_v1

        # Keep credentials
        self._nuvla_client.nuvlaedge_credentials = self._stored_session.credentials

    def _generate_irs_from_settings(self):
        if self._stored_session.credentials:
            logging.debug('Generating new IRS from settings')
            self._nuvla_client.irs = get_irs(self.nuvlaedge_uuid,
                                             self._stored_session.credentials.key,
                                             self._stored_session.credentials.secret)

    def _create_client_from_settings(self):
        from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper

        self._nuvla_client = NuvlaClientWrapper(self.nuvla_endpoint, self.nuvla_endpoint_insecure, self.nuvlaedge_uuid)

        self._irs_migration()

        self._handle_api_key_secret_from_env()

        if not self._nuvla_client.irs and self._stored_session.irs:
            logging.info("Nuvla API key found in stored session, using it to login")
            self._nuvla_client.irs = self._stored_session.irs

        if not self._nuvla_client.irs and not self._stored_session.irs:
            self._generate_irs_from_settings()

        if self._nuvla_client.irs:
            try:
                login_success = self._nuvla_client.login_nuvlaedge()
            except RuntimeError as e:
                if 'irs' in str(e) and self._stored_session.credentials:
                    self._generate_irs_from_settings()
                    login_success = self._nuvla_client.login_nuvlaedge()
                else:
                    raise

            # To prevent a situation where the stored session is not valid anymore,
            # we need to check if the UUID's match before the assessment of the uuid.
            if login_success and self._check_uuid_match_with_nuvla_session():
                # After logging in if UUID's match, save the session to file
                self._nuvla_client.save_current_state_to_file()

    @property
    def status_handler(self):
        return self._status_handler

    @property
    def nuvlaedge_uuid(self):
        return self._nuvlaedge_uuid

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
