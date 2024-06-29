from pathlib import Path
from unittest import TestCase
from mock import mock, patch, PropertyMock


from nuvlaedge.common.data_gateway import DataGatewayPub, DataGatewayConfig


class TestDataGatewayPub(TestCase):
    def setUp(self):
        self.mock_mqtt_client = mock.MagicMock()
        self.mock_endpoint = 'data-gateway'
        self.mock_port = 1883
        self.mock_timeout = 90
        self.dw_conf = DataGatewayConfig(
            enabled=True,
            endpoint=self.mock_endpoint,
            port=self.mock_port,
            ping_interval=self.mock_timeout
        )
        self.conf_path = Path('/tmp/dw_config.json')
        self.mock_data_gateway = DataGatewayPub(config_file=self.conf_path)

        self.mock_data_gateway.client = self.mock_mqtt_client

    @patch('nuvlaedge.common.data_gateway.logger')
    def test_connect(self, mock_logger):

        self.mock_data_gateway.connect()
        self.mock_mqtt_client.connect.assert_called_once_with(host=self.mock_endpoint,
                                                              port=self.mock_port,
                                                              keepalive=self.mock_timeout)
        self.mock_mqtt_client.loop_start.assert_called_once()
        self.assertEqual(2, mock_logger.info.call_count)

        mock_logger.info.reset_mock()
        self.mock_data_gateway.client.connect.side_effect = Exception('mock_exception')
        self.mock_data_gateway.connect()
        mock_logger.error.assert_called_once()
        mock_logger.info.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.file_exists_and_not_empty')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.has_config_changed')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub._read_config')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.is_connected', new_callable=PropertyMock)
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.connect')
    def test_is_dw_available(self,
                             mock_connect, mock_is_connected,
                             mock_read_config, mock_conf_change,
                             mock_file_exists, mock_logger):
        mock_file_exists.return_value = True
        mock_conf_change.return_value = True

        self.assertFalse(self.mock_data_gateway.is_dw_available())
        mock_read_config.assert_called_once()
        mock_logger.info.assert_called_once_with('Data gateway is not yet enabled')

        mock_logger.reset_mock()

        self.mock_data_gateway.data_gateway_config = self.dw_conf
        mock_is_connected.side_effect = [False, False]
        self.assertFalse(self.mock_data_gateway.is_dw_available())
        mock_connect.assert_called_once()

        mock_is_connected.side_effect = [False, True]
        self.assertTrue(self.mock_data_gateway.is_dw_available())

        mock_is_connected.side_effect = [True, True]
        self.assertTrue(self.mock_data_gateway.is_dw_available())

        mock_logger.reset_mock()
        mock_read_config.side_effect = Exception('mock_exception')
        self.assertFalse(self.mock_data_gateway.is_dw_available())
        mock_logger.error.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.Path.stat')
    def test_has_config_changed(self, mock_stat):
        self.mock_data_gateway.config_edit_time = 0.0
        self.assertTrue(self.mock_data_gateway.has_config_changed)

        mock_data = mock.Mock()
        mock_data.st_mtime = 100
        mock_stat.return_value = mock_data
        self.mock_data_gateway.config_edit_time = 100
        self.assertFalse(self.mock_data_gateway.has_config_changed)

        mock_data.st_mtime = 101
        self.assertTrue(self.mock_data_gateway.has_config_changed)

    def test_disconnect(self):
        self.mock_data_gateway.disconnect()
        self.mock_mqtt_client.loop_stop.assert_called_once()
        self.mock_mqtt_client.disconnect.assert_called_once()

    def test_is_connected(self):
        self.mock_mqtt_client.is_connected.return_value = True
        self.assertTrue(self.mock_data_gateway.is_connected)

        self.mock_mqtt_client.is_connected.return_value = False
        self.assertFalse(self.mock_data_gateway.is_connected)

    def test_publish(self):
        mock_topic = 'mock_topic'
        mock_payload = 'mock_payload'
        mock_wait = 1

        self.mock_data_gateway._publish(mock_topic, mock_payload)
        self.mock_mqtt_client.publish.assert_called_once_with(mock_topic, payload=mock_payload)
        self.mock_mqtt_client.publish.return_value.wait_for_publish.assert_called_once_with(mock_wait)

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub._publish')
    def test_send_full_telemetry(self, mock_publish, mock_logger):
        mock_data = mock.MagicMock()
        mock_data.model_dump.return_value = 'mock_json'
        mock_json = '"mock_json"'
        mock_res = mock.MagicMock()
        mock_res.is_published.return_value = True

        mock_publish.return_value = mock_res

        self.mock_data_gateway._send_full_telemetry(mock_data)
        mock_publish.assert_called_once_with(self.mock_data_gateway.TELEMETRY_TOPIC, payload=mock_json)
        self.assertEqual(2, mock_logger.debug.call_count)

        mock_logger.reset_mock()
        mock_res.is_published.return_value = False
        self.mock_data_gateway._send_full_telemetry(mock_data)
        mock_logger.error.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub._publish')
    def test_send_cpu_info(self, mock_publish, mock_logger):
        mock_data = mock.MagicMock()
        mock_data.resources = {'cpu': {'raw-sample': 'mock_cpu'}}
        mock_res = mock.MagicMock()
        mock_res.is_published.return_value = True

        mock_publish.return_value = mock_res

        self.mock_data_gateway._send_cpu_info(mock_data)
        mock_publish.assert_called_once_with('cpu', 'mock_cpu')
        mock_logger.debug.assert_not_called()

        mock_logger.reset_mock()
        mock_data.resources = {'cpu': {'raw-sample': None}}
        self.mock_data_gateway._send_cpu_info(mock_data)
        mock_logger.debug.assert_called_once()

        mock_logger.reset_mock()
        mock_data = mock.MagicMock()
        mock_data.resources = {'cpu': {'raw-sample': 'mock_cpu'}}
        mock_res.is_published.return_value = False
        self.mock_data_gateway._send_cpu_info(mock_data)
        mock_logger.error.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub._publish')
    def test_send_memory_info(self, mock_publish, mock_logger):
        mock_data = mock.MagicMock()
        mock_data.resources = {'memory': {'raw-sample': 'mock_memory'}}
        mock_res = mock.MagicMock()
        mock_res.is_published.return_value = True

        mock_publish.return_value = mock_res

        self.mock_data_gateway._send_memory_info(mock_data)
        mock_publish.assert_called_once_with('ram', 'mock_memory')
        mock_logger.debug.assert_not_called()

        mock_logger.reset_mock()
        mock_data.resources = {'memory': {'raw-sample': None}}
        self.mock_data_gateway._send_memory_info(mock_data)
        mock_logger.debug.assert_called_once()

        mock_logger.reset_mock()
        mock_data = mock.MagicMock()
        mock_data.resources = {'memory': {'raw-sample': 'mock_memory'}}
        mock_res.is_published.return_value = False
        self.mock_data_gateway._send_memory_info(mock_data)
        mock_logger.error.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub._publish')
    def test_send_disk_info(self, mock_publish, mock_logger):
        mock_data = mock.MagicMock()
        mock_data.resources = {'disks': ['mock_disk']}
        mock_res = mock.MagicMock()
        mock_res.is_published.return_value = True

        mock_publish.return_value = mock_res

        self.mock_data_gateway._send_disk_info(mock_data)
        mock_publish.assert_called_once_with('disks', '"mock_disk"')
        mock_logger.debug.assert_not_called()

        mock_logger.reset_mock()
        mock_data.resources = {'disks': []}
        self.mock_data_gateway._send_disk_info(mock_data)
        mock_logger.debug.assert_called_once()

    @patch('nuvlaedge.common.data_gateway.logger')
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.is_dw_available')
    def test_send_telemetry(self, mock_available, mock_logger):
        mock_data = mock.MagicMock()

        mock_sender = mock.MagicMock()
        self.mock_data_gateway.SENDERS = {'mock_sender': mock_sender}

        mock_available.return_value = False
        self.mock_data_gateway.send_telemetry(mock_data)
        mock_available.assert_called_once()

        mock_logger.reset_mock()
        mock_available.return_value = True

        self.mock_data_gateway.send_telemetry(mock_data)
        mock_sender.assert_called_once()

        mock_logger.reset_mock()

        mock_sender.side_effect = Exception('mock_exception')
        self.mock_data_gateway.send_telemetry(mock_data)
        mock_logger.error.assert_called_once()
