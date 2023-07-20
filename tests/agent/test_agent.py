import os
import sys
import threading

import nuvlaedge.agent.infrastructure
from nuvlaedge.agent.agent import Agent
from nuvlaedge.agent.activate import Activate
from mock import Mock, patch
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
        self.test_agent: Agent = Agent(True)
        self.test_agent._activate = activate_mock

    def tearDown(self):
        del os.environ['NUVLAEDGE_UUID']

    @patch(atomic_write)
    @patch('threading.Event.wait')
    def test_activate_nuvlaedge(self, wait_mock, atomic_write_mock):
        self.test_agent.activate.activation_is_possible.side_effect = [(False, None), (True, None)]

        self.test_agent.activate.update_nuvlaedge_resource.return_value = \
            ({'nuvlabox-status': 1}, None)
        self.test_agent.activate_nuvlaedge()
        self.assertEqual(self.test_agent.activate.activation_is_possible.call_count, 2)
        self.assertEqual(self.test_agent.activate.update_nuvlaedge_resource.call_count, 1)

    @patch('nuvlaedge.agent.agent.Infrastructure')
    def test_initialize_infrastructure(self, infra_mock):
        it_mock = Mock()
        it_mock.installation_home = True
        infra_mock.return_value = it_mock
        with patch(self.agent_open) as mock_open, patch(self.atomic_write), patch(self.os_makedir):
            self.test_agent.initialize_infrastructure()

    @patch('nuvlaedge.agent.agent.Telemetry')
    def test_initialize_telemetry(self, tel_mock):
        self.test_agent.telemetry
        self.assertNotEqual(self.test_agent.telemetry, None)

    @patch('nuvlaedge.agent.agent.Agent.activate_nuvlaedge')
    def test_initialize_agent(self, act_mock):
        self.assertTrue(self.test_agent.initialize_agent())
        act_mock.assert_called_once()

    @patch(os_makedir)
    @patch(atomic_write)
    def test_send_heartbeat(self, atomic_write_mock, os_makedir_mock):
        self.test_agent._telemetry = Mock()
        tel_mock = Mock()
        tel_mock.diff.return_value = ({}, ['a'])
        tel_mock.status.get.return_value = ''
        self.test_agent._telemetry = tel_mock
        with patch('logging.Logger.warning') as mock_warn:
            self.test_agent.send_heartbeat()
        self.assertEqual(tel_mock.status.update.call_count, 1)

        tel_mock.status.update.reset_mock()
        tel_mock.status.get.return_value = 1
        self.test_agent.past_status_time = 2
        api_mock = Mock()
        ret_mock = Mock()
        ret_mock.data = "ret"
        api_mock.edit.return_value = ret_mock
        self.test_agent._telemetry.api.return_value = api_mock
        self.assertEqual(self.test_agent.send_heartbeat(), "ret")
        self.assertEqual(tel_mock.status.update.call_count, 1)
        self.assertEqual(api_mock.edit.call_count, 1)

        self.test_agent._telemetry.api.side_effect = OSError
        with self.assertRaises(OSError):
            self.test_agent.send_heartbeat()

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
        self.test_agent.run_pull_jobs(['1'])
        self.assertEqual(it_mock.launch.call_count, 1)

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

    @patch('nuvlaedge.agent.agent.Agent.send_heartbeat')
    @patch('nuvlaedge.agent.agent.Agent.handle_pull_jobs')
    @patch('threading.Thread.start')
    @patch('nuvlaedge.agent.agent.Infrastructure')
    def test_run_single_cycle(self, inf_mock, mock_start, pull_mock, mock_beat):
        self.test_agent.telemetry_thread = False
        self.test_agent._telemetry = Mock()
        self.test_agent._infrastructure = Mock()
        self.test_agent.run_single_cycle()
        self.assertEqual(mock_start.call_count, 3)
        pull_mock.assert_called_once()
