from queue import Queue
from unittest import TestCase
from unittest.mock import Mock, patch

import nuvlaedge.agent.workers.commissioner
from nuvlaedge.agent.workers.commissioner import Commissioner
from nuvlaedge.agent.workers.commissioner import CommissioningAttributes
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient
from pathlib import Path
import json


class TestCommissioner(TestCase):
    def setUp(self):
        self.mock_coe = Mock(spec=COEClient)
        self.mock_nuvla_client = Mock(spec=NuvlaClientWrapper)
        self.mock_status_channel = Mock(spec=Queue)
        self.test_commissioner = Commissioner(self.mock_coe,
                                              self.mock_nuvla_client,
                                              self.mock_status_channel)

    @patch('nuvlaedge.agent.workers.commissioner.VPNHandler.get_vpn_ip')
    def test_build_nuvlaedge_endpoint(self, mock_vpn_ip):
        self.test_commissioner.coe_client.get_api_ip_port.return_value = 'address', 'port'
        mock_vpn_ip.return_value = 'vpn_address'
        self.assertEqual("https://vpn_address:port", self.test_commissioner._build_nuvlaedge_endpoint())
        mock_vpn_ip.return_value = None
        self.assertEqual("https://address:port", self.test_commissioner._build_nuvlaedge_endpoint())

    @patch.object(Path, 'open')
    def test_get_tls_keys(self, mock_path):
        mock_file1 = Mock()
        mock_file2 = Mock()
        mock_file3 = Mock()
        mock_path.return_value.__enter__.side_effect = [mock_file1, mock_file2, mock_file3]
        mock_file1.read.return_value = "ca"
        mock_file2.read.return_value = "cert"
        mock_file3.read.return_value = "key"
        self.assertEqual(("ca", "cert", "key"), self.test_commissioner.get_tls_keys())

    @patch('nuvlaedge.agent.workers.commissioner.file_exists_and_not_empty')
    def test_load_previous_commission(self, mock_exists):
        mock_exists.return_value = False
        self.test_commissioner._load_previous_commission()
        mock_exists.reset_mock()
        mock_exists.return_value = True
        mock_file = Mock()
        with patch.object(Path, 'open') as mock_open:
            with patch.object(json, 'load') as mock_json:
                mock_open.return_value.__enter__.return_value = mock_file
                load_dict = {'nuvlaedge_uuid': 'nuvlaedge-id'}
                mock_json.return_value = load_dict
                self.test_commissioner.nuvla_client._nuvlaedge_uuid = 'random'
                self.test_commissioner._load_previous_commission()
                self.assertIsNone(self.test_commissioner._last_payload.tags)
                self.test_commissioner.nuvla_client._nuvlaedge_uuid = 'nuvlaedge-id'
                self.test_commissioner._load_previous_commission()
                mock_json.side_effect = json.JSONDecodeError('msg', 'doc', 1)
                self.test_commissioner._load_previous_commission()

    @patch.object(NuvlaClientWrapper, 'commission')
    @patch('nuvlaedge.agent.workers.commissioner.write_file')
    def test_commission(self, mock_write, test_wrapper):
        self.test_commissioner._current_payload.tags = ['tag']
        test_wrapper.return_value = True
        with patch.object(CommissioningAttributes, 'model_dump') as mock_model_dump:
            mock_model_dump.return_value = {'nuvlaedge_uuid': ''}
            self.test_commissioner.nuvla_client._nuvlaedge_uuid = 'nuvlaedge-id'
            self.test_commissioner._commission()
            self.assertEqual(self.test_commissioner._last_payload.tags, self.test_commissioner._current_payload.tags)
            mock_write.assert_called_once()

    @patch('nuvlaedge.agent.workers.commissioner.NuvlaEdgeStatusHandler.running')
    @patch('nuvlaedge.agent.workers.commissioner.CommissioningAttributes')
    def test_run(self, mock_attrs, mock_running):
        self.test_commissioner.coe_client = Mock()
        self.test_commissioner.coe_client.get_cluster_info.return_value = {'cluster_info': ''}
        self.test_commissioner._commission = Mock()
        self.test_commissioner._update_coe_data = Mock()
        self.test_commissioner._update_cluster_data = Mock()
        self.test_commissioner._update_attributes = Mock()

        self.test_commissioner._last_payload = 't'
        mock_attrs.return_value = 't'
        self.test_commissioner.nuvla_client._nuvlaedge_uuid = 'nuvlaedge-id'
        self.test_commissioner.run()
        self.test_commissioner._commission.assert_not_called()

