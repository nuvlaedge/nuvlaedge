import os
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
import logging

from pydantic import BaseModel

logger: logging.Logger = logging.getLogger(__name__)


@contextmanager
def atomic_writer(file: Path, **kwargs):
    """
    Context manager to write to a file atomically
    Args:
        file: path of file
        **kwargs: kwargs passed to tempfile.NamedTemporaryFile()

    Returns: None

    """
    path = file.parent
    prefix = file.name
    kwargs_ = dict(mode='w+', dir=path, prefix=f'tmp_{prefix}_')
    kwargs_.update(kwargs)

    with tempfile.NamedTemporaryFile(delete=False, **kwargs_) as tmpfile:
        yield tmpfile
    os.replace(tmpfile.name, file)


def __atomic_write(file, data, **kwargs):
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


def file_exists(file: str | Path):
    """
    Checks whether a file exists (and it is a file)
    Args:
        file: File path to check

    Returns: true if conditions are met

    """
    if isinstance(file, str):
        file = Path(file)

    return file.exists() and file.is_file()


def file_exists_and_not_empty(filename: str | Path):
    """
    Checks whether a file exists (and it is a file) and whether it's empty
    Args:
        filename: File path to check

    Returns: true if conditions are met

    """
    if isinstance(filename, str):
        filename = Path(filename)

    return file_exists(filename) and filename.stat().st_size != 0


def read_file(file: str | Path,
              decode_json=False,
              remove_file_on_error=True,
              warn_on_missing: bool = False,
              **kwargs) -> dict | str | None:
    """

    """

    if isinstance(file, str):
        file = Path(file)

    if not file_exists_and_not_empty(file):
        if warn_on_missing:
            logger.warning(f"File {file} does not exists or is empty")
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


__default_model_kwargs: dict = {
    'indent': 4,
    'exclude_none': True,
    'by_alias': True,
    'include': {},
    'exclude': {}
}

__default_json_kwargs: dict = {'indent': 4}


def __get_kwargs(new_kwargs: dict, default_kwargs: dict) -> tuple[dict, dict]:
    temp_kwargs = default_kwargs.copy()

    for k, v in new_kwargs.items():
        if k in temp_kwargs:
            temp_kwargs.update({k: v})
    temp_kwargs = {k: v for k, v in temp_kwargs.items() if v}
    remaining_kwargs = {k: v for k, v in new_kwargs.items() if k not in temp_kwargs}
    return temp_kwargs, remaining_kwargs


def __get_model_kwargs(target_kwargs: dict) -> tuple[dict, dict]:
    return __get_kwargs(target_kwargs, __default_model_kwargs)


def __get_json_kwargs(target_kwargs: dict) -> tuple[dict, dict]:
    return __get_kwargs(target_kwargs, __default_json_kwargs)


def _write_content_to_file(content: str, file: Path, fail_if_error: bool, **kwargs):
    if content is None:
        logger.info(f"Content empty, won't write an empty file {file}. Such a waste...")
        return

    # Write and raise issue if so indicated in the parameter fail_if_error
    try:
        __atomic_write(file, content, **kwargs)
    except Exception as ex:
        logger.warning(f'Could not write {content} into {file} : {ex}')
        file.unlink(missing_ok=True)
        if fail_if_error:
            raise


def _write_json_to_file(content: dict,
                        file: Path,
                        fail_if_error: bool,
                        **kwargs):
    json_kwargs, write_kwargs = __get_json_kwargs(kwargs)
    _write_content_to_file(json.dumps(content, **json_kwargs), file, fail_if_error, **write_kwargs)


def _write_model_to_file(content: BaseModel,
                         file: Path,
                         fail_if_error: bool,
                         **kwargs):
    model_kwargs, write_kwargs = __get_model_kwargs(kwargs)
    str_content: str = content.model_dump_json(**model_kwargs)
    _write_content_to_file(str_content, file, fail_if_error, **write_kwargs)


def write_file(content: str | dict | list[dict] | BaseModel,
               file: str | Path,
               fail_if_error: bool = False,
               **kwargs):
    """
    Writes the provided content to a file. The content can be a string, dictionary, list of dictionaries, or a
     BaseModel instance.
    The method uses atomic writing to ensure data integrity. If the content is a BaseModel instance, it is serialized
     to JSON before writing.
    If the content is a dictionary or a list of dictionaries, it is converted to a JSON string before writing.

    Args:
        content (str | dict | list[dict] | BaseModel): The content to write to the file. Can be a string, dictionary,
         list of dictionaries, or a BaseModel instance.
        file (str | Path): The path of the file to write to. Can be a string or a Path instance.
        fail_if_error (bool, optional): If True, raises an exception if an error occurs while writing. Defaults to False
        **kwargs: Additional keyword arguments passed to the underlying writing functions.

    Raises:
        ValueError: If the content type is not supported or if the content is empty and fail_if_error is True.
        """
    # From this line on, file handling only works with pathlib for consistency
    if isinstance(file, str):
        file = Path(file)
    logger.debug(f"Writing content type {type(content)} to file {file}")

    # Assert content type attribute and convert it to string
    match content:
        case str():
            logger.debug("Processing string")
            _write_content_to_file(content, file, fail_if_error=fail_if_error, **kwargs)
        case dict() | list():
            logger.debug("Processing dictionary")
            _write_json_to_file(content, file, fail_if_error=fail_if_error, **kwargs)
        case BaseModel():
            logger.debug("Processing pydantic model")
            _write_model_to_file(content, file, fail_if_error=fail_if_error, **kwargs)
        case _:
            logger.warning(f"Write File function can only write types: str, dict, BaseModel. Cannot write file {file}")
            if fail_if_error:
                raise ValueError("Cannot write empty content")


def copy_file(origin: Path, target: Path, overwrite: bool = False, fail_if_error: bool = False):
    """
    Copy a file to another location
    Args:
        origin: Path of the file to be copied
        target: Path of the location where the file is to be copied
        overwrite: If True, overwrites the target file if it exists. Defaults to False
        fail_if_error: If True, raises an exception if an error occurs while copying. Defaults to False
    Returns: None
    """
    if not file_exists_and_not_empty(origin):
        logger.warning(f"File {origin} does not exist")
        return

    if file_exists_and_not_empty(target) and not overwrite:
        logger.warning(f"File {target} already exists and overwrite is not set")
        return

    try:
        target.write_bytes(origin.read_bytes())
    except Exception as ex:
        logger.warning(f"Could not copy file {origin} to {target} : {ex}")
        if fail_if_error:
            raise
