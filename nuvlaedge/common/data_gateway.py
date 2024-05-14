import json
from functools import wraps
import logging
from pathlib import Path
from typing import Callable

import paho.mqtt.client as mqtt
from pydantic import BaseModel

from nuvlaedge.common.constants import CTE
from .constant_files import FILE_NAMES
from .file_operations import file_exists_and_not_empty, read_file
from .nuvlaedge_logging import get_nuvlaedge_logger
from ..agent.workers.telemetry import TelemetryPayloadAttributes

logger: logging.Logger = get_nuvlaedge_logger(__name__)


SenderFunc = Callable[[TelemetryPayloadAttributes], None]


class DataGatewayConfig(BaseModel):
    endpoint: str = CTE.DATA_GATEWAY_ENDPOINT
    port: int = CTE.DATA_GATEWAY_PORT
    ping_interval: int = CTE.DATA_GATEWAY_PING_INTERVAL
    enabled: bool = False


class DataGatewayPub:
    TELEMETRY_TOPIC = 'nuvlaedge-status'

    def __init__(self, config_file: Path = FILE_NAMES.DATA_GATEWAY_CONFIG_FILE):

        self.dw_config_file: Path = config_file
        self.client: mqtt.Client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # Initialise the data gateway configuration, should always have enabled as default
        self.data_gateway_config: DataGatewayConfig = DataGatewayConfig()
        self.config_edit_time: float = 0.0
        self.SENDERS: dict[str, SenderFunc] = {"telemetry_info": self._send_full_telemetry,
                                               "cpu_info": self._send_cpu_info,
                                               "ram_info": self._send_memory_info,
                                               "disk_info": self._send_disk_info}

    @property
    def has_config_changed(self) -> bool:
        if self.config_edit_time <= 0:
            return True

        if self.dw_config_file.stat().st_mtime > self.config_edit_time:
            return True

        return False

    def _read_config(self):
        logger.info(f"Loading data gateway configuration from file {self.dw_config_file}...")
        conf: str = read_file(self.dw_config_file)
        self.data_gateway_config = DataGatewayConfig.model_validate_json(conf)
        self.config_edit_time = self.dw_config_file.stat().st_mtime
        logger.info(f"Data gateway loaded from file edited on {self.config_edit_time}")
        logger.info(f"Data gateway configuration: {self.data_gateway_config.model_dump_json(indent=4)}")

    def is_dw_available(self) -> bool:
        if file_exists_and_not_empty(self.dw_config_file) and self.has_config_changed:
            try:
                self._read_config()
            except Exception as e:
                logger.error(f"Failed to read data gateway configuration: {e}")
                return False

        if not self.data_gateway_config.enabled:
            logger.info("Data gateway is not yet enabled")
            return False

        if not self.is_connected:
            self.connect()
            return self.is_connected

        else:
            return True

    def connect(self):
        logger.info("Connecting to the data gateway...")
        try:
            self.client.connect(host=self.data_gateway_config.endpoint,
                                port=self.data_gateway_config.port,
                                keepalive=self.data_gateway_config.ping_interval)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to the data gateway: {e}")
            return
        logger.info("Connecting to the data gateway... Success")

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
        if not self.is_dw_available():
            return

        logger.info("Sending telemetry to mqtt...")
        for name, sender in self.SENDERS.items():
            try:
                logger.debug(f"Sending {name} to mqtt...")
                sender(data)
            except Exception as e:
                logger.error(f"Failed to send telemetry ({name}) to mqtt: {e}")


data_gateway_client = DataGatewayPub()
