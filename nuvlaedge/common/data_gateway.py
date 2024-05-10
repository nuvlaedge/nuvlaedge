import json
import logging
from typing import Callable

import paho.mqtt.client as mqtt

from nuvlaedge.common.constants import CTE
from .nuvlaedge_logging import get_nuvlaedge_logger
from ..agent.workers.telemetry import TelemetryPayloadAttributes

logger: logging.Logger = get_nuvlaedge_logger(__name__)


SenderFunc = Callable[[TelemetryPayloadAttributes], None]


class DataGatewayPub:
    TELEMETRY_TOPIC = 'nuvlaedge-status'

    def __init__(self,
                 endpoint: str = CTE.DATA_GATEWAY_ENDPOINT,
                 port: int = CTE.DATA_GATEWAY_PORT,
                 timeout: int = CTE.DATA_GATEWAY_TIMEOUT):
        self.endpoint: str = endpoint
        self.port: int = port
        self.timeout: int = timeout

        self.client: mqtt.Client = mqtt.Client()

        self.SENDERS: dict[str, SenderFunc] = {"telemetry_info": self._send_full_telemetry,
                                               "cpu_info": self._send_cpu_info,
                                               "ram_info": self._send_memory_info,
                                               "disk_info": self._send_disk_info}

    def connect(self):
        logger.info("Connecting to the data gateway...")
        try:
            res = self.client.connect(host=self.endpoint,
                                      port=self.port,
                                      keepalive=self.timeout)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to the data gateway: {e}")
            return
        logger.info(f"Connected to the data gateway with result: {res}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected()

    def _publish(self, topic: str, payload: str) -> mqtt.MQTTMessageInfo:
        r = self.client.publish(topic, payload=payload)
        logger.debug(f"Waiting for topic {topic} to publish...")
        r.wait_for_publish(1)
        return r

    def _send_full_telemetry(self, data: TelemetryPayloadAttributes):
        logger.debug("Sending full telemetry to mqtt...")
        data = data.model_dump(exclude_none=True, by_alias=True)
        res = self._publish(self.TELEMETRY_TOPIC, payload=json.dumps(data))

        if not res.is_published():
            logger.error(f"Failed to send telemetry to mqtt topic: {self.TELEMETRY_TOPIC} ")
        logger.debug("Sending full telemetry to mqtt... Success")

    def _send_cpu_info(self, data: TelemetryPayloadAttributes):
        cpu = data.resources.get('cpu', {}).get('raw-sample')
        if not cpu:
            logger.debug("No CPU data to send to the data gateway")
            return
        res = self._publish('cpu', cpu)

        if not res.is_published():
            logger.error("Failed to send cpu info to mqtt")

    def _send_memory_info(self, data: TelemetryPayloadAttributes):
        memory = data.resources.get('memory', {}).get('raw-sample')
        if not memory:
            logger.debug("No memory data to send to the data gateway")
            return
        res = self._publish('ram', memory)

        if not res.is_published():
            logger.error("Failed to send memory info to mqtt")

    def _send_disk_info(self, data: TelemetryPayloadAttributes):
        disks = data.resources.get('disks', [])
        if not disks:
            logger.debug("No disk data to send to the data gateway")
            return
        for disk in disks:
            self._publish("disks", json.dumps(disk))

    def send_telemetry(self, data: TelemetryPayloadAttributes):
        if not self.is_connected:
            self.connect()
            if not self.is_connected:
                logger.error("Failed to connect to the data gateway")
                return

        logger.info("Sending telemetry to mqtt...")
        for name, sender in self.SENDERS.items():
            try:
                logger.debug(f"Sending {name} to mqtt...")
                sender(data)
            except Exception as e:
                logger.error(f"Failed to send telemetry ({name}) to mqtt: {e}")


data_gateway_client = DataGatewayPub()
