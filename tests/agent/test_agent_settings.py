import os
from unittest import TestCase
from mock import Mock, patch

from nuvlaedge.agent.settings import (
    get_cmd_line_settings,
    parse_cmd_line_args,
    AgentSettings,
    NuvlaEdgeSession,
    NuvlaApiKeyTemplate,
    InsufficientSettingsProvided
)

env_variables = {
    "COMPOSE_PROJECT_NAME": "mock_project",
    "NUVLAEDGE_UUID": "mock_uuid",
    "NUVLAEDGE_LOG_LEVEL": "DEBUG",
    "NUVLAEDGE_API_KEY": "mock_api_key",
    "NUVLAEDGE_API_SECRET": "mock_api_secret",
    "NUVLAEDGE_EXCLUDED_MONITORS": "mock_monitor1,mock_monitor2",
    "NUVLAEDGE_THREAD_MONITORS": False,
    "NUVLAEDGE_IMMUTABLE_SSH_PUB_KEY": "mock_ssh_pub_key",
    "NUVLAEDGE_JOB_ENGINE_LITE_IMAGE": "mock_image",
    "HOST_HOME": "/home/mock_user",
    "VPN_INTERFACE_NAME": "mock_vpn_interface",
    "VPN_CONFIG_EXTRA": "mock_vpn_config",
    "NUVLA_ENDPOINT": "https://mock.nuvla.io",
    "NUVLA_ENDPOINT_INSECURE": False,
    "NE_IMAGE_REGISTRY": "mock_registry",
    "NE_IMAGE_ORGANIZATION": "mock_organization",
    "NE_IMAGE_REPOSITORY": "mock_repository",
    "NE_IMAGE_TAG": "mock_tag",
    "NE_IMAGE_INSTALLER": "mock_installer",
    "NUVLAEDGE_COMPUTE_API_ENABLE": 0,
    "NUVLAEDGE_VPN_CLIENT_ENABLE": 1,
    "NUVLAEDGE_JOB_ENABLE": 1,
    "COMPUTE_API_PORT": 8080,
    "NUVLAEDGE_DEBUG": False,
    "NUVLAEDGE_LOGGING_DIRECTORY": "/var/log/nuvlaedge",
    "DISABLE_FILE_LOGGING": False
}


class TestAgentSettings(TestCase):
    @patch('nuvlaedge.agent.settings.AgentSettings.initialise')
    def setUp(self, mock_init):
        os.environ["NUVLAEDGE_UUID"] = 'some_uuid'
        self.test_settings = AgentSettings()
        
        self.mock_nuvla_client = Mock()
        self.test_settings._nuvla_client = self.mock_nuvla_client

    def test_verify_conversion(self):
        ne_session = NuvlaEdgeSession(verify=False)
        self.assertIsNotNone(ne_session.insecure)

    def test_validate_nuvlaedge_thread_monitors(self):
        with patch.dict('os.environ', {'NUVLAEDGE_THREAD_MONITORS': 'yes'}):
            settings = AgentSettings(nuvlaedge_thread_monitors=None)
            self.assertFalse(settings.nuvlaedge_thread_monitors)

    @patch('nuvlaedge.agent.settings.read_file')
    def test_initialize(self, mock_read_file):
        endpoint = 'test.nuvla'
        mock_read_file.return_value = {'endpoint': endpoint}
        settings = AgentSettings(nuvlaedge_thread_monitors=None)
        self.assertEqual(settings.nuvla_endpoint, endpoint)

    def test_nuvla_client(self):
        self.assertEqual(self.test_settings.nuvla_client, self.mock_nuvla_client)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.login_nuvlaedge')
    def test_create_client_from_settings(self, mock_login_nuvlaedge):
        self.test_settings._create_client_from_settings()
        self.assertIsNone(self.test_settings._nuvla_client.irs)

        # API Key and Secret in env vars
        mock_login_nuvlaedge.side_effect = [True, False]
        self.test_settings.nuvlaedge_api_key = 'new-key'
        self.test_settings.nuvlaedge_api_secret = 'new-secret'
        self.test_settings._nuvla_client = self.mock_nuvla_client
        self.test_settings._create_client_from_settings()
        self.assertIsNotNone(self.test_settings._nuvla_client.irs)

        # API key&secret in env vars and existing session and login with api-key failed
        mock_login_nuvlaedge.reset_mock(side_effect=True)
        mock_login_nuvlaedge.side_effect = [True, False]
        self.test_settings._stored_session = NuvlaEdgeSession()
        self.test_settings._nuvla_client = self.mock_nuvla_client
        self.test_settings._create_client_from_settings()
        self.assertIsNone(self.test_settings._nuvla_client.nuvlaedge_credentials)
        self.assertIsNotNone(self.test_settings.nuvla_client.irs)

        creds = NuvlaApiKeyTemplate(key='key', secret='secret')

        # API key&secret in session and in env vars
        mock_login_nuvlaedge.reset_mock(side_effect=True)
        mock_login_nuvlaedge.side_effect = [True, False]
        self.test_settings._stored_session = NuvlaEdgeSession(credentials=creds)
        self.test_settings._create_client_from_settings()
        self.assertIsNotNone(self.test_settings._nuvla_client.nuvlaedge_credentials)
        self.assertIsNotNone(self.test_settings.nuvla_client.irs)
        self.assertEqual('new-key', self.test_settings._nuvla_client.nuvlaedge_credentials.key)

        # API key&secret in session but not in env var and no irs
        mock_login_nuvlaedge.reset_mock(side_effect=True)
        mock_login_nuvlaedge.return_value = False
        self.test_settings.nuvlaedge_api_key = None
        self.test_settings.nuvlaedge_api_secret = None
        self.test_settings._stored_session = NuvlaEdgeSession(credentials=creds)
        self.test_settings._create_client_from_settings()
        self.assertIsNotNone(self.test_settings._nuvla_client.irs)

        # NuvlaEdge UUID in session
        ne_uuid = 'nuvlaedge/uuid'
        self.test_settings._stored_session = NuvlaEdgeSession(nuvlaedge_uuid=ne_uuid)
        self.test_settings._create_client_from_settings()

        self.test_settings._stored_session = NuvlaEdgeSession(nuvlaedge_uuid=None, irs_v2='irs')

        client_class_path = 'nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper'
        with patch(f'{client_class_path}.save_current_state_to_file') as mock_save_current_state_to_file, \
             patch(f'{client_class_path}.find_nuvlaedge_id_from_nuvla_session') as mock_nuvlaedge_id_from_nuvla_session:

            mock_nuvlaedge_id_from_nuvla_session.return_value = ne_uuid

            # With login success
            mock_login_nuvlaedge.return_value = True
            self.test_settings._nuvlaedge_uuid = ne_uuid
            self.test_settings._nuvla_client.login_nuvlaedge = Mock()
            self.test_settings._create_client_from_settings()
            mock_save_current_state_to_file.assert_called_once()

            # Test exception in login
            mock_save_current_state_to_file.reset_mock()
            mock_login_nuvlaedge.reset_mock(return_value=True, side_effect=True)
            mock_login_nuvlaedge.side_effect = Exception
            self.assertRaises(Exception, self.test_settings._create_client_from_settings)
            mock_save_current_state_to_file.assert_not_called()
            mock_login_nuvlaedge.assert_called_once()

            # Test recover from credentials
            mock_save_current_state_to_file.reset_mock()
            mock_login_nuvlaedge.reset_mock(return_value=True, side_effect=True)
            mock_login_nuvlaedge.side_effect = [RuntimeError('Failed to decode irs'), True]
            self.test_settings._stored_session = NuvlaEdgeSession(credentials=creds)
            self.test_settings._create_client_from_settings()
            mock_save_current_state_to_file.assert_called_once()
            self.assertEqual(mock_login_nuvlaedge.call_count, 2)

            # Test cannot recover from credentials
            mock_save_current_state_to_file.reset_mock()
            mock_login_nuvlaedge.reset_mock(return_value=True, side_effect=True)
            mock_login_nuvlaedge.side_effect = RuntimeError
            self.assertRaises(RuntimeError, self.test_settings._create_client_from_settings)
            mock_save_current_state_to_file.assert_not_called()
            mock_login_nuvlaedge.assert_called_once()

    def test_ne_uuid_not_match_nuvla_session_identifier(self):
        mock_nuvlaedge_id_from_nuvla_session = Mock()
        self.test_settings.nuvla_client.find_nuvlaedge_id_from_nuvla_session = mock_nuvlaedge_id_from_nuvla_session
        self.test_settings._status_handler = Mock()

        self.test_settings._nuvlaedge_uuid = 'uuid-1'
        mock_nuvlaedge_id_from_nuvla_session.return_value = 'uuid-2'
        self.assertFalse(self.test_settings._check_uuid_match_with_nuvla_session())
        self.test_settings._status_handler.warning.assert_called_once()

        self.test_settings._status_handler.reset_mock()

        # both None
        self.test_settings._nuvlaedge_uuid = None
        mock_nuvlaedge_id_from_nuvla_session.return_value = None
        self.assertFalse(self.test_settings._check_uuid_match_with_nuvla_session())
        self.test_settings._status_handler.warning.assert_called_once()


    # Tests for parse_cmd_line_args
    @patch('nuvlaedge.agent.settings.ArgumentParser.parse_args')
    @patch('nuvlaedge.agent.settings.logging.error')
    def test_parse_cmd_line_args(self, mock_error, mock_parse_args):
        mock_parse_args.side_effect = Exception('error')
        self.assertIsNone(parse_cmd_line_args())
        mock_error.assert_called_once_with('Errors parsing command line: error')
        mock_error.reset_mock()

        mock_parse_args.side_effect = None
        mock_parse_args.return_value = None
        self.assertIsNone(parse_cmd_line_args())

    # Tests for get_cmd_line_settings
    @patch('nuvlaedge.agent.settings.parse_cmd_line_args')
    def test_get_cmd_line_settings(self, mock_parse_cmd_line_args):
        mock_parse_cmd_line_args.return_value = None
        self.assertEqual(get_cmd_line_settings(self.test_settings), self.test_settings)

        mock_parse_cmd_line_args.return_value = Mock(debug=True, log_level='DEBUG')
        self.assertEqual(get_cmd_line_settings(self.test_settings), self.test_settings)
        self.assertTrue(self.test_settings.nuvlaedge_debug)
        self.assertEqual(self.test_settings.nuvlaedge_log_level, 'DEBUG')

    def test_find_nuvlaedge_uuid(self):
        self.test_settings.nuvlaedge_uuid_env = "nuvlabox/ENV_NUVLAEDGE_UUID"
        self.test_settings._stored_session = NuvlaEdgeSession()
        self.mock_nuvla_client.nuvlaedge_credentials = None
        self.assertEqual(self.test_settings._find_nuvlaedge_uuid(), "nuvlabox/ENV_NUVLAEDGE_UUID")

        stored_mock = Mock()
        stored_mock.nuvlaedge_uuid = "nuvlabox/STORED_NUVLAEDGE_UUID"
        status_mock = Mock()
        status_mock.warning.return_value = True
        self.test_settings._status_handler = status_mock
        status_mock.warning.return_value = True
        self.test_settings._stored_session = stored_mock
        self.assertEqual(self.test_settings._find_nuvlaedge_uuid(), "nuvlabox/STORED_NUVLAEDGE_UUID")
        self.assertEqual(1, status_mock.warning.call_count)

        stored_mock.nuvlaedge_uuid = "STORED_NUVLAEDGE_UUID"
        self.assertEqual(self.test_settings._find_nuvlaedge_uuid(), "nuvlabox/STORED_NUVLAEDGE_UUID")

        with self.assertRaises(InsufficientSettingsProvided):
            self.test_settings.nuvlaedge_uuid_env = None
            self.test_settings._stored_session = NuvlaEdgeSession()
            self.test_settings._find_nuvlaedge_uuid()

    @patch('nuvlaedge.agent.settings.AgentSettings.initialise')
    def test_env_import(self, mock_initialise):
        original_env = dict(os.environ)
        # Set environment variables from the dictionary
        for key, value in env_variables.items():

            os.environ[key] = str(value)

        # Create a new AgentSettings object
        agent_settings = AgentSettings()

        # Check if the values of the AgentSettings attributes match the values in the dictionary
        for key, value in env_variables.items():
            if key == "NUVLAEDGE_UUID":
                key = 'NUVLAEDGE_UUID_ENV'
            self.assertEqual(getattr(agent_settings, key.lower()), value, f"Error in {key} val {value}")

        os.environ.clear()
        os.environ.update(original_env)

    def test_handle_api_key_secret_from_env(self):
        self.test_settings.nuvlaedge_api_key = 'api-key'
        self.test_settings.nuvlaedge_api_secret = 'api-secret'

        self.test_settings._stored_session = NuvlaEdgeSession()
        self.mock_nuvla_client.login_nuvlaedge.return_value = True
        self.test_settings._handle_api_key_secret_from_env()
        self.assertIsNotNone(self.test_settings._nuvla_client.irs)

        # with preexisting old credentials
        credentials = NuvlaApiKeyTemplate(key='old-key', secret='old-secret')
        self.test_settings._stored_session = NuvlaEdgeSession(credentials=credentials)
        self.mock_nuvla_client.login_nuvlaedge.return_value = True
        self.test_settings._handle_api_key_secret_from_env()
        self.assertIsNotNone(self.test_settings._nuvla_client.irs)
        self.assertNotEqual(self.test_settings._nuvla_client.nuvlaedge_credentials, credentials)

        # nuvla return login failure
        self.test_settings._stored_session = NuvlaEdgeSession()
        self.test_settings._nuvla_client.irs = None
        self.mock_nuvla_client.login_nuvlaedge.return_value = False
        self.test_settings._handle_api_key_secret_from_env()
        self.assertIsNone(self.test_settings._nuvla_client.irs)

        # login fails with exception
        self.test_settings._stored_session = NuvlaEdgeSession()
        self.mock_nuvla_client.login_nuvlaedge.side_effect = RuntimeError
        self.test_settings._handle_api_key_secret_from_env()
        self.assertIsNone(self.test_settings._nuvla_client.irs)

    @patch('nuvlaedge.agent.settings.CTE')
    def test_irs_migration(self, patch_cte):
        def get_session():
            return NuvlaEdgeSession.model_validate({
                'nuvlaedge_uuid': ne_uuid,
                'irs': 'MDEyMzQ1Njc4OWFiY2RlZtYpd2DhppINNf/9ELmMMt0='
            })

        ne_uuid = '11111111-2222-3333-4444-555555555555'
        self.test_settings._nuvlaedge_uuid = ne_uuid
        self.test_settings._stored_session = get_session()
        patch_cte.MACHINE_ID = '66666666-7777-8888-9999-000000000000'
        self.test_settings._irs_migration()
        self.assertIsNotNone(self.test_settings._stored_session.irs_v2)
        self.assertIsNotNone(self.test_settings._stored_session.irs)
        self.assertNotEqual(self.test_settings._stored_session.irs_v2,
                            self.test_settings._stored_session.irs_v1)

        self.test_settings._nuvlaedge_uuid = ''
        self.test_settings._stored_session = get_session()
        with self.assertLogs(level='ERROR') as log:
            self.test_settings._irs_migration()
            self.assertTrue(any([('Failed' in i) for i in log.output]))

        # ignore unknown attribute
        session = NuvlaEdgeSession.model_validate({'unknown_attribute': '?'})
        self.assertRaises(AttributeError, getattr, session, 'unknown_attribute')

