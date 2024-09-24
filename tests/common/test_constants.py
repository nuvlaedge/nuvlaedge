import unittest

from mock import patch

from nuvlaedge.common.constants import _get_machine_id


class TestConstants(unittest.TestCase):

    @patch('nuvlaedge.common.constants.read_file')
    def test_get_machine_id(self, mock_read_file):
        path_prefix = '/wrong_path'

        mock_read_file.side_effect = [None, None]
        self.assertEqual(_get_machine_id(path_prefix), '')

        mock_read_file.side_effect = ['machine-id-1', 'machine-id-2']
        self.assertEqual(_get_machine_id(path_prefix), 'machine-id-1')

        mock_read_file.side_effect = [None, 'machine-id-a']
        self.assertEqual(_get_machine_id(path_prefix), 'machine-id-a')
