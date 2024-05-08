
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch

import mock
from nuvla.api import Api
from nuvla.api.models import CimiResource, CimiCollection

import nuvlaedge.agent.nuvla.client_wrapper
from nuvlaedge.agent.nuvla.resources import NuvlaID, AutoNuvlaEdgeResource, AutoUpdateNuvlaEdgeTrackedResource
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper, NuvlaApiKeyTemplate, SessionValidationError


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

    def test_nuvlaedge_status_uuid_property(self):
        self.test_client._nuvlaedge_status_uuid = 'status-uuid_1'
        self.assertEqual('status-uuid_1', self.test_client.nuvlaedge_status_uuid)

        with patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge',
                   new_callable=mock.PropertyMock) as mock_nuvlaedge:
            self.test_client._nuvlaedge_status_uuid = None
            mock_res = Mock()
            mock_res.nuvlabox_status = 'status-uuid'
            mock_nuvlaedge.return_value = mock_res

            self.assertEqual('status-uuid', self.test_client.nuvlaedge_status_uuid)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._is_resource_available')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._init_resource')
    def test_nuvlaedge_property(self, mock_init, mock_available):
        self.test_client._resources = {'nuvlaedge': 'resource_1'}
        mock_available.return_value = True
        self.assertEqual('resource_1', self.test_client.nuvlaedge)
        mock_init.assert_not_called()

        mock_available.return_value = False
        self.assertEqual('resource_1', self.test_client.nuvlaedge)
        mock_init.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._is_resource_available')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._init_resource')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge',new_callable=mock.PropertyMock)
    def test_nuvlaedge_status_property(self, test_nuvlaedge, mock_init, mock_available):
        self.test_client._resources = {'nuvlaedge-status': 'resource_1'}
        mock_available.return_value = True
        self.assertEqual('resource_1', self.test_client.nuvlaedge_status)
        mock_init.assert_not_called()

        mock_available.return_value = False
        self.assertEqual('resource_1', self.test_client.nuvlaedge_status)
        mock_init.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._is_resource_available')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._init_resource')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge',new_callable=mock.PropertyMock)
    def test_vpn_credential_property(self, mock_nuvlaedge, mock_init, mock_available):
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            mock_res = Mock()
            mock_nuvlaedge.return_value = mock_res
            mock_res.vpn_server_id = None
            self.assertIsNone(self.test_client.vpn_credential)
            mock_warning.assert_called_once()

        mock_res.vpn_server_id = 'id_1'
        self.test_client._resources = {'vpn-credential': 'resource_1'}
        mock_available.return_value = True
        self.assertEqual('resource_1', self.test_client.vpn_credential)
        mock_init.assert_not_called()

        mock_available.return_value = False
        self.assertEqual('resource_1', self.test_client.vpn_credential)
        mock_init.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._is_resource_available')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper._init_resource')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge', new_callable=mock.PropertyMock)
    def test_vpn_server_property(self, mock_nuvlaedge, mock_init, mock_available):
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            mock_res = Mock()
            mock_nuvlaedge.return_value = mock_res
            mock_res.vpn_server_id = None
            self.assertIsNone(self.test_client.vpn_credential)
            mock_warning.assert_called_once()

        mock_res.vpn_server_id = 'id_1'
        self.test_client._resources = {'vpn-server': 'resource_1'}
        mock_available.return_value = True
        self.assertEqual('resource_1', self.test_client.vpn_server)
        mock_init.assert_not_called()

        mock_available.return_value = False
        self.assertEqual('resource_1', self.test_client.vpn_server)
        mock_init.assert_called_once()

    def test_is_resource_available(self):
        self.test_client._resources = {'resource_1': 'resource_1'}
        self.assertTrue(self.test_client._is_resource_available('resource_1'))

        self.test_client._resources = {}
        self.assertFalse(self.test_client._is_resource_available('resource_1'))

        self.test_client._resources = {'resource_1': None}
        self.assertFalse(self.test_client._is_resource_available('resource_1'))

    @patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.debug')
    def test_init_resource(self, mock_debug):
        mock_type = Mock(spec=AutoUpdateNuvlaEdgeTrackedResource)
        mock_res = Mock()
        mock_type.return_value = mock_res

        self.test_client._init_resource('resource_1', mock_type, NuvlaID('id'))
        mock_debug.assert_called_once()
        mock_res.force_update.assert_called_once()
        mock_type.assert_called_once()

    def test_login_nuvlaedge(self):
        mock_response = Mock()
        self.mock_nuvla.login_apikey.return_value = mock_response
        self.test_client.nuvlaedge_credentials = Mock()
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            mock_response.status_code = 401
            self.test_client.login_nuvlaedge()
            self.mock_nuvla.login_apikey.assert_called_once()
            mock_warning.assert_called_once()

        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.debug') as mock_debug:
            mock_response.status_code = 200
            self.test_client.login_nuvlaedge()
            mock_debug.assert_called_once()

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.save_current_state_to_file')
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

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge', new_callable=mock.PropertyMock)
    def test_commission(self, mock_nuvlaedge):
        mock_res = Mock()
        mock_nuvlaedge.return_value = mock_res
        self.mock_nuvla._cimi_post.return_value = None
        self.assertIsNone(self.test_client.commission({}))
        mock_res.force_update.assert_not_called()

        self.mock_nuvla._cimi_post.return_value = {'nice': 'response'}
        self.assertEqual(self.test_client.commission({}), {'nice': 'response'})
        mock_res.force_update.assert_called_once()
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

    def test_heartbeat(self):
        self.mock_nuvla._cimi_post.return_value = {'nice': 'response'}

        self.assertEqual({'nice': 'response'}, self.test_client.heartbeat())
        self.mock_nuvla._cimi_post.assert_called_with(f"{self.mock_uuid}/heartbeat")

        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
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
        self.test_client.nuvlaedge_credentials = Mock()
        self.test_client.save_current_state_to_file()
        self.assertEqual(3, mock_write.call_count)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.login_nuvlaedge')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaEdgeSession.model_validate')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.read_file')
    def test_from_session_store(self, mock_read, mock_validate, mock_login):
        test_file = 'file'

        mock_read.reset_mock()
        mock_read.return_value = 'session'
        mock_validate.return_value = Mock()
        self.assertIsInstance(NuvlaClientWrapper.from_session_store(test_file), NuvlaClientWrapper)
        mock_validate.assert_called_once_with('session')
        mock_login.assert_called_once()

        mock_read.reset_mock()
        mock_read.return_value = 'session'
        mock_validate.side_effect = ValueError('mock_exception')
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            with self.assertRaises(SessionValidationError):
                self.assertIsNone(NuvlaClientWrapper.from_session_store(test_file))
                mock_read.assert_called_once()
                mock_warning.assert_called_once()