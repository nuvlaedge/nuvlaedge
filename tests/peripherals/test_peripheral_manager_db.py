from pathlib import Path
from datetime import datetime, timedelta

from unittest import TestCase

import mock

from nuvlaedge.peripherals.peripheral_manager_db import PeripheralData, PeripheralsDBManager
from nuvlaedge.models.nuvla_resources import NuvlaBoxPeripheralResource as PeripheralResource


class TestPeripheralsDBManager(TestCase):

    def setUp(self) -> None:
        self.mock_nuvla = mock.Mock()
        self.test_db = PeripheralsDBManager(self.mock_nuvla, 'test_uuid')

    @staticmethod
    def get_sample_peripheral_resource():
        return PeripheralResource(state='RUNNING',
                                  refresh_interval=30,
                                  identifier='id_1',
                                  available=True,
                                  classes=['class'])

    @staticmethod
    def get_sample_peripheral_data():
        return PeripheralData(identifier='id_1',
                              available=True,
                              classes=['class'])

    @mock.patch.object(PeripheralsDBManager, 'synchronize')
    def test_content(self, mock_sync):
        with mock.patch('time.time') as mock_time:
            mock_time.return_value = 3*61
            self.test_db._last_synch = 0
            test_content = self.test_db.content
            self.assertEqual(test_content, {})
            self.assertEqual(self.test_db._last_synch, 3*61)
            self.assertEqual(self.test_db.content, {})

    @mock.patch.object(PeripheralsDBManager, 'decode_new_peripherals')
    @mock.patch.object(PeripheralsDBManager, 'update_local_storage')
    def test_synchronize(self, mock_storage, mock_decode):
        # Test no peripherals found remotely
        mock_collection = mock.Mock()
        mock_collection.count = 0
        self.mock_nuvla.search.return_value = mock_collection
        self.test_db.synchronize()
        self.assertEqual(self.test_db._local_db, {})
        self.assertEqual(self.test_db._latest_update, {})

        # Test remote found
        mock_collection.count = 1
        mock_data = mock.Mock
        mock_data.updated = 100
        test_peripheral = {
            'id': mock_data
        }

        mock_decode.return_value = test_peripheral
        self.test_db.synchronize()
        self.assertEqual(self.test_db._latest_update, {'id': 100})
        mock_storage.assert_called_once()

        # Test remove update from local registry
        mock_storage.reset_mock()
        self.test_db._latest_update = {'id2': mock_data}
        self.test_db.synchronize()
        self.assertNotIn('id2', self.test_db._latest_update)
        mock_storage.assert_called_once()

    def test_update_local_storage(self):
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        test_model = self.get_sample_peripheral_resource()
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.dump") as mock_dump:
                self.test_db._local_db = {'id_1': test_model}
                self.test_db.update_local_storage()
                mock_dump.assert_called_once_with({'id_1': test_model.model_dump(by_alias=True, exclude_none=True)},
                                                  mock.ANY,
                                                  default=str,
                                                  indent=4
                                                  )

    def test_decode_new_peripherals(self):

        self.assertFalse(self.test_db.decode_new_peripherals([]), 'Empty list should return empty peripherals')

        sample_model = {'state': 'RUNNING',
                        'refresh_interval': 30,
                        'identifier': 'id_1',
                        'available': True,
                        'classes': ['class']}
        sample_mock = mock.Mock()
        sample_mock.data = sample_model
        self.assertIsInstance(self.test_db.decode_new_peripherals([sample_mock])['id_1'], PeripheralResource)

    def test_add_peripheral(self):
        test_peripheral_data = PeripheralData(
            identifier='id_1',
            available=True,
            classes=['class']
        )

        # Assert with error code
        with mock.patch.object(PeripheralsDBManager, 'add_remote_peripheral') as mock_add_remote, \
                mock.patch.object(PeripheralsDBManager, 'add_local_peripheral') as mock_add_local:
            mock_add_remote.return_value = ('per_id', 400)
            self.test_db.add_peripheral(test_peripheral_data)
            mock_add_remote.assert_called_once()
            self.assertFalse(self.test_db._latest_update)
            mock_add_local.assert_not_called()

        # Assert success remote add
        with mock.patch.object(PeripheralsDBManager, 'add_remote_peripheral') as mock_add_remote, \
                mock.patch.object(PeripheralsDBManager, 'add_local_peripheral') as mock_add_local:
            mock_add_remote.return_value = ('per_id', 200)
            self.test_db.add_peripheral(test_peripheral_data)
            mock_add_remote.assert_called_once()
            self.assertTrue(self.test_db._latest_update)
            mock_add_local.assert_called_once()

    def test_add_local_peripheral(self):
        test_resource = self.get_sample_peripheral_resource()
        self.test_db.add_local_peripheral(test_resource)
        self.assertTrue(test_resource.identifier in self.test_db._local_db)

    def test_add_remote_peripheral(self):
        mock_response = mock.Mock()
        mock_response.data = {}
        self.mock_nuvla.add.return_value = mock_response

        test_resource = self.get_sample_peripheral_resource()
        self.assertEqual((None, None), self.test_db.add_remote_peripheral(test_resource),
                         'Empty response from Nuvla should return None tuple')

        mock_response.data = {
            'resource-id': 'id'
        }
        self.assertEqual(('id', None), self.test_db.add_remote_peripheral(test_resource),
                         'Partial response should return partial results')

    @mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.content',
                new_callable=mock.PropertyMock)
    def test_remove_peripheral(self, mock_content):
        with mock.patch.object(PeripheralsDBManager, 'remove_local_peripheral') as mock_remove_local, \
                mock.patch.object(PeripheralsDBManager, 'remove_remote_peripheral') as mock_remove_remote:
            mock_remove_remote.return_value = 404
            self.test_db.remove_peripheral('id')
            mock_remove_remote.assert_called_once()
            mock_remove_local.assert_not_called()

        with mock.patch.object(PeripheralsDBManager, 'remove_local_peripheral') as mock_remove_local, \
                mock.patch.object(PeripheralsDBManager, 'remove_remote_peripheral') as mock_remove_remote:
            mock_remove_remote.return_value = 200
            self.test_db.remove_peripheral('id')
            mock_remove_remote.assert_called_once()
            mock_remove_local.assert_called_once()

    def test_remove_local_peripheral(self):
        self.test_db._local_db = {'id': 'data'}
        self.test_db._latest_update = {'id': datetime.now()}
        self.test_db.remove_local_peripheral('id')
        self.assertFalse(self.test_db._local_db)
        self.assertFalse(self.test_db._latest_update)

    def test_remove_remote_peripheral(self):
        mock_response = mock.Mock()
        mock_response.data = {'status': 200}
        self.mock_nuvla.delete.return_value = mock_response

        self.assertEqual(self.test_db.remove_remote_peripheral('id'), 200)

    def test_add(self):
        with mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.keys',
                        new_callable=mock.PropertyMock) as mock_keys_property:
            with mock.patch.object(PeripheralsDBManager, 'add_peripheral') as mock_add_peripheral, \
                    mock.patch.object(PeripheralsDBManager, 'update_local_storage') as mock_update_local:

                test_data = self.get_sample_peripheral_data()
                mock_keys_property.return_value = ['id']
                self.test_db.add({'id': test_data})
                mock_add_peripheral.assert_not_called()
                mock_update_local.assert_called_once()

            with mock.patch.object(PeripheralsDBManager, 'add_peripheral') as mock_add_peripheral, \
                    mock.patch.object(PeripheralsDBManager, 'update_local_storage') as mock_update_local:

                test_data = self.get_sample_peripheral_data()
                mock_keys_property.return_value = []
                self.test_db.add({'id': test_data})
                mock_add_peripheral.assert_called_once()
                mock_update_local.assert_called_once()

        with mock.patch.object(PeripheralsDBManager, 'add_peripheral') as mock_add_peripheral, \
                mock.patch.object(PeripheralsDBManager, 'update_local_storage') as mock_update_local, \
                mock.patch.object(PeripheralsDBManager, 'synchronize') as mock_sync:

            test_data = self.get_sample_peripheral_data()
            mock_keys_property.return_value = []
            self.test_db.add({'id': test_data})
            mock_add_peripheral.assert_called_once()
            mock_update_local.assert_called_once()

    def test_peripheral_expired(self):
        self.test_db._latest_update = {'id': datetime.now()}
        self.assertFalse(self.test_db.peripheral_expired('id'))

        self.test_db._latest_update = {'id': datetime.now() - timedelta(seconds=self.test_db.EXPIRATION_TIME+1)}
        self.assertTrue(self.test_db.peripheral_expired('id'))

    @mock.patch.object(PeripheralsDBManager, 'synchronize')
    @mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.keys', new_callable=mock.PropertyMock)
    @mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.peripheral_expired')
    @mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.remove_peripheral')
    @mock.patch('nuvlaedge.peripherals.peripheral_manager_db.PeripheralsDBManager.update_local_storage')
    def test_remove(self, mock_update_storage, mock_remove, mock_expired, mock_keys, mock_sync):
        self.test_db.remove(set())
        mock_update_storage.assert_not_called()

        mock_keys.return_value = ['id1', 'id2']
        mock_expired.side_effect = (True, False)
        self.test_db.remove({'id1', 'key', 'id2'})
        mock_update_storage.assert_called_once()
        mock_remove.assert_called_once()

    def test_edit(self):
        test_data = {'id': self.get_sample_peripheral_data()}
        with mock.patch.object(PeripheralsDBManager, 'update_local_storage') as mock_update_local:
            self.test_db.edit(test_data)
            self.assertTrue('id' in self.test_db._latest_update)
            mock_update_local.assert_called_once()
