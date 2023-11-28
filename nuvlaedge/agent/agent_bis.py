import logging
from threading import Event
from typing import Callable

from nuvlaedge.agent.nuvla.resources.nuvlaedge import State
from nuvlaedge.agent.orchestrator.docker import DockerClient
from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient
from nuvlaedge.agent.telemetry import Telemetry
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.peripherals.peripheral_manager import PeripheralManager

logger: logging.Logger = logging.getLogger(__name__)


class Agent:
    def __init__(self,
                 agent_config,
                 exit_event: Event | None = None,
                 on_nuvlaedge_update: Callable[[dict], None] | None = None):
        logging.debug(f"Initialising Agent Class")

        self._exit: Event = exit_event
        self.on_nuvlaedge_update: Callable[[dict], None] | None = on_nuvlaedge_update

        # Wrapper for Nuvla API library specialised in NuvlaEdge
        self._nuvla_client: NuvlaClientWrapper | None = None

        # NuvlaWatchdog. Checks Nuvla for fields that might change in runtime
        self._nuvla_watchdog = None

        # Container orchestration engine: either docker or k8s implementation
        self._coe_engine: DockerClient | KubernetesClient | None = None

        # Local telemetry instance
        self._telemetry: Telemetry | None = None

        # Peripheral manager instance
        self._peripheral_manager: PeripheralManager | None = None

    def initialise_agent(self):
        """

        Returns:

        """
        # Find previous installations
        # Run start up process if needed
        current_state: State = State.NEW

    def run(self):
        ...
