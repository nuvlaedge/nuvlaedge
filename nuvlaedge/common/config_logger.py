"""
Module to be imported first in any NuvlaEdge entrypoint so logging
configuration if done before any log
"""
import os
import logging
import logging.config


LOGGING_BASIC_FORMAT: str = '[%(asctime)s - %(name)s/%(funcName)s - %(levelname)s]: %(message)s'
LOGGING_DEFAULT_LEVEL = logging.INFO


def initialize_logging(config_file: str = '', debug: bool = False, log_level: str = ''):
    """
    Resets handlers that might have been created before proper configuration of logging
    :param config_file:
    :param debug:
    :param log_level
    :return:
    """
    # Remove possible initial handlers before configuring
    while len(logging.root.handlers) > 0:
        logging.root.removeHandler(logging.root.handlers[-1])

    # Load configuration from file if present, else apply default configuration
    if config_file:
        logging.config.fileConfig(config_file)
    else:
        logging.basicConfig(format=LOGGING_BASIC_FORMAT, level=LOGGING_DEFAULT_LEVEL)

    root_logger: logging.Logger = logging.getLogger()

    # Then assert which logging level to apply if any override configuration has been selected
    # Priority goes as follows:
    # If debug == True, set always debug log level
    # else, command line log level overrides the environmental variable log level which at the same time
    # overrides the file configuration log level
    if debug:
        root_logger.setLevel(logging.DEBUG)
    else:
        env_level: str = os.environ.get('NUVLAEDGE_LOG_LEVEL', '')

        if log_level:
            env_level = log_level

        if env_level:
            root_logger.setLevel(logging.getLevelName(env_level))
        else:
            root_logger.setLevel(LOGGING_DEFAULT_LEVEL)
