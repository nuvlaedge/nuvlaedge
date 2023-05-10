import json
from unittest import TestCase

import mock

from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.broker.file_broker import FileBroker


class TestPeripheral(TestCase):
    def setUp(self) -> None:
        self.test_peripheral: Peripheral = Peripheral('test_peripheral')

    def test_hash_discoveries(self):
        sample = {'d': 'd'}
        self.assertEqual(Peripheral.hash_discoveries({'d': 'd'}), hash(json.dumps(sample, sort_keys=True)))

    def test_run_single_iteration(self):
        mock_callable = mock.Mock()
        mock_callable.return_value = {}
        with mock.patch.object(FileBroker, 'publish') as mock_pub:
            self.test_peripheral.run_single_iteration(mock_callable)
            mock_pub.assert_not_called()
            mock_callable.assert_called_once()

            mock_callable.reset_mock()
            mock_callable.return_value = {'name': 'peripheral'}
            self.test_peripheral.run_single_iteration(mock_callable)
            mock_pub.assert_called_once()
