#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mock
import time
import unittest

from mock import MagicMock

from nuvlaedge.agent.orchestrator.job_local import JobLocal


class JobLocalTestCase(unittest.TestCase):

    def setUp(self) -> None:
        api = MagicMock()
        self.obj = JobLocal(api)

    def test_init(self):
        self.assertIsInstance(self.obj, JobLocal)

    def test_is_nuvla_job_running(self):
        job_id = 'fake-id-1'
        job_exec_id = 'fake-exec-id-1'
        self.assertFalse(self.obj.is_nuvla_job_running(job_id, job_exec_id))

    @mock.patch('nuvla.job_engine.job.executor.executor.Executor.process_job')
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

        time.sleep(0.001)
        mock_process_job.assert_called_once()
