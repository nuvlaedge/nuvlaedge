#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest

from nuvlaedge.system_manager.requirements import SystemRequirements


class SystemRequirementsTestCase(unittest.TestCase):

    def setUp(self):
        self.obj = SystemRequirements()
        self.obj.container_runtime = mock.MagicMock()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertEqual(self.obj.minimum_requirements, {
            "cpu": 1,
            "ram": 480,
            "disk": 2
        },
                         'Failed to initialize System Requirements class')

    @mock.patch('multiprocessing.cpu_count')
    def test_check_cpu_requirements(self, mock_cpu_count):
        # if not enough CPUs, get False
        mock_cpu_count.return_value = 0
        self.assertFalse(self.obj.check_cpu_requirements(),
                         'Ignored that there are not enough CPUs to meet the requirements')
        self.assertEqual(len(self.obj.not_met), 1,
                         'Missing error message about unfulfilled requirement')
        self.obj.not_met = []

        # otherwise, True
        mock_cpu_count.return_value = 1
        self.assertTrue(self.obj.check_cpu_requirements(),
                        'Says CPU requirements are not met when they are')

    def test_check_ram_requirements(self):
        # if not enough RAM, get False
        self.obj.container_runtime.get_ram_capacity.return_value = 0.123
        self.assertFalse(self.obj.check_ram_requirements(),
                         'Ignored that there is not enough RAM to meet the requirements')
        self.assertEqual(len(self.obj.not_met), 1,
                         'Missing error message about unfulfilled requirement')
        self.obj.not_met = []

        # otherwise, True
        self.obj.container_runtime.get_ram_capacity.return_value = 1230
        self.assertTrue(self.obj.check_ram_requirements(),
                        'Says RAM requirements are not met when they are')

    @mock.patch('shutil.disk_usage')
    def test_check_disk_requirements(self, mock_disk_usage):
        # if not enough disk, get False
        mock_disk_usage.return_value = [0]
        self.assertFalse(self.obj.check_disk_requirements(),
                         'Ignored that there is not enough disk to meet the requirements')
        self.assertEqual(len(self.obj.not_met), 1,
                         'Missing error message about unfulfilled requirement')
        self.obj.not_met = []

        # otherwise, True
        mock_disk_usage.return_value = [10000000000]
        self.assertTrue(self.obj.check_disk_requirements(),
                        'Says Disk requirements are not met when they are')

    @mock.patch.object(SystemRequirements, 'check_cpu_requirements')
    @mock.patch.object(SystemRequirements, 'check_ram_requirements')
    @mock.patch.object(SystemRequirements, 'check_disk_requirements')
    def test_check_all_hw_requirements(self, mock_check_cpu, mock_check_ram, mock_check_disk):
        # only if all are True we get True
        mock_check_cpu.return_value = mock_check_ram.return_value = mock_check_disk.return_value = False
        self.assertFalse(self.obj.check_all_hw_requirements(),
                         'Failed to check that NO system requirements are met')

        mock_check_cpu.return_value = mock_check_ram.return_value = True
        self.assertFalse(self.obj.check_all_hw_requirements(),
                         'Saying minimum requirements are met when there is not enough Disk')

        mock_check_disk.return_value = True
        self.assertTrue(self.obj.check_all_hw_requirements(),
                        'Failed to check valid system requirements')
