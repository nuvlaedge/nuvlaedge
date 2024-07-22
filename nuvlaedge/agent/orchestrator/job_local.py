
import logging

from collections import deque
from threading import Thread, Semaphore

from nuvla.job_engine.job.executor.executor import Executor, LocalOneJobQueue
from nuvla.job_engine.job.job import Job, JOB_RUNNING, JOB_FAILED

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class TinyQueue:

    def __init__(self):
        self.queue = deque()
        self._sema = Semaphore(0)

    def put(self, item):
        self.queue.append(item)
        self._sema.release()

    def get(self, block=True, timeout=None):
        if not self._sema.acquire(block, timeout):
            raise EOFError
        return self.queue.popleft()

    def __contains__(self, item):
        return item in self.queue


class JobLocal:
    """
    Execute jobs directly in the agent
    """

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.running_job = ''
        self.previous_jobs = deque(maxlen=20)
        self.job_queue = TinyQueue()
        self.job_executor_thread = None
        logger.info('JobLocal initialized')

    def create_start_thread(self):
        if not self.is_running:
            logger.info('JobLocal thread not running. (re)starting it')
            self.job_executor_thread = Thread(name='jobs-executor', target=self.run, daemon=True)
            self.job_executor_thread.start()

    @property
    def is_running(self) -> bool:
        return (self.job_executor_thread is not None and
                self.job_executor_thread.ident is not None and
                self.job_executor_thread.is_alive())

    def run(self):
        while True:
            job_id = self.job_queue.get()
            self.running_job = job_id
            self.log_state()
            _job = Job(self.api, LocalOneJobQueue(job_id), FILE_NAMES.root_fs)
            if _job.get('state') == JOB_RUNNING:
                logger.info(f'Job {job_id} already in running state. Do nothing.')
                continue
            logger.debug(f'Running job {job_id} locally')
            Executor.process_job(_job)
            self.previous_jobs.append(job_id)
            self.running_job = ''

    def is_nuvla_job_running(self, job_id, job_execution_id):
        return self.running_job == job_id

    def launch_job(self, job_id, *args, **kwargs):
        self.log_state()
        if job_id == self.running_job:
            logger.debug(f'Job {job_id} currently running')
        elif job_id in self.job_queue:
            logger.debug(f'Job {job_id} already in the queue')
        elif job_id in self.previous_jobs:
            logger.debug(f'Job {job_id} already executed')
        else:
            logger.debug(f'Job {job_id} added to the queue')
            self.job_queue.put(job_id)
            self.create_start_thread()

    def log_state(self):
        logger.debug(f'''
            Job currently running: {self.running_job} 
            Jobs in the queue: {list(self.job_queue.queue)} 
            Last executed jobs: {list(self.previous_jobs)} 
        ''')
