"""

"""
import os
import json
import logging
import threading

from contextlib import contextmanager
from datetime import datetime

from nuvlaedge.agent.common.util import execute_cmd

logger: logging.Logger = logging.getLogger(__name__)


@contextmanager
def timed_event(timeout: int):
    """
    Auxiliary function to control timed while loops with a  context manager
    :param timeout:
    :return: yields the event flag controlling the timeout
    """
    logger.debug(f'Starting timeout event {timeout}')
    event = threading.Event()
    timer = threading.Timer(timeout, event.set)
    timer.start()
    try:
        yield event
    finally:
        timer.cancel()


def dump_dict_to_str(d: dict) -> str:
    """
    Dumps a dictionary to a string
    :param d: dictionary to dump
    :return: string representation of the dictionary
    """
    if not isinstance(d, dict) or not d:
        return ""
    return json.dumps(d, indent=4)


def format_datetime_for_nuvla(t: datetime) -> str:
    """
    Formats a datetime object to the Nuvla format
    :param t: datetime object
    :return: string formatted datetime
    """
    str_time = t.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    return str_time if str_time.endswith('Z') else str_time + 'Z'


def get_certificate_expiry(cert_path):
    if not os.path.isfile(cert_path):
        logger.warning(f'Cannot get certificate expiry. Path do not exists: {cert_path}')
        return None

    command = ["openssl", "x509",
               "-enddate", "-noout",
               "-in", cert_path,
               "-dateopt", "iso_8601"]
    cert_check = execute_cmd(command)

    if cert_check.returncode != 0 or not cert_check.stdout:
        logger.warning(f'Failed to get certificate expiry ({cert_check.returncode}): {cert_check.stderr}')
        return None

    expiry_date_iso8601 = cert_check.stdout.strip().split('=')[-1]
    return datetime.fromisoformat(expiry_date_iso8601)

