"""

"""
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
