import logging
import os
import signal
import socket
import sys
import threading
import time
import traceback
from threading import Event, Thread

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


def print_threads():
    print("\n\n================== THREAD DEBUG DUMP START ==================\n")
    threads = {t.ident: t for t in threading.enumerate()}
    current_frames = sys._current_frames()


    for thread_id, frame in current_frames.items():
        thread = threads.get(thread_id)
        thread_name = thread.name if thread else "Unknown"
        is_alive = thread.is_alive() if thread else False

        stack = ''.join(traceback.format_stack(frame))
        print(f"\n\n--- Thread ID: {thread_id} | Name: {thread_name} | Alive: {is_alive} ---")
        print(stack)

    print("\n\n================== THREAD DEBUG DUMP STOP ==================\n")

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
    agent_thread: Thread = Thread(target=nuvlaedge_agent.run, name="Agent", daemon=True)
    agent_thread.start()

    try:
        # Give some time for the startup of the agent
        while agent_thread.is_alive():
            debug_threads = os.getenv("DEBUG_THREADS", "False").lower().strip()
            if debug_threads in ('1', 'on', 't', 'true', 'y', 'yes'):
                print_threads()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Shutting down... ")
    except Exception as ex:
        print("\n[UNKNOWN ERROR] An unknown error triggered agent exit: \n\n")
        print(f"\n {ex}")

    if agent_thread.is_alive():
        agent_event.set()
        agent_thread.join(timeout=120)

