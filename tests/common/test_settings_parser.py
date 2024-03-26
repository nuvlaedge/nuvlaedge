from pathlib import Path

from unittest import TestCase

from pydantic_settings import BaseSettings
import toml
from mock import patch, mock_open

from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings


class TestNuvlaConfig(TestCase):

    @patch.object(BaseSettings, 'model_validate')
    @patch.object(toml, 'loads')
    @patch.object(Path, 'exists')
    @patch.object(Path, 'is_file')
    def test_from_toml(self, mock_is_file, mock_exists, mock_loads, mock_parse):
        with self.assertRaises(FileNotFoundError):
            mock_is_file.return_value = False
            mock_exists.return_value = False
            NuvlaEdgeBaseSettings.from_toml(Path('testPath'))

        mock_is_file.return_value = True
        mock_exists.return_value = True
        opener = mock_open(read_data='FILEDATA=TRUE')
        mock_loads.return_value = 'TOMLDATA'

        def mocked_open(self, *args, **kwargs):
            return opener(self, *args, **kwargs)

        with patch.object(Path, 'open', mocked_open):
            NuvlaEdgeBaseSettings.from_toml(Path('test_path'))
            mock_loads.assert_called_with('FILEDATA=TRUE')
            mock_parse.assert_called_with('TOMLDATA')

