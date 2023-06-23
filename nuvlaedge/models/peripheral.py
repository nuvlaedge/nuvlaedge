from pydantic import validator

from nuvlaedge.models import NuvlaEdgeBaseModel


class PeripheralData(NuvlaEdgeBaseModel):
    identifier: str
    available: bool
    classes: list

    name: str | None
    device_path: str | None
    port: int | None
    interface: str | None
    product: str | None
    version: int | None
    additional_assets: dict | None
    vendor: str | None
    product: str | None
    local_data_gateway_endpoint: str | None
    raw_data_sample: str | None
    data_gateway_enabled: bool | None
    serial_number: str | None
    video_device: str | None
    resources: list | None

    @validator('device_path', 'vendor', 'raw_data_sample', 'serial_number', 'video_device')
    def validate_device_path(cls, v):
        if isinstance(v, str) and not v:
            raise ValueError('Cannot be an empty string')
        return v
