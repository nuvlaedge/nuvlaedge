import os
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
import logging

logger: logging.Logger = logging.getLogger(__name__)


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


def read_file(file: str | Path, decode_json=False, remove_file_on_error=True, **kwargs) -> dict | str | None:
    """
    Reads a JSON file. Json encoding errors should be handled by calling instance

    :param decode_json: True if want to decode json file else not
    :param remove_file_on_error: True if removes the file else not
    :param file: path of the file to be read
    :return: content of the file, as a dict if any. An empty dict if file doesn't exist or is empty
    """

    if isinstance(file, str):
        file = Path(file)

    if not file.exists() or not file.is_file():
        logger.warning(f"File {file} does not exists")
        return None
    if file.stat().st_size == 0:
        logger.debug(f"File {file} is empty")
        return None

    with file.open(mode='r', **kwargs) as f:
        file_content = f.read()
        if decode_json:
            try:
                return json.loads(file_content)
            except Exception as ex:
                logger.warning(f'Exception in loading of json file {file.name} : {ex}')
                if remove_file_on_error:
                    file.unlink(missing_ok=True)
        else:
            return file_content
    return None


def create_directory(_dir: str | Path):
    """
    Create a directory with default permissions
    :param _dir: Can be passed as a string or Path variable
    :return:
    """
    if isinstance(_dir, str):
        _dir = Path(_dir)

    _dir.mkdir(parents=True, exist_ok=True)


def write_file(content, file: str | Path, write_json=False, **kwargs):
    """

    :param content: content to be written
    :param file: The file in which content has to be written
    :param write_json: write as json
    :return:
    """
    if isinstance(file, str):
        file = Path(file)

    try:
        if write_json:
            with file.open('w') as f:
                json.dump(content, f, **kwargs)
        else:
            atomic_write(file, content, **kwargs)
    except Exception as ex:
        logger.warning(f'Could not write {content} into {file} : {ex}')
        file.unlink()
