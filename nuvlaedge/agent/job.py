# -*- coding: utf-8 -*-

""" NuvlaEdge Job

Relays pull-mode jobs to local job-engine-lite
"""
import base64
from typing import Protocol, Any

from nuvla.api.api import DEFAULT_COOKIE_FILE
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
                   cookies: Any = None,
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
        launch_params: dict = {
            "job_id": self.job_id,
            "job_execution_id": self.job_id_clean,
            "nuvla_endpoint": self.nuvla_client._host.removeprefix("https://"),
            "nuvla_endpoint_insecure": self.nuvla_client._insecure,
            "api_key": None,
            "api_secret": None,
            "cookies": None,
            "docker_image": self.job_engine_lite_image
        }

        if self.nuvla_client.nuvlaedge_client.session.persist_cookie:
            with open(DEFAULT_COOKIE_FILE, "r") as f:
                cookie_data = f.read()
                launch_params["cookies"] = base64.b64encode(cookie_data.encode('utf-8')).decode('utf-8')

        else:
            key, secret = from_irs(self.nuvla_client.nuvlaedge_uuid, self.nuvla_client.irs)
            launch_params["api_key"] = key
            launch_params["api_secret"] = secret

        self.coe_client.launch_job(**launch_params)
