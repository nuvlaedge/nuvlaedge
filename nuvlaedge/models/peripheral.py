from pydantic import field_validator

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel


class PeripheralData(NuvlaEdgeBaseModel):
    identifier: str
    available: bool
    classes: list

    name: str | None = None
    device_path: str | None = None
    port: int | None = None
    interface: str | None = None
    product: str | None = None
    version: int | None = None
    additional_assets: dict | None = None
    vendor: str | None = None
    local_data_gateway_endpoint: str | None = None
    raw_data_sample: str | None = None
    data_gateway_enabled: bool | None = None
    serial_number: str | None = None
    video_device: str | None = None
    resources: list | None = None

    @field_validator('device_path', 'vendor', 'raw_data_sample', 'serial_number', 'video_device')
    def validate_device_path(cls, v):
        if isinstance(v, str) and not v:
            raise ValueError('Cannot be an empty string')
        return v
