import json
import logging
import time
from abc import ABC
from typing import Any
from pydantic import BaseModel

from nuvla.api import Api
from nuvla.api.models import CimiResource

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from .nuvla_id import NuvlaID


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class NuvlaResourceBase(NuvlaEdgeBaseModel):
    """

    """
    # These entries are mandatory when the message is received from Nuvla. Cannot/Should not be created or edited
    # by the NuvlaEdge.
    id: NuvlaID | None = None
    resource_type: str | None = None
    created: str | None = None
    updated: str | None = None
    acl: dict | None = None

    # Optional params in the common schema
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    parent: str | None = None  # Nuvla ID format
    resource_metadata: str | None = None
    operations: list | None = None
    created_by: str | None = None
    updated_by: str | None = None


class AutoUpdateNuvlaEdgeTrackedResource(NuvlaResourceBase):

    # Keeps track of the accessed field of the model. This allows for selective retrieval from Nuvla,
    # reducing network traffic
    _accessed_fields: dict[str, float] = {}
    _is_synced: bool = False

    # Nuvla Client used to sync the resource
    _nuvla_client: Api | None = None
    _resource_id: NuvlaID | None = None

    # Keeps track of the last Nuvla synchronisation
    _last_update_time: float = -1.0

    # Minimum period to update the resource. Might be overriden from inheritance
    _MIN_UPDATE_PERIOD: int = 60

    # Fields time out after being accessed. This is to avoid keeping fields in memory that are not used anymore.
    _FIELD_TIMEOUT_PERIOD: int = _MIN_UPDATE_PERIOD * 3

    def __init__(self, nuvla_client: Api, resource_id: NuvlaID, **data: Any):
        super().__init__(**data)
        self._nuvla_client = nuvla_client
        self._resource_id = resource_id

    def _sync(self):
        """ Syncs the resource with Nuvla. This is a standardised method that might be overriden by the child classes
         in case the sync is more complex.

        """

        _select: set | None = self._get_accessed_fields()

        # If it is the first time retrieving the NuvlaEdge, retrieve the full document
        if self._last_update_time < 0:
            logger.debug(f"Retrieving full {self._resource_id} resource")
            _select = None

        logger.debug(f"Updating NuvlaEdge fields: {_select} from resource {self._resource_id}")
        resource: CimiResource = self._nuvla_client.get(self._resource_id, select=_select)

        self._update_fields(resource.data)

        self._last_update_time = time.perf_counter()

    def force_update(self):
        """ Forces an update of the resource from Nuvla.

         Should only be triggered after a change in the resource by commissioning/activate operations
        """
        self._last_update_time = -1.0
        self._sync()

    def _update_fields(self, data: dict[str, Any]):
        """ Updates the model fields of the resource with the data provided by Nuvla."""
        for field, value in data.items():
            f_name = field.replace('-', '_')
            if f_name in self.model_fields:
                self.__setattr__(f_name, value)

    def __getattribute__(self, item):
        if item in object.__getattribute__(self, 'model_fields'):
            self._accessed_fields.update({item.replace('_', '-'): time.perf_counter()})

            if (time.perf_counter() - self._last_update_time > self._MIN_UPDATE_PERIOD or
                    object.__getattribute__(self, item) is None):
                logger.debug(f"Updating {self.__class__.__name__} resource")
                self._sync()
        return object.__getattribute__(self, item)

    def _compute_fields(self):
        """ Cleans the fields that have not been accessed for a while."""
        t_time = time.perf_counter()
        new_fields = {k for k, v in self._accessed_fields.items() if t_time - v > self._FIELD_TIMEOUT_PERIOD}
        _ = [self._accessed_fields.pop(i) for i in new_fields]

    def _get_accessed_fields(self) -> set | None:
        """ Returns the fields that have been accessed.

        Returns:
            set: The set of fields that have been accessed.
        """
        self._compute_fields()
        return set(self._accessed_fields.keys()) if len(self._accessed_fields) > 0 else None
