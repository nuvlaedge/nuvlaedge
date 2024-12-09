# -*- coding: utf-8 -*-
import unittest

from mock import Mock, patch, mock_open


from nuvlaedge.agent.workers.monitor.components.power import PowerMonitor
from nuvlaedge.agent.workers.monitor.data.power_data import PowerData, PowerEntry


class TestPowerMonitor(unittest.TestCase):

    @staticmethod
    def get_base_monitor() -> PowerMonitor:
        mock_telemetry = Mock()
        power_monitor = PowerMonitor('test_monitor', mock_telemetry, True)
        setattr(power_monitor, 'available_power_drivers', ['ina3221x'])
        return power_monitor

    @patch('os.listdir')
    @patch('os.path.exists')
    def test_get_powers(self, mock_exists, mock_listdir):
        power_open: str = 'nuvlaedge.agent.workers.monitor.components.power.open'
        test_monitor: PowerMonitor = self.get_base_monitor()
        mock_exists.return_value = False
        self.assertEqual([], test_monitor.get_powers('some_text'),
                         'Got power consumption even when I2C drivers cannot be found')

        # else, go through the model
        mock_exists.return_value = True
        # if addresses do not match, get [] again
        mock_listdir.return_value = ['not-match']
        self.assertEqual([], test_monitor.get_powers('ina3221x'),
                         'Got power consumption even when I2C drivers cannot be found')

        # otherwise
        mock_listdir.return_value = ['0-0040', '0-0041']
        # if metrics_folder_path does not exist, get []
        mock_exists.side_effect = \
            [True] + \
            [False for _ in range(
                0,
                len(test_monitor._NVIDIA_MODEL['ina3221x']['boards']))]
        self.assertEqual([], test_monitor.get_powers('ina3221x'),
                         'Got power consumption even though I2C metrics_folder_path do '
                         'not exist')

        # NOTE: ['0-0040', '0-0041'] only matches with 2 boards
        # if metrics_folder_path exists, rail file must exist as well otherwise get []
        # 2 boards matching + 3 channels/board
        mock_exists.side_effect = [True] + \
                                  [False, True] + [False, False,
                                                   False]
        self.assertEqual([], test_monitor.get_powers('ina3221x'),
                         'Got power consumption even though I2C rail files do not exist')

        # if rail files exist, open them, unless there is an error, which means = []
        with patch(power_open, mock_open(read_data=None)):
            # 2 boards matching + 3 channels
            mock_exists.side_effect = [True, False, True, True, True, True] + [False]*100
            self.assertEqual([], test_monitor.get_powers('ina3221x'),
                             'Got power consumption when rail files cannot be read')

        # if reading goes well, but metrics_folder_path is empty, get []
        mock_exists.side_effect = [True] + \
                                  [False, True] + [True, True,
                                                   True]  # 2 boards matching + 3 channels
        mock_listdir.side_effect = [['0-0040', '0-0041'],
                                    [], [], []]  # 3 channel reading
        with patch(power_open,
                   mock_open(read_data='valid_data')):
            self.assertEqual([], test_monitor.get_powers('ina3221x'),
                             'Got power consumption when rail files cannot be read')

        # if reading data is valid and metrics_folder_path contains the desired metric
        # matches
        mock_exists.side_effect = [True] + \
                                  [False, True] + [True, True,
                                                   True]  # 2 boards matching + 3 channels
        channel = 0
        list_dir_right_sequence = [['0-0040', '0-0041'],
                                   [f'in_current{channel}_input',
                                    f'in_voltage{channel}_input',
                                    f'in_power{channel}_input',
                                    f'crit_current_limit_{channel}'], [],
                                   []]  # 3 channel reading (1st valid)
        mock_listdir.side_effect = list_dir_right_sequence

        with patch(power_open,
                   mock_open(read_data='not-float-data')):
            self.assertEqual([], test_monitor.get_powers('ina3221x'),
                             'Got power consumption when rail files can be read but do '
                             'not have data as a float')

        mock_exists.side_effect = [True] + \
                                  [False, True] + [True, True,
                                                   True]  # 2 boards matching + 3 channels
        channel = 0
        mock_listdir.side_effect = list_dir_right_sequence
        expected_output = [
            {'energy-consumption': 1, 'metric-name': '1_current', 'unit': 'mA'},
            {'energy-consumption': 1, 'metric-name': '1_voltage', 'unit': 'mV'},
            {'energy-consumption': 1, 'metric-name': '1_power', 'unit': 'mW'},
            {'energy-consumption': 1, 'metric-name': '1_critical_current_limit',
             'unit': 'mA'}
        ]

        with patch(power_open, mock_open(read_data='1')):
            self.assertEqual(test_monitor.get_powers('ina3221x')[0].dict(by_alias=True),
                             expected_output[0],
                             'Unable to get power consumption')

    @patch('nuvlaedge.agent.workers.monitor.components.power.PowerMonitor.get_powers')
    def test_update_data_and_populate_nb_report(self, mock_get_powers):
        test_monitor: PowerMonitor = self.get_base_monitor()
        self.assertIsNone(test_monitor.data.power_entries)
        mock_get_powers.return_value = []
        test_monitor.update_data()
        self.assertFalse(test_monitor.data.power_entries)

        test_entry = PowerEntry(metric_name='current',
                                energy_consumption=1, unit='mA')
        mock_get_powers.return_value = [test_entry]
        test_monitor.update_data()
        self.assertEqual(test_monitor.data.power_entries['current'], test_entry)

    def test_populate_telemetry_payload(self):
        mock_data = PowerData()
        mock_data.power_entries = {'current': PowerEntry(metric_name='current',
                                                         energy_consumption=1, unit='mA')}
        test_monitor: PowerMonitor = self.get_base_monitor()
        test_monitor.data = mock_data

        test_monitor.populate_telemetry_payload()
        expected_resources = {
            "power-consumption": [
                {
                    "energy-consumption": 1,
                    "metric-name": "current",
                    "unit": "mA"
                }
            ]
        }
        self.assertEqual(expected_resources, test_monitor.telemetry_data.resources)
