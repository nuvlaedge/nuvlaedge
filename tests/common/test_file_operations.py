import unittest
import os
from typing import Optional
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from pydantic import BaseModel

from nuvlaedge.common.file_operations import __get_kwargs as get_kwargs
from nuvlaedge.common.file_operations import __default_model_kwargs as default_model_kwargs
from nuvlaedge.common.file_operations import _write_content_to_file as write_content_to_file
from nuvlaedge.common.file_operations import _write_model_to_file as write_model_to_file
from nuvlaedge.common.file_operations import _write_json_to_file as write_json_to_file
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.common.file_operations import write_file, read_file, file_exists_and_not_empty, \
    create_directory


patch_file_path = 'nuvlaedge.common.file_operations.Path'


class TestingModel(NuvlaEdgeStaticModel):
    """
        This is a test class with basic params
        used for the test of file operations
    """
    param1: Optional[str] = None,
    param2: Optional[list[str]] = None


class TestFileOperations(unittest.TestCase):

    def setUp(self) -> None:
        self.cwd = '/tmp/'
        self.temp_file = self.cwd + 'temp'
        self.temp_path_file: Path = Path(self.temp_file)

        self.mock_path_instance = None
        self.mock_path_class = None

    def setup_path(self, mock_class):
        self.mock_path_instance = MagicMock()
        self.mock_path_class = mock_class
        self.mock_path_class.return_value = self.mock_path_instance

    @patch(patch_file_path)
    def test_file_exists_and_not_empty(self, mock_path) -> None:
        self.setup_path(mock_path)

        self.mock_path_instance.exists.return_value = False

        self.assertFalse(file_exists_and_not_empty(''))
        self.mock_path_class.assert_called_once()
        self.mock_path_instance.exists.assert_called_once()
        self.mock_path_instance.is_file.assert_not_called()

    @patch(patch_file_path)
    @patch('nuvlaedge.common.file_operations.file_exists_and_not_empty')
    def test_read_file(self, mock_exists, mock_path) -> None:
        self.setup_path(mock_path)
        mock_exists.return_value = False
        self.assertIsNone(read_file(self.temp_file))

        mock_exists.return_value = True
        mock_file = MagicMock()
        self.mock_path_instance.open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = ''
        self.assertEqual(read_file(self.temp_file, decode_json=False), '')

        mock_file.read.return_value = '{"test": "value"}'
        self.assertEqual(read_file(self.temp_file, decode_json=True), {"test": "value"})

        mock_file.read.return_value = 'NOT A JSON'
        self.assertIsNone(read_file(self.temp_file, decode_json=True, remove_file_on_error=True))
        self.mock_path_instance.unlink.assert_called_once()

    @patch('nuvlaedge.common.file_operations._write_json_to_file')
    @patch('nuvlaedge.common.file_operations._write_content_to_file')
    @patch('nuvlaedge.common.file_operations._write_model_to_file')
    def test_write_file(self, mock_model, mock_content, mock_json):
        with self.assertRaises(ValueError):
            write_file(set(), "empty_path", fail_if_error=True)

        with patch('nuvlaedge.common.file_operations.logger.warning') as mock_log:
            write_file(set(), "empty_path", fail_if_error=False)
            mock_log.assert_called_once()

        write_file("STR_Content", "empty_path", fail_if_error=True)
        mock_content.assert_called_once()

        write_file({'test': 'value'}, "empty_path", fail_if_error=True)
        mock_json.assert_called_once()

        test_model = TestingModel(param1='value')

        write_file(test_model, "empty_path", fail_if_error=True)
        mock_model.assert_called_once()

    @patch('nuvlaedge.common.file_operations.__atomic_write')
    def test_write_content_to_file(self, mock_atomic_write):
        self.assertIsNone(write_content_to_file(None, Path('empty_path'), fail_if_error=True))

        self.assertIsNone(write_content_to_file("Content", Path('empty_path'), fail_if_error=True))
        mock_atomic_write.assert_called_once()

        mock_atomic_write.side_effect = ValueError("ERROR")
        mock_path = MagicMock()
        with self.assertRaises(ValueError):
            self.assertIsNone(write_content_to_file("Content", mock_path, fail_if_error=True))
            mock_path.unlink.assert_called_once()

    def test_get_kwargs(self):
        test_args = default_model_kwargs.copy()
        test_args = {k: v for k, v in test_args.items() if v}

        self.assertEqual(get_kwargs({}, default_model_kwargs),
                         (test_args, {}))
        test_args['indent'] = 6
        self.assertEqual(get_kwargs({"indent": 6}, default_model_kwargs), (test_args, {}))

    @patch('nuvlaedge.common.file_operations.__get_model_kwargs')
    @patch('nuvlaedge.common.file_operations._write_content_to_file')
    def test_write_model(self, mock_write_file, mock_get_args):
        mock_model = MagicMock()
        mock_get_args.return_value = ({}, {})
        write_model_to_file(mock_model, Path('empty_path'), fail_if_error=True)
        mock_get_args.assert_called_once()
        mock_write_file.assert_called_once()
        mock_model.model_dump_json.assert_called_once()

    @patch('nuvlaedge.common.file_operations.__get_json_kwargs')
    @patch('nuvlaedge.common.file_operations._write_content_to_file')
    def test_write_json(self, mock_write_file, mock_get_args):
        mock_json = {'value': 'as'}
        mock_get_args.return_value = ({}, {})
        write_json_to_file(mock_json, Path('empty_path'), fail_if_error=True)
        mock_get_args.assert_called_once()
        mock_write_file.assert_called_once()

    def test_create_directory(self):
        create_directory(self.cwd + '/tempdir')
        _dir = Path(self.cwd + '/tempdir')
        _dir.rmdir()


if __name__ == '__main__':
    unittest.main()
