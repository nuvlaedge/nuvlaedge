import os
from unittest import TestCase
from mock import Mock, patch

from nuvlaedge.agent.settings import (parse_cmd_line_args,
                                      AgentSettings,
                                      get_cmd_line_settings,
                                      get_agent_settings)

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

    def test_assert_nuvlaedge_uuid(self):
        self.test_settings.nuvlaedge_uuid_env = "nuvlabox/ENV_NUVLAEDGE_UUID"
        self.test_settings._stored_session = None
        self.mock_nuvla_client.nuvlaedge_credentials = None
        self.assertEqual(self.test_settings._assert_nuvlaedge_uuid(), "nuvlabox/ENV_NUVLAEDGE_UUID")

        self.mock_nuvla_client.login_nuvlaedge.return_value = True
        self.mock_nuvla_client.nuvlaedge_credentials = True
        self.mock_nuvla_client.find_nuvlaedge_id_from_nuvla_session.return_value = "nuvlabox/NUVLA_NUVLAEDGE_UUID"
        self.assertEqual(self.test_settings._assert_nuvlaedge_uuid(), "nuvlabox/NUVLA_NUVLAEDGE_UUID")

        stored_mock = Mock()
        stored_mock.nuvlaedge_uuid = "nuvlabox/STORED_NUVLAEDGE_UUID"
        status_mock = Mock()
        status_mock.warning.return_value = True
        self.test_settings._status_handler = status_mock
        status_mock.warning.return_value = True
        self.test_settings._stored_session = stored_mock
        self.assertEqual(self.test_settings._assert_nuvlaedge_uuid(), "nuvlabox/STORED_NUVLAEDGE_UUID")
        self.assertEqual(2, status_mock.warning.call_count)

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
