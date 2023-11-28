"""
Contains the definitions and spec of Nuvla Resources
"""

from pydantic import validator

from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.models.peripheral import PeripheralData


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
