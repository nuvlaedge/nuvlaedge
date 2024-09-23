# -*- coding: utf-8 -*-

""" NuvlaEdge Job

Relays pull-mode jobs to local job-engine-lite
"""
from typing import Protocol, Any

from nuvlaedge.agent.common.util import from_irs
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper


class JobLauncher(Protocol):
    def launch_job(self,
                   job_id: Any,
                   job_execution_id: Any,
                   nuvla_endpoint: Any,
                   nuvla_endpoint_insecure: bool = False,
                   api_key: Any = None,
                   api_secret: Any = None,
                   docker_image: Any = None) -> Any:
        """ An object capable of running jobs from JobId """

    def is_nuvla_job_running(self, job_id: Any, job_id_clean: Any) -> bool:
        """ A JobLauncher can assert if a job is already running """


class Job:
    """ The Job class, which includes all methods and
    properties necessary to handle pull mode jobs

    Attributes:
        job_id: Nuvla UUID of the job
        job_engine_lite_image: Docker image for Job Engine lite
    """

    def __init__(self, 
                 coe_client: JobLauncher,
                 client_wrapper: NuvlaClientWrapper,
                 job_id,
                 job_engine_lite_image):
        """
        Constructs a Job object
        """
        self.coe_client: JobLauncher = coe_client
        self.nuvla_client: NuvlaClientWrapper = client_wrapper

        self.job_id = job_id
        self.job_id_clean = job_id.replace('/', '-')
        self.do_nothing = self.check_job_is_running()
        self.job_engine_lite_image = job_engine_lite_image

    def check_job_is_running(self):
        """ Checks if the job is already running """
        return self.coe_client.is_nuvla_job_running(self.job_id, self.job_id_clean)

    def launch(self):
        """ Starts a Job Engine Lite container with this job

        :return:
        """
        key, secret = from_irs(self.nuvla_client.nuvlaedge_uuid, self.nuvla_client.irs)
        self.coe_client.launch_job(
            self.job_id, self.job_id_clean, self.nuvla_client._host.removeprefix("https://"),
            self.nuvla_client._insecure,
            key,
            secret,
            self.job_engine_lite_image)
