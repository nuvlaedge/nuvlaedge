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

    @patch('nuvlaedge.agent.workers.commissioner.Commissioner._save_commissioned_data')
    def test_commission(self, mock_save):
        self.test_commissioner._last_payload = CommissioningAttributes(cluster_id="mock-cluster-id", tags=["mock-tags"])
        self.test_commissioner._current_payload = CommissioningAttributes(cluster_id="mock-cluster-id-2")

        expected_payload = {
            'cluster-id': 'mock-cluster-id-2',
            'removed': ['tags']
        }
        self.test_commissioner.nuvla_client.commission.return_value = True
        self.test_commissioner._commission()

        self.test_commissioner.nuvla_client.commission.assert_called_with(payload=expected_payload)
        mock_save.assert_called_once()
        self.assertEqual(self.test_commissioner._last_payload, self.test_commissioner._current_payload)

        mock_save.reset_mock()
        self.test_commissioner.nuvla_client.commission.reset_mock()

        # Without removing fields
        self.test_commissioner._last_payload = CommissioningAttributes(cluster_id="mock-cluster-id", tags=["mock-tags"])
        self.test_commissioner._current_payload = CommissioningAttributes(cluster_id="mock-cluster-id-2", tags=["mock-tags"])

        expected_payload = {
            'cluster-id': 'mock-cluster-id-2',
        }
        self.test_commissioner.nuvla_client.commission.return_value = True
        self.test_commissioner._commission()

        self.test_commissioner.nuvla_client.commission.assert_called_with(payload=expected_payload)
        mock_save.assert_called_once()
        self.assertEqual(self.test_commissioner._last_payload, self.test_commissioner._current_payload)

        # With failed commission
        self.test_commissioner.nuvla_client.commission.reset_mock()
        mock_save.reset_mock()
        self.test_commissioner.nuvla_client.commission.return_value = False
        self.test_commissioner._last_payload = CommissioningAttributes(cluster_id="mock-cluster-id", tags=["mock-tags"])
        self.test_commissioner._current_payload = CommissioningAttributes(cluster_id="mock-cluster-id-2",
                                                                          tags=["mock-tags"])

        self.test_commissioner._commission()
        mock_save.assert_not_called()
        self.test_commissioner.nuvla_client.commission.assert_called_with(payload=expected_payload)
        self.assertNotEqual(self.test_commissioner._last_payload, self.test_commissioner._current_payload)

    def test_nuvlaedge_uuid(self):
        self.test_commissioner.nuvla_client.nuvlaedge_uuid = 'nuvlaedge-id'
        self.assertEqual('nuvlaedge-id', self.test_commissioner.nuvlaedge_uuid)

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

    def test_cluster_data(self):
        self.test_commissioner.nuvla_client.nuvlaedge_uuid = 'nuvlaedge-id'

        mock_current_payload = Mock()
        self.test_commissioner._current_payload = mock_current_payload
        self.mock_coe.get_cluster_info.return_value = None

        self.test_commissioner._update_cluster_data()

        self.mock_coe.get_cluster_info.assert_called_with(default_cluster_name="cluster_nuvlaedge-id")
        mock_current_payload.update.assert_not_called()

        self.mock_coe.get_cluster_info.return_value = {'cluster-id': 'mock-cluster-id'}

        self.test_commissioner._update_cluster_data()
        mock_current_payload.update.assert_called_with({"cluster-id":'mock-cluster-id'})

    @patch('nuvlaedge.agent.workers.commissioner.Commissioner._build_nuvlaedge_endpoint')
    @patch('nuvlaedge.agent.workers.commissioner.Commissioner.get_tls_keys')
    def test_update_coe_data(self, mock_tls, mock_endpoint_build):
        mock_current_payload = Mock()
        self.test_commissioner._current_payload = mock_current_payload
        self.mock_coe.define_nuvla_infra_service.return_value = {'service': 'service'}
        self.mock_coe.ORCHESTRATOR_COE = "not swarm"

        mock_endpoint_build.return_value = "https://address:port"
        tls = {"ca": "ca", "cert": "cert", "key": "key"}
        mock_tls.return_value = tls

        self.test_commissioner._update_coe_data()

        mock_endpoint_build.assert_called_once()
        mock_tls.assert_called_once()
        self.mock_coe.define_nuvla_infra_service.assert_called_with("https://address:port", *tls)
        mock_current_payload.update.assert_called_with({'service': 'service'})

        self.mock_coe.ORCHESTRATOR_COE = "swarm"
        self.mock_coe.get_join_tokens.return_value = ('manager', 'worker')
        self.test_commissioner._update_coe_data()

        self.mock_coe.get_join_tokens.assert_called_once()
        self.assertEqual(mock_current_payload.swarm_token_manager, 'manager')
        self.assertEqual(mock_current_payload.swarm_token_worker, 'worker')

    @patch('nuvlaedge.agent.workers.commissioner.Commissioner._get_nuvlaedge_capabilities')
    @patch('nuvlaedge.agent.workers.commissioner.Commissioner._update_coe_data')
    @patch('nuvlaedge.agent.workers.commissioner.Commissioner._update_cluster_data')
    def test_update_attributes(self, mock_cluster_data, mock_update_coe, mock_get_capabilities):
        mock_ne_status = Mock()
        mock_ne_status.node_id = None
        mock_payload = Mock()
        self.test_commissioner._current_payload = mock_payload
        self.test_commissioner.nuvla_client.nuvlaedge_status = mock_ne_status
        mock_get_capabilities.return_value = 'capabilities'

        self.test_commissioner._update_attributes()

        mock_cluster_data.assert_not_called()
        mock_update_coe.assert_called_once()
        mock_get_capabilities.assert_called_once()
        self.assertEqual(mock_payload.capabilities, 'capabilities')

        mock_ne_status.node_id = 'node-id'
        self.test_commissioner._update_attributes()
        mock_cluster_data.assert_called_once()


