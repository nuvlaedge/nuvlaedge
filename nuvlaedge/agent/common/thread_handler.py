import logging
from threading import Thread
logger: logging.Logger = logging.getLogger(__name__)


def log(level, message, *args, **kwargs):
    logger.log(level, message.format(*args, **kwargs))


def is_thread_creation_needed(name, thread,
                              log_not_exist=(logging.INFO, 'Creating {} thread'),
                              log_not_alive=(logging.WARNING,
                                             'Recreating {} thread because it is not alive'),
                              log_alive=(logging.DEBUG, 'Thread {} is alive'),
                              *args, **kwargs):
    if not thread:
        log(*log_not_exist, name, *args, **kwargs)
    elif not thread.is_alive():
        log(*log_not_alive, name, *args, **kwargs)
    else:
        log(*log_alive, name, *args, **kwargs)
        return False
    return True


def create_start_thread(**kwargs):
    th = Thread(daemon=True, **kwargs)
    th.start()
    return th
