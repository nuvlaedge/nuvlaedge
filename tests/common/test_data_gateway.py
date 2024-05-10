from unittest import TestCase
from mock import mock, patch


from nuvlaedge.common.data_gateway import DataGatewayPub


class TestDataGatewayPub(TestCase):
    def setUp(self):
        self.mock_mqtt_client = mock.MagicMock()
        self.mock_endpoint = 'mock_endpoint'
        self.mock_port = 1234
        self.mock_timeout = 10

        self.mock_data_gateway = DataGatewayPub(endpoint=self.mock_endpoint,
                                           port=self.mock_port,
                                           timeout=self.mock_timeout)

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
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.is_connected', new_callable=mock.PropertyMock)
    @patch('nuvlaedge.common.data_gateway.DataGatewayPub.connect')
    def test_sent_telemetry(self, mock_connect, mock_is_connected, mock_logger):
        mock_data = mock.MagicMock()

        mock_sender = mock.MagicMock()
        self.mock_data_gateway.SENDERS = {'mock_sender': mock_sender}

        mock_is_connected.side_effect = [False, False]
        self.mock_data_gateway.send_telemetry(mock_data)
        mock_connect.assert_called_once()
        mock_logger.error.assert_called_once()

        mock_logger.reset_mock()
        mock_connect.reset_mock()
        mock_is_connected.side_effect = [False, True]

        self.mock_data_gateway.send_telemetry(mock_data)
        mock_connect.assert_called_once()
        mock_sender.assert_called_once()

        mock_logger.reset_mock()
        mock_is_connected.reset_mock()

        mock_is_connected.side_effect = [True, True]
        mock_sender.side_effect = Exception('mock_exception')
        self.mock_data_gateway.send_telemetry(mock_data)
        mock_logger.error.assert_called_once()
