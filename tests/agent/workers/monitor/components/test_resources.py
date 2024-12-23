# -*- coding: utf-8 -*-
import unittest
from mock import Mock, patch, MagicMock

from nuvlaedge.agent.workers.monitor.components.resources import ResourcesMonitor
from nuvlaedge.agent.workers.monitor.data.resources_data import ResourcesData, DiskDataStructure, \
    CPUDataStructure, MemoryDataStructure


class TestResourcesMonitor(unittest.TestCase):

    @staticmethod
    def get_test_monitor():
        mock_telemetry = Mock()
        return ResourcesMonitor('test_monitor', mock_telemetry, True)

    @patch('psutil.disk_usage')
    def test_get_static_disks(self, mock_disk):
        mock_disk.return_value = [0]
        with self.assertRaises(IndexError):
            ResourcesMonitor.get_static_disks()

        mock_disk.return_value = [0, 0]
        self.assertTrue(ResourcesMonitor.get_static_disks())

    def test_clean_disk_report(self):

        test_report: dict = {}
        self.assertIsNone(ResourcesMonitor.clean_disk_report(test_report))

        test_report['size'] = 10e10
        test_report['fused'] = 50
        test_report['name'] = "ThisIsAName"
        self.assertIsInstance(ResourcesMonitor.clean_disk_report(test_report),
                              DiskDataStructure)

        test_report['size'] = 0
        self.assertIsNone(ResourcesMonitor.clean_disk_report(test_report))

    @patch('nuvlaedge.agent.workers.monitor.components.resources.execute_cmd')
    def test_get_disk_usage(self, mock_cmd):
        run = MagicMock()
        # if cmd fails, get a fallbacl list
        run.returncode = 1
        mock_cmd.return_value = run
        test_monitor: ResourcesMonitor = self.get_test_monitor()
        self.assertEqual(['capacity', 'device', 'used'],
                         sorted(test_monitor.get_disks_usage()[0].dict(by_alias=True,
                                                                       exclude_none=True)
                                .keys()),
                         'Failed to get fallback disk usage when command fails')
        self.assertEqual(len(test_monitor.get_disks_usage()), 1,
                         'Fallback disk usage should only have one disk')

        # otherwise
        run.returncode = 0
        run.stdout = '''{
                    "blockdevices": [
                        {"name":"ram0", "size":4194304, "mountpoint":null, "fsused":null},
                        {"name":"loop0", "size":null, "mountpoint":null, "fsused":null},
                        {"name":"mmcblk0", "size":31914983424, "mountpoint":null, "fsused":null,
                         "children": [
                             {"name":"mmcblk0p1", "size":2369951744, "mountpoint":null, "fsused":null},
                             {"name":"mmcblk0p7", "size":29239017472, "mountpoint":"/", "fsused":"25306009600"}
                         ]
                         }
                    ]
                }'''

        # those without a mountpoint are ignored, so in fact, we only expect one entry
        # from the above devices
        expected = {
                'device': 'mmcblk0p7',
                'capacity': 29239017472,
                'used': 25306009600
        }

        self.assertEqual(test_monitor.get_disks_usage()[0].
                         dict(by_alias=True, exclude_none=True),
                         expected,
                         'Failed to get disk usage')

    @patch('json.dumps')
    def test_get_disk_resources(self, mock_dumps):
        test_monitor = self.get_test_monitor()
        test_monitor.get_disks_usage = Mock()
        test_monitor.get_disks_usage.return_value = []
        self.assertFalse(test_monitor.get_disk_resources())

        mock_dumps.return_value = 'thisisraw'
        mock_disk = Mock()
        mock_disk.dict.return_value = ""
        mock_disk.raw_sample = ""
        mock_disk.topic = ""
        test_monitor.get_disks_usage.return_value = [mock_disk]
        test_monitor.get_disk_resources()
        self.assertEqual(mock_disk.topic, 'disks')
        self.assertEqual(mock_disk.raw_sample, 'thisisraw')

    def test_get_cpu_data(self):
        test_monitor = self.get_test_monitor()
        self.assertIsInstance(test_monitor.get_cpu_data(), CPUDataStructure)

    def test_get_memory_data(self):
        test_monitor = self.get_test_monitor()
        self.assertIsInstance(test_monitor.get_memory_data(), MemoryDataStructure)

    def test_update_data(self):
        test_monitor = self.get_test_monitor()
        test_monitor.get_disk_resources = Mock()
        test_monitor.get_disk_resources.return_value = [DiskDataStructure()]
        test_monitor.update_data()
        self.assertIsInstance(test_monitor.data.cpu, CPUDataStructure)


    def test_populate_telemetry_payload(self):
        test_monitor = self.get_test_monitor()
        test_monitor.populate_telemetry_payload()
        self.assertIsNone(test_monitor.telemetry_data.resources)

        mock_data = ResourcesData()
        mock_data.disks = [DiskDataStructure(
            device='device',
            capacity=1,
            used=1
        )]
        mock_data.cpu = CPUDataStructure(
            capacity=1,
            load=1,
            load_1=1,
            load_5=1,
            context_switches=1,
            interrupts=1,
            software_interrupts=1,
            system_calls=1
        )
        mock_data.ram = MemoryDataStructure(
            capacity=1,
            used=1
        )
        test_monitor.data = mock_data
        test_monitor.populate_telemetry_payload()
        self.assertEqual(test_monitor.telemetry_data.resources, mock_data.dict(by_alias=True, exclude_none=True))
