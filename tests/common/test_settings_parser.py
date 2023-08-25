from pathlib import Path

from unittest import TestCase

from pydantic import BaseSettings
import tomllib
from mock import patch, mock_open

from nuvlaedge.common.settings_parser import NuvlaConfig


class TestNuvlaConfig(TestCase):

    @patch.object(BaseSettings, 'parse_obj')
    @patch.object(tomllib, 'loads')
    @patch.object(Path, 'exists')
    @patch.object(Path, 'is_file')
    def test_from_toml(self, mock_is_file, mock_exists, mock_loads, mock_parse):
        with self.assertRaises(FileNotFoundError):
            mock_is_file.return_value = False
            mock_exists.return_value = False
            NuvlaConfig.from_toml(Path('testPath'))

        mock_is_file.return_value = True
        mock_exists.return_value = True
        opener = mock_open(read_data='FILEDATA')
        mock_loads.return_value = 'TOMLDATA'
        def mocked_open(self, *args, **kwargs):
            return opener(self, *args, **kwargs)

        with patch.object(Path, 'open', mocked_open):
            NuvlaConfig.from_toml(Path('test_path'))
            mock_loads.assert_called_with('FILEDATA')
            mock_parse.assert_called_with('TOMLDATA')

