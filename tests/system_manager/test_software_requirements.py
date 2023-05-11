#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from nuvlaedge.system_manager.Requirements import SoftwareRequirements
import logging
import mock
import os
import unittest


class SoftwareRequirementsTestCase(unittest.TestCase):

    def setUp(self):
        self.obj = SoftwareRequirements()
        self.obj.container_runtime = mock.MagicMock()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertIsNotNone(self.obj.log,
                             'Failed to initialize Software Requirements class')
        self.assertEqual(self.obj.not_met, [],
                         'Failed to initialize list of requirements that are not met')

    def test_check_sw_requirements(self):
        # COE version must be compatible and enabled
        self.obj.container_runtime.is_version_compatible.return_value = False
        self.obj.container_runtime.is_coe_enabled.return_value = True
        self.assertFalse(self.obj.check_sw_requirements(),
                         'Failed to check SW requirements')
        self.assertEqual(len(self.obj.not_met), 1,
                         'One SW requirement was not met, but did not get which one')

        # otherwise, True
        self.obj.not_met = []
        self.obj.container_runtime.is_version_compatible.return_value = True
        self.assertTrue(self.obj.check_sw_requirements(),
                        'Says Software requirements are not met when they are')


