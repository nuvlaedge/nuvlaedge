import base64
import logging
import os
import socket
import time
from subprocess import run, PIPE, TimeoutExpired
from typing import List, Optional
import requests
import yaml

from nuvla.job_engine.job.base import main
from nuvla.job_engine.job.executor.executor import Executor

from nuvlaedge.common.constants import CTE
from nuvlaedge.agent.common import util
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class JobLocal:
    """
    Execute jobs directly in the agent
    """

    def __init__(self):
        super().__init__()


    def is_nuvla_job_running(self, job_id, job_execution_id):
        return False

    def launch_job(self, job_id, job_execution_id, nuvla_endpoint,
                   nuvla_endpoint_insecure=False, api_key=None, api_secret=None,
                   docker_image=None):
        """
        Launches a job on the local node using the specified Docker image. Takes into account
        various parameters to configure the Docker container. It also handles errors during
        the container creation and starting process.

        Args:
            job_id (str): Unique identifier of the job to be launched.
            job_execution_id (str): Unique identifier of the job execution.
            nuvla_endpoint (str): Endpoint for the Nuvla API.
            nuvla_endpoint_insecure (bool, optional): If true, the Nuvla endpoint is insecure. Defaults to False.
            api_key (str, optional): API Key for the Nuvla API. Defaults to None.
            api_secret (str, optional): API Secret for the Nuvla API. Defaults to None.
            docker_image (str, optional): Docker image to be used for the job. Defaults to None.

        Raises:
            Exception: If there's an error during the container creation or starting process.

        Returns:
            None
        """

        command = f'-- /app/job_executor.py --api-url https://{nuvla_endpoint} ' \
                  f'--api-key {api_key} ' \
                  f'--api-secret {api_secret} ' \
                  f'--job-id {job_id}'

        if nuvla_endpoint_insecure:
            command += ' --api-insecure'

        environment = {k: v for k, v in os.environ.items()
                       if k.startswith('NE_IMAGE_') or k.startswith('JOB_')}

        logger.info(f'Starting job "{job_id}" with  command: "{command}"')

        create_kwargs = dict(
            command=command,
            name=job_execution_id,
            hostname=job_execution_id,
            environment=environment
        )


