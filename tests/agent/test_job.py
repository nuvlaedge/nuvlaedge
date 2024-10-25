#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import mock
import unittest

from nuvlaedge.agent.job import Job
from nuvlaedge.agent.common.util import get_irs


class JobTestCase(unittest.TestCase):

    def setUp(self):
        self.shared_volume = "mock/path"
        self.job_id = "job/fake-id"
        self.job_engine_lite_image = 'job-lite'
        # monkeypatches
        self.mock_coe_client = mock.Mock()

        self.mock_nuvla_client = mock.Mock()
        self.mock_nuvla_client._host = 'fake.nuvla.io'
        self.mock_nuvla_client._insecure = False

        with mock.patch('nuvlaedge.agent.job.Job.check_job_is_running') as mock_job_is_running:
            mock_job_is_running.return_value = False
            self.obj = Job(self.mock_coe_client, self.mock_nuvla_client, self.job_id, self.job_engine_lite_image)

        ###
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_init(self):
        # according to setUp, do_nothing is False and job_id should have been cleaned
        self.assertFalse(self.obj.do_nothing,
                         'Failed to check if job is running at class instantiation')
        self.assertEqual(self.obj.job_id_clean, self.job_id.replace('/', '-'),
                         'Failed to convert job ID into container-friendly name')

    def test_check_job_is_running(self):
        self.obj.coe_client.is_nuvla_job_running.return_value = False
        # simply return the output from the coe_client function
        self.assertFalse(self.obj.check_job_is_running(),
                         'Failed to check job is NOT running')

        self.obj.coe_client.is_nuvla_job_running.return_value = True
        self.assertTrue(self.obj.check_job_is_running(),
                        'Failed to check job is running')

    def test_launch(self):
        self.obj.coe_client.launch_job.return_value = None

        # otherwise, launch the job
        self.mock_nuvla_client.nuvlaedge_uuid = '0e9c180e-f4a8-488a-89d4-e6ee6496b4d7'
        self.mock_nuvla_client.nuvlaedge_client.session.persist_cookie = False
        self.mock_nuvla_client.irs = get_irs(self.mock_nuvla_client.nuvlaedge_uuid, 'fake-key', 'fake-secret')
        self.assertIsNone(self.obj.launch(), 'Failed to launch job')
        launch_params: dict = {
            "job_id": self.obj.job_id,
            "job_execution_id": self.obj.job_id_clean,
            "nuvla_endpoint": self.obj.nuvla_client._host.removeprefix("https://"),
            "nuvla_endpoint_insecure": self.obj.nuvla_client._insecure,
            "api_key": 'fake-key',
            "api_secret": 'fake-secret',
            "cookies": None,
            "docker_image": self.job_engine_lite_image
        }
        self.obj.coe_client.launch_job.assert_called_once_with(**launch_params)
