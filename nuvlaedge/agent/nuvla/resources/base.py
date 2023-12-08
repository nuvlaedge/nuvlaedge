from datetime import datetime

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
