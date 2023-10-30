import json
from unittest import IsolatedAsyncioTestCase

import mock
import pytest

from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.broker.file_broker import FileBroker


class TestPeripheral(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.test_peripheral: Peripheral = Peripheral(name='test_peripheral')
        self.test_peripheral_async: Peripheral = Peripheral(name='test_peripheral_async', async_mode=True)

    def test_hash_discoveries(self):
        sample = {'d': 'd'}
        self.assertEqual(Peripheral.hash_discoveries({'d': 'd'}), hash(json.dumps(sample, sort_keys=True)))

    async def test_run_single_iteration_async(self):
        await self._test_run_single_iteration(async_mode=True)

    async def test_run_single_iteration_sync(self):
        await self._test_run_single_iteration()

    async def _test_run_single_iteration(self, async_mode: bool = False):
        if async_mode:
            mock_callable = mock.AsyncMock()
            test_peripheral = self.test_peripheral_async
        else:
            mock_callable = mock.Mock()
            test_peripheral = self.test_peripheral
        mock_callable.return_value = {}
        with mock.patch.object(FileBroker, 'publish') as mock_pub:
            await test_peripheral.run_single_iteration(mock_callable)
            mock_pub.assert_not_called()
            mock_callable.assert_called_once()

            mock_callable.reset_mock()
            mock_callable.return_value = {'name': 'peripheral'}
            await test_peripheral.run_single_iteration(mock_callable)
            mock_pub.assert_called_once()
