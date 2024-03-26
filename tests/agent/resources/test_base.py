from unittest import TestCase
from unittest.mock import patch, Mock, call

from nuvlaedge.agent.nuvla.resources.base import AutoUpdateNuvlaEdgeTrackedResource


class TestAutoUpdateNuvlaEdgeTrackedResource(TestCase):
    def setUp(self):
        self.nuvla_client = Mock()
        self.resource_id = 'mock'
        self.resource = AutoUpdateNuvlaEdgeTrackedResource(nuvla_client=self.nuvla_client, resource_id=self.resource_id)

    def test_init(self):
        self.assertEqual(self.resource._nuvla_client, self.nuvla_client)
        self.assertEqual(self.resource._resource_id, self.resource_id)
        self.assertEqual(self.resource._last_update_time, -1.0)
        self.assertEqual(self.resource._MIN_UPDATE_PERIOD, 60)
        self.assertEqual(self.resource._FIELD_TIMEOUT_PERIOD, 180)
        self.assertEqual(self.resource._accessed_fields, {})

    # Test _sync method
    @patch('nuvlaedge.agent.nuvla.resources.base.time')
    @patch.object(AutoUpdateNuvlaEdgeTrackedResource, '_update_fields')
    def test_sync(self, mock_update, mock_time):
        mock_time.perf_counter.return_value = 1
        with patch('nuvlaedge.agent.nuvla.resources.base.logging.Logger.debug') as mock_debug:
            self.resource._sync()
            self.nuvla_client.get.assert_called_once_with(self.resource_id, select=None)
            self.assertEqual(self.resource._last_update_time, 1)
            mock_update.assert_called_once_with(self.nuvla_client.get.return_value.data)
            print(mock_debug.call_args_list)
            self.assertEqual(mock_debug.call_args_list,
                             [call('Retrieving full {} resource'.format(self.resource_id)),
                              call('Updating NuvlaEdge fields: None from resource {}'.format(self.resource_id))])

    # Test force_update method
    @patch.object(AutoUpdateNuvlaEdgeTrackedResource, '_sync')
    def test_force_update(self, mock_sync):
        self.resource._last_update_time = 1
        self.resource.force_update()
        self.assertEqual(self.resource._last_update_time, -1)
        mock_sync.assert_called_once()

    # Test _update_fields method
    @patch.object(AutoUpdateNuvlaEdgeTrackedResource, '_sync')
    def test_update_fields(self, mock_sync):
        data = {'id': 'value1', 'name': 'value2'}
        self.resource._update_fields(data)
        self.assertEqual(self.resource.id, 'value1')
        self.assertEqual(self.resource.name, 'value2')

    # Test __getattribute__ method
    @patch.object(AutoUpdateNuvlaEdgeTrackedResource, '_sync')
    @patch('nuvlaedge.agent.nuvla.resources.base.time')
    def test_getattribute(self, mock_time, mock_sync):
        mock_time.perf_counter.return_value = 1
        self.resource._last_update_time = 1
        _ = self.resource.id
        self.assertEqual(self.resource._accessed_fields, {'id': 1})
        mock_sync.assert_called_once()
        _ = self.resource.id
        self.assertEqual(mock_sync.call_count, 2)
