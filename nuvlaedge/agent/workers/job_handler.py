"""

"""
import logging
from queue import Queue

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.orchestrator import COEClient


logger: logging.Logger = logging.getLogger(__name__)


class JobHandler:
    def __init__(self,
                 coe_client: COEClient,
                 nuvla_client: NuvlaClientWrapper,
                 job_channel: Queue[NuvlaID]):

        self.job_channel: Queue[NuvlaID] = job_channel

        self.coe_client: COEClient = coe_client
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        self.running_jobs: list[str] = []

    def run(self):
        # Waits forever for jobs to arrive
        logger.info("JobHandler listening in job channel")
        job_id: NuvlaID = self.job_channel.get()


