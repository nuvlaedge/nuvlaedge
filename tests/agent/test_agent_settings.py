import os
from unittest import TestCase
import mock

from nuvlaedge.agent.settings import (parse_cmd_line_args,
                                      AgentSettings,
                                      get_cmd_line_settings,
                                      get_agent_settings)

import nuvlaedge.agent.settings as settings


class TestAgentSettings(TestCase):
    def setUp(self):
        os.environ["NUVLAEDGE_UUID"] = 'some_uuid'
        self.test_settings = AgentSettings()

    # Tests for parse_cmd_line_args
    @mock.patch('nuvlaedge.agent.settings.ArgumentParser.parse_args')
    @mock.patch('nuvlaedge.agent.settings.logging.error')
    def test_parse_cmd_line_args(self, mock_error, mock_parse_args):
        mock_parse_args.side_effect = Exception('error')
        self.assertIsNone(parse_cmd_line_args())
        mock_error.assert_called_once_with('Errors parsing command line: error')
        mock_error.reset_mock()

        mock_parse_args.side_effect = None
        mock_parse_args.return_value = None
        self.assertIsNone(parse_cmd_line_args())

    # Tests for get_cmd_line_settings
    @mock.patch('nuvlaedge.agent.settings.parse_cmd_line_args')
    def test_get_cmd_line_settings(self, mock_parse_cmd_line_args):
        mock_parse_cmd_line_args.return_value = None
        self.assertEqual(get_cmd_line_settings(self.test_settings), self.test_settings)

        mock_parse_cmd_line_args.return_value = mock.Mock(debug=True, log_level='DEBUG')
        self.assertEqual(get_cmd_line_settings(self.test_settings), self.test_settings)
        self.assertTrue(self.test_settings.nuvlaedge_debug)
        self.assertEqual(self.test_settings.nuvlaedge_log_level, 'DEBUG')

    def test_assert_nuvlaedge_uuid(self):
        self.test_settings.nuvlaedge_uuid_env = "nuvlabox/ENV_NUVLAEDGE_UUID"
        self.assertEqual(self.test_settings._assert_nuvlaedge_uuid(), "nuvlabox/ENV_NUVLAEDGE_UUID")

