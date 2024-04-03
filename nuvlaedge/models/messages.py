import json
from datetime import datetime
from pathlib import Path

from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.file_operations import read_file


class NuvlaEdgeMessage(NuvlaEdgeBaseModel):
    sender: str
    data: dict
    time: datetime | None = None


def parse_message(file_location: Path | str) -> NuvlaEdgeMessage | None:
    """
    Receives the file location and returns a NuvlaEdgeMessage type.
    Time and sender come encoded in the name, data is the content of the file
    :param file_location:
    :return:
    """

    message = read_file(file_location, decode_json=True)
    if message:
        return NuvlaEdgeMessage.model_validate(message)
    return None
