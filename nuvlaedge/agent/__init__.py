import logging
import socket
from threading import Event

from nuvlaedge.common.nuvlaedge_logging import set_logging_configuration
from nuvlaedge.agent.settings import AgentSettings, get_agent_settings


def main():
    # We need to configure logging before importing any nuvlaedge module with loggers
    # so there is no need to reconfigure them after the import
    set_logging_configuration(debug=get_agent_settings().agent_debug,
                              log_level=logging.getLevelName(get_agent_settings().nuvlaedge_log_level),
                              log_path=get_agent_settings().agent_logging_directory,
                              disable_file_logging=get_agent_settings().disable_agent_file_logging)
    agent_event: Event = Event()

    from nuvlaedge.common.constants import CTE
    from nuvlaedge.agent.agent import Agent

    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)

    nuvlaedge_agent: Agent = Agent(exit_event=agent_event, settings=get_agent_settings())
    nuvlaedge_agent.start_agent()
    nuvlaedge_agent.run()

