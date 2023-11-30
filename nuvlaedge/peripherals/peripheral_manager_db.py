"""

"""
import json
import logging
import time
from typing import Set, List, Dict, Tuple
from datetime import datetime
from copy import deepcopy

from nuvla.api import Api
from nuvla.api.models import CimiCollection, CimiResponse
from nuvlaedge.models.peripheral import PeripheralData
from nuvlaedge.models.nuvla_resources import NuvlaBoxPeripheralResource as PeripheralResource
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.constant_files import FILE_NAMES


class PeripheralsDBManager:
    """
    Controls the different databases of the peripheral manager
    """
    LOCAL_DB_SYNC_PERIOD = 3*60  # Every 3 minutes the local DB is synchronized with the Nuvla stored peripherals
    EXPIRATION_TIME = 5*60  # Rent

    def __init__(self, nuvla_client: Api, nuvlaedge_uuid: str):
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.uuid: str = nuvlaedge_uuid
        self.nuvla_client: Api = nuvla_client if nuvla_client else Api()

        self._latest_update: Dict[str, datetime] = {}
        self._local_db: Dict[str, PeripheralResource] = {}

        self._last_synch: int = 0

    @property
    def content(self) -> Dict:
        """
        Property DB that controls with which frequency the local database is updated and ensures the returned
        register is never out of date
        :return:
        """
        if time.time() - self._last_synch > self.LOCAL_DB_SYNC_PERIOD:
            self.synchronize()
            self._last_synch = time.time()

        return self._local_db

    @property
    def keys(self) -> Set:
        return set(self.content.keys())

    def synchronize(self):
        """
        Synchronizes the local database with the remote. Remote database will always prevail
        :return: None
        """
        # Raise a warning if the systems are desynchronized
        # Retrieve all the resources related to this NuvlaEdge with the parent field
        nuvla_peripherals: CimiCollection = \
            self.nuvla_client.search(CTE.PERIPHERAL_RES_NAME,
                                     filter=f'parent="{self.uuid}"')
        if nuvla_peripherals.count == 0:
            self.logger.info('No resources registered in Nuvla to update')
            self._local_db = {}
            self._latest_update = {}
            return

        # Decode the NuvlaPeripherals into a dictionary following {'identifier': 'data'}
        self._local_db = self.decode_new_peripherals(nuvla_peripherals.resources)

        # Synchronize the latest update with Nuvla identifiers
        for i in set(self._latest_update.keys()) - set(self._local_db.keys()):
            self._latest_update.pop(i)

        for i in set(self._local_db.keys()) - set(self._latest_update.keys()):
            self._latest_update[i] = self._local_db.get(i).updated

        self.update_local_storage()

    def update_local_storage(self):
        """
        Backs up the local storage into a file. Completely erases the previous content
        :return:
        """
        try:
            with FILE_NAMES.LOCAL_PERIPHERAL_DB.open('w') as file:
                # Assign the default encoder Pydantic Models
                to_save = {k: v.dict(by_alias=True, exclude_none=True) for k, v in self._local_db.items()}
                json.dump(to_save, file, default=str, indent=4)
        except Exception as ex:
            self.logger.error(f'Error while opening {FILE_NAMES.LOCAL_PERIPHERAL_DB} : {ex}')

    @staticmethod
    def decode_new_peripherals(new_peripherals: List) -> Dict[str, PeripheralResource]:
        """
        Takes a list of new received peripherals and rearranges them into a dictionary:
        {
            'per_identifier_1': {peripheral_data},
            'per_identifier_2': {peripheral_data_2}
        }
        If any of the peripherals don't container the compulsory fields, ignores it and
         reports as a warning
        :param new_peripherals: Newly received peripherals
        :return: A dictionary rearranging new peripherals.
        """
        if not new_peripherals:
            return {}
        ret = {}
        for p in new_peripherals:
            ret[p.data['identifier']] = PeripheralResource.parse_obj(p.data)
        return ret

    def add_peripheral(self, peripheral: PeripheralData):
        """
        Adds a device to both local and remote registry
        :param peripheral: Data confirming the detected peripheral device
        :return:
        """
        # Format new peripheral resource
        res: PeripheralResource = PeripheralResource.parse_obj(peripheral)
        # When adding a peripheral to Nuvla both Parent and Version fields must be filled
        res.parent = self.uuid
        res.version = CTE.PERIPHERAL_SCHEMA_VERSION

        # Add to remote,
        peripheral_id, reg_status = self.add_remote_peripheral(res)

        if reg_status in [200, 201]:
            self.logger.info(f'Peripheral {peripheral.identifier} successfully registered in Nuvla')

            # Locally, we store the Peripheral resource with an id and the current datetime to keep track of
            # the latest updated time
            res.id = peripheral_id
            self._latest_update[peripheral.identifier] = datetime.now()

            self.add_local_peripheral(res)
        else:
            self.logger.warning(f'Cannot add {peripheral.identifier} to Nuvla with error code {reg_status}')

    def add_local_peripheral(self, peripheral: PeripheralResource):
        """
        Stores the new peripheral in the local registry
        :param peripheral:
        :return:
        """
        self._local_db.update({peripheral.identifier: peripheral})

    def add_remote_peripheral(self, peripheral: PeripheralResource) -> Tuple[str, str]:
        """
        Stores the new peripheral in the remote registry
        :param peripheral:
        :return:
        """
        # Add peripheral to Nuvla
        # If nuvla returns ID, add it to the PeripheralData structure
        # if success, return ID and None
        # else return None, Error code
        response: CimiResponse = self.nuvla_client.add(
            CTE.PERIPHERAL_RES_NAME,
            peripheral.dict(by_alias=True,
                            exclude_none=True))
        p_id = response.data.get('resource-id')
        p_status = response.data.get('status')
        self.logger.debug(f'Peripheral {peripheral.identifier} registered with status {p_status}')
        return p_id, p_status

    def remove_peripheral(self, peripheral_id: str):
        """
        Removes the peripheral from local and Nuvla DB if exists
        :param peripheral_id:
        :return: Status Response for the cimi delete action
        """
        # Remove from Nuvla extracting the Nuvlabox-peripheral ID from the corresponding field
        del_status = self.remove_remote_peripheral(self.content.get(peripheral_id).id)

        if del_status in [200, 201]:
            self.logger.info(f'Peripheral "{peripheral_id}" successfully removed from Nuvla, removing from local')
            self.remove_local_peripheral(peripheral_id)
        else:
            self.logger.warning(f'Error {del_status} deleting peripheral from Nuvla')

    def remove_local_peripheral(self, peripheral_id: str):
        """
        Removes the peripheral from the local registry
        :param peripheral_id:
        :return:
        """
        # Add peripheral to local registry
        self._local_db.pop(peripheral_id)
        self._latest_update.pop(peripheral_id)

    def remove_remote_peripheral(self, peripheral_res_id: str) -> int:
        """
        Removes a peripheral from
        :param peripheral_res_id:
        :return:
        """
        response: CimiResponse = self.nuvla_client.delete(peripheral_res_id)

        p_status = response.data.get('status')
        self.logger.debug(f'Peripheral {peripheral_res_id} removed from Nuvla with status {p_status}')
        return p_status

    def add(self, new_peripherals: Dict[str, PeripheralData]):
        """

        :param new_peripherals:
        :return:
        """
        self.logger.info(f'Adding peripherals to DB {new_peripherals}')
        for k, v in new_peripherals.items():
            if k in self.keys:
                # Check should have already been done
                self.logger.info(f'Identifier {k}, already registered, move to edit')
                continue

            self.add_peripheral(v)

        self.logger.info('After adding in the local DB, backup to file')
        self.update_local_storage()

    def peripheral_expired(self, peripheral_id: str) -> bool:
        """
        Given a peripheral identifier, checks if its last updated date is > EXPIRATION_TIME
        :param peripheral_id:
        :return:
        """
        now = datetime.now().timestamp()
        then = self._latest_update.get(peripheral_id).timestamp()

        return (now - then) > self.EXPIRATION_TIME

    def remove(self, peripherals: Set):
        """

        :param peripherals:
        :return:
        """
        # Remove only if the device has been offline for more than 5 minutes
        self.logger.info(f'Removing peripherals from DB {peripherals}')
        update_flag = False
        for p in peripherals:
            # Try to remove each device individually
            if p not in self.keys:
                continue

            # Updated field should always be filled, either when updating from Nuvla or when creating the Peripheral
            if self.peripheral_expired(p):
                self.logger.info(f'Peripheral "{p}" last report more than {self.EXPIRATION_TIME/60} min ago, removing')
                update_flag = True
                self.remove_peripheral(p)

        self.logger.debug('After removing in the local DB, backup to file')
        if update_flag:
            self.update_local_storage()

    def edit(self, new_peripherals: Dict[str, PeripheralData]):
        """

        :param new_peripherals:
        :return:
        """
        self.logger.info('Checking if information has changed in peripherals')
        for identifier, data in new_peripherals.items():
            self._latest_update[identifier] = datetime.now()

        self.logger.debug('After editing the local DB, backup to file')
        self.update_local_storage()
