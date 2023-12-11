import json
from datetime import datetime
from pathlib import Path

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel


class NuvlaEdgeMessage(NuvlaEdgeBaseModel):
    sender: str
    data: dict
    time: datetime | None = None


def parse_message(file_location: Path | str) -> NuvlaEdgeMessage:
    """
    Receives the file location and returns a NuvlaEdgeMessage type.
    Time and sender come encoded in the name, data is the content of the file
    :param file_location:
    :return:
    """
    if isinstance(file_location, str):
        file_location = Path(file_location)

    if not file_location.exists():
        raise FileExistsError(f'Message {file_location} does not exist')

    with file_location.open('r') as file:
        js = json.load(file)

        return NuvlaEdgeMessage.model_validate(js)
