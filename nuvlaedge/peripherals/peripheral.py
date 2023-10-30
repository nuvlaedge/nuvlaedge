"""

"""
import json
import logging
from threading import Event

from nuvlaedge.broker import NuvlaEdgeBroker
from nuvlaedge.broker.file_broker import FileBroker
from nuvlaedge.common.constant_files import FILE_NAMES


class Peripheral:

    def __init__(self, name: str, scanning_interval: int = 30, async_mode: bool = False):
        self.logger: logging.Logger = logging.getLogger(name)

        self._name: str = name
        self._id: str = ''
        self._scanning_interval: int = scanning_interval
        self._async_mode: bool = async_mode

        self.broker: NuvlaEdgeBroker = FileBroker()
        self.last_hash: int = 0

    @staticmethod
    def hash_discoveries(devices: dict) -> int:
        return hash(json.dumps(devices, sort_keys=True))

    async def run_single_iteration(self, run_peripheral: callable, **kwargs):
        self.logger.info('Discovering peripherals')
        if self._async_mode:
            discovered_peripherals: dict = await run_peripheral(**kwargs)
        else:
            discovered_peripherals: dict = run_peripheral(**kwargs)
        # Maybe we should always publish, regardless of the previous device and let the manager decide what to
        # do with the repetition

        if discovered_peripherals:
            self.logger.info(f'New devices discovered in {self._name} peripheral:  {discovered_peripherals.keys()}')
            self.broker.publish(FILE_NAMES.PERIPHERALS_FOLDER.name + '/' + self._name,
                                discovered_peripherals,
                                self._name)

    async def run(self, run_peripheral: callable, **kwargs):
        """
        Runs the peripheral telemetry function
        :return:
        """
        e = Event()
        while True:
            await self.run_single_iteration(run_peripheral, **kwargs)
            e.wait(timeout=self._scanning_interval)
