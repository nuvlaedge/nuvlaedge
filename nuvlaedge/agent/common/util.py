"""
This file gathers general utilities demanded by most of the classes such as a command executor
"""

import os
import logging
import signal
import tempfile

from contextlib import contextmanager
from typing import List, Union, Dict
from subprocess import (Popen, run, PIPE, TimeoutExpired,
                        SubprocessError, STDOUT, CompletedProcess)


base_label = 'nuvlaedge.component=True'
default_project_name = 'nuvlaedge'
compose_project_name = os.getenv('COMPOSE_PROJECT_NAME', default_project_name)
compute_api = compose_project_name + '-compute-api'

COMPUTE_API_INTERNAL_PORT = 5000


def str_if_value_or_none(value):
    return str(value) if value else None


def execute_cmd(command: List[str], method_flag: bool = True) \
        -> Union[Dict, CompletedProcess, None]:
    """ Shell wrapper to execute a command

    @param command: command to execute
    @param method_flag: flag to witch between run and Popen command exection
    @return: all outputs
    """
    try:
        if method_flag:
            return run(command, stdout=PIPE, stderr=STDOUT, encoding='UTF-8')

        with Popen(command, stdout=PIPE, stderr=PIPE) as shell_pipe:
            stdout, stderr = shell_pipe.communicate()

            return {'stdout': stdout,
                    'stderr': stderr,
                    'returncode': shell_pipe.returncode}

    except OSError as ex:
        logging.error(f"Trying to execute non existent file: {ex}")

    except ValueError as ex:
        logging.error(f"Invalid arguments executed: {ex}")

    except TimeoutExpired as ex:
        logging.error(f"Timeout {ex} expired waiting for command: {command}")

    except SubprocessError as ex:
        logging.error(f"Exception not identified: {ex}")

    return None


@contextmanager
def atomic_writer(file, **kwargs):
    """ Context manager to write to a file atomically

    :param file: path of file
    :param kwargs: kwargs passed to tempfile.NamedTemporaryFile()
    """
    path, prefix = os.path.split(file)
    kwargs_ = dict(mode='w+', dir=path, prefix=f'tmp_{prefix}_')
    kwargs_.update(kwargs)

    with tempfile.NamedTemporaryFile(delete=False, **kwargs_) as tmpfile:
        yield tmpfile
    os.replace(tmpfile.name, file)


def atomic_write(file, data, **kwargs):
    """ Write data to a file atomically

    :param file: path of file
    :param data: data to write to the file
    :param kwargs: kwargs passed to tempfile.NamedTemporaryFile
    """
    with atomic_writer(file, **kwargs) as f:
        return f.write(data)


def file_exists_and_not_empty(filename):
    return (os.path.exists(filename)
            and os.path.getsize(filename) > 0)


def raise_timeout(signum, frame):
    raise TimeoutError


@contextmanager
def timeout(time):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(time)

    try:
        yield
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)