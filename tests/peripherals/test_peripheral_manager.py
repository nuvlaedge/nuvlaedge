from pathlib import Path
from datetime import datetime

from unittest import TestCase
import mock

from nuvlaedge.models.peripheral import PeripheralData
from nuvlaedge.models.messages import NuvlaEdgeMessage
from nuvlaedge.agent.workers.peripheral_manager import PeripheralManager, PeripheralsDBManager


class TestPeripheralManager(TestCase):
    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'mkdir')
    def setUp(self, mock_mkdir, mock_exists) -> None:
        mock_exists.return_value = True
        self.mock_broker = mock.Mock()
        self.mock_broker.keys.return_value = {'p1'}
        self.mock_broker.keys = {'p1'}
        self.mock_nuvla = mock.Mock()
        self.mock_channel = mock.Mock()
        self.test_manager = PeripheralManager(self.mock_nuvla, 'uuid', self.mock_channel)
        self.test_manager.broker = self.mock_broker

    @mock.patch.object(Path, 'is_dir')
    @mock.patch.object(Path, 'iterdir')
    def test_update_running_managers(self, mock_iterdir, mock_isdir):
        mock_iterdir.return_value = []
        self.test_manager.update_running_managers()
        self.assertEqual(len(self.test_manager.running_peripherals), 0)

        mock_isdir.return_value = True
        mock_iterdir.return_value = [Path('Mock')]
        self.test_manager.update_running_managers()
        self.assertEqual(len(self.test_manager.running_peripherals), 1)

    def test_process_new_peripherals(self):
        test_peripherals = {'p1': PeripheralData(identifier='id', available=True, classes=['myClass'])}

        with mock.patch.object(PeripheralsDBManager, 'add') as mock_add, \
            mock.patch.object(PeripheralsDBManager, 'remove') as mock_remove, \
            mock.patch.object(PeripheralsDBManager, 'edit') as mock_edit, \
            mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.keys',
                       new_callable=mock.PropertyMock) as mock_keys:

            mock_keys.return_value = set()
            self.test_manager.process_new_peripherals(test_peripherals)
            mock_add.assert_called_once()
            mock_edit.assert_not_called()
            mock_remove.assert_not_called()

            mock_keys.return_value = {'p1'}
            self.test_manager.process_new_peripherals(test_peripherals)
            mock_edit.assert_called_once()
            mock_remove.assert_not_called()

            self.test_manager.process_new_peripherals({})
            mock_remove.assert_called_once()

    def test_available_messages(self):
        self.test_manager.running_peripherals = {Path('p1'), Path('p2')}
        self.mock_broker.consume.return_value = []

        for _ in self.test_manager.available_messages:
            continue
        self.assertEqual(self.mock_broker.consume.call_count, 2)

        with self.assertRaises(AttributeError):
            self.mock_broker.consume.return_value = ['not_a_good_message']
            for _ in self.test_manager.available_messages:
                continue

        sample_message = NuvlaEdgeMessage(
            sender='sender',
            data={'id': 'idx'},
            time=datetime.now())
        self.mock_broker.consume.return_value  = [sample_message]

        for i in self.test_manager.available_messages:
            self.assertEqual(i, {'id': 'idx'})

    def test_join_new_peripherals(self):

        self.assertEqual({}, self.test_manager.join_new_peripherals([]))

        sample_peripheral = {
            'identifier': 'idx',
            'available': True,
            'classes': ['net']
        }

        self.assertEqual(
            {'idx': PeripheralData.model_validate(sample_peripheral)},
            self.test_manager.join_new_peripherals([{'idx': sample_peripheral}])
        )

        with mock.patch('logging.Logger.exception') as manager_logger:
            manager_logger.return_value = False
            sample_peripheral['classes'] = 'notalist'
            self.test_manager.join_new_peripherals([sample_peripheral])
            self.assertEqual(3, manager_logger.call_count)
