import logging
import signal
import socket
from threading import Event

from nuvlaedge.common.nuvlaedge_logging import set_logging_configuration, LoggingSettings

logging_settings = LoggingSettings()
set_logging_configuration(
    debug=logging_settings.nuvlaedge_debug,
    log_level=logging.getLevelName(logging_settings.nuvlaedge_log_level),
    log_path=logging_settings.nuvlaedge_logging_directory,
    disable_file_logging=logging_settings.disable_file_logging
)

from nuvlaedge.agent.common.legacy_support import transform_legacy_config_if_needed
from nuvlaedge.agent.settings import AgentSettings, get_agent_settings
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.common.thread_tracer import signal_usr1


def main():
    # We need to configure logging before importing any nuvlaedge module with loggers
    # so there is no need to reconfigure them after the import
    signal.signal(signal.SIGUSR1, signal_usr1)
    agent_settings = get_agent_settings()

    # set_logging_configuration(debug=agent_settings.nuvlaedge_debug,
    #                           log_level=logging.getLevelName(agent_settings.nuvlaedge_log_level),
    #                           log_path=agent_settings.nuvlaedge_logging_directory,
    #                           disable_file_logging=agent_settings.disable_file_logging)
    agent_event: Event = Event()

    from nuvlaedge.common.constants import CTE
    from nuvlaedge.agent.agent import Agent

    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)

    nuvlaedge_agent: Agent = Agent(exit_event=agent_event,
                                   settings=agent_settings)
    nuvlaedge_agent.start_agent()
    nuvlaedge_agent.run()
