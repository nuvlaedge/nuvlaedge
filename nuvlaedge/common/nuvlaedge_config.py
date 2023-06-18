"""
Module to be imported first in any NuvlaEdge entrypoint so logging
configuration if done before any log
"""
import os
import logging
import logging.config
import sys

from argparse import ArgumentParser

LOGGING_BASIC_FORMAT: str = '[%(asctime)s - %(name)s/%(funcName)s - %(levelname)s]: %(message)s'
LOGGING_DEFAULT_LEVEL = 'INFO'


def initialize_logging(log_level: str = '', config_file: str = ''):
    """
    Resets handlers that might have been created before proper configuration of logging
    :param log_level
    :param config_file
    :return:
    """
    # Remove possible initial handlers before configuring
    while len(logging.root.handlers) > 0:
        logging.root.removeHandler(logging.root.handlers[-1])

    # Load configuration from file if present, else apply default configuration
    if config_file:
        logging.config.fileConfig(config_file)
    else:
        logging.basicConfig(format=LOGGING_BASIC_FORMAT, level=logging.INFO)

    if log_level:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.getLevelName(log_level))


def nuvlaedge_arg_parser(component_name: str, additional_arguments: callable = None) -> ArgumentParser:
    """
    Common arguments creator for all NuvlaEdge components.
    It also receives a custom_arguments function to add extra arguments that
    might be required in different components
    :return: A configured ArgumentParser object
    """

    parser: ArgumentParser = ArgumentParser(description=f"NuvlaEdge {component_name}",
                                            exit_on_error=False)
    parser.add_argument('-l', '--log-level', dest='log_level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO', help='Log level')
    parser.add_argument('-d', '--debug', dest='log_level',
                        action='store_const', const='DEBUG',
                        help='Set log level to debug')

    # If more arguments are required, implement the function on the specific component and pass it
    # to this function as an argument
    if additional_arguments:
        additional_arguments(parser)

    return parser


def parse_arg(parser: ArgumentParser, args=None):
    try:
        return parser.parse_args(args)
    except Exception as e:
        logging.error(f'Error while parsing argument: {e}')
    return None


def handle_environment_variables():
    log_level = os.environ.get('NUVLAEDGE_LOG_LEVEL')
    if log_level \
            and '--log-level' not in sys.argv \
            and '-l' not in sys.argv:
        sys.argv += ['--log-level', log_level]


def parse_arguments_and_initialize_logging(component_name: str,
                                           additional_arguments: callable = None,
                                           logging_config_file: str = ''):
    parser = nuvlaedge_arg_parser(component_name, additional_arguments)
    handle_environment_variables()
    args = parse_arg(parser)

    log_level = 'INFO'
    if args:
        log_level = args.log_level

    initialize_logging(log_level=log_level, config_file=logging_config_file)
    return args
