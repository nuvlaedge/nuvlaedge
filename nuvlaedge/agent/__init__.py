import json
import logging
import signal
import socket
from functools import partial
from pathlib import Path
from threading import Event

from nuvlaedge.common.constants import CTE
from nuvlaedge.agent.agent import Agent
from nuvlaedge.agent.settings import AgentSettings
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging

logger: logging.Logger = logging.getLogger()


def sigterm_stop(signum, frame, agent_stop):
    """
    Callback for SIGTERM capture. SIGTERM is the signal sent by docker when stopped.
    This will try to graciously stop all the agent dependencies
    Args:
        signum:
        frame:
        agent_stop:

    Returns: None

    """
    logger.error("CAPTURED SIGNAL SIGTERM, STOPPING AGENT")
    agent_stop.set()


def main():
    agent_event: Event = Event()

    # sigterm_handler = partial(sigterm_stop, agent_stop=agent_event)
    # signal.signal(signal.SIGTERM, sigterm_handler)

    # TODO: ATM no command line arguments are parsed into the settings.
    nuvlaedge_agent: Agent = Agent(exit_event=agent_event, settings=AgentSettings())
    nuvlaedge_agent.start_agent()
    nuvlaedge_agent.run()


def entry():
    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)

    # Global logging configuration
    # logging_config_file = 'config/agent_logger_config.conf'
    logging_config_file = '/etc/nuvlaedge/agent/config/agent_logger_config.conf'
    parse_arguments_and_initialize_logging(
        'Agent',
        logging_config_file=logging_config_file)

    main()


if __name__ == '__main__':
    entry()
    logger.error("Am I really exiting?")
