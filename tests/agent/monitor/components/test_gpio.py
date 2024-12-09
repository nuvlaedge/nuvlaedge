# -*- coding: utf-8 -*-
import logging
import unittest

from mock import Mock, patch

from nuvlaedge.agent.workers.monitor.components.gpio import GpioMonitor
from nuvlaedge.agent.workers.monitor.data.gpio_data import GpioData, GpioPin


gpio_output = '''+-----+-----+---------+------+---+---Pi 2---+---+------+---------+-----+-----+
 | BCM | wPi |   Name  | Mode | V | Physical | V | Mode | Name    | wPi | BCM |
 +-----+-----+---------+------+---+----++----+---+------+---------+-----+-----+
 |     |     |    3.3v |      |   |  1 || 2  |   |      | 5v      |     |     |
 |   2 |   8 |   SDA.1 | ALT0 | 1 |  3 || 4  |   |      | 5V      |     |     |
 |   3 |   9 |   SCL.1 | ALT0 | 1 |  5 || 6  |   |      | 0v      |     |     |
 |   4 |   7 | GPIO. 7 |   IN | 1 |  7 || 8  | 1 | ALT0 | TxD     | 15  | 14  |
 |     |     |      0v |      |   |  9 || 10 | 1 | ALT0 | RxD     | 16  | 15  |
 |  17 |   0 | GPIO. 0 |   IN | 0 | 11 || 12 | 0 | IN   | GPIO. 1 | 1   | 18  |
 |  27 |   2 | GPIO. 2 |   IN | 0 | 13 || 14 |   |      | 0v      |     |     |
 |  22 |   3 | GPIO. 3 |   IN | 0 | 15 || 16 | 0 | IN   | GPIO. 4 | 4   | 23  |
 |     |     |    3.3v |      |   | 17 || 18 | 0 | IN   | GPIO. 5 | 5   | 24  |
 |  10 |  12 |    MOSI | ALT0 | 0 | 19 || 20 |   |      | 0v      |     |     |
 |   9 |  13 |    MISO | ALT0 | 0 | 21 || 22 | 0 | IN   | GPIO. 6 | 6   | 25  |
 |  11 |  14 |    SCLK | ALT0 | 0 | 23 || 24 | 1 | OUT  | CE0     | 10  | 8   |
 |     |     |      0v |      |   | 25 || 26 | 1 | OUT  | CE1     | 11  | 7   |
 |   0 |  30 |   SDA.0 |   IN | 1 | 27 || 28 | 1 | IN   | SCL.0   | 31  | 1   |
 |   5 |  21 | GPIO.21 |   IN | 1 | 29 || 30 |   |      | 0v      |     |     |
 |   6 |  22 | GPIO.22 |   IN | 1 | 31 || 32 | 0 | IN   | GPIO.26 | 26  | 12  |
 |  13 |  23 | GPIO.23 |   IN | 0 | 33 || 34 |   |      | 0v      |     |     |
 |  19 |  24 | GPIO.24 |   IN | 0 | 35 || 36 | 0 | IN   | GPIO.27 | 27  | 16  |
 |  26 |  25 | GPIO.25 |   IN | 0 | 37 || 38 | 0 | IN   | GPIO.28 | 28  | 20  |
 |     |     |      0v |      |   | 39 || 40 | 0 | IN   | GPIO.29 | 29  | 21  |
 +-----+-----+---------+------+---+----++----+---+------+---------+-----+-----+
 | BCM | wPi |   Name  | Mode | V | Physical | V | Mode | Name    | wPi | BCM |
 +-----+-----+---------+------+---+---Pi 2---+---+------+---------+-----+-----+'''


class TestGpioMonitor(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    @staticmethod
    def get_base_monitor() -> GpioMonitor:
        mock_telemetry = Mock()
        with patch('nuvlaedge.agent.workers.monitor.components.gpio.execute_cmd') as mock_cmd:
            mock_cmd.return_value = True
            return GpioMonitor('test_monitor', mock_telemetry, True)

    @patch('nuvlaedge.agent.workers.monitor.components.gpio.GpioMonitor.gpio_availability')
    def test_init(self, mock_availability):
        mock_availability.return_value = True
        mock_telemetry = Mock()
        gpio_monitor = GpioMonitor('test_monitor', mock_telemetry, True)
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

    @patch('nuvlaedge.agent.workers.monitor.components.gpio.execute_cmd')
    def test_gpio(self, mock_execute_cmd):
        test_monitor: GpioMonitor = self.get_base_monitor()

        gpio_out = Mock()
        gpio_out.stdout = gpio_output
        mock_execute_cmd.return_value = gpio_out

        test_monitor.update_data()
        self.assertEqual(40, len(test_monitor.data.pins))
        test_monitor.update_data()

    def test_populate_telemetry_payload(self):
        test_monitor: GpioMonitor = self.get_base_monitor()
        test_monitor.data.pins = {1: GpioPin(pin=1, name='GPIO. 1', bcm=4, mode='IN', voltage=1),
                                  2: GpioPin(pin=2, name='GPIO. 2', bcm=5, mode='OUT', voltage=0)}
        test_monitor.populate_telemetry_payload()
        self.assertEqual(test_monitor.telemetry_data.gpio_pins, test_monitor.data.pins)
