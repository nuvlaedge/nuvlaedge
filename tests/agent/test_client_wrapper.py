
from unittest import TestCase
from unittest.mock import Mock, patch

import mock
from nuvla.api import Api
from nuvla.api.models import CimiResource

from nuvlaedge.agent.settings import NuvlaApiKeyTemplate
from nuvlaedge.agent.common.util import from_irs, get_irs
from nuvlaedge.agent.nuvla.resources import NuvlaID, AutoUpdateNuvlaEdgeTrackedResource
from nuvlaedge.agent.nuvla.client_wrapper import (NuvlaClientWrapper,
                                                  SessionValidationError,
                                                  format_host,
                                                  logger)


class TestClientWrapper(TestCase):
    def setUp(self):
        self.mock_nuvla = Mock(spec=Api)
        self.mock_uuid = NuvlaID('nuvlabox/0000')
        self.host = 'https://mock_host.io'
        self.mock_insecure = True
        self.test_client = NuvlaClientWrapper(host=self.host,
                                              insecure=self.mock_insecure,
                                              nuvlaedge_uuid=self.mock_uuid)
        self.test_client.nuvlaedge_client = self.mock_nuvla
        self.test_client.irs = get_irs(self.mock_uuid, 'key_1', 'secret_1')

    def test_format_host(self):
        self.assertEqual('https://nuvla.io', format_host('nuvla.io'))
        self.assertEqual('http://nuvla.io', format_host('http://nuvla.io'))
        self.assertEqual('https://nuvla.io', format_host('https://nuvla.io'))
        self.assertEqual('https://test.nuvla.io', format_host('test.nuvla.io'))
        self.assertEqual('http://test.nuvla.io', format_host('http://test.nuvla.io'))
        self.assertEqual('https://test.nuvla.io', format_host('https://test.nuvla.io'))
        self.assertEqual('https://test.nuvla.io', format_host('https://test.nuvla.io'))

    def test_set_nuvlaedge_uuid(self):
        self.test_client.set_nuvlaedge_uuid(self.mock_uuid)
        self.assertEqual(self.test_client.nuvlaedge_uuid, self.mock_uuid)

    def test_host(self):
        self.assertEqual(self.test_client.host, self.host)

    def test_endpoint(self):
        self.assertEqual(self.test_client.endpoint, self.host)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge')
    def test_vpn_server_not_found(self, mock_nuvlaedge):
        mock_nuvlaedge.vpn_server_id = None
        self.assertIsNone(self.test_client.vpn_server)

    @patch('nuvlaedge.agent.nuvla.client_wrapper.logger')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge', new_callable=mock.PropertyMock)
    def test_update_nuvlaedge_resource_if_changed(self, mock_nuvlaedge_property, mock_logger):
        self.test_client._last_ne_resource_sync = "Now"
        self.assertFalse(self.test_client.update_nuvlaedge_resource_if_changed("Now"))
        mock_logger.debug.assert_not_called()

        mock_nuvlaedge = Mock()
        mock_nuvlaedge_property.return_value = mock_nuvlaedge

        self.assertTrue(self.test_client.update_nuvlaedge_resource_if_changed("Then"))
        mock_logger.debug.assert_called_once()
        mock_nuvlaedge.force_update.assert_called_once()
        self.assertEqual("Then", self.test_client._last_ne_resource_sync)


    def test_supported_nuvla_telemetry_fields_property(self):
        metadata = {
            "attributes": [
                {"name": "coe-resources"},
                {"name": "resources",
                 "child-types": [{"name": "container-stats"}]}
            ]
        }
        mock_get = Mock()
        mock_get.data = metadata
        self.mock_nuvla.get.return_value = mock_get
        telemetry_fields = self.test_client.supported_nuvla_telemetry_fields
        self.mock_nuvla.get.assert_called_once()
        self.assertEqual(['coe-resources', 'resources', 'resources.container-stats'],
                         telemetry_fields)
        self.assertIn('resources.container-stats', telemetry_fields)

        # assert cached
        self.test_client.supported_nuvla_telemetry_fields
        self.mock_nuvla.get.assert_called_once()

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
        self.assertEqual(from_irs(self.mock_uuid, self.test_client.irs), ('key_1', 'secret_1'))

        mock_login.return_value = False
        with self.assertLogs(logger, level='WARNING') as log:
            self.test_client.activate()
            self.assertTrue(any([('Could not log in after activation' in i) for i in log.output]))

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

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.nuvlaedge_status_uuid')
    def test_telemetry_patch(self, mock_status_uuid):
        mock_res = Mock(spec=CimiResource)
        mock_res.data = {'jobs': ['job1']}
        self.mock_nuvla.edit_patch.return_value = mock_res
        self.assertEqual({'jobs': ['job1']}, self.test_client.telemetry_patch([{}], set()))

    def test_log_debug_telemetry_jsonpatch(self):
        with self.assertLogs(logger, level='DEBUG') as log:
            self.test_client._log_debug_telemetry_jsonpatch([], [])
            self.assertGreater(len(log.output), 0)

        with self.assertLogs(logger, level='DEBUG') as log:
            self.test_client._log_debug_telemetry_jsonpatch([{'foo': 1, 'bar': 2}], [])
            r = list(filter(lambda x: 'WARNING' in x.levelname, log.records))
            self.assertEqual(1, len(r))
            self.assertIn('Error logging telemetry patch', r[0].message)

    # @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaEdgeSession')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.write_file')
    def test_save_current_state_to_file(self, mock_write):
        self.test_client.nuvlaedge_credentials = None
        self.test_client.save_current_state_to_file()
        self.assertEqual(1, mock_write.call_count)

        with patch('pathlib.Path.exists') as mock_path_exists:
            mock_path_exists.return_value = True
            mock_write.reset_mock()
            self.test_client.nuvlaedge_credentials = NuvlaApiKeyTemplate(key='key', secret='secret')
            self.test_client.save_current_state_to_file()
            self.assertEqual(3, mock_write.call_count)

    def test_find_nuvlaedge_id_from_nuvla_session(self):
        self.assertIsNone(self.test_client.find_nuvlaedge_id_from_nuvla_session())

        mock_get = Mock()
        uuid = '126f1242-5256-4435-9376-2dad10f2388a'
        mock_get.data = {'identifier': f'nuvlabox/{uuid}'}
        self.mock_nuvla.get.return_value = mock_get
        self.assertEqual(self.test_client.find_nuvlaedge_id_from_nuvla_session().uuid, uuid)

        ne_uuid = 'nuvlabox/56f49e36-6ca5-11ef-a8fd-4797009c58a7'
        mock_res = Mock(spec=CimiResource)
        mock_res.data = {'identifier': ne_uuid, 'user': ne_uuid}
        self.mock_nuvla.get.return_value = mock_res
        self.assertEqual(self.test_client.find_nuvlaedge_id_from_nuvla_session(), ne_uuid)

        self.mock_nuvla.current_session.side_effect = EOFError
        self.assertIsNone(self.test_client.find_nuvlaedge_id_from_nuvla_session())

    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.save_current_state_to_file')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaClientWrapper.login_nuvlaedge')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.NuvlaEdgeSession.model_validate')
    @patch('nuvlaedge.agent.nuvla.client_wrapper.read_file')
    def test_from_session_store(self, mock_read, mock_validate, mock_login, mock_save):
        test_file = 'file'

        mock_read.reset_mock()
        mock_read.return_value = 'session'
        mock_nuvlaedge_session = Mock()
        mock_nuvlaedge_session.irs = None
        mock_nuvlaedge_session.nuvlaedge_uuid = 'uuid'
        mock_nuvlaedge_session.credentials = NuvlaApiKeyTemplate(key='key', secret='secret')
        mock_validate.return_value = mock_nuvlaedge_session
        self.assertIsInstance(NuvlaClientWrapper.from_session_store(test_file), NuvlaClientWrapper)
        mock_validate.assert_called_once_with('session')
        mock_login.assert_called_once()
        mock_save.assert_not_called()

        mock_nuvlaedge_session.irs = None
        mock_nuvlaedge_session.nuvlaedge_uuid = None
        NuvlaClientWrapper.from_session_store(test_file)

        mock_nuvlaedge_session.nuvlaedge_uuid = 'uuid'
        mock_nuvlaedge_session.irs = get_irs('uuid', 'key', 'secret')
        NuvlaClientWrapper.from_session_store(test_file)

        mock_read.reset_mock()
        mock_read.return_value = 'session'
        mock_validate.side_effect = ValueError('mock_exception')
        with patch('nuvlaedge.agent.nuvla.client_wrapper.logging.Logger.warning') as mock_warning:
            with self.assertRaises(SessionValidationError):
                self.assertIsNone(NuvlaClientWrapper.from_session_store(test_file))
                mock_read.assert_called_once()
                mock_warning.assert_called_once()


