import logging
import socket
from threading import Event

from nuvlaedge.common.nuvlaedge_logging import set_logging_configuration, get_nuvlaedge_logger
from nuvlaedge.agent.settings import AgentSettings, get_agent_settings

if __name__ == '__main__':
    """ We need to configure logging before importing any nuvlaedge module with loggers 
    so there is no need to reconfigure them after the import 
    """
    set_logging_configuration(debug=get_agent_settings().agent_debug,
                              log_level=logging.getLevelName(get_agent_settings().nuvlaedge_log_level),
                              log_path=get_agent_settings().agent_logging_directory,
                              disable_file_logging=get_agent_settings().disable_agent_file_logging)

from nuvlaedge.common.constants import CTE
from nuvlaedge.agent.agent import Agent


logger: logging.Logger = get_nuvlaedge_logger(__name__)


def main():
    agent_event: Event = Event()

    nuvlaedge_agent: Agent = Agent(exit_event=agent_event, settings=get_agent_settings())
    nuvlaedge_agent.start_agent()
    nuvlaedge_agent.run()


if __name__ == '__main__':
    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)
    main()
