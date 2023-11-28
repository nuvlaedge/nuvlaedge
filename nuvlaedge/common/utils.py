"""

"""
import os
import tempfile
import json
import logging
from contextlib import contextmanager
import threading
from pathlib import Path

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


@contextmanager
def atomic_writer(file, **kwargs):
    """
    Context manager to write to a file atomically
    Args:
        file: path of file
        **kwargs: kwargs passed to tempfile.NamedTemporaryFile()

    Returns: None

    """
    path, prefix = os.path.split(file)
    kwargs_ = dict(mode='w+', dir=path, prefix=f'tmp_{prefix}_')
    kwargs_.update(kwargs)

    with tempfile.NamedTemporaryFile(delete=False, **kwargs_) as tmpfile:
        yield tmpfile
    os.replace(tmpfile.name, file)


def atomic_write(file, data, **kwargs):
    """
    Write data to a file atomically
    Args:
        file: path of file
        data: data to write to the file
        **kwargs: kwargs passed to tempfile.NamedTemporaryFile

    Returns: None

    """
    with atomic_writer(file, **kwargs) as f:
        return f.write(data)


def file_exists_and_not_empty(filename: str | Path):
    """
    Checks whether a file exists (and it is a file) and whether it's empty
    Args:
        filename: File path to check

    Returns: true if conditions are met

    """
    if isinstance(filename, str):
        filename = Path(filename)

    return filename.exists() and filename.is_file() and filename.stat().st_size != 0


def write_dict_to_file(data: dict, file: str | Path, override: bool = False) -> None:
    if isinstance(file, str):
        file = Path(file)

    if file_exists_and_not_empty(file) and not override:
        logger.warning(f"Cannot write data to file {file}, use override")
        return

    atomic_write(file, json.dumps(data, indent=4))


def read_json_file(file: str | Path) -> dict:
    """
    Reads a JSON file. Json encoding errors should be handled by calling instance

    :param file: path of the file to be read
    :return: content of the file, as a dict if any. An empty dict if file doesn't exist or is empty
    """

    if isinstance(file, str):
        file = Path(file)

    if not file.exists() or not file.is_file():
        logger.warning(f"File {file} does not exists")
        return {}
    if file.stat().st_size == 0:
        logger.debug(f"File {file} is empty")
        return {}

    with file.open('r') as f:
        return json.load(f)


