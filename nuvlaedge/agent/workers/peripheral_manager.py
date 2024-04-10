"""

"""
import logging
from pathlib import Path
from queue import Queue
from threading import Event, Thread

from pydantic import ValidationError
from nuvla.api import Api as NuvlaClient

from nuvlaedge.agent.common.status_handler import NuvlaEdgeStatusHandler, StatusReport
from nuvlaedge.broker.file_broker import FileBroker
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.models.messages import NuvlaEdgeMessage
from nuvlaedge.peripherals.peripheral_manager_db import PeripheralsDBManager
from nuvlaedge.broker import NuvlaEdgeBroker
from nuvlaedge.models.peripheral import PeripheralData
from nuvlaedge.common.file_operations import create_directory


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class PeripheralManager:
    """
    A class that manages peripherals, including checking for new peripherals, adding, editing, and deleting peripherals.

    Attributes:
        REFRESH_RATE (int): Peripheral refresh rate in seconds.
        NUVLA_SYNCHRONIZATION_PERIOD (int): Synchronization period for checking Nuvla DB and local DB.
        PERIPHERALS_LOCATION (Path): Location of the peripherals folder.

    Methods:
        __init__(nuvla_client, nuvlaedge_uuid): Initializes the PeripheralManager class.
        update_running_managers(): Checks which peripheral scanners are currently running.
        process_new_peripherals(new_peripherals): Assess what to do with the new received peripherals.
        available_messages(): Generator that allows to iterate over the latest messages of the peripheral managers.
        join_new_peripherals(new_peripherals): Takes a list of new received peripherals and rearranges them into a dictionary.
        run(): Runs the peripheral manager.

    Example:
        manager = PeripheralManager(nuvla_client, nuvlaedge_uuid)
        manager.run()
    """
    REFRESH_RATE = 30  # Peripheral refresh rate in seconds
    # Normally, NuvlaDB and local DB shouldn't be desynchronized. For safety, we check Nuvla db and synchronize the
    # local one with it for safe keeping
    NUVLA_SYNCHRONIZATION_PERIOD = 4*REFRESH_RATE

    PERIPHERALS_LOCATION: Path = FILE_NAMES.PERIPHERALS_FOLDER

    def __init__(self, nuvla_client: NuvlaClient,
                 nuvlaedge_uuid: str,
                 status_channel: Queue[StatusReport]
                 ):
        """
        Initializes an instance of the class with the given parameters.

        Args:
            nuvla_client: An instance of NuvlaClient class for communication with the Nuvla database.
            nuvlaedge_uuid: A string representing the UUID of the Nuvlaedge instance.

        """
        # Required to check the Nuvla database and filter present peripherals
        self._uuid: str = nuvlaedge_uuid

        # Broker instance to consume messages from the peripherals
        self.broker: NuvlaEdgeBroker = FileBroker()

        # Particular class to control and wrap the handling of peripherals
        self.db: PeripheralsDBManager = PeripheralsDBManager(nuvla_client, nuvlaedge_uuid)

        # Event to control the thread, time it and exit it
        self.exit_event: Event = Event()

        self.running_peripherals: set = set()
        self.registered_peripherals: dict[str, PeripheralData] = {}

        self.status_channel: Queue[StatusReport] = status_channel

        create_directory(FILE_NAMES.PERIPHERALS_FOLDER)

        NuvlaEdgeStatusHandler.starting(self.status_channel, 'Peripheral Manager')

    def update_running_managers(self):
        """
        Updates the set of running managers by checking the status of peripherals.

        This method iterates through the files in the `PERIPHERALS_FOLDER` directory and checks if each file represents
         a running peripheral manager. If a file is a directory, it means that the peripheral manager is running.
         The `running_peripherals` set is updated with the running managers.

        Returns:
            None
        """
        logger.debug(f'Getting peripheral status from: {FILE_NAMES.PERIPHERALS_FOLDER}')

        for f in FILE_NAMES.PERIPHERALS_FOLDER.iterdir():
            if f.is_dir():
                logger.debug(f'{f} peripheral manager running')
                self.running_peripherals.add(f)

    def process_new_peripherals(self, new_peripherals: dict[str, PeripheralData]):
        """
        Process new peripherals and update the database accordingly.

        Args:
            new_peripherals (dict[str, PeripheralData]): A dictionary containing information about the new peripherals. The keys are unique identifiers for each peripheral, and the values are
        * PeripheralData objects.

        """
        # Process unique identifiers to compare new with stored
        new_identifiers = set(new_peripherals.keys())
        present_identifiers = self.db.keys

        # Peripherals not registered in Nuvla but detected in the last iteration
        to_add = new_identifiers - present_identifiers

        if to_add:
            self.db.add({i: new_peripherals[i] for i in to_add})

        # Peripherals registered in Nuvla no longer present in the systems
        to_delete = present_identifiers - new_identifiers
        if to_delete:
            self.db.remove(to_delete)

        # Peripherals registered and detected in the last iteration that need to check for changes
        to_check = new_identifiers & present_identifiers
        if to_check:
            self.db.edit({i: new_peripherals[i] for i in to_check})

    @property
    def available_messages(self):
        """
        Generator that allows to iterate over the latest messages of the peripheral mangers when present
        :return: Yields the latest available message for each peripheral manager
        """
        # Iterate running peripherals
        for peripheral_manager in self.running_peripherals:
            # Consume messages from broker
            new_devices: list[NuvlaEdgeMessage] = \
                self.broker.consume(f'{self.PERIPHERALS_LOCATION.name}/{peripheral_manager.name}')

            # Skip empty messages or errors
            if not new_devices:
                continue

            try:
                # Yield latest message
                yield sorted(new_devices, key=lambda x: x.time)[0].data
            except IndexError:
                # We should never reach here, catch the possible index error to prevent the manager
                # from dying due to broker errors
                logger.warning(f'Error sorting messages from peripheral {peripheral_manager} channel')

    def join_new_peripherals(self, new_peripherals: list[dict]) -> dict[str, PeripheralData]:
        """
        Takes a list of new received peripherals and rearranges them into a dictionary:
        {
            'per_identifier_1': {peripheral_data},
            'per_identifier_2': {peripheral_data_2}
        }
        If any of the peripherals don't contain the compulsory fields, ignores it and reports as a warning
        :param new_peripherals: Newly received peripherals
        :return: A dictionary rearranging new peripherals.
        """
        if not new_peripherals:
            return {}

        peripheral_acc: dict = {}
        for manager_report in new_peripherals:
            for identifier, data in manager_report.items():
                try:
                    peripheral_acc[identifier] = PeripheralData.model_validate(data)
                except ValidationError:
                    logger.exception(f'Error processing data from device {identifier}')

        return peripheral_acc

    def run(self) -> None:
        """
        Method to run the scanning process for detected devices.
        """
        logger.info('Scanning for detected devices')
        NuvlaEdgeStatusHandler.running(self.status_channel, 'Peripheral Manager')

        self.update_running_managers()

        # New peripherals accumulator for different peripheral managers
        new_peripherals = [m for m in self.available_messages]

        # Decode all new messages at once. This function is an auxiliary tool for the DB to decode
        # peripherals coming from Nuvla that can be reused here
        new_peripherals = self.join_new_peripherals(new_peripherals)

        # Process the new peripherals data
        if new_peripherals:
            self.process_new_peripherals(new_peripherals)

        self.exit_event.wait(self.REFRESH_RATE)

