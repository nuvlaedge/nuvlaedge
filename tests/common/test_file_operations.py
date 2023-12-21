import unittest
import os
from typing import Optional
from pathlib import Path

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeStaticModel
from nuvlaedge.common.file_operations import write_file, read_file, file_exists_and_not_empty, \
    create_directory


class Testing(NuvlaEdgeStaticModel):
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

    def test_read_write_files(self):
        # write json data and read them correctly
        _test = Testing()
        _test.param1 = 'Testing Param 1'
        _test.param2 = [_test.param1]

        write_file(_test, self.temp_file)
        content = read_file(self.temp_file, decode_json=True)
        self.assertEqual(content['param1'], 'Testing Param 1')
        self.assertEqual(content['param2'], ['Testing Param 1'])
        os.unlink(self.temp_file)

        # read non existent file
        self.assertIsNone(read_file(self.temp_file, decode_json=True))
        f = open(self.temp_file, 'w')
        f.close()
        self.assertIsNone(read_file(self.temp_file, decode_json=True))
        self.assertFalse(file_exists_and_not_empty(self.temp_file))
        os.unlink(self.temp_file)

    def test_create_directory(self):
        create_directory(self.cwd + '/tempdir')
        _dir = Path(self.cwd + '/tempdir')
        _dir.rmdir()


if __name__ == '__main__':
    unittest.main()
