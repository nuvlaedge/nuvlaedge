"""
Main entrypoint script for the agent component in the NuvlaEdge engine
Controls all the functionalities of the Agent
"""
from dataclasses import dataclass
import logging.config
import signal
import socket
import time

from threading import Event, Thread

from nuvlaedge.common.timed_actions import ActionHandler, TimedAction
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.agent.agent import Agent, Activate, Infrastructure
from nuvlaedge.common.thread_tracer import signal_usr1

# Nuvlaedge globals
network_timeout: int = 10
refresh_interval: int = 30

root_logger: logging.Logger = logging.getLogger()


def preflight_check(
        activator: Activate,
        exit_event: Event,
        nb_updated_date: str,
        infra: Infrastructure):
    """
    Checks if the NuvlaEdge resource has been updated in Nuvla

    Args:
        activator:
        exit_event:
        nb_updated_date:
        infra:

    Returns:

    """
    global refresh_interval

    nuvlaedge_resource: dict = activator.get_nuvlaedge_info()

    if nuvlaedge_resource.get('state', '').startswith('DECOMMISSION'):
        root_logger.info(f"Remote NuvlaEdge resource state "
                         f"{nuvlaedge_resource.get('state', '')}, exiting agent")
        exit_event.set()

    vpn_server_id = nuvlaedge_resource.get("vpn-server-id")

    if nb_updated_date != nuvlaedge_resource['updated'] and not exit_event.is_set():
        refresh_interval = nuvlaedge_resource['refresh-interval']
        root_logger.info(f'NuvlaEdge resource updated. Refresh interval value: '
                         f'{refresh_interval}')

        old_nuvlaedge_resource = activator.create_nb_document_file(nuvlaedge_resource)

        if vpn_server_id != old_nuvlaedge_resource.get("vpn-server-id"):
            root_logger.info(f'VPN Server ID has been added/changed in Nuvla: '
                             f'{vpn_server_id}')
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

    main_agent: Agent = Agent()
    main_agent.initialize_agent()

    watchdog_thread: Thread | None = None
    nuvlaedge_info_updated_date: str = ''

    action_handler: ActionHandler = ActionHandler([
        # TimedAction(
        #     name='heartbeat',
        #     period=15,
        #     action=main_agent.send_heartbeat
        # ),
        TimedAction(
            name='telemetry',
            period=60,
            action=main_agent.send_telemetry
        )
    ])

    while not main_event.is_set():
        # Time Start
        start_cycle: float = time.time()

        # ----------------------- Main Agent functionality ------------------------------
        if not watchdog_thread or not watchdog_thread.is_alive():
            watchdog_thread = Thread(target=preflight_check,
                                     args=(main_agent.activate,
                                           main_event,
                                           nuvlaedge_info_updated_date,
                                           main_agent.infrastructure
                                           ,),
                                     daemon=True)
            watchdog_thread.start()

        main_agent.run_single_cycle(action_handler.next.action)

        # -------------------------------------------------------------------------------

        # Account cycle time
        cycle_duration = time.time() - start_cycle
        next_cycle_in = action_handler.sleep_time()
        root_logger.debug(f'End of cycle. Cycle duration: {cycle_duration} sec. Next '
                          f'cycle in {next_cycle_in} sec.')

        main_event.wait(timeout=next_cycle_in)


def entry():
    # Global logging configuration
    logging_config_file = '/etc/nuvlaedge/agent/config/agent_logger_config.conf'
    parse_arguments_and_initialize_logging(
        'Agent',
        logging_config_file=logging_config_file)

    # Logger for the root script
    root_logger.info('Configuring Agent class and main script')

    main()


if __name__ == '__main__':
    entry()
