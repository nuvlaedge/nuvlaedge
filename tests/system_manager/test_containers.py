#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest
from nuvlaedge.system_manager.common import coe_client


class ContainersCase(unittest.TestCase):

    def setUp(self) -> None:
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            self.obj = coe_client.Containers(logging)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertIsInstance(self.obj.coe_client, coe_client.Docker,
                              'Failed to initialize coe_client variable')
