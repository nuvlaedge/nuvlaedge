from datetime import datetime

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel


class NuvlaResourceBase(NuvlaEdgeBaseModel):
    """

    """
    # These entries are mandatory when the message is received from Nuvla. Cannot/Should not be created or edited
    # by the NuvlaEdge.
    id: NuvlaID | None
    resource_type: str | None
    created: datetime | None
    updated: datetime | None
    acl: dict | None

    # Optional params in the common schema
    name: str | None
    description: str | None
    tags: list[str] | None
    parent: str | None  # Nuvla ID format
    resource_metadata: str | None
    operations: list | None
    created_by: str | None
    updated_by: str | None
