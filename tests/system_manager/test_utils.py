#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import string
import unittest
import nuvlaedge.system_manager.common.utils as utils


class DockerTestCase(unittest.TestCase):

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_set_operational_status(self):
        # writes twice
        with mock.patch("nuvlaedge.system_manager.common.utils.open") as mock_open:
            self.assertIsNone(utils.set_operational_status('status', []),
                              'Failed to set operational status')
            self.assertEqual(mock_open.call_count, 2,
                             'Should write two files when setting operational status')

    @mock.patch('os.path.exists')
    def test_status_file_exists(self, mock_exists):
        # simple check for file existence
        mock_exists.return_value = False
        self.assertFalse(utils.status_file_exists(),
                         'Says status file exists when it does not')

        mock_exists.return_value = True
        self.assertTrue(utils.status_file_exists(),
                        'Says status file does not exist when it does')

    def test_random_choices(self):
        assert ['a'] == utils.random_choices('a')
        assert ['a'] * 5 == utils.random_choices('a', 5)

        choices = utils.random_choices(string.ascii_letters, 5)
        assert 5 == len(choices)
        assert all(map(lambda x: x in string.ascii_letters, choices))
        assert True in map(lambda x: x != choices[0], choices[1:])
