# -*- coding: utf-8 -*-
import docker
import json
import logging
import mock
import pathlib
import requests
import unittest
from threading import Thread

import tests.agent.utils.fake as fake
from pathlib import Path
from threading import Thread

from nuvlaedge.agent.common.nuvlaedge_common import NuvlaEdgeCommon
from nuvlaedge.agent.infrastructure import Infrastructure


from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.agent.orchestrator.factory import get_container_runtime



class InfrastructureTestCase(unittest.TestCase):

    agent_infrastructure_open = 'nuvlaedge.agent.infrastructure.open'
    atomic_write = 'nuvlaedge.agent.common.util.atomic_write'

    def setUp(self):
        Infrastructure.__bases__ = (fake.Fake.imitate(NuvlaEdgeCommon, Thread),)
        with mock.patch('nuvlaedge.agent.infrastructure.Telemetry') as mock_telemetry:
            mock_telemetry.return_value = mock.MagicMock()
            self.shared_volume = "mock/path"
            self.refresh_period = 16    # change the default
            self.obj = Infrastructure(get_container_runtime(),
                                      self.shared_volume,
                                      mock_telemetry,
                                      refresh_period=self.refresh_period)

        # monkeypatch NuvlaEdgeCommon attributes
        self.obj.data_volume = self.shared_volume
        self.obj.swarm_manager_token_file = 'swarm_manager_token_file'
        self.obj.swarm_worker_token_file = 'swarm_worker_token_file'
        self.obj.ca = 'ca'
        self.obj.cert = 'cert'
        self.obj.key = 'key'
        self.obj.nuvlaedge_id = 'nuvlabox/fake-id'
        self.obj.context = 'context'
        self.obj.commissioning_file = '.commission'
        self.obj.container_runtime = mock.MagicMock()
        self.obj.nuvlaedge_status_file = '.status'
        self.obj.container_runtime.infra_service_endpoint_keyname = 'swarm-endpoint'
        self.obj.vpn_credential = 'vpn-credential'
        self.obj.vpn_key_file = 'nuvlaedge-vpn.key'
        self.obj.vpn_csr_file = 'nuvlaedge-vpn.csr'
        self.obj.vpn_client_conf_file = 'vpn-conf'
        self.obj.vpn_interface_name = 'vpn'
        self.obj.vpn_config_extra = ''
        self.obj.ssh_flag = '.ssh'
        self.obj.ssh_pub_key = 'ssh key from env'
        self.obj.nuvla_timestamp_format = "%Y-%m-%dT%H:%M:%SZ"
        self.obj.installation_home = '/home'
        self.obj.hostfs = '/rootfs'
        ###
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # make sure the refresh period has been set
        self.assertEqual(self.obj.refresh_period, self.refresh_period,
                         'Infrastructure class was not initialized correctly')

    @mock.patch('json.dumps')
    def test_write_file(self, mock_json_dumps):
        content = {'foo': 'bar'}
        mock_json_dumps.return_value = ''

        with mock.patch("nuvlaedge.agent.infrastructure.open") as mock_open, \
             mock.patch(self.atomic_write):
            mock_open.return_value.write.return_value = None
            self.assertEqual(self.obj.write_file('mock-file', 'something'), None,
                             'Unable to write raw string to file')

        mock_json_dumps.assert_not_called()
        # is JSON, then json.dumps must be called
        with mock.patch("nuvlaedge.agent.infrastructure.open") as mock_open, \
             mock.patch(self.atomic_write):
            mock_open.return_value.write.return_value = None
            self.assertEqual(self.obj.write_file('mock-file', content, is_json=True), None,
                             'Unable to write JSON to file')

        mock_json_dumps.assert_called_once_with(content)

    @mock.patch('nuvlaedge.agent.infrastructure.Infrastructure.write_file')
    def test_swarm_token_diff(self, mock_write_file):
        # if one of the token files is not found, write the current tokens and return
        # True (assume is different)
        mock_write_file.return_value = None
        with mock.patch(self.agent_infrastructure_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertTrue(self.obj.swarm_token_diff('a', 'b'),
                            'Failed to find Swarm token files but did not return True '
                            '(should have written new tokens)')
            self.assertEqual(mock_write_file.call_count, 2,
                             'Failed to write manager and worker token files when previous token files are not found')
            # same for errors while reading the files
            mock_open.side_effect = IndexError
            mock_write_file.reset_mock()
            self.assertTrue(self.obj.swarm_token_diff('a', 'b'),
                            'Failed to read Swarm token files but did not return True (should have written new tokens)')
            self.assertEqual(mock_write_file.call_count, 2,
                             'Failed to write manager and worker token files when previous token files cannot be read')

        mock_write_file.reset_mock()
        # if token files can be opened and read, return False
        with mock.patch(self.agent_infrastructure_open, mock.mock_open(read_data='test\n')):
            self.assertFalse(self.obj.swarm_token_diff('new_manager', 'new_worker'),
                             'Unable to check diff between Swarm tokens')
            mock_write_file.assert_not_called()

    def test_get_tls_keys(self):
        # when failing to find or read any of the TLS key files, return None
        with mock.patch(self.agent_infrastructure_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertFalse(self.obj.get_tls_keys(),
                             'Returned TLS keys even though their files could not be found')
            mock_open.side_effect = IndexError
            self.assertFalse(self.obj.get_tls_keys(),
                             'Returned TLS keys even though their files could not be read')

        # when everything is ok, return the 3 files content as a tuple
        files_content = 'tls'
        opener = mock.mock_open(read_data=files_content)

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        # if file exists and content is the same, return empty dict
        with mock.patch.object(Path, 'open', mocked_open):
        # with mock.patch(self.agent_infrastructure_open, mock.mock_open(read_data=files_content)):
            self.assertEqual(self.obj.get_tls_keys(), (files_content, files_content, files_content),
                             'Unable to get TLS keys')

    @mock.patch('time.sleep')
    @mock.patch.object(Infrastructure, 'build_vpn_credential_search_filter')
    @mock.patch.object(Infrastructure, 'api')
    def test_do_commission(self, mock_api, mock_build_filter, mock_sleep):
        # if payload is not given, return None
        self.assertEqual(self.obj.do_commission(None), None,
                         'Tried to do commission without a payload')

        mock_api.return_value = fake.FakeNuvlaApi('')
        # if there's an error posting the payload, return False
        mock_api.side_effect = TimeoutError
        self.assertFalse(self.obj.do_commission('payload'),
                         'Did not return False when failing to POST payload')

        # if vpn-csr is not in payload, simply succeed and return True
        mock_api.reset_mock(side_effect=True)
        self.assertTrue(self.obj.do_commission({"payload": ""}),
                        'Failed to commissioning with payload without vpn-csr')

        # otherwise
        payload = {"payload": "", "vpn-csr": "fake-csr"}
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"vpn-server-id": "test"}])):
                mock_build_filter.return_value = 'filter=arg="value"'
                # if we can not get the VPN credential from Nuvla (for whatever reason), it returns None
                mock_sleep.return_value = None
                mock_api.return_value.search = mock.MagicMock()
                mock_api.return_value.search.side_effect = RuntimeError

                self.assertIsNone(self.obj.do_commission(payload),
                                  'Failed to return None cannot fetch VPN credential from Nuvla')
                mock_api.return_value.search.assert_called()
                mock_sleep.assert_not_called()  # only called on IndexError

            with mock.patch("json.load", mock.MagicMock(side_effect=[{"vpn-server-id": "test"}])):
                mock_api.return_value.search.side_effect = IndexError
                self.assertIsNone(self.obj.do_commission(payload),
                                  'Failed to return None when VPN credential cannot be parsed')
                mock_sleep.assert_called()

            with mock.patch("json.load", mock.MagicMock(side_effect=[{"vpn-server-id": "test"}])):
                # if there are no issues, a VPN might be found
                mock_api.return_value = fake.FakeNuvlaApi('')
                mock_api.return_value._cimi_get = mock.MagicMock()
                vpn_cred = {
                    'vpn-ca-certificate': 'ca',
                    'vpn-intermediate-ca': 'i-ca',
                    'vpn-certificate': 'cert',
                    'vpn-shared-key': 's-key',
                    'vpn-common-name-prefix': 'prefix'
                }
                mock_api.return_value._cimi_get.return_value = {**{
                    'vpn-endpoints': [{
                        "endpoint": 'mock',
                        "port": 'mock',
                        "protocol": 'mock'
                    }]
                }, **vpn_cred}

                self.assertTrue(set(vpn_cred.keys()).issubset(list(self.obj.do_commission(payload).keys())),
                                'Unable to commission with VPN payload')
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"vpn-server-id": "test"}])):
                self.assertIn('vpn-endpoints-mapped', self.obj.do_commission(payload).keys(),
                              'Missing fields after commissioning with VPN CSR')

    def test_needs_commission(self):
        # if commission file is not found, return the same arg as input
        current_conf = {'foo': 'bar'}
        with mock.patch(self.agent_infrastructure_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.needs_commission(current_conf), current_conf,
                             'Unable to check if commissioning is needed when commission file does not exist')

        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        # if file exists and content is the same, return empty dict
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[current_conf])):
                self.assertEqual(self.obj.needs_commission(current_conf), {},
                                 'Returned a difference on commissioning payload when there is none')

        # if file's content container the current conf, plus other stuff, still return {}
        old_conf = {**current_conf, **{'old': 'var'}}
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[old_conf])):
                self.assertEqual(self.obj.needs_commission(current_conf), {},
                                 'Returned a difference on commissioning payload when new conf is a subset of the old')

        # however, if the new conf has new attrs or values, return them as the diff
        new_conf = {'old': 'var_new', 'foo2': 'bar2'}
        current_conf.update(new_conf)
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[old_conf])):
                self.assertEqual(self.obj.needs_commission(current_conf), new_conf,
                                 'Failed to calculate difference between new commissioning payload and old')

    def test_get_nuvlaedge_capabilities(self):
        commission_payload = {}
        # monkeypatch the check for capability
        self.obj.container_runtime.has_pull_job_capability.return_value = False

        # fn will change the given arg
        self.obj.get_nuvlaedge_capabilities(commission_payload)
        self.assertEqual(commission_payload, {'capabilities': []},
                         'Failed to get NB capabilities when there is no PULL mode')

        self.obj.container_runtime.has_pull_job_capability.return_value = True
        self.obj.get_nuvlaedge_capabilities(commission_payload)
        self.assertEqual(commission_payload, {'capabilities': ['NUVLA_JOB_PULL']},
                         'Failed to get NB capabilities when PULL mode is set')

    @mock.patch('requests.get')
    def test_compute_api_is_running(self, mock_get):

        # only works for non-k8s installations
        self.obj.container_runtime.ORCHESTRATOR = 'kubernetes'
        self.assertFalse(self.obj.compute_api_is_running(),
                         'Tried to check compute-api for a Kubernetes installation')

        self.obj.container_runtime.ORCHESTRATOR = 'docker'
        # if compute-api is running, return True
        compute_api_container = mock.MagicMock()
        compute_api_container.status = 'stopped'
        self.obj.container_runtime.client.containers.get.return_value = compute_api_container
        self.assertFalse(self.obj.compute_api_is_running(),
                         'Unable to detect that compute-api is not running')

        # if running, try to reach its API
        # if an exception occurs, return False
        compute_api_container.status = 'running'
        self.obj.container_runtime.client.containers.get.return_value = compute_api_container
        mock_get.side_effect = TimeoutError
        self.assertFalse(self.obj.compute_api_is_running(),
                         'Assuming compute-api is running even though we could not assess that')
        mock_get.assert_called_once()
        # except if the exception is SSL related
        mock_get.side_effect = requests.exceptions.SSLError
        self.assertTrue(self.obj.compute_api_is_running(),
                        'Unable to detect that compute-api is running')

    def test_get_local_nuvlaedge_status(self):
        with mock.patch(self.agent_infrastructure_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.get_local_nuvlaedge_status(), {},
                             'Returned something other than {} even though NB status file does not exist')

        nb_status = {'foo': 'bar'}
        with mock.patch(self.agent_infrastructure_open, mock.mock_open(read_data=json.dumps(nb_status))):
            self.assertEqual(self.obj.get_local_nuvlaedge_status(), nb_status,
                             'Unable to get NuvlaEdge Status from local file')

    @mock.patch.object(Infrastructure, 'get_local_nuvlaedge_status')
    def test_get_node_role_from_status(self, mock_get_status):
        mock_get_status.return_value = {}
        # simple attribute lookup
        self.assertEqual(self.obj.get_node_role_from_status(), None,
                         'Failed to lookup node role when attribute is not in status')

        mock_get_status.return_value = {'cluster-node-role': 'fake-role'}
        self.assertEqual(self.obj.get_node_role_from_status(), 'fake-role',
                         'Failed to lookup node role from status')

    def test_read_commissioning_file(self):
        # if file does not exist, return {}
        with mock.patch(self.agent_infrastructure_open) as mock_open:
            mock_open.side_effect = FileNotFoundError
            self.assertEqual(self.obj.read_commissioning_file(), {},
                             'Failed to return {} when commissioning file does not exist')

        commission_content = {'foo': 'bar'}
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[commission_content])):
                self.assertEqual(self.obj.read_commissioning_file(), commission_content,
                                 'Failed to read commissioning file')

    @mock.patch.object(Infrastructure, 'get_local_nuvlaedge_status')
    def test_needs_cluster_commission(self, mock_get_status):
        self.obj.container_runtime.get_node_info.return_value = None
        # if cluster details DO NOT exist, check for a match on the node ID for WORKER commissioning
        self.obj.container_runtime.get_cluster_info.return_value = False
        node_id = 'fake-id'
        mock_get_status.return_value = {'node-id': node_id}
        self.obj.container_runtime.get_node_id.return_value = None
        self.assertEqual(self.obj.needs_cluster_commission(), {},
                         'Says cluster commissioning is needed when node ID is not set by the Docker client')
        self.obj.container_runtime.get_node_id.return_value = 'other-id'
        self.assertEqual(self.obj.needs_cluster_commission(), {},
                         'Says cluster commissioning is needed when node ID does not match')
        self.obj.container_runtime.get_node_id.return_value = node_id
        self.assertEqual(self.obj.needs_cluster_commission(), {"cluster-worker-id": node_id},
                         'Unable to infer cluster commissioning as a WORKER')

        # if cluster info exists, then this is a manager, so check for whole cluster commissioning
        self.obj.container_runtime.get_cluster_info.return_value = {
            'cluster-managers': ['some other node']
        }
        self.assertEqual(self.obj.needs_cluster_commission(), {},
                         'Says full cluster commissioning is needed when manager ID is not in cluster-managers')

        self.obj.container_runtime.get_cluster_info.return_value = {
            'cluster-managers': [node_id]
        }
        self.assertEqual(self.obj.needs_cluster_commission(), {'cluster-managers': [node_id]},
                         'Unable to infer whether full cluster commissioning is needed')

    def test_get_compute_endpoint(self):
        self.obj.container_runtime.get_api_ip_port.return_value = (None, None)
        # if all we have are None values, then we also get None
        self.assertEqual(self.obj.get_compute_endpoint(''), (None, None),
                         'Returned a compute endpoint even though there is not enough information to infer it')

        # if VPN IP is given, use it
        self.obj.container_runtime.get_api_ip_port.return_value = (None, 5000)
        self.assertEqual(self.obj.get_compute_endpoint('1.1.1.1'), ('https://1.1.1.1:5000', 5000),
                         'Unable to get compute endpoint when there is a VPN IP')

        # otherwise, infer it
        self.obj.container_runtime.get_api_ip_port.return_value = ('2.2.2.2', 5555)
        self.assertEqual(self.obj.get_compute_endpoint(''), ('https://2.2.2.2:5555', 5555),
                         'Unable to infer compute endpoint and port')

    @mock.patch.object(Infrastructure, 'get_node_role_from_status')
    def test_needs_partial_decommission(self, mock_get_role):
        # return nothing for managers
        mock_get_role.return_value = 'manager'
        self.assertIsNone(self.obj.needs_partial_decommission({}, {}, {}),
                          'Tried to do partial commissioning for a manager')

        mock_get_role.return_value = 'worker'
        self.obj.container_runtime.get_partial_decommission_attributes.return_value = []
        request_payload = {}
        # if there is nothing new to remove, then return the same
        full_payload = {
            'this': 'test'
        }
        old_payload = {
            'removed': []
        }
        # values are changed within function
        self.obj.needs_partial_decommission(request_payload, full_payload, old_payload)
        self.assertEqual({}, request_payload,
                         'Trying to do partial commissioning when there are no values to remove')

        # if there is something to remove, make sure it is popped from the request_payload
        request_payload = {
            'this': 'value',
            'that': 'value',
        }
        full_payload = {
            'this': 'value',
            'that': 'value',
            'another-key': True
        }
        old_payload = {
            'removed': []
        }
        self.obj.container_runtime.get_partial_decommission_attributes.return_value = ['this']
        self.obj.needs_partial_decommission(request_payload, full_payload, old_payload)

        self.assertEqual(request_payload, {'that': 'value', 'removed': ['this']},
                         'Failed to remove commissioning attributed for request payload')
        self.assertNotIn('this', full_payload,
                         'Failed to remove attribute from full commissioning payload')
        self.assertIn('another-key', full_payload,
                      'Removed commissioning key by accident')
        self.assertEqual(old_payload, {'removed': []},
                         'Modified old payload by accident')

    def test_commissioning_attr_has_changed(self):
        # if nothing has changed, nothing is done
        old = {'list-attr': ['1-value', '2-value'], 'str-attr': 'value'}
        current = old.copy()
        payload = {}
        # regardless of the attr type
        self.obj.commissioning_attr_has_changed(current, old, 'str-attr', payload)
        self.assertEqual(payload, {},
                         'Payload has been wrongfully changed, when checking a string attribute')
        self.obj.commissioning_attr_has_changed(current, old, 'list-attr', payload)
        self.assertEqual(payload, {},
                         'Payload has been wrongfully changed, when checking a list attribute')

        # if attrs change though, they must go into the payload
        current.update({'list-attr': ['3-value'], 'str-attr': 'value2'})
        self.obj.commissioning_attr_has_changed(current, old, 'str-attr', payload)
        self.assertEqual(payload, {'str-attr': 'value2'},
                         'Failed to add modified string attribute to commission payload')
        payload = {}    # reset payload for new test
        self.obj.commissioning_attr_has_changed(current, old, 'list-attr', payload)
        self.assertEqual(payload, {'list-attr': ['3-value']},
                         'Failed to set modified list attribute in commission payload')
        payload = {}

        # when using compare_with_nb_resource, the old[attr] is ignored
        current = old.copy()
        # with mock.patch(self.agent_infrastructure_open, mock.mock_open(read_data='{"str-attr": "older-value"}')):
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"str-attr": "older-value"}])):
                self.obj.commissioning_attr_has_changed(current, old, 'str-attr', payload, compare_with_nb_resource=True)
                # old has been updated
                self.assertEqual(old['str-attr'], 'older-value',
                                 'Failed to update old commission payload based on attr value from NuvlaEdge context')
                # payload still match with current, since it's old who was updated based on NB context
                self.assertEqual(payload, {'str-attr': 'value'},
                                 'Failed to add modified string attribute to commission payload, from NuvlaEdge context')

    @mock.patch.object(Infrastructure, 'get_tls_keys')
    @mock.patch.object(Infrastructure, 'write_file')
    @mock.patch.object(Infrastructure, 'do_commission')
    @mock.patch.object(Infrastructure, 'needs_partial_decommission')
    @mock.patch.object(Infrastructure, 'get_nuvlaedge_capabilities')
    @mock.patch.object(Infrastructure, 'swarm_token_diff')
    @mock.patch.object(Infrastructure, 'commissioning_attr_has_changed')
    @mock.patch.object(Infrastructure, 'get_compute_endpoint')
    @mock.patch.object(Infrastructure, 'read_commissioning_file')
    @mock.patch.object(Infrastructure, 'needs_cluster_commission')
    def test_try_commission(self, mock_needs_cluster_commission, mock_read_commission,
                            mock_get_comp_endpoint, mock_attr_changed,
                            mock_swarm_token_diff, mock_get_capabilities, mock_needs_partial_decommission,
                            mock_do_commission, mock_write_file, mock_get_tls_keys):

        swarm_endpoint = 'https://127.1.1.1:5000'

        self.obj.container_runtime.get_join_tokens.return_value = ()
        mock_needs_cluster_commission.return_value = {'cluster-managers': ['node-id']}
        mock_read_commission.return_value = {}
        self.obj.telemetry_instance.get_vpn_ip.return_value = '1.1.1.1'
        mock_get_comp_endpoint.return_value = (swarm_endpoint, 5000)
        self.obj.container_runtime.get_node_labels.return_value = None
        mock_attr_changed.return_value = None

        mock_get_tls_keys.return_value = ('ca', 'cert', 'key')
        self.obj.container_runtime.define_nuvla_infra_service.return_value = {
            'swarm-endpoint': swarm_endpoint,
            'swarm-client-ca': 'ca',
            'swarm-client-cert': 'cert',
            'swarm-client-key': 'key'
        }
        mock_swarm_token_diff.return_value = None
        self.obj.container_runtime.join_token_manager_keyname = 'swarm-token-manager'
        self.obj.container_runtime.join_token_worker_keyname = 'swarm-token-worker'
        mock_get_capabilities.return_value = None
        mock_needs_partial_decommission.return_value = None
        mock_do_commission.return_value = None
        mock_write_file.return_value = None

        # if compute-api is not running, then IS is not defined
        self.obj.container_runtime.compute_api_is_running = mock.MagicMock()
        self.obj.container_runtime.compute_api_is_running.return_value = False

        self.obj.try_commission()
        self.obj.container_runtime.define_nuvla_infra_service.assert_called_with(
            swarm_endpoint, 'ca', 'cert', 'key')
        # and if there are no joining tokens, then commissioning_attr_has_changed is not called
        self.assertEqual(mock_attr_changed.call_count, 0,
                         'commissioning_attr_has_changed called when no join tokens are available')

        # if compute-api is running, the IS is defined
        self.obj.container_runtime.compute_api_is_running.return_value = False
        self.obj.container_runtime.get_join_tokens.return_value = ('manager-token', 'worker-token') # ignored in this test
        mock_do_commission.reset_mock()     # reset counters

        self.obj.try_commission()

        self.obj.container_runtime.define_nuvla_infra_service.assert_called_with(
            swarm_endpoint,
            *('ca', 'cert', 'key'))

        # given the aforementioned return_values, we expect the following commissioning payload to be sent and saved
        expected_payload = {
            'swarm-endpoint': swarm_endpoint,
            'swarm-client-ca': 'ca',
            'swarm-client-cert': 'cert',
            'swarm-client-key': 'key',
            'cluster-managers': ['node-id'],
            'capabilities': []
        }
        mock_do_commission.assert_called_once_with(expected_payload)

    def test_build_vpn_credential_search_filter(self):
        # should simply return a string, formatted with the NB ID and input arg
        vpn_server_id = 'fake-vpn-server-id'
        expected = f'method="create-credential-vpn-nuvlabox" ' \
                   f'and vpn-common-name="{self.obj.nuvlaedge_id}" and parent="{vpn_server_id}"'
        self.assertEqual(self.obj.build_vpn_credential_search_filter(vpn_server_id), expected,
                         'Failed to build VPN credential search filter')

    @mock.patch.object(Infrastructure, 'commission_vpn')
    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'unlink')
    def test_validate_local_vpn_credential(self, mock_unlink, mock_exists, mock_commission_vpn):
        local_vpn_content = {
            'updated': 'old'
        }
        mock_exists.return_value = True
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open), \
                mock.patch("json.load", mock.MagicMock(side_effect=[local_vpn_content])), \
                mock.patch('nuvlaedge.agent.common.util.file_exists_and_not_empty') as mock_util:
            mock_util.return_value = True
            self.obj.validate_local_vpn_credential(local_vpn_content)
            mock_commission_vpn.assert_not_called()
            mock_unlink.assert_not_called()

        remote_content = {
            'updated': 'new'
        }
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[remote_content])):
                self.obj.validate_local_vpn_credential(local_vpn_content)
                mock_commission_vpn.assert_called_once()
                mock_unlink.assert_called_once()

    @mock.patch.object(Infrastructure, 'write_file')
    @mock.patch.object(Infrastructure, 'commission_vpn')
    def test_fix_vpn_credential_mismatch(self, mock_commission_vpn, mock_write_file):
        # if vpn-client container doesn't exist, nothing is done
        self.obj.container_runtime.is_vpn_client_running.side_effect = docker.errors.NotFound('', requests.Response())
        self.obj.fix_vpn_credential_mismatch({})
        mock_commission_vpn.assert_not_called()
        mock_write_file.assert_not_called()

        # if vpn-client container is not found, commission the VPN
        self.obj.container_runtime.is_vpn_client_running.side_effect = None
        self.obj.container_runtime.is_vpn_client_running.return_value = False
        self.obj.fix_vpn_credential_mismatch({})
        mock_commission_vpn.assert_called_once()
        mock_write_file.assert_not_called()

        # result should be the same if check for vpn-client does not throw exception but says "False"
        self.obj.container_runtime.is_vpn_client_running.reset_mock(side_effect=True)
        self.obj.container_runtime.is_vpn_client_running.return_value = False
        mock_commission_vpn.reset_mock()
        self.obj.fix_vpn_credential_mismatch({})
        mock_commission_vpn.assert_called_once()
        mock_write_file.assert_not_called()

        # if it is running
        # but there's no VPN IP, the result is again the same
        mock_commission_vpn.reset_mock()
        self.obj.container_runtime.is_vpn_client_running.return_value = True
        self.obj.telemetry_instance.get_vpn_ip.return_value = None
        self.assertIsNone(self.obj.fix_vpn_credential_mismatch({}),
                          'Unable to commission VPN when VPN IP is not set')
        mock_commission_vpn.assert_called_once()
        mock_write_file.assert_not_called()

        # if VPN IP is set, then save cred file
        self.obj.telemetry_instance.get_vpn_ip.return_value = '1.1.1.1'
        self.assertIsNone(self.obj.fix_vpn_credential_mismatch({}),
                          'Unable to save VPN credential locally when VPN IP and client are already set')
        mock_commission_vpn.assert_called_once()
        mock_write_file.assert_called_once()

    @mock.patch('nuvlaedge.agent.infrastructure.path.exists')
    @mock.patch('nuvlaedge.agent.infrastructure.path.getsize')
    @mock.patch.object(Infrastructure, 'commission_vpn')
    @mock.patch.object(Infrastructure, 'api')
    @mock.patch.object(Infrastructure, 'validate_local_vpn_credential')
    @mock.patch.object(Infrastructure, 'fix_vpn_credential_mismatch')
    @mock.patch.object(Infrastructure, 'build_vpn_credential_search_filter')
    def test_watch_vpn_credential(self, mock_build_filter, mock_fix_vpn_cred, mock_validate_local_vpn,
                                  mock_api, mock_commission_vpn, mock_getsize, mock_exists):
        # if there's no VPN IS, return None
        self.assertIsNone(self.obj.watch_vpn_credential(''),
                          'Tried to watch VPN credential when there is no VPN server IS')
        mock_fix_vpn_cred.assert_not_called()
        mock_validate_local_vpn.assert_not_called()
        mock_build_filter.assert_not_called()
        mock_api.assert_not_called()
        mock_commission_vpn.assert_not_called()
        mock_exists.assert_not_called()
        mock_getsize.assert_not_called()

        mock_api.return_value = fake.FakeNuvlaApi('')
        mock_getsize.return_value = 0

        # otherwise, search the cred, and if NOT found, ask for it again
        mock_api.side_effect = IndexError
        self.assertIsNone(self.obj.watch_vpn_credential('fake-vpn-is'),
                          'Failed to watch VPN credential when VPN credential could not be fetched from Nuvla')
        mock_api.assert_called_once()
        mock_commission_vpn.assert_called_once()

        # if credential is fetched from Nuvla
        mock_api.reset_mock(side_effect=True)   # reset counters
        mock_getsize.reset_mock()
        # GET is called
        # if local files exist, then simply validate
        mock_exists.return_value = True
        mock_getsize.return_value = 1
        self.assertIsNone(self.obj.watch_vpn_credential('fake-vpn-is'),
                          'Failed to watch VPN credential when VPN credential exists Nuvla')

        self.assertEqual(mock_api.call_count, 2,
                         'There should have been one SEARCH and one GET requests to Nuvla, for the VPN credential')



        # but if local file does not match/exist, then fixing is needed
        mock_getsize.return_value = 0
        self.assertIsNone(self.obj.watch_vpn_credential('fake-vpn-is'),
                          'Failed to watch VPN credential when VPN credential exists Nuvla but not locally')

    @mock.patch.object(Infrastructure, 'write_file')
    @mock.patch.object(Infrastructure, 'push_event')
    @mock.patch('nuvlaedge.agent.infrastructure.path.exists')
    def test_set_immutable_ssh_key(self, mock_exists, mock_push_event, mock_write_file):
        mock_write_file.return_value = None
        # if ssh flag already exists, get None
        mock_exists.return_value = True
        with mock.patch(self.agent_infrastructure_open, mock.mock_open(read_data='ssh key')):
            self.assertIsNone(self.obj.set_immutable_ssh_key(),
                              'Trying to set immutable SSH key when it was already set')

        # otherwise
        mock_exists.return_value = False

        # if class vars are not set, return None and don't continue
        self.obj.installation_home = None
        self.assertIsNone(self.obj.set_immutable_ssh_key(),
                          'Unable to handle immutable SSH key when there are missing settings')
        mock_push_event.assert_not_called()

        # otherwise, if ssh_folder does not exist, push event
        mock_push_event.return_value = None
        self.obj.installation_home = '/home'
        self.assertIsNone(self.obj.set_immutable_ssh_key(),
                          'Unable to handle immutable SSH key when trying to push event to Nuvla')
        mock_push_event.assert_called_once()

        # if ssh folder exists, try to install Key
        mock_exists.side_effect = [False, True]
        mock_push_event.reset_mock()
        # if key cannot be set, just ignore and return
        self.obj.container_runtime.install_ssh_key.return_value = None
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"owner": "user"}])):
                self.assertIsNone(self.obj.set_immutable_ssh_key(),
                                  'Unable to handle failure to set immutable SSH key')

                self.obj.container_runtime.install_ssh_key.assert_called_once()
                mock_push_event.assert_not_called()
                mock_write_file.assert_not_called()

        # if set successfully, save it locally
        mock_exists.side_effect = [False, True]
        self.obj.container_runtime.install_ssh_key.return_value = True

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"owner": "user"}])):
                self.assertIsNone(self.obj.set_immutable_ssh_key(),
                                  'Unable to set immutable SSH key')

                mock_push_event.assert_not_called()
                mock_write_file.assert_called_once()

        # if there's an error while setting key, push event
        mock_exists.side_effect = [False, True]
        self.obj.container_runtime.install_ssh_key.side_effect = TimeoutError
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[{"owner": "user"}])):
                self.assertIsNone(self.obj.set_immutable_ssh_key(),
                                  'Unable to push event when failing to set immutable SSH key')

                mock_push_event.assert_called_once()

    @mock.patch.object(Infrastructure, 'try_commission')
    @mock.patch("time.sleep", side_effect=InterruptedError)
    def test_run(self, mock_sleep, mock_commission):
        mock_commission.return_value = None
        # there's no return, it is an infinite loop
        # let's mock an interrupe, which means we commission once
        self.assertRaises(InterruptedError, self.obj.run)
        mock_commission.assert_called_once()
        mock_sleep.assert_called_once()

        # even if there's an exception in the commissioning cycle, it just
        # restarts the cycle again
        mock_commission.reset_mock()    # reset counters
        mock_sleep.reset_mock()
        mock_commission.side_effect = RuntimeError
        self.assertRaises(InterruptedError, self.obj.run)
        mock_commission.assert_called_once()
        mock_sleep.assert_called_once()
