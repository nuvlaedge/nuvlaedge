# -*- coding: utf-8 -*-

""" NuvlaEdge Job

Relays pull-mode jobs to local job-engine-lite
"""

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper

from nuvlaedge.agent.orchestrator import COEClient


class Job:
    """ The Job class, which includes all methods and
    properties necessary to handle pull mode jobs

    Attributes:
        data_volume: path to shared NuvlaEdge data
        job_id: Nuvla UUID of the job
        job_engine_lite_image: Docker image for Job Engine lite
    """

    def __init__(self, 
                 coe_client: COEClient,
                 client_wrapper: NuvlaClientWrapper,
                 job_id,
                 job_engine_lite_image):
        """
        Constructs an Job object
        """
        self.coe_client: COEClient = coe_client
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
        self.coe_client.launch_job(
            self.job_id, self.job_id_clean, self.nuvla_client._host.removeprefix("https://"),
            self.nuvla_client._verify,
            self.nuvla_client.nuvlaedge_credentials.key,
            self.nuvla_client.nuvlaedge_credentials.secret,
            self.job_engine_lite_image)
