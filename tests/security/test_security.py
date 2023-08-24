import os
import subprocess
import logging
from unittest import TestCase
from pathlib import Path
from datetime import datetime
import json
import time

import mock
import nuvla
from mock import patch, mock_open, Mock
import xml.etree.ElementTree

import nuvlaedge.security.security
from nuvlaedge.security.security import Security
from nuvlaedge.security.settings import SecurityConfig
from nuvlaedge.security.constants import ONLINE_VULSCAN_DB_PREFIX, DATE_FORMAT


class TestSecurity(TestCase):

    @patch.object(Security, 'wait_for_nuvlaedge_ready')
    @patch.object(Path, 'mkdir')
    @patch.object(os, 'listdir')
    def setUp(self, list_dir, mock_mkdir, mock_wait):
        mock_wait.return_value = True
        # Mock Config
        self.config: SecurityConfig = SecurityConfig()

        # Mock class
        self.security: Security = Security(self.config)

    @patch.object(os.path, 'exists')
    @patch('nuvlaedge.security.security.Api')
    def test_authenticate(self, mock_api, mock_exists):

        mock_exists.return_value = False
        with patch("builtins.open", mock_open(read_data="data")) as mock_file, \
                patch('json.loads') as mock_loads:
            # mock_open.reads.return_value = None
            self.assertIsNone(self.security.authenticate())

        mock_exists.return_value = True
        with patch("builtins.open", mock_open(read_data="data")) as mock_file, \
                patch('json.loads') as mock_loads:
            mock_loads.return_value = {'api-key': 'key',
                                       'secret-key': 'secret'}
            self.security.authenticate()
            mock_loads.assert_called_once()

    @patch.object(time, 'sleep')
    @patch.object(nuvlaedge.security.security, 'timeout')
    @patch.object(os.path, 'exists')
    def test_wait_for_nuvlaedge_ready(self, mock_exists, mock_timeout, mock_time):
        mock_timeout.return_value.__enter__.return_value.name = 'timeout'
        mock_time.sleep.return_value = None
        mock_exists.side_effect = [False, True, False, True]

        with patch("builtins.open", mock_open(read_data="random data")) as mock_file:
            self.security.wait_for_nuvlaedge_ready()
            self.assertEqual(2, mock_time.call_count)
            self.assertFalse(self.security.nuvla_endpoint_insecure)

        mock_exists.reset_mock()
        mock_exists.side_effect = [False, True, False, True]
        with patch("builtins.open",
                   mock_open(read_data="NUVLA_ENDPOINT=nuvla.io\nNUVLA_ENDPOINT_INSECURE=True")) as mock_file:
            self.security.wait_for_nuvlaedge_ready()
            self.assertTrue(self.security.nuvla_endpoint_insecure)
            self.assertEqual('nuvla.io', self.security.nuvla_endpoint)

    @patch.object(os, 'listdir')
    def test_get_external_db_as_csv(self, mock_listdir):
        self.security.execute_cmd = Mock()
        self.security.set_previous_external_db_update = Mock()
        ret_mock = Mock()
        ret_mock.startswith.return_value = True
        mock_listdir.return_value = [ret_mock]
        self.security.execute_cmd.return_value = None
        self.security.get_external_db_as_csv()
        self.assertEqual(3, self.security.execute_cmd.call_count)
        self.assertEqual(self.security.vulscan_dbs, [ret_mock])
        self.security.set_previous_external_db_update.assert_called_once()

        self.security.execute_cmd.reset_mock()
        self.security.set_previous_external_db_update.reset_mock()
        self.security.execute_cmd.side_effect = subprocess.CalledProcessError(returncode=1, cmd='ERROR')
        self.security.get_external_db_as_csv()
        self.security.execute_cmd.assert_called_once()
        self.security.set_previous_external_db_update.assert_called_once()

        self.security.execute_cmd.reset_mock()
        self.security.set_previous_external_db_update.reset_mock()
        with patch.object(os.path, 'exists') as mock_exists, \
                patch.object(os, 'remove') as mock_remove:
            mock_exists.return_value = True
            self.security.get_external_db_as_csv()
            mock_remove.assert_called_once()

    @patch('nuvlaedge.security.security.datetime')
    def test_set_previous_external_db_update(self, mock_datetime):
        date_mock = Mock()
        date_mock.strftime.return_value = 'DATE'
        mock_datetime.utcnow.return_value = date_mock
        with patch.object(os.path, 'exists') as mock_exists, patch.object(os, 'mkdir') as mock_mkdir:
            mock_exists.return_value = False
            with patch("builtins.open", mock_open()) as mock_o:
                self.security.set_previous_external_db_update()
                mock_mkdir.assert_called_once()

        with patch.object(os.path, 'exists') as mock_exists, patch.object(os, 'mkdir') as mock_mkdir:
            mock_exists.return_value = True
            mock_mkdir.assert_not_called()

    @patch.object(logging, 'error')
    def test_execute_cmd(self, mock_log):
        with patch('nuvlaedge.security.security.run') as mock_run:
            # Test Selection flag
            self.security.execute_cmd(['some'])
            mock_run.assert_called_once()
            expected_return = {'stdout': 'Out',
                               'stderr': 'NoError',
                               'returncode': 0}
            mock_run.return_value = expected_return
            self.assertEqual(self.security.execute_cmd(['some']), expected_return)

        with patch('nuvlaedge.security.security.run') as mock_run:
            mock_run.side_effect = OSError('ERR')
            self.assertIsNone(self.security.execute_cmd(['some']))

        with patch('nuvlaedge.security.security.run') as mock_run:
            mock_run.side_effect = ValueError('ERR')
            self.assertIsNone(self.security.execute_cmd(['some']))

        with patch('nuvlaedge.security.security.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('ERR', timeout=1)
            self.assertIsNone(self.security.execute_cmd(['some']))

        with patch('nuvlaedge.security.security.run') as mock_run:
            mock_run.side_effect = subprocess.SubprocessError('ERR')
            self.assertIsNone(self.security.execute_cmd(['some']))


    @patch.object(os, 'listdir')
    def test_gather_external_db_file_names(self, mock_listdir):
        mock_listdir.return_value = ['random_refix']
        self.security.gather_external_db_file_names()
        self.assertFalse(self.security.vulscan_dbs)

        mock_listdir.return_value = [ONLINE_VULSCAN_DB_PREFIX]
        self.security.gather_external_db_file_names()
        self.assertEqual([ONLINE_VULSCAN_DB_PREFIX], self.security.vulscan_dbs)

    @patch.object(os.path, 'exists')
    def test_get_previous_external_db_update(self, mock_exists):
        self.security.gather_external_db_file_names = Mock()

        mock_exists.return_value = False
        self.assertEqual(datetime(1970, 1, 1), self.security.get_previous_external_db_update())

        mock_exists.return_value = True
        with patch("builtins.open", mock_open(read_data="random_datatime")) as mock_file:
            self.assertEqual(datetime(1970, 1, 1), self.security.get_previous_external_db_update())

        sample_date = "23-Aug-2023 (14:08:11.571703)"
        with patch("builtins.open", mock_open(read_data=sample_date)) as mock_file:
            self.security.vulscan_dbs = True
            self.assertEqual(datetime.strptime(sample_date, DATE_FORMAT),
                             self.security.get_previous_external_db_update())

            self.security.vulscan_dbs = False
            self.assertEqual(datetime(1970, 1, 1), self.security.get_previous_external_db_update())

    @patch.object(Security, 'authenticate')
    @patch.object(Security, 'get_external_db_as_csv')
    def test_update_vulscan_db(self, mock_external_db, mock_auth):
        mock_api = Mock()
        mock_auth.return_value = mock_api
        mock_collection = Mock()
        mock_collection.resources = []
        mock_api.search.return_value = mock_collection

        self.assertIsNone(self.security.update_vulscan_db())
        mock_api.logout.assert_called_once()
        mock_external_db.assert_not_called()

        mock_res = Mock()
        mock_res.data = {'updated': 2022}
        mock_collection.resources = [mock_res]
        self.security.local_db_last_update = 2023
        self.security.update_vulscan_db()
        mock_external_db.assert_not_called()

        self.security.local_db_last_update = False
        self.security.update_vulscan_db()
        mock_external_db.assert_called_once()

    @patch.object(Security, 'extract_basic_info_from_xml_port')
    @patch.object(Security, 'extract_ports_with_vulnerabilities')
    def test_parse_vulscan_xml(self, mock_extract, mock_info):
        ...

    @patch('nuvlaedge.security.security.Popen')
    def test_run_cve_scan(self, mock_popen):
        process = mock_popen.return_value.__enter__.return_value
        process.returncode = 0

        process.communicate.return_value = (None, b'Err')
        self.assertFalse(self.security.run_cve_scan(['ls']))

        process.communicate.return_value = (b'STD', b'Err')
        self.assertTrue(self.security.run_cve_scan(['ls']))

    @patch.object(Security, 'run_cve_scan')
    @patch.object(Security, 'parse_vulscan_xml')
    def test_run_scan(self, mock_parser, mock_run_cve):

        self.security.vulscan_dbs = ['database']
        mock_run_cve.return_value = None
        self.security.run_scan()
        mock_parser.assert_not_called()

        mock_run_cve.return_value = 'Scan'
        with patch("builtins.open", mock_open()) as mock_file, patch.object(json, 'dump') as mock_dump:
            self.security.run_scan()
            mock_parser.assert_called_once()
            mock_dump.assert_called_once()

