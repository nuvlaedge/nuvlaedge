from pathlib import Path
from queue import Queue
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open, PropertyMock, MagicMock

import docker.errors

from nuvlaedge.agent.worker import WorkerExitException
from nuvlaedge.agent.workers.vpn_handler import VPNHandler, VPNConfig, VPNConfigurationMissmatch, \
    VPNCredentialCreationTimeOut
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


@patch('nuvlaedge.agent.workers.vpn_handler.VPNConfig.model_dump')
def test_dump_to_template(mock_model_dump):
    test_vpn_config = VPNConfig()
    mock_model_dump.return_value = {}
    test_vpn_config.vpn_intermediate_ca = ['mock_ca_1', 'mock_ca_2']
    test_vpn_config.vpn_intermediate_ca_is = ['mock_ca_1', 'mock_ca_2']
    assert test_vpn_config.dump_to_template() == {"vpn_intermediate_ca": 'mock_ca_1 mock_ca_2',
                                                  "vpn_intermediate_ca_is": 'mock_ca_1 mock_ca_2'}
    mock_model_dump.assert_called_once()


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
                vpn_channel=self.mock_vpn_channel,
                status_channel=self.mock_status_channel,
                vpn_extra_conf=self.mock_vpn_extra_conf)

    @patch('nuvlaedge.agent.workers.vpn_handler.NuvlaEdgeStatusHandler')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.exists')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.mkdir')
    def test_init(self, mock_mkdir, mock_exists, mock_status_handler):
        mock_exists.return_value = False
        self.test_vpn_handler = VPNHandler(
            coe_client=self.mock_coe_client,
            nuvla_client=self.mock_nuvla_client,
            vpn_channel=self.mock_vpn_channel,
            status_channel=self.mock_status_channel,
            vpn_extra_conf=self.mock_vpn_extra_conf)
        mock_mkdir.assert_called_once()
        mock_status_handler.starting.assert_called_once()

    @patch('nuvlaedge.agent.workers.vpn_handler.utils')
    def test_certificates_exists(self, mock_utils):
        mock_utils.file_exists_and_not_empty.side_effect = [True, True]
        self.assertTrue(self.test_vpn_handler.certificates_exists())
        self.assertEqual(2, mock_utils.file_exists_and_not_empty.call_count)

        mock_utils.file_exists_and_not_empty.side_effect = [True, False]
        self.assertFalse(self.test_vpn_handler.certificates_exists())

        mock_utils.file_exists_and_not_empty.side_effect = [False, False]
        self.assertFalse(self.test_vpn_handler.certificates_exists())

    @patch('nuvlaedge.agent.workers.vpn_handler.utils')
    def test_get_vpn_ip(self, mock_utils):
        mock_utils.file_exists_and_not_empty.return_value = False
        self.assertIsNone(self.test_vpn_handler.get_vpn_ip())

        mock_utils.file_exists_and_not_empty.return_value = True
        with patch.object(Path, 'open', mock_open(read_data='1.1.1.1')):
            self.assertEqual(self.test_vpn_handler.get_vpn_ip(), '1.1.1.1',
                             'Failed to get VPN IP')

    def test_check_vpn_client_state(self):
        self.mock_coe_client.is_vpn_client_running.reset_mock()
        self.mock_coe_client.is_vpn_client_running.return_value = False
        self.assertEqual(self.test_vpn_handler.check_vpn_client_state(), (True, False))

        self.mock_coe_client.is_vpn_client_running.reset_mock()
        self.mock_coe_client.is_vpn_client_running.return_value = True
        self.assertEqual(self.test_vpn_handler.check_vpn_client_state(), (True, True))

        self.mock_coe_client.is_vpn_client_running.side_effect = docker.errors.NotFound('mock_exception')
        self.assertEqual(self.test_vpn_handler.check_vpn_client_state(), (False, False))

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.certificates_exists')
    @patch('nuvlaedge.agent.workers.vpn_handler.time')
    def test_wait_certificates(self, mock_time, mock_cert_exists):
        mock_time.perf_counter.side_effect = [0, 3, 5, 25]
        mock_cert_exists.side_effect = [False, True]

        self.test_vpn_handler.wait_certificates_ready()
        self.assertEqual(mock_time.perf_counter.call_count, 3)
        mock_time.sleep_assert_called_once_with(0.3)

        with self.assertRaises(TimeoutError):
            mock_time.perf_counter.side_effect = [0, 3, 25]
            mock_cert_exists.side_effect = [False, True]
            self.test_vpn_handler.wait_certificates_ready()

    @patch('nuvlaedge.agent.workers.vpn_handler.time')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.save_credential')
    def test_wait_credential_creation(self, mock_save_creds, mock_time):
        mock_time.perf_counter.side_effect = [0, 25]
        self.assertFalse(self.test_vpn_handler.wait_credential_creation())
        mock_save_creds.assert_not_called()

        mock_time.perf_counter.side_effect = [0, 3, 5, 25]

        self.mock_nuvla_client.vpn_credential.model_copy.return_value = {'mock_key': 'mock_value'}
        self.assertTrue(self.test_vpn_handler.wait_credential_creation())
        self.assertEqual(self.test_vpn_handler.vpn_credential, {'mock_key': 'mock_value'})
        mock_time.sleep.assert_not_called()

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.wait_certificates_ready')
    @patch('nuvlaedge.agent.workers.vpn_handler.util')
    @patch('nuvlaedge.agent.workers.vpn_handler.Path.unlink')
    @patch('nuvlaedge.agent.workers.vpn_handler.utils')
    def test_generate_certificates(self, mock_utils, mock_unlink, mock_agent_util, mock_wait_certs):
        mock_utils.file_exists_and_not_empty.side_effect = [False, False]
        mock_agent_util.execute_cmd.return_value = {'stdout': 'mock_stdout',
                                                    'stderr': 'mock_stderr',
                                                    'returncode': 1}
        self.mock_nuvla_client.nuvlaedge_uuid = 'nuvlabox/uuid'

        with patch('nuvlaedge.agent.workers.vpn_handler.logging.Logger.error') as mock_error:
            self.test_vpn_handler.generate_certificates()
            mock_unlink.assert_not_called()
            mock_agent_util.execute_cmd.assert_called_once()
            mock_wait_certs.assert_not_called()
            mock_error.assert_called_once_with(
                'Cannot generate certificates for VPN connection: mock_stdout | mock_stderr')

            mock_utils.file_exists_and_not_empty.side_effect = [True, True]
            mock_agent_util.execute_cmd.return_value = {'stdout': 'mock_stdout',
                                                        'stderr': 'mock_stderr',
                                                        'returncode': 0}
            self.test_vpn_handler.generate_certificates()
            self.assertEqual(2, mock_unlink.call_count)
            mock_wait_certs.assert_called_once()

            mock_utils.file_exists_and_not_empty.side_effect = [True, True]
            mock_wait_certs.reset_mock()
            self.test_vpn_handler.generate_certificates(wait=False)
            mock_wait_certs.assert_not_called()

    def test_trigger_commission(self):
        with patch.object(Path, 'open', mock_open(read_data='read_data')):
            self.test_vpn_handler.trigger_commission()
            self.mock_vpn_channel.put.assert_called_with('read_data')

    def test_vpn_needs_commission(self):
        self.mock_nuvla_client.vpn_credential = False
        self.assertTrue(self.test_vpn_handler.vpn_needs_commission())

        mock_vpn_credential = Mock()
        mock_vpn_credential_2 = Mock()
        self.mock_nuvla_client.vpn_credential = mock_vpn_credential_2
        self.test_vpn_handler.vpn_credential = mock_vpn_credential
        self.assertTrue(self.test_vpn_handler.vpn_needs_commission())

        self.test_vpn_handler.vpn_credential = mock_vpn_credential_2
        mock_vpn_server = Mock()
        mock_vpn_server.id = 'id'
        self.test_vpn_handler.vpn_server = mock_vpn_server
        self.mock_nuvla_client.nuvlaedge.vpn_server_id = 'different_id'
        self.assertTrue(self.test_vpn_handler.vpn_needs_commission())

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = 'id'
        self.assertFalse(self.test_vpn_handler.vpn_needs_commission())

    def test_get_vpn_key(self):
        with patch.object(Path, 'open', mock_open(read_data='read_data')):
            self.assertEqual(self.test_vpn_handler.get_vpn_key(), 'read_data')

    def test_map_endpoints(self):
        mock_vpn_server = Mock()
        sample_connection = {
            'endpoint': 'endpoint_1',
            'port': 'port_1',
            'protocol': 'protocol_1'
        }
        mock_vpn_server.vpn_endpoints = [sample_connection, sample_connection]
        self.test_vpn_handler.vpn_server = mock_vpn_server
        self.assertEqual(self.test_vpn_handler.map_endpoints(),
                         f"\n<connection>\nremote endpoint_1 port_1 protocol_1\n</connection>\n"
                         f"\n<connection>\nremote endpoint_1 port_1 protocol_1\n</connection>\n")

    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.save_vpn_config')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.map_endpoints')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.get_vpn_key')
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
        self.test_vpn_handler.configure_vpn_client()

        # Assert
        self.assertEqual(2, mock_vpn_config.update.call_count)
        mock_save_vpn_config.assert_called_once()

    @patch('nuvlaedge.agent.workers.vpn_handler.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.check_vpn_client_state')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.vpn_needs_commission')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.generate_certificates')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.trigger_commission')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.wait_credential_creation')
    @patch('nuvlaedge.agent.workers.vpn_handler.VPNHandler.configure_vpn_client')
    def test_run(self,
                 mock_configure_vpn_client,
                 mock_wait_credential,
                 mock_trigger_commission,
                 mock_generate_certificates,
                 mock_needs_commission,
                 mock_client_state,
                 mock_running):

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = None
        with self.assertRaises(WorkerExitException):
            self.test_vpn_handler.run()
            mock_running.assert_called_once()

        self.mock_nuvla_client.nuvlaedge.vpn_server_id = "infrastructure-service/uuid"
        mock_client_state.return_value = (False, False)
        with self.assertRaises(VPNConfigurationMissmatch):
            self.test_vpn_handler.run()

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


