
import logging
import os

from nuvla.job_engine.job.executor.executor import Executor, LocalOneJobQueue
from nuvla.job_engine.job.job import Job

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class JobLocal:
    """
    Execute jobs directly in the agent
    """

    def __init__(self, api):
        super().__init__()
        self.api = api

    def is_nuvla_job_running(self, job_id, job_execution_id):
        return False

    def launch_job(self, job_id, job_execution_id, *args, **kwargs):
        job = Job(self.api, LocalOneJobQueue(job_id), FILE_NAMES.root_fs)
        Executor.process_job(job)
