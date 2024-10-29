# -*- coding: utf-8 -*-
import unittest

from mock import Mock, patch

from nuvlaedge.agent.workers.monitor.components.gpio import GpioMonitor
from nuvlaedge.agent.workers.monitor.data.gpio_data import GpioData, GpioPin
from nuvlaedge.agent.workers.monitor.edge_status import EdgeStatus


class TestGpioMonitor(unittest.TestCase):

    @staticmethod
    def get_base_monitor() -> GpioMonitor:
        mock_telemetry = Mock()
        mock_telemetry.edge_status = EdgeStatus()
        with patch('nuvlaedge.agent.workers.monitor.components.gpio.execute_cmd') as mock_cmd:
            mock_cmd.return_value = True
            return GpioMonitor('test_monitor', mock_telemetry, True)

    @patch('nuvlaedge.agent.workers.monitor.components.gpio.GpioMonitor.gpio_availability')
    def test_init(self, mock_availability):
        mock_availability.return_value = True
        edge_status = EdgeStatus()
        mock_telemetry = Mock()
        mock_telemetry.edge_status = edge_status
        gpio_monitor = GpioMonitor('test_monitor', mock_telemetry, True)
        self.assertTrue(edge_status.gpio_pins)
        self.assertIsInstance(edge_status.gpio_pins, GpioData)
        gpio_monitor.__init__('test_monitor', mock_telemetry)

    @patch('nuvlaedge.agent.workers.monitor.components.gpio.execute_cmd')
    def test_gpio_availability(self, mock_cmd):
        test_monitor: GpioMonitor = self.get_base_monitor()
        mock_cmd.return_value = "dummy"
        self.assertTrue(test_monitor.gpio_availability())

        mock_cmd.side_effect = FileNotFoundError
        self.assertFalse(test_monitor.gpio_availability())

    def test_parse_pin_cell(self):
        # Test line index is within range
        test_monitor: GpioMonitor = self.get_base_monitor()
        self.assertIsNone(test_monitor.parse_pin_cell([], 'line'))

        # example of a GPIO readall
        # +-----+-----+---------+------+---+---Pi 4B--+---+------+---------+-----+-----+
        # | BCM | wPi |   Name  | Mode | V | Physical | V | Mode | Name    | wPi | BCM |
        # +-----+-----+---------+------+---+----++----+---+------+---------+-----+-----+
        # |     |     |    3.3v |      |   |  1 || 2  |   |      | 5v      |     |     |
        # |   2 |   8 |   SDA.1 |   IN | 1 |  3 || 4  |   |      | 5v      |     |     |
        # |   3 |   9 |   SCL.1 |   IN | 1 |  5 || 6  |   |      | 0v      |     |     |
        # ...

        # let's take a valid line: pins 3 and 4
        gpio_line = ' |   2 |   8 |   SDA.1 |   IN | 1 |  3 || 4  |   |      | 5v      ' \
                    '|     |     |'
        first_pin_indexes = [1, 3, 4, 5, 6]
        second_pin_indexes = [14, 11, 10, 9, 8]

        # first, we need to read an int from the line, and if this is not possible, get
        # None index 3 cannot be converted to int:
        self.assertIsNone(test_monitor.parse_pin_cell([0, 0, 0, 0, 3], gpio_line),
                          'Failed to get No GPIO info when values cannot be converted to '
                          'int')

        # same for any other exception (like IndexError)
        self.assertIsNone(test_monitor.parse_pin_cell([0, 0, 0, 0, 333], gpio_line),
                          'Failed to get No GPIO info reading error occurs')

        # if all goes well, the above values should be cast to their right var type,
        # and returned in a dict
        expected_output_pin_3 = {
            'bcm': 2,
            'name': 'SDA.1',
            'mode': 'IN',
            'voltage': 1,
            'pin': 3
        }
        expected_output_pin_4 = {
            'name': '5v',
            'pin': 4
        }

        self.assertEqual(
            test_monitor.parse_pin_cell(
                first_pin_indexes,
                gpio_line).dict(by_alias=True, exclude_none=True),
            expected_output_pin_3,
            'Failed to parse left side GPIO pin')
        self.assertEqual(
            test_monitor.parse_pin_cell(
                second_pin_indexes,
                gpio_line).dict(by_alias=True, exclude_none=True),
            expected_output_pin_4,
            'Failed to parse right side GPIO pin')

        test_monitor._gpio_expected_attr.append({'dum': 'noVal'})
        self.assertIsNone(test_monitor.parse_pin_cell(
                first_pin_indexes,
                gpio_line))

    @patch('nuvlaedge.agent.workers.monitor.components.gpio.GpioMonitor.parse_pin_cell')
    def test_parse_pin_line(self, mock_cell):
        mock_cell.return_value = None
        test_monitor: GpioMonitor = self.get_base_monitor()
        self.assertEqual(test_monitor.parse_pin_line('line'), (None, None))

    def test_gather_gpio_lines(self):
        ...

    def test_update_data(self):
        ...

    def test_populate_nb_report(self):
        test_monitor: GpioMonitor = self.get_base_monitor()

        test_monitor.data = GpioData(telemetry_name='test_monitor')
        test_monitor.data.pins = {}
        gpio_pin = GpioPin()
        gpio_pin.pin = 1
        test_monitor.data.pins[gpio_pin.pin] = gpio_pin

        telemetry_data = {}
        test_monitor.populate_nb_report(telemetry_data)
        self.assertEqual({'gpio-pins': {1: {'pin': 1}}}, telemetry_data)
