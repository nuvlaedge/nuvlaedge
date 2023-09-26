import unittest
import mock
from unittest.mock import patch, Mock, MagicMock

from nuvlaedge.common.nmap_output_xml_parser import NmapOutputXMLParser
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import Element


class TestNmapOutputXMLParser(unittest.TestCase):

    def setUp(self) -> None:
        self.file = '/tmp/common_tests/sample.xml'
        self.parser = NmapOutputXMLParser(self.file)

    @patch.object(ElementTree, 'parse')
    @patch.object(ElementTree, 'getroot')
    def test_parse(self, mock_getroot, mock_parse):
        self.parser.parse()
        mock_parse.assert_called_with(self.file, None)
        mock_getroot.assert_called_once()

    @patch.object(ElementTree, 'parse')
    @patch.object(ElementTree, 'getroot')
    def test_get_modbus_details(self, mock_getroot, mock_parse):
        mock_getroot.return_value.attrib = mock.MagicMock()
        self.parser.parse()
        sample = {'args': 'random'}
        mock_parse.assert_called_with(self.file, None)
        mock_getroot.return_value.attrib.__getitem__.side_effect = sample.__getitem__
        mock_getroot.return_value.attrib.__contains__.side_effect = sample.__contains__
        details = self.parser.get_modbus_details()
        self.assertEqual({}, details)
        mock_getroot.return_value.findall.assert_not_called()

        sample['args'] = 'modbus'
        hosts = {'addr': '127.0.0.1'}
        host_mock = MagicMock()
        host_mock.find.return_value.attrib.__getitem__.side_effect = hosts.__getitem__
        port_attrs = {
            'protocol': 'tcp',
            'portid': '54000',
        }
        port_state_attr = {'state': 'open'}
        port_attrib_mock = MagicMock()
        port_attrib_mock.attrib.__getitem__.side_effect = port_attrs.__getitem__
        port_attrib_mock.attrib.__contains__.side_effect = port_attrs.__contains__
        port_attrib_mock.find.return_value.attrib.__getitem__.side_effect = port_state_attr.__getitem__
        identifier_1 = {'key': 'sid 0xf5'}
        identifier_mock_1 = MagicMock()
        identifier_mock_1.attrib.__getitem__.side_effect = identifier_1.__getitem__
        identifier_element_1_mock = MagicMock()
        identifier_element_2_mock = MagicMock()
        identifier_element_3_mock = MagicMock()
        identifier_mock_1.findall.return_value = [identifier_element_1_mock, identifier_element_2_mock, identifier_element_3_mock]
        identifier_element_1_attrib = {'key': 'Slave ID data'}
        identifier_element_1_mock.text = 'Pymodbus-PM-2.3.0\xFF'
        identifier_element_2_attrib = {'key': 'Device identification'}
        identifier_element_2_mock.text = 'Pymodbus-PM-2.3.0'
        identifier_element_3_attrib = {'key': 'Random'}
        identifier_element_1_mock.attrib.__getitem__.side_effect = identifier_element_1_attrib.__getitem__
        identifier_element_2_mock.attrib.__getitem__.side_effect = identifier_element_2_attrib.__getitem__
        identifier_element_3_mock.attrib.__getitem__.side_effect = identifier_element_3_attrib.__getitem__

        mock_getroot.return_value.findall.side_effect = [
            [host_mock],
            [port_attrib_mock]
        ]
        port_attrib_mock.findall.return_value = [identifier_mock_1]
        details = self.parser.get_modbus_details()
        expected = {
            '127.0.0.1': [
                {'port': 54000, 'interface': 'TCP', 'available': True, 'identifiers': [{'key': 245, 'classes':
                    ['Pymodbus-PM-2.3.0\xFF'], 'vendor': 'Pymodbus-PM-2.3.0', 'name': 'Modbus 54000/TCP '
                                                                                    'Pymodbus-PM-2.3.0\xFF - 245'}]}
            ]
        }
        mock_getroot.return_value.findall.assert_called()
        self.assertEqual(expected, details)
