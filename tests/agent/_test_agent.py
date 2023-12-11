import os
import sys
import threading

from nuvla.api.models import CimiResource

import nuvlaedge.agent._infrastructure
from nuvlaedge.agent._agent_old import Agent
from nuvlaedge.agent._activate import Activate

from nuvlaedge.common.timed_actions import TimedAction

from mock import ANY, Mock, PropertyMock, patch
from unittest import TestCase


class TestAgent(TestCase):
    os_makedir: str = 'os.makedirs'
    agent_open: str = 'nuvlaedge.agent.agent.open'
    atomic_write: str = 'nuvlaedge.agent.common.util.atomic_write'

    @patch(os_makedir)
    @patch(atomic_write)
    @patch('nuvlaedge.agent.common.nuvlaedge_common')
    @patch('nuvlaedge.agent.activate.Activate')
    def setUp(self, activate_mock, ne_mock, atomic_write_mock, os_makedir_mock) -> None:
        os.environ['NUVLAEDGE_UUID'] = 'fake-uuid'
        self.test_agent: Agent = Agent()
        self.test_agent._activate = activate_mock

    def tearDown(self):
        del os.environ['NUVLAEDGE_UUID']

    def test_fetch_nuvlaedge(self):
        self.test_agent._activate.nuvlaedge_resource = None
        self.assertIsNone(self.test_agent.nuvlaedge_resource)

    @patch(atomic_write)
    @patch('threading.Event.wait')
    def test_activate_nuvlaedge(self, wait_mock, atomic_write_mock):
        self.test_agent.activate.activation_is_possible.side_effect = [(False, None), (True, None), (True, True)]

        self.test_agent.activate.nuvla_login.return_value = \
            ({'nuvlabox-status': 1}, None)
        self.test_agent.activate_nuvlaedge()
        self.assertEqual(self.test_agent.activate.activation_is_possible.call_count, 2)
        self.assertEqual(self.test_agent.activate.nuvla_login.call_count, 1)

        self.test_agent.activate.nuvla_endpoint_insecure = False
        self.test_agent.activate_nuvlaedge()

        self.test_agent._activate = None
        with patch('nuvlaedge.agent.agent.Activate') as mock_activate:
            self.test_agent.activate

    @patch('nuvlaedge.agent.agent.Infrastructure')
    def test_initialize_infrastructure(self, infra_mock):
        it_mock = Mock()
        it_mock.installation_home = True
        infra_mock.return_value = it_mock
        with patch(self.agent_open) as mock_open, patch(self.atomic_write), patch(self.os_makedir):
            self.test_agent.initialize_infrastructure()
            # Host user home not defined
            self.test_agent.infrastructure.installation_home = None
            self.test_agent.initialize_infrastructure()

    @patch('nuvlaedge.agent.agent.Telemetry')
    def test_initialize_telemetry(self, tel_mock):
        self.test_agent.telemetry
        self.assertNotEqual(self.test_agent.telemetry, None)

    @patch('nuvlaedge.agent.agent.Agent.activate_nuvlaedge')
    def test_initialize_agent(self, act_mock):
        self.assertTrue(self.test_agent.initialize_agent())
        act_mock.assert_called_once()

    def test_send_heartbeat(self):
        tel_mock = Mock()
        self.test_agent._telemetry = tel_mock
        sample_data_return = {
            'jobs': ['j1', 'j2']
        }
        api_mock = Mock()
        response_mock = Mock()
        response_mock.data = sample_data_return

        # Heartbeat not supported on Nuvla server
        api_mock.operation.return_value = response_mock
        self.test_agent._telemetry.api.return_value = api_mock
        self.assertEqual({}, self.test_agent.send_heartbeat())

        # Heartbeat supported on Nuvla server
        nuvlaedge_resource = CimiResource(
            {'operations': [{'href': 'nuvlabox/<uuid>/heartbeat',
                            'rel': 'heartbeat'}]})
        self.test_agent.activate.nuvlaedge_resource = nuvlaedge_resource
        self.assertEqual(sample_data_return, self.test_agent.send_heartbeat())
        api_mock.operation.assert_called_once_with(nuvlaedge_resource, 'heartbeat')

        with patch('nuvlaedge.agent.agent.Agent.sync_nuvlaedge_resource') as mock_sync:
            response_mock.data = {'doc-last-updated': 'some date'}
            self.test_agent.send_heartbeat()
            mock_sync.assert_called_once()

    @patch(os_makedir)
    @patch(atomic_write)
    @patch('nuvlaedge.agent.agent.Agent.sync_nuvlaedge_resource')
    @patch('nuvlaedge.agent.agent.Agent.is_heartbeat_supported_server_side', new_callable=PropertyMock)
    def test_send_telemetry(self, is_heartbeat_mock, sync_mock, atomic_write_mock, os_makedir_mock):
        self.test_agent._telemetry = Mock()
        tel_mock = Mock()
        tel_mock.diff.return_value = ({}, ['a'])
        tel_mock.status.get.return_value = ''
        self.test_agent._telemetry = tel_mock
        with patch('logging.Logger.warning') as mock_warn:
            self.test_agent.send_telemetry()
        self.assertEqual(tel_mock.status.update.call_count, 1)

        tel_mock.status.update.reset_mock()
        tel_mock.status.get.return_value = 1
        self.test_agent.past_status_time = 2
        api_mock = Mock()
        ret_mock = Mock()
        ret_mock.data = "ret"
        api_mock.edit.return_value = ret_mock
        self.test_agent._telemetry.api.return_value = api_mock
        self.assertEqual(self.test_agent.send_telemetry(), "ret")
        self.assertEqual(tel_mock.status.update.call_count, 1)
        self.assertEqual(api_mock.edit.call_count, 1)

        self.test_agent._telemetry.api.side_effect = OSError
        with self.assertRaises(OSError):
            self.test_agent.send_telemetry()
        self.test_agent._telemetry.api.reset_mock(side_effect=True)

        # heartbeat supported
        is_heartbeat_mock.return_value = True
        self.test_agent.send_telemetry()
        sync_mock.assert_not_called()

        # heartbeat not supported
        is_heartbeat_mock.return_value = False
        self.test_agent.send_telemetry()
        sync_mock.assert_called()

        # status_current_time > past_status_time
        tel_mock.status.update.reset_mock()
        tel_mock.status.get.return_value = 2
        self.test_agent.past_status_time = 1
        self.test_agent.send_telemetry()
        api_mock.edit.assert_called_with(ANY, data=ANY, select=['a'])

    @patch('nuvlaedge.agent.agent.Job')
    @patch('nuvlaedge.agent.job.Job.launch')
    def test_run_pull_jobs(self, mock_launch, mock_job):
        self.test_agent.run_pull_jobs([])
        self.assertEqual(mock_job.call_count, 0)

        infra_mock = Mock()
        self.test_agent._infrastructure = infra_mock
        self.test_agent.run_pull_jobs(['1'])
        self.assertEqual(mock_job.call_count, 1)
        self.assertEqual(mock_launch.call_count, 0)

        it_mock = Mock()
        it_mock.do_nothing = False
        it_mock.launch.return_value = "None"
        mock_job.return_value = it_mock
        self.test_agent.run_pull_jobs(['2'])
        self.assertEqual(it_mock.launch.call_count, 1)

        it_mock.launch.side_effect = Exception('error')
        self.test_agent.run_pull_jobs(['3'])
        self.assertEqual(it_mock.launch.call_count, 2)


    @patch('nuvlaedge.agent.agent.Infrastructure')
    @patch('nuvlaedge.agent.agent.Thread.start')
    def test_handle_pull_jobs(self, mock_thread, infra_mock):
        infra_mock.coe_client.job_engine_lite_image = True
        self.test_agent._infrastructure = infra_mock
        self.test_agent.handle_pull_jobs({'jobs': ['1', '2']})
        mock_thread.assert_called_once()
        mock_thread.reset_mock()

        infra_mock.coe_client.job_engine_lite_image = False
        self.test_agent.handle_pull_jobs({})
        self.assertEqual(mock_thread.call_count, 0)

        with patch('logging.Logger.warning') as mock_warn:
            self.test_agent.handle_pull_jobs({'jobs': 'PI'})
            mock_warn.assert_called_once()

    @patch('nuvlaedge.agent.agent.Agent.send_telemetry')
    @patch('nuvlaedge.agent.agent.Agent.handle_pull_jobs')
    @patch('threading.Thread.start')
    @patch('nuvlaedge.agent.agent.Infrastructure')
    def test_run_single_cycle(self, inf_mock, mock_start, pull_mock, mock_beat):
        self.test_agent.telemetry_thread = False
        self.test_agent._telemetry = Mock()
        self.test_agent._infrastructure = Mock()

        action = TimedAction(
            name='telemetry',
            period=60,
            action=self.test_agent.send_telemetry)

        self.test_agent.run_single_cycle(action)
        self.assertEqual(mock_start.call_count, 3)
        pull_mock.assert_called_once()

        # with threads alreay alive
        with patch('threading.Thread.is_alive') as mock_th_is_alive:
            mock_th_is_alive.return_value = True

            # telemetry
            self.test_agent.run_single_cycle(action)
            self.assertIsNotNone(self.test_agent._peripheral_manager)

            # heartbeat
            action.name = 'heartbeat'
            self.test_agent.telemetry_thread = None
            self.test_agent.peripherals_thread = None
            self.test_agent.run_single_cycle(action)
            self.assertIsNone(self.test_agent.telemetry_thread)
            self.assertIsNone(self.test_agent.peripherals_thread)


    def test_update_nuvlaedge_configuration(self):
        mock_current = {
            'updated': 0,
            'vpn-server-id': 'ID'
        }
        mock_old = {
            'updated': 0,
            'vpn-server-id': 'ID'
        }
        self.test_agent.old_nuvlaedge_data = mock_old.copy()
        self.test_agent.activate.nuvlaedge_resource = CimiResource(mock_current)

        mock_update_periods = Mock()
        self.test_agent.on_nuvlaedge_update = mock_update_periods

        mock_infra = Mock()
        self.test_agent._infrastructure = mock_infra

        # Resource hasn't been updated since the last check, do nothing
        self.test_agent.old_nuvlaedge_data = mock_old.copy()
        self.test_agent._update_nuvlaedge_configuration()
        mock_infra.commission_vpn.assert_not_called()
        mock_update_periods.assert_not_called()

        # Resource changed, with same vpn id
        mock_current['updated'] = 1
        self.test_agent.old_nuvlaedge_data = mock_old.copy()
        self.test_agent._update_nuvlaedge_configuration()
        mock_update_periods.assert_called_once()
        mock_infra.commission_vpn.assert_not_called()
        mock_update_periods.reset_mock()

        # Everything has changed
        mock_current['vpn-server-id'] = 'ID_BIS'
        self.test_agent.old_nuvlaedge_data = mock_old.copy()
        self.test_agent._update_nuvlaedge_configuration()
        mock_update_periods.assert_called_once()
        mock_infra.commission_vpn.assert_called_once()

        # old_nuvlaedge_data and on_nuvlaedge_update not set
        self.test_agent.old_nuvlaedge_data = None
        self.test_agent.on_nuvlaedge_update = None
        mock_read_ne_doc = Mock()
        mock_read_ne_doc.return_value = {}
        self.test_agent._activate.read_ne_document_file = mock_read_ne_doc
        self.test_agent._update_nuvlaedge_configuration()
        mock_read_ne_doc.assert_called_once()

    @patch('nuvlaedge.agent.agent.Agent.fetch_nuvlaedge_resource')
    @patch('nuvlaedge.agent.agent.Agent._update_nuvlaedge_configuration')
    def test_resource_synchronization(self, mock_update_config, mock_fetch_nuvlaedge):
        mock_activator = Mock()
        self.test_agent._activate = mock_activator

        mock_exit = Mock()
        self.test_agent.exit_event = mock_exit

        mock_infra = Mock()
        self.test_agent._infrastructure = mock_infra

        # If the nuvlaedge has been decommissioned
        mock_activator.nuvlaedge_resource = CimiResource({'state': 'DECOMMISSIONING'})
        self.test_agent.sync_nuvlaedge_resource()
        mock_exit.set.assert_called_once()

        # Normal state
        mock_activator.nuvlaedge_resource = CimiResource({'state': 'ACTIVATED',
                                                          'vpn-server-id': None})
        self.test_agent.sync_nuvlaedge_resource()
        mock_update_config.assert_called_once()
        mock_infra.watch_vpn_credential.assert_not_called()

        mock_activator.nuvlaedge_resource = CimiResource({'state': 'ACTIVATED',
                                                          'vpn-server-id': 'ID'})
        self.test_agent.sync_nuvlaedge_resource()
        mock_infra.watch_vpn_credential.assert_called_with('ID')

        # without exit_event
        self.test_agent.exit_event = None
        mock_activator.nuvlaedge_resource = CimiResource({'state': 'DECOMMISSIONING'})
        self.test_agent.sync_nuvlaedge_resource()
