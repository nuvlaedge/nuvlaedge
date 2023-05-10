"""
Contains the definitions and spec of Nuvla Resources
"""
from datetime import datetime

from pydantic import validator

from nuvlaedge.models import NuvlaEdgeBaseModel
from nuvlaedge.models.peripheral import PeripheralData


class NuvlaResourceBase(NuvlaEdgeBaseModel):
    """

    """
    # These entries are mandatory when the message is received from Nuvla. Cannot/Should not be created or edited
    # by the NuvlaEdge.
    # TODO: Maybe we can skip here the compulsory check of parameters to add flexibility to the model
    id: str | None
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


class NuvlaBoxAttributes(NuvlaEdgeBaseModel):
    version: int
    owner: str | None

    nuvlabox_status: str | None
    infrastructure_service_group: str | None
    credential_api_key: str | None
    host_level_management_api_key: str | None


class NuvlaBoxResource(NuvlaEdgeBaseModel):

    state: str
    refresh_interval: int
    
    location: list | None
    supplier: str | None
    organization: str | None
    manufacturer_serial_number: str | None
    firmware_version: str | None
    hardware_type: str | None
    form_factor: str | None
    wifi_ssid: str | None
    wifi_password: str | None
    root_password: str | None
    login_username: str | None
    login_password: str | None
    comment: str | None
    lan_cidr: str | None
    hw_revision_code: str | None
    monitored: bool | None
    vpn_server_id: str | None
    internal_data_gateway_endpoint: str | None
    ssh_keys: list[str] | None
    capabilities: list[str] | None
    online: bool | None
    inferred_location: list[float] | None
    nuvlabox_engine_version: str | None

    @validator('*')
    def non_empty_str(cls, v):
        print(v)
        if isinstance(v, str):
            return v if v else None
        return v


class NuvlaBoxPeripheralResource(NuvlaResourceBase, PeripheralData):
    ...
