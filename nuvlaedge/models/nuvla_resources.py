"""
Contains the definitions and spec of Nuvla Resources
"""

from pydantic import field_validator

from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.models.peripheral import PeripheralData


class NuvlaBoxAttributes(NuvlaEdgeBaseModel):
    version: int
    owner: str | None = None

    nuvlabox_status: str | None = None
    infrastructure_service_group: str | None = None
    credential_api_key: str | None = None
    host_level_management_api_key: str | None = None


class NuvlaBoxResource(NuvlaEdgeBaseModel):

    state: str
    refresh_interval: int
    
    location: list | None = None
    supplier: str | None = None
    organization: str | None = None
    manufacturer_serial_number: str | None = None
    firmware_version: str | None = None
    hardware_type: str | None = None
    form_factor: str | None = None
    wifi_ssid: str | None = None
    wifi_password: str | None = None
    root_password: str | None = None
    login_username: str | None = None
    login_password: str | None = None
    comment: str | None = None
    lan_cidr: str | None = None
    hw_revision_code: str | None = None
    monitored: bool | None = None
    vpn_server_id: str | None = None
    internal_data_gateway_endpoint: str | None = None
    ssh_keys: list[str] | None = None
    capabilities: list[str] | None = None
    online: bool | None = None
    inferred_location: list[float] | None = None
    nuvlabox_engine_version: str | None = None

    @field_validator('*')
    def non_empty_str(cls, v):
        print(v)
        if isinstance(v, str):
            return v if v else None
        return v


class NuvlaBoxPeripheralResource(NuvlaResourceBase, PeripheralData):
    ...
