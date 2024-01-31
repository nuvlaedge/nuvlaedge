"""
NuvlaEdge logging

NuvlaEdge logging is configured so by default logs to console with the level configured. Also, logs to individual files
errors and warnings
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Global logging settings. They should only be modified from set_logging_configuration.
# This settings won't affect already existing loggers
_DEBUG: bool = False
_LOG_LEVEL: int = logging.INFO
_DISABLE_FILE_LOGGING: bool = False


logger: logging.Logger | None = None

if os.getenv('TOX_TESTENV'):
    # With this there is no need to trick every test module, it should work using /tmp/
    _LOG_PATH: Path = Path('/tmp/nuvlaedge/')
else:
    _LOG_PATH: Path = Path('/var/log/nuvlaedge')

COMMON_LOG_FILE: Path = _LOG_PATH / 'nuvlaedge.log'

COMMON_LOG_FORMATTER: logging.Formatter = \
    logging.Formatter('[%(asctime)s - %(levelname)s - %(name)s/%(funcName)s]: %(message)s')
COMMON_HANDLER: logging.StreamHandler | None = None


def set_logging_configuration(debug: bool,
                              log_path: str | Path = _LOG_PATH,
                              log_level: int | None = _LOG_LEVEL,
                              disable_file_logging: bool = _DISABLE_FILE_LOGGING) -> None:
    global _DEBUG, _LOG_LEVEL, _LOG_PATH, _DISABLE_FILE_LOGGING
    _DEBUG = debug
    _LOG_LEVEL = log_level
    _DISABLE_FILE_LOGGING = disable_file_logging

    if isinstance(log_path, str):
        _LOG_PATH = Path(log_path)
    else:
        _LOG_PATH = log_path

    if not _LOG_PATH.exists():
        logging.warning(f"Configured logging path {log_path} doesn't exist, creating it.")
        """
        It is expected the logging to be stored in a docker/k8s volume to give it persistence
        service:
            volumes:
               - nuvlaedge_logs:/var/log/nuvlaedge
        volumes:
            - nuvlaedge_logs:
        With that configuration the directory should always exists
        """
        _LOG_PATH.mkdir(parents=True)


def __get_file_handler(filename: str) -> logging.FileHandler:
    """
    This function creates and returns a file handler object with specified formatting and logging level.
    The handler uses a rotating file handler, which rotates logs when they reach a certain size.

    Args:
        filename (str): The name (without file extension) of the log file to create the file handler for.
        The log files are saved with '.log' extension in the '_LOG_PATH' directory.

    Returns:
        logging.FileHandler: the file handler object with set logging level and format.
        For debugging mode (when '_DEBUG' is True), the logging level is set to DEBUG.

    Raises:
        OSError: an error occurred while creating or opening the log file.
    """
    if not _LOG_PATH.exists():
        _LOG_PATH.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(_LOG_PATH/f"{filename}.log", maxBytes=5*1024*1024)
    file_handler.setFormatter(COMMON_LOG_FORMATTER)
    file_handler.setLevel(logging.WARNING)

    if _DEBUG:
        file_handler.setLevel(_LOG_LEVEL)

    return file_handler


def __get_common_handler() -> logging.StreamHandler:
    """
    Returns the common handler for logging.

    The method checks if the global variable COMMON_HANDLER is already set. If it is set, the method returns the value
     of the variable. If not, it creates a new instance of logging.StreamHandler and assigns it to the
     variable COMMON_HANDLER.

    The created handler is configured with the common log formatter(COMMON_LOG_FORMATTER) and the log level(_LOG_LEVEL).
     If the _DEBUG flag is set, the log level is set to logging.DEBUG.

    Returns:
        logging.StreamHandler: The common console handler for logging.

    """

    stream_handler = logging.StreamHandler(stream=sys.stdout)

    stream_handler.setFormatter(COMMON_LOG_FORMATTER)
    stream_handler.setLevel(_LOG_LEVEL)

    if _DEBUG:
        stream_handler.setLevel(logging.DEBUG)

    return stream_handler


def __sanityze_logger_name(logger_name: str | None) -> tuple[str | None, str]:

    if logger_name is None:
        return logger_name, 'nuvlaedge'

    modules = logger_name.split('.')
    if len(modules) <= 1:
        return logger_name, logger_name

    # For corner cases
    match modules[-1]:
        case '__init__':
            module_name = modules[-2] + '_init'
        case '__main__':
            module_name = modules[-2] + '_main'
        case _:
            module_name = modules[-1]

    package = '.'.join(modules)

    return package, module_name


def get_nuvlaedge_logger(name: str | None = None) -> logging.Logger:
    """
    Configures a new logger for NuvlaEdge. The logging configuration expects the logger name to come from the module
    level variable name `__name__`.
    Args:
        name: The name of the logger. If no name is provided, the root logger will be configured.

    Returns:
        A logging.Logger object that has been configured according to the provided parameters.
    """
    global logger
    if logger is None and name is not None:
        logger = get_nuvlaedge_logger()

    package, module_name = __sanityze_logger_name(name)

    sub_logger = logging.getLogger(package)
    sub_logger.propagate = False
    sub_logger.level = _LOG_LEVEL
    sub_logger.addHandler(__get_common_handler())
    sub_logger.addHandler(__get_file_handler(module_name))

    return sub_logger


def recompute_nuvlaedge_loggers():
    for k, v in logging.root.manager.loggerDict.items():
        if isinstance(v, logging.Logger) and k.startswith(('nuvlaedge.', 'nuvla.', '__main__')):
            logging.root.manager.loggerDict[k] = get_nuvlaedge_logger(k)

