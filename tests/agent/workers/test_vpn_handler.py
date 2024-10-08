from pathlib import Path
from queue import Queue
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, PropertyMock

import docker.errors

from nuvlaedge.agent.workers.vpn_handler import (VPNHandler,
                                                 VPNConfig,
                                                 VPNCredentialCreationTimeOut)
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.nuvla.resources import (InfrastructureServiceResource,
                                             CredentialResource)
from nuvlaedge.agent.nuvla.resources.nuvlaedge_res import State
from nuvlaedge.agent.orchestrator import COEClient


class TestVPNConfig(TestCase):

    def setUp(self):
        self.test_vpn_config = VPNConfig()

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNConfig.model_dump')
    def test_dump_to_template(self, mock_model_dump):
        mock_model_dump.return_value = {}
        self.test_vpn_config.vpn_intermediate_ca = ['mock_ca_1', 'mock_ca_2']
        self.test_vpn_config.vpn_intermediate_ca_is = ['mock_ca_1', 'mock_ca_2']
        assert self.test_vpn_config.dump_to_template() == {"vpn_intermediate_ca": 'mock_ca_1 mock_ca_2',
                                                           "vpn_intermediate_ca_is": 'mock_ca_1 mock_ca_2'}
        mock_model_dump.assert_called_once()

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNConfig.model_dump')
    def test_update(self, mock_model_dump):
        mock_model_dump.return_value = {}
        self.test_vpn_config.update(self.test_vpn_config)

        mock_model_dump.return_value = {'wrong-key': 'val', 'vpn_extra_config': 'verb 6'}
        self.test_vpn_config.update(self.test_vpn_config)


class TestVPNHandler(TestCase):
    def setUp(self):
        self.mock_coe_client = Mock(spec=COEClient)
        self.mock_nuvla_client = Mock(spec=NuvlaClientWrapper)
        self.mock_vpn_channel = Mock(spec=Queue)
        self.mock_status_channel = Mock(spec=Queue)
        self.mock_vpn_extra_conf = ""
        with patch('nuvlaedge.agent.workers.vpn_handler.Path.exists') as mock_exists:
            mock_exists.return_value = True
            self.test_vpn_handler = VPNHandler(
                coe_client=self.mock_coe_client,
                nuvla_client=self.mock_nuvla_client,
                status_channel=self.mock_status_channel,
                vpn_enable_flag=1,
                vpn_extra_conf=self.mock_vpn_extra_conf)

    @patch('nuvlaedge.agent.workers.vpn_handler.NuvlaEdgeStatusHandler')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.exists')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.mkdir')
    def test_init(self, mock_mkdir, mock_exists, mock_status_handler):
        mock_exists.return_value = False
        self.test_vpn_handler = VPNHandler(
            coe_client=self.mock_coe_client,
            nuvla_client=self.mock_nuvla_client,
            status_channel=self.mock_status_channel,
            vpn_enable_flag=1,
            vpn_extra_conf=self.mock_vpn_extra_conf)
        mock_mkdir.assert_called_once()
        mock_status_handler.starting.assert_called_once()

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations')
    def test_certificates_exists(self, mock_utils):
        mock_utils.file_exists_and_not_empty.side_effect = [True, True]
        self.assertTrue(self.test_vpn_handler._certificates_exists())
        self.assertEqual(2, mock_utils.file_exists_and_not_empty.call_count)

        mock_utils.file_exists_and_not_empty.side_effect = [True, False]
        self.assertFalse(self.test_vpn_handler._certificates_exists())

        mock_utils.file_exists_and_not_empty.side_effect = [False, False]
        self.assertFalse(self.test_vpn_handler._certificates_exists())

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations')
    def test_get_vpn_ip(self, mock_fileOps):
        mock_fileOps.read_file.return_value = None
        self.assertIsNone(self.test_vpn_handler.get_vpn_ip())

        vpn_ip = '1.1.1.1'

        mock_fileOps.read_file.return_value = vpn_ip
        self.assertEqual(self.test_vpn_handler.get_vpn_ip(), vpn_ip,
                             'Failed to get VPN IP')

        mock_fileOps.read_file.return_value = f'{vpn_ip}\n'
        self.assertEqual(self.test_vpn_handler.get_vpn_ip(), vpn_ip)

        mock_fileOps.read_file.side_effect = IOError
        self.assertIsNone(self.test_vpn_handler.get_vpn_ip())

    def test_check_vpn_client_state(self):
        self.mock_coe_client.is_vpn_client_running.reset_mock()
        self.mock_coe_client.is_vpn_client_running.return_value = False
        self.assertEqual(self.test_vpn_handler._check_vpn_client_state(), (True, False))

        self.mock_coe_client.is_vpn_client_running.reset_mock()
        self.mock_coe_client.is_vpn_client_running.return_value = True
        self.assertEqual(self.test_vpn_handler._check_vpn_client_state(), (True, True))

        self.mock_coe_client.is_vpn_client_running.side_effect = docker.errors.NotFound('mock_exception')
        self.assertEqual(self.test_vpn_handler._check_vpn_client_state(), (False, False))

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._certificates_exists')
    @patch('nuvlaedge.agent.workers.vpn_handler.time')
    def test_wait_certificates(self, mock_time, mock_cert_exists):
        mock_time.perf_counter.side_effect = [0, 3, 5, 25]
        mock_cert_exists.side_effect = [False, True]

        self.test_vpn_handler._wait_certificates_ready()
        self.assertEqual(mock_time.perf_counter.call_count, 3)
        mock_time.sleep_assert_called_once_with(0.3)

        with self.assertRaises(TimeoutError):
            mock_time.perf_counter.side_effect = [0, 3, 25]
            mock_cert_exists.side_effect = [False, True]
            self.test_vpn_handler._wait_certificates_ready()

    @patch('nuvlaedge.agent.workers.vpn_handler.time')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._save_vpn_credential')
    def test_wait_credential_creation(self, mock_save_creds, mock_time):
        mock_time.perf_counter.side_effect = [0, 25]
        self.assertFalse(self.test_vpn_handler._wait_credential_creation())
        mock_save_creds.assert_not_called()

        mock_time.perf_counter.side_effect = [0, 3, 5, 25]
        self.mock_nuvla_client.vpn_credential.model_copy.return_value = {'mock_key': 'mock_value'}
        self.assertTrue(self.test_vpn_handler._wait_credential_creation())
        self.assertEqual(self.test_vpn_handler.vpn_credential, {'mock_key': 'mock_value'})
        mock_time.sleep.assert_not_called()

        mock_time.perf_counter.side_effect = [0, 1, 3]
        self.mock_nuvla_client.vpn_credential.vpn_certificate = None
        self.assertFalse(self.test_vpn_handler._wait_credential_creation(2))
        mock_time.sleep.assert_called()

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._wait_certificates_ready')
    @patch('nuvlaedge.agent.workers.vpn_handler.util')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.unlink')
    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations')
    def test_generate_certificates(self, mock_utils, mock_unlink, mock_agent_util, mock_wait_certs):
        mock_utils.file_exists_and_not_empty.side_effect = [False, False]
        mock_agent_util.execute_cmd.return_value = {'stdout': 'mock_stdout',
                                                    'stderr': 'mock_stderr',
                                                    'returncode': 1}
        self.mock_nuvla_client.nuvlaedge_uuid = 'nuvlabox/uuid'

        with patch('nuvlaedge.agent.workers.vpn_handler.logging.Logger.error') as mock_error:
            self.test_vpn_handler._generate_certificates()
            mock_unlink.assert_not_called()
            mock_agent_util.execute_cmd.assert_called_once()
            mock_wait_certs.assert_not_called()
            mock_error.assert_called_once_with(
                'Cannot generate certificates for VPN connection: mock_stdout | mock_stderr')

            mock_utils.file_exists_and_not_empty.side_effect = [True, True]
            mock_agent_util.execute_cmd.return_value = {'stdout': 'mock_stdout',
                                                        'stderr': 'mock_stderr',
                                                        'returncode': 0}
            self.test_vpn_handler._generate_certificates()
            self.assertEqual(2, mock_unlink.call_count)
            mock_wait_certs.assert_called_once()

            mock_utils.file_exists_and_not_empty.side_effect = [True, True]
            mock_wait_certs.reset_mock()
            self.test_vpn_handler._generate_certificates(wait=False)
            mock_wait_certs.assert_not_called()

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations')
    @patch('nuvlaedge.agent.workers.vpn_handler.NuvlaEdgeStatusHandler')
    def test_trigger_commission(self, mock_status_handler, mock_fileOps):
        mock_fileOps.read_file.return_value = 'read_data'
        self.mock_nuvla_client.commission.return_value = {'vpn_csr': 'read_data'}
        with patch('nuvlaedge.agent.workers.vpn_handler.logging.Logger.debug') as mock_debug:
            self.test_vpn_handler._trigger_commission()
            self.assertEqual(3, mock_debug.call_count)

        self.mock_nuvla_client.commission.return_value = None
        with patch('nuvlaedge.agent.workers.vpn_handler.logging.Logger.error') as mock_error:
            self.test_vpn_handler._trigger_commission()
            mock_error.assert_called_once_with("Error commissioning VPN.")
            mock_status_handler.failing.assert_called_once()
        # self.mock_vpn_channel.put.assert_called_with('read_data')

    def test_is_nuvlaedge_commissioned(self):
        self.mock_nuvla_client.nuvlaedge.state = State.COMMISSIONED
        self.assertTrue(self.test_vpn_handler._is_nuvlaedge_commissioned())

        not_commissioned_states = (State.NEW,
                                   State.ACTIVATED,
                                   State.DECOMMISSIONED,
                                   State.DECOMMISSIONING,
                                   State.UNKNOWN)

        for s in not_commissioned_states:
            self.mock_nuvla_client.nuvlaedge.state = s
            self.assertFalse(self.test_vpn_handler._is_nuvlaedge_commissioned())

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._is_nuvlaedge_commissioned')
    def test_vpn_needs_commission(self, mock_is_commissioned):
        mock_is_commissioned.return_value = False
        self.assertFalse(self.test_vpn_handler._vpn_needs_commission())

        self.mock_nuvla_client.vpn_credential.vpn_certificate = False
        mock_is_commissioned.return_value = True
        self.assertTrue(self.test_vpn_handler._vpn_needs_commission())

        mock_vpn_credential = Mock()
        mock_vpn_credential_2 = Mock()
        self.mock_nuvla_client.vpn_credential = mock_vpn_credential_2
        self.test_vpn_handler.vpn_credential = mock_vpn_credential
        self.assertTrue(self.test_vpn_handler._vpn_needs_commission())

        self.test_vpn_handler.vpn_credential = mock_vpn_credential_2
        mock_vpn_server = Mock()
        mock_vpn_server.id = 'id'
        self.test_vpn_handler.vpn_server = mock_vpn_server
        self.mock_nuvla_client.nuvlaedge.vpn_server_id = 'different_id'
        self.assertTrue(self.test_vpn_handler._vpn_needs_commission())

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = 'id'
        self.assertFalse(self.test_vpn_handler._vpn_needs_commission())

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations')
    def test_get_vpn_key(self, mock_fileOps):
        mock_fileOps.read_file.return_value = 'read_data'
        self.assertEqual(self.test_vpn_handler._get_vpn_key(), 'read_data')

    def test_map_endpoints(self):
        mock_vpn_server = Mock()
        sample_connection = {
            'endpoint': 'endpoint_1',
            'port': 'port_1',
            'protocol': 'protocol_1'
        }
        mock_vpn_server.vpn_endpoints = [sample_connection, sample_connection]
        self.test_vpn_handler.vpn_server = mock_vpn_server
        self.assertEqual(self.test_vpn_handler._map_endpoints(),
                         f"\n<connection>\nremote endpoint_1 port_1 protocol_1\n</connection>\n"
                         f"\n<connection>\nremote endpoint_1 port_1 protocol_1\n</connection>\n")

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._save_vpn_config')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._map_endpoints')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._get_vpn_key')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNConfig.update')
    @patch('nuvlaedge.agent.workers.vpn_handler.string.Template')
    def test_configure_vpn_client(self,
                                  mock_template,
                                  mock_update,
                                  mock_vpn_key,
                                  mock_map_endpoints,
                                  mock_save_vpn_config):

        mock_vpn_config = MagicMock()
        mock_vpn_server = MagicMock()
        mock_vpn_credential = MagicMock()

        self.test_vpn_handler.vpn_config = mock_vpn_config
        self.test_vpn_handler.vpn_server = mock_vpn_server
        self.test_vpn_handler.vpn_credential = mock_vpn_credential
        
        mock_vpn_key.return_value = 'test_vpn_key'
        mock_map_endpoints.return_value = 'test_endpoints'
        mock_vpn_config.dump_to_template.return_value = 'test_template'

        # Act
        self.test_vpn_handler._configure_vpn_client()

        # Assert
        self.assertEqual(2, mock_vpn_config.update.call_count)
        mock_save_vpn_config.assert_called_once()

        self.test_vpn_handler.vpn_extra_conf = None
        self.test_vpn_handler._configure_vpn_client()
        self.assertFalse(mock_vpn_config.vpn_extra_config)
        self.assertEqual(mock_vpn_config.vpn_extra_config, '')

    @patch('nuvlaedge.agent.workers.vpn_handler.NuvlaEdgeStatusHandler')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._check_vpn_client_state')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._vpn_needs_commission')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._generate_certificates')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._trigger_commission')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._wait_credential_creation')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler._configure_vpn_client')
    def test_run(self,
                 mock_configure_vpn_client,
                 mock_wait_credential,
                 mock_trigger_commission,
                 mock_generate_certificates,
                 mock_needs_commission,
                 mock_client_state,
                 mock_status):

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = None
        self.test_vpn_handler.run()
        mock_status.stopped.assert_called_once()

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = "infrastructure-service/uuid"
        mock_client_state.return_value = (False, False)
        self.test_vpn_handler.run()
        mock_status.failing.assert_called_once()

        mock_client_state.return_value = (True, False)
        mock_needs_commission.return_value = False
        with patch('nuvlaedge.agent.workers.vpn_handler.logging.Logger.info') as mock_info:
            self.assertIsNone(self.test_vpn_handler.run())
            mock_info.assert_called_once_with("VPN credentials aligned. No need for commissioning")

        mock_needs_commission.return_value = True
        with self.assertRaises(VPNCredentialCreationTimeOut):
            mock_wait_credential.return_value = False
            self.test_vpn_handler.run()
            mock_trigger_commission.assert_called_once()
            mock_generate_certificates.assert_called_once()

        mock_wait_credential.return_value = True
        self.test_vpn_handler.run()
        mock_configure_vpn_client.assert_called_once()

        mock_status.reset_mock()
        mock_client_state.return_value = (False, False)
        self.test_vpn_handler.vpn_enable_flag = 0
        self.test_vpn_handler.run()
        mock_status.stopped.assert_called_once()

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations.read_file')
    def test_load_vpn_config(self, mock_read_file):
        mock_read_file.return_value = {'vpn_shared_key': 'shared'}
        self.test_vpn_handler._load_vpn_config()
        self.assertEqual(self.test_vpn_handler.vpn_config.vpn_shared_key, 'shared')

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations.write_file')
    def test_save_vpn_config(self, mock_write_file):
        self.test_vpn_handler._save_vpn_config('')
        self.assertEqual(mock_write_file.call_count, 2)

    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations.read_file')
    def test_load_vpn_server(self, mock_read_file):
        mock_read_file.return_value = None
        self.test_vpn_handler._load_vpn_server()
        self.assertIsNone(self.test_vpn_handler.vpn_server.vpn_common_name_prefix)

        with patch('nuvlaedge.agent.workers.vpn_handler.file_exists_and_not_empty') as mock_file_exists:
            mock_file_exists.return_value = True

            infra_service_resource = InfrastructureServiceResource(vpn_ca_certificate='ca')
            mock_nuvla_client_vpn_server = PropertyMock(return_value=infra_service_resource)
            type(self.mock_nuvla_client).vpn_server = mock_nuvla_client_vpn_server
            self.test_vpn_handler._load_vpn_server()
            self.assertEqual(self.test_vpn_handler.vpn_server.vpn_ca_certificate, 'ca')

            mock_read_file.return_value = {'vpn_scope': 'customer'}
            self.test_vpn_handler._load_vpn_server()
            self.assertEqual(self.test_vpn_handler.vpn_server.vpn_scope, 'customer')

    @patch('nuvlaedge.agent.workers.vpn_handler.file_exists_and_not_empty')
    @patch('nuvlaedge.agent.workers.vpn_handler.file_operations.read_file')
    def test_load_vpn_credential(self, mock_read_file, mock_file_exists):
        mock_read_file.return_value = None
        mock_file_exists.return_value = True

        credential_resource = CredentialResource(vpn_certificate='cert')
        mock_nuvla_client_vpn_credential = PropertyMock(return_value=credential_resource)
        type(self.mock_nuvla_client).vpn_credential = mock_nuvla_client_vpn_credential
        self.test_vpn_handler._load_vpn_credential()
        self.assertEqual(self.test_vpn_handler.vpn_credential.vpn_certificate, 'cert')

        mock_read_file.return_value = {'vpn_certificate_owner': 'toto'}
        self.test_vpn_handler._load_vpn_credential()
        self.assertEqual(self.test_vpn_handler.vpn_credential.vpn_certificate_owner, 'toto')
