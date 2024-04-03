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
        with mock.patch("nuvlaedge.system_manager.common.utils.write_file") as mock_open:
            self.assertIsNone(utils.set_operational_status('status', []),
                              'Failed to set operational status')
            self.assertEqual(mock_open.call_count, 2,
                             'Should write two files when setting operational status')

    def test_random_choices(self):
        assert ['a'] == utils.random_choices('a')
        assert ['a'] * 5 == utils.random_choices('a', 5)

        choices = utils.random_choices(string.ascii_letters, 5)
        assert 5 == len(choices)
        assert all(map(lambda x: x in string.ascii_letters, choices))
        assert True in map(lambda x: x != choices[0], choices[1:])
