#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest
import nuvlaedge.system_manager.common.ContainerRuntime as ContainerRuntime


class ContainersCase(unittest.TestCase):

    def setUp(self) -> None:
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            self.obj = ContainerRuntime.Containers(logging)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertIsInstance(self.obj.container_runtime, ContainerRuntime.Docker,
                              'Failed to initialize container_runtime variable')
