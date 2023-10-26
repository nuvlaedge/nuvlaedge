"""
Main entrypoint script for the agent component in the NuvlaEdge engine
Controls all the functionalities of the Agent
"""
import logging.config
import signal
import socket
import time

from threading import Event

from nuvlaedge.agent.agent import Agent, Activate, Infrastructure
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.common.thread_tracer import signal_usr1
from nuvlaedge.common.timed_actions import ActionHandler, TimedAction


root_logger: logging.Logger = logging.getLogger()

action_handler: ActionHandler = ActionHandler([])


def update_periods(nuvlaedge_resource: dict):
    # Update refreshing intervals
    refresh_interval = nuvlaedge_resource.get('refresh-interval',
                                              CTE.REFRESH_INTERVAL)
    heartbeat_interval = nuvlaedge_resource.get('heartbeat-interval',
                                               CTE.HEARTBEAT_INTERVAL)

    action_handler.edit_period('telemetry', refresh_interval)
    action_handler.edit_period('heartbeat', heartbeat_interval)

    root_logger.info(f'Telemetry period: {refresh_interval}s')
    root_logger.info(f'Heartbeat period: {heartbeat_interval}s')


def update_nuvlaedge_configuration(
        current_nuvlaedge_res: dict,
        old_nuvlaedge_res: dict,
        infra: Infrastructure):
    """
    Checks new the new nuvlaedge resource configuration for differences on the local
    registered one and updates (if required) the vpn and/or the heartbeat and telemetry
    periodic reports
    Args:
        current_nuvlaedge_res:
        old_nuvlaedge_res:
        infra:
    """
    if old_nuvlaedge_res['updated'] != current_nuvlaedge_res['updated']:
        update_periods(current_nuvlaedge_res)
        vpn_server_id = current_nuvlaedge_res.get("vpn-server-id")

        if vpn_server_id != old_nuvlaedge_res.get("vpn-server-id"):
            root_logger.info(f'VPN Server ID has been added/changed in Nuvla: '
                             f'{vpn_server_id}')
            infra.commission_vpn()


def resource_synchronization(
        activator: Activate,
        exit_event: Event,
        infra: Infrastructure):
    """
    Checks if the NuvlaEdge resource has been updated in Nuvla

    Args:
        activator:
        exit_event:
        infra:

    Returns:

    """

    nuvlaedge_resource: dict = activator.get_nuvlaedge_info()

    if nuvlaedge_resource.get('state', '').startswith('DECOMMISSION'):
        root_logger.info(f"Remote NuvlaEdge resource state "
                         f"{nuvlaedge_resource.get('state', '')}, exiting agent")
        exit_event.set()
        return

    vpn_server_id = nuvlaedge_resource.get("vpn-server-id")
    old_nuvlaedge_resource = activator.create_nb_document_file(nuvlaedge_resource)

    update_nuvlaedge_configuration(nuvlaedge_resource,
                                   old_nuvlaedge_resource,
                                   infra)

    # if there's a mention to the VPN server, then watch the VPN credential
    if vpn_server_id:
        infra.watch_vpn_credential(vpn_server_id)


def initialize_action(name: str,
                      period: int,
                      action: callable,
                      remaining_time: float = 0,
                      arguments: tuple | None = None,
                      karguments: dict | None = None):
    action_handler.add(
        TimedAction(
            name=name,
            period=period,
            action=action,
            remaining_time=remaining_time,
            arguments=arguments,
            karguments=karguments))


def main():
    """
    Initialize the main agent class. This class will also initialize submodules:
      - Activator
      - Telemetry
      - Infrastructure

    Returns: None
    """
    signal.signal(signal.SIGUSR1, signal_usr1)

    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)

    main_event: Event = Event()

    main_agent: Agent = Agent()
    main_agent.initialize_agent()

    # Adds the main agent actions to the agent handler
    initialize_action(name='heartbeat',
                      period=CTE.HEARTBEAT_INTERVAL,
                      remaining_time=CTE.HEARTBEAT_INTERVAL,
                      action=main_agent.send_heartbeat)
    initialize_action(name='telemetry',
                      period=CTE.REFRESH_INTERVAL,
                      action=main_agent.send_telemetry,
                      remaining_time=CTE.REFRESH_INTERVAL/2)
    initialize_action(name='sync_resources',
                      period=30,
                      action=resource_synchronization,
                      arguments=(main_agent.activate,
                                 main_event,
                                 main_agent.infrastructure))

    while not main_event.is_set():
        # Time Start
        start_cycle: float = time.time()

        action = action_handler.next
        main_agent.run_single_cycle(action)

        # root_logger.debug('Action summary after action_handler.next - ' + action_handler.actions_summary())

        # Account cycle time
        cycle_duration = time.time() - start_cycle
        next_cycle_in = action_handler.sleep_time()

        root_logger.info(f'Action "{action.name}" completed in {cycle_duration:.2f} seconds. '
                         f'Next action "{action_handler._actions[0].name}" will be run in {next_cycle_in:.2f} seconds.')

        root_logger.debug('Action summary after action_handler.sleep_time() - ' + action_handler.actions_summary())

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
