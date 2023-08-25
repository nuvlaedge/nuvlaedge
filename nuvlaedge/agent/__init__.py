"""
Main entrypoint script for the agent component in the NuvlaEdge engine
Controls all the functionalities of the Agent
"""

import logging
import logging.config
import signal
import socket
import time

from threading import Event, Thread

from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.agent.agent import Agent, Activate, Infrastructure


# Nuvlaedge globals
network_timeout: int = 10
refresh_interval: int = 30

root_logger: logging.Logger = logging.getLogger()


def log_threads_stackstraces():
    import sys
    import threading
    import traceback
    import faulthandler
    print_args = dict(file=sys.stderr, flush=True)
    print("\nfaulthandler.dump_traceback()", **print_args)
    faulthandler.dump_traceback()
    print("\nthreading.enumerate()", **print_args)
    for th in threading.enumerate():
        print(th, **print_args)
        traceback.print_stack(sys._current_frames()[th.ident])
    print(**print_args)


def signal_usr1(signum, frame):
    log_threads_stackstraces()


def preflight_check(activator: Activate, exit_flag: bool, nb_updated_date: str,
                    infra: Infrastructure):
    """
    Checks if the NuvlaEdge resource has been updated in Nuvla

    Args:
        activator: instance of Activate
        infra:
        nb_updated_date:
        exit_flag:
    """
    global refresh_interval

    nuvlaedge_resource: dict = activator.get_nuvlaedge_info()

    if nuvlaedge_resource.get('state', '').startswith('DECOMMISSION'):
        root_logger.info(f"Remote NuvlaEdge resource state {nuvlaedge_resource.get('state', '')}, exiting agent")
        exit_flag = False

    vpn_server_id = nuvlaedge_resource.get("vpn-server-id")

    if nb_updated_date != nuvlaedge_resource['updated'] and exit_flag:
        refresh_interval = nuvlaedge_resource['refresh-interval']
        root_logger.info(f'NuvlaEdge resource updated. Refresh interval value: '
                         f'{refresh_interval}')

        old_nuvlaedge_resource = activator.create_nb_document_file(nuvlaedge_resource)

        if vpn_server_id != old_nuvlaedge_resource.get("vpn-server-id"):
            root_logger.info(f'VPN Server ID has been added/changed in Nuvla: {vpn_server_id}')
            infra.commission_vpn()

    # if there's a mention to the VPN server, then watch the VPN credential
    if vpn_server_id:
        infra.watch_vpn_credential(vpn_server_id)


def main():
    """
    Initialize the main agent class. This class will also initialize submodules:
      - Activator
      - Telemetry
      - Infrastructure

    Returns: None
    """
    signal.signal(signal.SIGUSR1, signal_usr1)

    socket.setdefaulttimeout(network_timeout)

    main_event: Event = Event()
    agent_exit_flag: bool = True

    main_agent: Agent = Agent(agent_exit_flag)
    main_agent.initialize_agent()

    watchdog_thread: Thread | None = None
    nuvlaedge_info_updated_date: str = ''

    while agent_exit_flag:
        # Time Start
        start_cycle: float = time.time()
        # ----------------------- Main Agent functionality ------------------------------

        if not watchdog_thread or not watchdog_thread.is_alive():
            watchdog_thread = Thread(target=preflight_check,
                                     args=(main_agent.activate,
                                           agent_exit_flag,
                                           nuvlaedge_info_updated_date,
                                           main_agent.infrastructure
                                           ,),
                                     daemon=True)
            watchdog_thread.start()

        main_agent.run_single_cycle()

        # -------------------------------------------------------------------------------

        # Account cycle time
        cycle_duration = time.time() - start_cycle
        next_cycle_in = refresh_interval - cycle_duration - 1
        root_logger.debug(f'End of cycle. Cycle duration: {cycle_duration} sec. Next '
                          f'cycle in {next_cycle_in} sec.')

        main_event.wait(timeout=next_cycle_in)


def entry():
    # Global logging configuration
    logging_config_file = '/etc/nuvlaedge/agent/config/agent_logger_config.conf'
    parse_arguments_and_initialize_logging('Agent', logging_config_file=logging_config_file)

    # Logger for the root script
    root_logger.info('Configuring Agent class and main script')

    main()


if __name__ == '__main__':
    entry()
