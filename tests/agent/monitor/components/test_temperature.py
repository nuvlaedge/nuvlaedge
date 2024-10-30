# -*- coding: utf-8 -*-
import unittest

from mock import Mock, patch, mock_open

from nuvlaedge.agent.workers.telemetry import TelemetryPayloadAttributes
from nuvlaedge.agent.workers.monitor.components.temperature import TemperatureMonitor
from nuvlaedge.agent.workers.monitor.data.temperature_data import TemperatureData, TemperatureZone
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus


temperature_class_path = 'nuvlaedge.agent.workers.monitor.components.temperature'
temperature_monitor_class_path = f'{temperature_class_path}.TemperatureMonitor'


class TestTemperatureMonitor(unittest.TestCase):

    @staticmethod
    def get_base_monitor() -> TemperatureMonitor:
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        mock_telemetry.edge_status.power = None
        return TemperatureMonitor('test_monitor', mock_telemetry, True)

    def test_init(self):
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        mock_telemetry.edge_status.temperatures = None
        TemperatureMonitor('test_monitor', mock_telemetry, True)
        self.assertTrue(mock_telemetry.edge_status.temperatures)
        self.assertIsInstance(mock_telemetry.edge_status.temperatures, TemperatureData)

    def test_update_temperature_entry(self):
        test_monitor: TemperatureMonitor = self.get_base_monitor()
        test_monitor.data.temperatures = []
        test_monitor.update_temperature_entry('cpu', 45.1)

        self.assertIn('cpu', test_monitor.local_temp_registry)
        self.assertIsInstance(test_monitor.local_temp_registry['cpu'], TemperatureZone)

    @patch(f'{temperature_class_path}.psutil')
    @patch(f'{temperature_monitor_class_path}.update_temperature_entry')
    def test_update_temperatures_with_psutil(self, mock_entry, mock_ps):
        test_monitor: TemperatureMonitor = self.get_base_monitor()
        mock_temperature = Mock()
        mock_temperature.current = 10
        results: dict = {'acpitz': mock_temperature,
                         'core': mock_temperature}
        mock_ps.sensors_temperatures.return_value = results
        mock_entry.return_value = None
        test_monitor.update_temperatures_with_psutil()
        self.assertEqual(mock_entry.call_count, 2)

    def test_read_temperature_file(self):
        test_monitor: TemperatureMonitor = self.get_base_monitor()
        # if there's an error reading files, return None,None
        with patch(f'{temperature_class_path}.open', mock_open(read_data=None)):
            self.assertEqual(test_monitor.read_temperature_file('', ''), (None, None),
                             'Failed to read temperature files when one cannot be read')

        # if files can be read, return their content
        with patch(f'{temperature_class_path}.open',
                   mock_open(read_data='test')):
            self.assertEqual(test_monitor.read_temperature_file('', ''),
                             ('test', 'test'),
                             'Failed to read temperature files')

    @patch(f'{temperature_monitor_class_path}.read_temperature_file')
    @patch('os.listdir')
    @patch('os.path.exists')
    def test_update_temperatures_with_file(self, mock_exists, mock_listdir,
                                           mock_read_temperature_files):

        test_monitor: TemperatureMonitor = self.get_base_monitor()
        test_monitor.data.temperatures = []
        # otherwise, if thermal paths do no exist, return []
        mock_listdir.return_value = ['dir1', 'dir2']
        mock_exists.side_effect = [True, False, False]
        test_monitor.update_temperatures_with_file()
        self.assertFalse(test_monitor.data.temperatures,
                         'Failed to get temperature when thermal files do not exist')
        mock_listdir.assert_called_once()

        # same if thermal files do not exist
        mock_exists.side_effect = [False]*100
        mock_listdir.return_value = ['thermal-dir1', 'thermal-dir2']
        test_monitor.update_temperatures_with_file()
        self.assertFalse(test_monitor.data.temperatures,
                         'Failed to get temperature when thermal files do not exist')

        # if they exist, we can open them, but if there's an error reading them or they
        # are None, we get [] again
        mock_read_temperature_files.return_value = (None, None)
        mock_exists.reset_mock(side_effect=True)
        mock_exists.return_value = True
        test_monitor.update_temperatures_with_file()
        self.assertFalse(test_monitor.data.temperatures,
                         'Failed to get temperature when thermal files have invalid content')

        # if readings succeed, but values are not of the right type, get []
        mock_read_temperature_files.return_value = ('metric', 'bad-type-value')
        test_monitor.update_temperatures_with_file()
        self.assertFalse(test_monitor.data.temperatures,
                         'Failed to get temperature when thermal files have content of the wrong type')

        # otherwise, get temperatures
        mock_read_temperature_files.return_value = ('metric', 1000)
        expected_output = [{
            "thermal-zone": 'metric',
            "value": 1
        }, {
            "thermal-zone": 'metric',
            "value": 1
        }]
        test_monitor.update_temperatures_with_file()
        self.assertEqual(test_monitor.local_temp_registry['metric'].dict(by_alias=True),
                         expected_output[0],
                         'Failed to get temperatures')

    @patch(f'{temperature_monitor_class_path}.update_temperatures_with_file')
    @patch(f'{temperature_monitor_class_path}.update_temperatures_with_psutil')
    @patch('os.path.exists')
    def test_update_data(self, mock_exists, mock_psutil, mock_update_file):
        # Test data initialization
        test_monitor: TemperatureMonitor = self.get_base_monitor()

        mock_psutil.return_value = None
        mock_update_file.return_value = None

        self.assertIsNone(test_monitor.data.temperatures)

        # Test data update
        with patch(f'{temperature_class_path}.psutil') as mock_sens:
            mock_exists.return_value = False
            mock_sens.__setattr__('sensors_temperatures', 'thisisavalue')
            test_monitor.update_data()
            self.assertFalse(test_monitor.data.temperatures)
            mock_psutil.assert_called_once()

        mock_exists.return_value = True
        test_monitor.update_data()
        mock_update_file.assert_called_once()

    @patch(f'{temperature_monitor_class_path}.update_temperatures_with_file')
    @patch('os.path.exists')
    def test_populate_nb_report(self, mock_exists, mock_update_file):
        test_monitor: TemperatureMonitor = self.get_base_monitor()

        mock_update_file.return_value = None
        mock_exists.return_value = True

        test_monitor.local_temp_registry = {
            'cpu-thermal': TemperatureZone(thermal_zone='cpu-thermal', value=85.123),
            'GPU-therm': TemperatureZone(thermal_zone='GPU-therm', value=39.5),
        }
        test_monitor.update_data()

        telemetry_payload = TelemetryPayloadAttributes()
        data = test_monitor.data.model_dump(exclude_none=True, by_alias=True)
        telemetry_payload.update(data)

        telemetry_data = telemetry_payload.model_dump(exclude_none=True, by_alias=True)
        self.assertEqual(telemetry_data, {
            'temperatures': [{'thermal-zone': 'cpu-thermal', 'value': 85.123},
                             {'thermal-zone': 'GPU-therm', 'value': 39.5}]})
