from typing import Protocol

from nuvlaedge.models.messages import NuvlaEdgeMessage


class NuvlaEdgeBroker(Protocol):
    def consume(self, channel: str) -> list[NuvlaEdgeMessage]:
        ...

    def publish(self, channel: str, data: dict | NuvlaEdgeMessage, sender: str = '') -> bool:
        ...
