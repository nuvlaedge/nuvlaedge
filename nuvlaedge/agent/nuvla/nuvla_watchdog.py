"""

"""
import logging
from dataclasses import dataclass

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper


logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class WatchedField:
    resource_name: str
    fields_name: str

    last_update: float
    update_period: int


class NuvlaWatchDog:
    def __init__(self, nuvla_client: NuvlaClientWrapper):
        self.nuvla_client: NuvlaClientWrapper = nuvla_client

        self.watched_fields: dict[str, WatchedField] = {}

    def add_field(self, field: str):
        if field in self.watched_fields:
            logger.warning("Field already being watched")
            return

    def remove_field(self, field: str):
        if field not in self.watched_fields:
            logger.warning(f"Field {field} not present in watched fields")
            return

        self.watched_fields.pop(field)

