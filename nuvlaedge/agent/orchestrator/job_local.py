
import logging
import os

from nuvla.job_engine.job.executor.executor import Executor, LocalOneJobQueue
from nuvla.job_engine.job.job import Job

from nuvlaedge.common.constant_files import FILE_NAMES
# from nuvlaedge.common.utils import replace_env
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class JobLocal:
    """
    Execute jobs directly in the agent
    """

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.environment = {k: v for k, v in os.environ.items()
                            if k.startswith('NE_IMAGE_') or k.startswith('JOB_')}

    def is_nuvla_job_running(self, job_id, job_execution_id):
        return False

    def launch_job(self, job_id, job_execution_id, *args, **kwargs):

        job = Job(self.api, LocalOneJobQueue(job_id), FILE_NAMES.root_fs)

        #with replace_env(self.environment):
        Executor.process_job(job)


# TODO: remove the content below when next version of job-engine is released

from nuvla.job_engine.job.actions import get_action, ActionNotImplemented
from nuvla.job_engine.job.actions.utils.bulk_action import BulkAction
from nuvla.job_engine.job.job import JobUpdateError, \
    JOB_FAILED, JOB_SUCCESS, JOB_QUEUED, JOB_RUNNING
from nuvla.job_engine.job.util import retry_kazoo_queue_op, status_message_from_exception

@classmethod
def process_job(cls, job):
    try:

        if 'action' not in job:
            raise ValueError('Invalid job: {}.'.format(job))
        action_name = job.get('action')
        action = get_action(action_name)
        if not action:
            raise ActionNotImplemented(action_name)
        action_instance = action(None, job)

        job.set_state(JOB_RUNNING)
        return_code = action_instance.do_work()
    except ActionNotImplemented as e:
        logging.error('Action "{}" not implemented'.format(str(e)))
        # Consume not implemented action to avoid queue
        # to be filled with not implemented actions
        msg = f'Not implemented action {job.id}'
        status_message = '{}: {}'.format(msg, str(e))
        job.update_job(state=JOB_FAILED, status_message=status_message)
    except JobUpdateError as e:
        logging.error('{} update error: {}'.format(job.id, str(e)))
    except Exception:
        status_message = status_message_from_exception()
        if job.get('execution-mode', '').lower() == 'mixed':
            status_message = 'Re-running job in pull mode after failed first attempt: ' \
                             f'{status_message}'
            job._edit_job_multi({'state': JOB_QUEUED,
                                 'status-message': status_message,
                                 'execution-mode': 'pull'})
            retry_kazoo_queue_op(job.queue, 'consume')
        else:
            job.update_job(state=JOB_FAILED, status_message=status_message, return_code=1)
        logging.error(f'Failed to process {job.id}, with error: {status_message}')
    else:
        if isinstance(action_instance, BulkAction):
            retry_kazoo_queue_op(job.queue, 'consume')
            logging.info(f'Bulk job removed from queue {job.id}.')
        else:
            state = JOB_SUCCESS if return_code == 0 else JOB_FAILED
            job.update_job(state=state, return_code=return_code)
            logging.info('Finished {} with return_code {}.'.format(job.id, return_code))


Executor.process_job = process_job

