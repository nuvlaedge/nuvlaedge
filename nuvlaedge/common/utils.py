"""

"""
import json
import logging
from contextlib import contextmanager
import threading

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
