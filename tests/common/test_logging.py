import logging
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock

import nuvlaedge.common.nuvlaedge_logging as ne_logging


class TestNuvlaEdgeLogging(TestCase):
    @patch('nuvlaedge.common.nuvlaedge_logging.Path.mkdir')
    @patch('nuvlaedge.common.nuvlaedge_logging.Path.exists')
    def test_set_logging_configuration(self, mock_exists, mock_mkdir):
        mock_exists.return_value = False
        ne_logging.set_logging_configuration(True, '/tmp/', logging.INFO)
        self.assertTrue(ne_logging._DEBUG)
        self.assertEqual(ne_logging._LOG_PATH, Path('/tmp/'))
        self.assertIsInstance(ne_logging._LOG_PATH, Path)
        mock_mkdir.assert_called_once()

    # Tests for get_nuvlaedge_logger
    def test_get_nuvlaedge_logger(self):
        logger = ne_logging.get_nuvlaedge_logger()
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'root')

        logger = ne_logging.get_nuvlaedge_logger('test')
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'test')


