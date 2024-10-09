#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os
import time
import unittest

from mock import MagicMock, Mock, patch

from nuvlaedge.agent.orchestrator.job_local import JobLocal, get_job_local_timeout, job_timeout_default


class JobLocalTestCase(unittest.TestCase):

    def setUp(self) -> None:
        api = MagicMock()
        self.obj = JobLocal(api)

    def test_init(self):
        self.assertIsInstance(self.obj, JobLocal)

    def test_get_job_local_timeout(self):
        # default value
        self.assertEqual(get_job_local_timeout(), job_timeout_default)

        # proper value
        with patch.dict(os.environ, {'JOB_LOCAL_TIMEOUT': '600'}):
            self.assertEqual(get_job_local_timeout(), 600)

        # wrong value
        with patch.dict(os.environ, {'JOB_LOCAL_TIMEOUT': 'Yes'}):
            self.assertEqual(get_job_local_timeout(), job_timeout_default)

    def test_tiny_queue_non_blocking_get(self):
        self.assertRaises(EOFError, self.obj.job_queue.get, False)

    def test_is_nuvla_job_running(self):
        job_id = 'fake-id-1'
        job_exec_id = 'fake-exec-id-1'
        self.assertFalse(self.obj.is_nuvla_job_running(job_id, job_exec_id))

        self.obj.running_job = job_id
        self.assertTrue(self.obj.is_nuvla_job_running(job_id, job_exec_id))

    @patch('nuvlaedge.agent.orchestrator.job_local.Job')
    @patch('nuvla.job_engine.job.executor.executor.Executor.process_job')
    def test_nuvla_job_in_running_state(self, mock_process_job, mock_job):
        mock_job.return_value = {'state': 'RUNNING'}
        queue_get_mock = Mock()
        queue_get_mock.side_effect = ['job/running', StopIteration]
        self.obj.job_queue.get = queue_get_mock
        self.obj.set_job_failed = Mock()
        try:
            self.obj.run()
        except StopIteration:
            pass
        self.obj.set_job_failed.assert_called_once()
        mock_process_job.assert_not_called()

    @patch('nuvla.job_engine.job.executor.executor.Executor.process_job')
    def test_launch_job(self, mock_process_job):
        job_id = 'fake-id-2'
        job_exec_id = 'fake-exec-id-2'
        nuvla_endpoint = 'https://fake-nuvla.io'
        docker_image = 'sixsq/nuvlaedge:latest'

        ret = self.obj.launch_job(
            job_id, job_exec_id,
            nuvla_endpoint, nuvla_endpoint_insecure=False,
            api_key='credential/abc-def', api_secret='123-abc-456',
            docker_image=docker_image)
        self.assertIsNone(ret)
        time.sleep(0.01)
        mock_process_job.assert_called_once()

        # launching a job already in the job queue
        ret = self.obj.launch_job(job_id)

        # launching a job already running
        job_id_2 = 'job/running'
        self.obj.running_job = job_id_2
        self.obj.launch_job(job_id_2)
        self.assertNotIn(job_id_2, self.obj.job_queue)

        # launching a job already executed
        job_id_3 = 'job/executed'
        self.obj.previous_jobs.append(job_id_3)
        self.obj.launch_job(job_id_3)
        self.assertNotIn(job_id_3, self.obj.job_queue)

        # job timeout
        job_id_4 = 'job_timeout'
        self.obj.running_job = job_id_4
        self.obj.running_job_since = datetime.datetime.fromtimestamp(0)
        self.assertRaises(SystemExit, self.obj.launch_job, 'job/any')


