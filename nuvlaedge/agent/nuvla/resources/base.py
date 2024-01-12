import time
from typing import ClassVar

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel


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


class NuvlaEdgeTrackedResource(NuvlaResourceBase):
    accessed_fields: ClassVar[dict[str, float]] = {}

    _last_update_time: float = 0.0
    delete_period: ClassVar[float] = 180.0

    def __getattribute__(self, item):
        if item in object.__getattribute__(self, 'model_fields'):
            self.accessed_fields.update({item: time.perf_counter()})
        return object.__getattribute__(self, item)

    def clean_fields(self):
        t_time = time.perf_counter()
        new_fields = {k for k, v in self.accessed_fields.items() if t_time - v > self.delete_period}
        _ = [self.accessed_fields.pop(i) for i in new_fields]

    def get_fields(self):
        self.clean_fields()
        return set(self.accessed_fields.keys())
