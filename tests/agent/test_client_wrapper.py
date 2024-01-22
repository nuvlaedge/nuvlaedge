
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch

import mock
from nuvla.api import Api
from nuvla.api.models import CimiResource, CimiCollection

import nuvlaedge.agent.nuvla.client_wrapper
from nuvlaedge.agent.nuvla.resources import NuvlaID, AutoNuvlaEdgeResource
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper, NuvlaApiKeyTemplate


class TestClientWrapper(TestCase):
    def setUp(self):
        self.mock_nuvla = Mock(spec=Api)
        self.mock_uuid = NuvlaID('nuvlabox/0000')
        self.mock_verify = True
        self.host = 'https://mock_host.io'
        self.test_client = NuvlaClientWrapper(host=self.host,
                                              verify=self.mock_verify,
                                              nuvlaedge_uuid=self.mock_uuid)
        self.test_client.nuvlaedge_client = self.mock_nuvla

    @mock.patch('nuvlaedge.agent.nuvla.client_wrapper.time')
    def test_nuvlaedge_status_property(self, mock_time):
        assert True

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._save_current_state_to_file')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.login_nuvlaedge')
    def test_activate(self, mock_login, mock_save, mock_nuvlaedge):
        self.mock_nuvla._cimi_post.return_value = {}

        with self.assertRaises(KeyError):
            self.test_client.activate()

        self.mock_nuvla._cimi_post.return_value = {'api-key': 'key_1', 'secret-key': 'secret_1'}
        self.test_client.activate()
        mock_save.assert_called_once()
        mock_login.assert_called_once()
        self.assertEqual(NuvlaApiKeyTemplate(key='key_1', secret='secret_1'), self.test_client.nuvlaedge_credentials)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge')
    def test_commission(self, mock_nuvlaedge):
        self.mock_nuvla._cimi_post.return_value = {'nice': 'response'}
        self.assertEqual(self.test_client.commission({}), {'nice': 'response'})
        self.mock_nuvla._cimi_post.assert_called_with(resource_id=f"{self.mock_uuid}/commission",
                                                      json={})
        self.mock_nuvla._cimi_post.reset_mock()
        self.mock_nuvla._cimi_post.return_value = {'nice': 'response'}

        self.mock_nuvla._cimi_post.side_effect = Exception(ValueError)
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            self.test_client.commission({})
            self.mock_nuvla._cimi_post.assert_called_with(resource_id=f"{self.mock_uuid}/commission",
                                                          json={})
            mock_warning.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.login_nuvlaedge')
    def test_heartbeat(self, mock_login):
        self.mock_nuvla.is_authenticated.return_value = False
        self.mock_nuvla._cimi_post.return_value = {'nice': 'response'}

        self.assertEqual({'nice': 'response'}, self.test_client.heartbeat())
        mock_login.assert_called_once()
        self.mock_nuvla._cimi_post.assert_called_with(f"{self.mock_uuid}/heartbeat")

        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            self.mock_nuvla.is_authenticated.return_value = True
            self.mock_nuvla._cimi_post.side_effect = Exception(ValueError)
            self.test_client.heartbeat()
            mock_warning.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge_status_uuid')
    def test_telemetry(self, mock_status_uuid):
        mock_res = Mock(spec=CimiResource)
        mock_res.data = {'jobs': ['job1']}
        self.mock_nuvla.edit.return_value = mock_res
        self.assertEqual({'jobs': ['job1']}, self.test_client.telemetry({}, set()))


    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaEdgeSession')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.write_file')
    def test_save_current_state_to_file(self, mock_write, mock_session):
        self.test_client._save_current_state_to_file()
        mock_write.assert_called_once()


def test_from_session_store():
    ...


def test_from_nuvlaedge_credentials():
    ...


def test_from_agent_settings():
    ...
