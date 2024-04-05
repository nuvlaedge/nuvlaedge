import logging
import socket
from threading import Event

from nuvlaedge.agent.common.legacy_support import transform_legacy_config_if_needed
from nuvlaedge.common.nuvlaedge_logging import set_logging_configuration
from nuvlaedge.agent.settings import AgentSettings, get_agent_settings
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper


def main():
    # We need to configure logging before importing any nuvlaedge module with loggers
    # so there is no need to reconfigure them after the import
    agent_settings = get_agent_settings()
    set_logging_configuration(debug=agent_settings.nuvlaedge_debug,
                              log_level=logging.getLevelName(agent_settings.nuvlaedge_log_level),
                              log_path=agent_settings.nuvlaedge_logging_directory,
                              disable_file_logging=agent_settings.disable_file_logging)
    agent_event: Event = Event()

    # Adds support for updating to NuvlaEdge > 2.13.0
    transform_legacy_config_if_needed()

    from nuvlaedge.common.constants import CTE
    from nuvlaedge.agent.agent import Agent
    from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler

    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)
    status_handler = NuvlaEdgeStatusHandler()

    nuvlaedge_agent: Agent = Agent(exit_event=agent_event,
                                   settings=agent_settings,
                                   status_handler=status_handler)
    nuvlaedge_agent.start_agent()
    nuvlaedge_agent.run()

