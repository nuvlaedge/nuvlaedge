#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from pathlib import Path
import mock
import os
import unittest

import nuvla.api

import tests.agent.utils.fake as fake
from nuvlaedge.agent.common.nuvlaedge_common import NuvlaEdgeCommon
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.factory import get_coe_client


class NuvlaEdgeCommonTestCase(unittest.TestCase):
    agent_nuvlaedge_common_open = 'nuvlaedge.agent.common.nuvlaedge_common.open'
    atomic_write = 'nuvlaedge.agent.common.util.atomic_write'
    get_ne_id_api = 'nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon._get_nuvlaedge_id_from_api_session'

    @mock.patch('os.path.isdir')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.set_vpn_config_extra')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.set_nuvlaedge_id')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.save_nuvla_configuration')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.set_nuvla_endpoint')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.set_installation_home')
    def setUp(self, mock_set_install_home, mock_set_nuvla_endpoint, mock_save_nuvla_conf,
              mock_set_nuvlaedge_id, mock_set_vpn_config_extra, mock_os_isdir) -> None:
        self.installation_home = '/home/fake'
        mock_set_install_home.return_value = self.installation_home
        mock_set_nuvla_endpoint.return_value = ('fake.nuvla.io', True)
        mock_save_nuvla_conf.return_value = True
        mock_os_isdir.return_value = True
        mock_set_vpn_config_extra.return_value = ''
        mock_set_nuvlaedge_id.return_value = 'nuvlabox/fake-id'
        self.obj = NuvlaEdgeCommon(get_coe_client())
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        self.assertEqual(self.obj.data_volume, "/srv/nuvlaedge/shared",
                         'Default NuvlaEdge data volume path was not set correctly')

        # by default, we should have a Docker runtime client
        self.assertIsInstance(self.obj.coe_client, DockerClient,
                              'Container runtime not set to Docker client as expected')
        self.assertEqual(self.obj.mqtt_broker_host, 'data-gateway',
                         'data-gateway host name was not set')

        # VPN iface name should be vpn by default
        self.assertEqual(self.obj.vpn_interface_name, 'tun',
                         'VPN interface name was not set correctly')

    def test_set_vpn_config_extra(self):
        # if previously stored, read the extra config from the file
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data='foo')):
            self.assertEqual(self.obj.set_vpn_config_extra(), 'foo',
                             'Failed to read VPN extra config from persisted file')

        # if not previously stored, read the extra config from the env, and save it into a file
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open:
            mock_open.side_effect = [FileNotFoundError, mock.MagicMock()]
            os.environ.setdefault('VPN_CONFIG_EXTRA', r'--allow-pull-fqdn\n--client-nat snat network netmask alias')
            self.assertEqual(self.obj.set_vpn_config_extra(),
                             '--allow-pull-fqdn\n--client-nat snat network netmask alias',
                             'Failed to read extra VPN config from environment variable')

    @mock.patch('os.path.exists')
    def test_set_installation_home(self, mock_exists):
        # if there is not file storing this variable, then we get it from env
        default_value = '/home/fake2'
        os.environ['HOST_HOME'] = default_value
        mock_exists.return_value = False
        self.assertEqual(self.obj.set_installation_home(''), default_value,
                         'Failed to get installation home path from env')

        # if it exists, it reads the value from the file (with strip())
        mock_exists.return_value = True
        file_value = '/home/fake3'
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data=file_value + '\n')):
            self.assertEqual(self.obj.set_installation_home('fake-file'), file_value,
                             'Unable to get installation home path from file')

    def test_set_nuvla_endpoint(self):
        # first time, will read vars from env
        os.environ['NUVLA_ENDPOINT'] = 'fake.nuvla.io'
        os.environ['NUVLA_ENDPOINT_INSECURE'] = 'True'
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_nuvla_conf:
            mock_nuvla_conf.side_effect = FileNotFoundError
            self.assertEqual(self.obj.set_nuvla_endpoint(), ('fake.nuvla.io', True),
                             'Failed to retrieve Nuvla endpoint conf from env during first run')
            # same result in case the file exists but it is malformed
            mock_nuvla_conf.side_effect = IndexError
            self.assertEqual(self.obj.set_nuvla_endpoint(), ('fake.nuvla.io', True),
                             'Failed to retrieve Nuvla endpoint conf from env when local file is malformed')

            # different variations of the Nuvla endpoint should always result on a clean endpoint string
            os.environ['NUVLA_ENDPOINT'] = 'fake.nuvla.io/'
            self.assertEqual(self.obj.set_nuvla_endpoint(), ('fake.nuvla.io', True),
                             'Failed to remove slash from endpoint string')
            os.environ['NUVLA_ENDPOINT'] = 'https://fake.nuvla.io/'
            self.assertEqual(self.obj.set_nuvla_endpoint(), ('fake.nuvla.io', True),
                             'Failed to remove https:// from endpoint string')

            # wrt being insecure, for any value different from "false" (case-insensitive) it should always be True(bool)
            os.environ['NUVLA_ENDPOINT_INSECURE'] = 'something'
            self.assertEqual(self.obj.set_nuvla_endpoint()[1], True,
                             'Failed to set Nuvla insecure to True')
            os.environ['NUVLA_ENDPOINT_INSECURE'] = 'false'
            self.assertEqual(self.obj.set_nuvla_endpoint()[1], False,
                             'Failed to set Nuvla endpoint insecure to False')

            # works with bool env vars too
            os.environ['NUVLA_ENDPOINT_INSECURE'] = '0'
            self.assertEqual(self.obj.set_nuvla_endpoint()[1], True,
                             'Failed to parse Nuvla endpoint insecure from a numerical env var')

        # but if local conf exists, read from it
        local_conf = 'NUVLA_ENDPOINT=fake.nuvla.local.io\nNUVLA_ENDPOINT_INSECURE=False'
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data=local_conf)):
            self.assertEqual(self.obj.set_nuvla_endpoint(), ('fake.nuvla.local.io', False),
                             'Unable to get Nuvla endpoint details from local file')

    @mock.patch('os.path.exists')
    def test_save_nuvla_configuration(self, mock_exists):
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open, \
                mock.patch(self.atomic_write):
            # if file exists, don't do anything
            mock_exists.return_value = True
            self.assertIsNone(self.obj.save_nuvla_configuration('', ''),
                              'Returned something when None was expected')
            mock_open.assert_not_called()

            # if files does not exist, then write it
            mock_exists.return_value = False
            mock_open.return_value.write.return_value = None
            self.assertIsNone(self.obj.save_nuvla_configuration('file', 'content'),
                              'Returned something when None was expected')

    @mock.patch('os.path.exists')
    def test_set_nuvlaedge_id(self, mock_exists):
        # if there's no env and not previous ID saved on file, raise exception
        mock_exists.return_value = False
        self.assertRaises(Exception, self.obj.set_nuvlaedge_id)

        # if the file exists, but is malformed, also raise exception
        mock_exists.return_value = True
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data='foo: bar')):
            self.assertRaises(Exception, self.obj.set_nuvlaedge_id)

        # if file is correct, read from it and cleanup ID
        os.environ['NUVLAEDGE_UUID'] = 'nuvlabox/fake-id'
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data='{"id": "fake-id"}')):
            self.assertEqual(self.obj.set_nuvlaedge_id(), 'nuvlabox/fake-id',
                             'Unable to correctly get NuvlaEdge ID from context file')

        # and if provided by env, compare it
        # if not equal, raise exception
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"id": "fake-id"}])):
                os.environ['NUVLAEDGE_UUID'] = 'nuvlabox/fake-id-2'
                self.assertRaises(RuntimeError, self.obj.set_nuvlaedge_id)

        # if they are the same, all good
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data='{"id": "fake-id-2"}')):
            os.environ['NUVLAEDGE_UUID'] = 'nuvlabox/fake-id-2'
            self.assertEqual(self.obj.set_nuvlaedge_id(), 'nuvlabox/fake-id-2',
                             'Failed to check that the provided NUVLAEDGE_UUID env var is the same as the existing one')

        # if old file does not exist but env is provided, take it
        mock_exists.return_value = False
        os.environ['NUVLAEDGE_UUID'] = 'nuvlabox/fake-id-3'
        self.assertEqual(self.obj.set_nuvlaedge_id(), 'nuvlabox/fake-id-3',
                         'Unable to correctly get NuvlaEdge ID from env')

        # if the file exists and is empty but id can be found from the credential (api session)
        mock_exists.return_value = True
        del os.environ['NUVLAEDGE_UUID']
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data='')), \
                mock.patch(self.get_ne_id_api) as session_nuvlaedge_id:
            session_nuvlaedge_id.return_value = 'nuvlabox/fake-id-4'
            self.assertEqual(self.obj.set_nuvlaedge_id(), 'nuvlabox/fake-id-4',
                             'Failed to check that NuvlaEdge ID from session is used in case of an empty context file')

    def test_get_api_keys(self):
        # if there are no keys in env, return None,None
        self.assertEqual(self.obj.get_api_keys(), (None, None),
                         'Got API keys when none were defined')

        # keys are sensitive so they deleted from env if they exist
        os.environ['NUVLAEDGE_API_KEY'] = 'api-key'
        os.environ['NUVLAEDGE_API_SECRET'] = 'api-secret'
        self.assertEqual(self.obj.get_api_keys(), ('api-key', 'api-secret'),
                         'Unable to fetch API keys from env')

        for key in ['NUVLAEDGE_API_KEY', 'NUVLAEDGE_API_SECRET']:
            self.assertNotIn(key, os.environ,
                             f'{key} was not removed from env after lookup')

    def test_api(self):
        self.assertIsInstance(self.obj.api(), nuvla.api.Api,
                              'Nuvla Api instance is not of the right type')

    @mock.patch('logging.error')
    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.api')
    def test_push_event(self, mock_api, mock_log):
        # always get None, but if there's an error, log it
        mock_api.side_effect = TimeoutError
        mock_log.return_value = None
        self.assertIsNone(self.obj.push_event(''),
                          'Got something else than None, during an api error')

        # if all goes well, logging is not called again but still get None
        mock_api.reset_mock(side_effect=True)
        mock_api.return_value = fake.FakeNuvlaApi('')
        self.assertIsNone(self.obj.push_event('content'),
                          'Got something else than None during event push')

    def test_authenticate(self):
        api = fake.FakeNuvlaApi('')
        # the api instance should go in and out
        self.assertEqual(self.obj.authenticate(api, 'key', 'secret'), api,
                         'Unable to authenticate with Nuvla API')

    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.Popen')
    def test_shell_execute(self, mock_popen):
        # execute a command as given, and return a dict with the result
        mock_popen.return_value = mock.MagicMock()
        mock_popen.return_value.communicate.return_value = ("out", "err")
        mock_popen.return_value.returncode = 0
        self.assertEqual(self.obj.shell_execute('test'),
                         {'stdout': 'out', 'stderr': 'err', 'returncode': 0},
                         'Failed to get the result of a shell command execution')

    @mock.patch('json.dumps')
    def test_write_json_to_file(self, mock_json_dumps):
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open, \
                mock.patch(self.atomic_write) as mock_atomic_write:
            # if there's an open error, return False
            mock_open.side_effect = FileNotFoundError
            mock_atomic_write.side_effect = FileNotFoundError
            self.assertFalse(self.obj.write_json_to_file('path1', {}),
                             'Returned True when there was an error writing JSON to file')
            mock_open.reset_mock(side_effect=True)
            mock_atomic_write.reset_mock(side_effect=True)
            mock_json_dumps.side_effect = AttributeError
            self.assertFalse(self.obj.write_json_to_file('path2', {}),
                             'Returned True when there was an error with the JSON content')

        # if all goes well, return True
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open, \
                mock.patch(self.atomic_write):
            mock_open.return_value.write.return_value = None
            mock_json_dumps.reset_mock(side_effect=True)
            self.assertTrue(self.obj.write_json_to_file('path', {}),
                            'Failed to write JSON to file')

    def test_read_json_file(self):
        # always return a dict
        file_value = '{"foo": "bar"}'
        with mock.patch(self.agent_nuvlaedge_common_open, mock.mock_open(read_data=file_value)):
            self.assertEqual(self.obj.read_json_file('fake-file'), json.loads(file_value),
                             'Unable to read JSON from file')

    @mock.patch('nuvlaedge.agent.common.nuvlaedge_common.NuvlaEdgeCommon.set_local_operational_status')
    def test_get_operational_status(self, mock_set_status):
        with mock.patch.object(Path, 'open') as mock_open:
            # if file not found, return UNKNOWN
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.get_operational_status(), 'UNKNOWN',
                             'Should not be able to find operational status file but still got it')
            # same for reading error, but in this case, also reset the status file
            mock_open.side_effect = IndexError
            mock_set_status.return_value = None
            self.assertEqual(self.obj.get_operational_status(), 'UNKNOWN',
                             'Should not be able to read operational status but still got it')
            mock_set_status.assert_called_once()

        # otherwise, read file and get status out of it
        file_value = 'OPERATIONAL\nsomething else\njunk'
        with mock.patch.object(Path, 'open', mock.mock_open(read_data=file_value)):
            self.assertEqual(self.obj.get_operational_status(), 'OPERATIONAL',
                             'Unable to fetch valid operational status')

    def test_get_operational_status_notes(self):
        # on any error, give back []
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.get_operational_status_notes(), [],
                             'Got operational status notes when there should not be any')

        file_value = 'note1\nnote2\nnote3\n'

        opener = mock.mock_open(read_data=file_value)

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        # otherwise, give back the notes as a list
        with mock.patch.object(Path, 'open', mocked_open):
            self.assertEqual(self.obj.get_operational_status_notes(), file_value.splitlines(),
                             'Unable to get operational status notes')

    def test_set_local_operational_status(self):
        # should just write and return None
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open, \
                mock.patch(self.atomic_write):
            mock_open.return_value.write.return_value = None
            self.assertIsNone(self.obj.set_local_operational_status(''),
                              'Setting the operational status should return nothing')

    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'stat')
    def test_get_vpn_ip(self, mock_stat, mock_exists):
        # if vpn file does not exist or is empty, get None
        mock_exists.return_value = False
        self.assertIsNone(self.obj.get_vpn_ip(),
                          'Returned VPN IP when VPN file does not exist')
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 0
        self.assertIsNone(self.obj.get_vpn_ip(),
                          'Returned VPN IP when VPN file is empty')

        # otherwise, read the file and return the IP
        mock_stat.return_value.st_size = 1
        # with mock.patch(self.agent_telemetry_open, mock.mock_open(read_data='1.1.1.1')):

        with mock.patch.object(Path, 'open', mock.mock_open(read_data='1.1.1.1')):
            self.assertEqual(self.obj.get_vpn_ip(), '1.1.1.1',
                             'Failed to get VPN IP')

    @mock.patch.object(Path, 'exists')
    def test_write_vpn_conf(self, mock_exists):
        mock_exists.return_value = True
        with mock.patch(self.agent_nuvlaedge_common_open) as mock_open, \
                mock.patch(self.atomic_write):
            mock_open.return_value.write.return_value = None
            # if vpn fiels are not dict, it should raise a TypeError
            self.assertRaises(TypeError, self.obj.write_vpn_conf, "wrong-type")
            # if params are missing, raise KeyError
            self.assertRaises(KeyError, self.obj.write_vpn_conf, {'foo': 'bar'})
            # if all is good, return None
            vpn_values = {
                'vpn_interface_name': 'vpn',
                'vpn_ca_certificate': 'ca',
                'vpn_intermediate_ca_is': 'ca_is',
                'vpn_intermediate_ca': 'i_ca',
                'vpn_certificate': 'cert',
                'nuvlaedge_vpn_key': 'key',
                'vpn_shared_key': 's_key',
                'vpn_common_name_prefix': 'prefix',
                'vpn_endpoints_mapped': 'endpoints',
                'vpn_extra_config': 'some\nextra\nconf'
            }
            self.assertIsNone(self.obj.write_vpn_conf(vpn_values),
                              'Failed to write VPN conf')
