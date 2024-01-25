import logging
from datetime import datetime, timedelta
from queue import Queue
from typing import Literal

from pydantic import BaseModel

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class StatusReport(BaseModel):
    origin_module: str
    module_status: Literal['STARTING', 'RUNNING', 'STOPPED', 'FAILING', 'FAILED']
    date: datetime
    message: str = ''


class NuvlaEdgeStatusHandler:
    STATUS_TIMEOUT: int = 5*60

    def __init__(self):
        self._status: Literal['OPERATIONAL', 'UNKNOWN', 'DEGRADED'] = 'UNKNOWN'
        self._notes: list[str] = []
        self._message: str = ''

        self.status_channel: Queue[StatusReport] = Queue()

        self.module_reports: dict[str, StatusReport] = {}

    def add_module(self, module_status: StatusReport):
        self.module_reports[module_status.origin_module] = module_status

    def remove_module(self, module_name: str | StatusReport):
        if isinstance(module_name, StatusReport):
            module_name = module_name.origin_module

        self.module_reports.pop(module_name)

    def process_status(self):
        temp_status = 'UNKNOWN'
        temp_notes = []

        def time_diff(date: datetime) -> int:
            diff: timedelta = datetime.now() - date
            return diff.seconds

        for module_name, module_report in self.module_reports.items():
            logger.debug(f"Processing module {module_report}")

            if module_report.module_status in ['STOPPED', 'FAILING', 'FAILED']:
                logger.debug(f"Module {module_name} is in STOPPED, FAILING or FAILED")
                temp_status = 'DEGRADED'

            if module_report.module_status in ['STARTING', 'RUNNING'] and temp_status != 'DEGRADED':
                logger.debug(f"Module {module_name} is in STARTING or RUNNING")
                temp_status = 'OPERATIONAL'

            temp_notes.append('{name: <16} - {time_d: <6}s: {status: <9}{message}'.format(
                name=module_name,
                status=module_report.module_status,
                message=f' - {module_report.message}' if module_report.message else '',
                time_d=time_diff(module_report.date)))

        # Update the status and notes
        self._status = temp_status
        self._notes = temp_notes

    def update_status(self):
        logger.debug(f"Consuming received status reports")
        while not self.status_channel.empty():
            self.add_module(self.status_channel.get())

        logger.debug(f"Processing {len(self.module_reports)} status reports")
        self.process_status()

    def get_status(self) -> tuple[str, list[str]]:
        self.update_status()
        return self._status, self._notes

    @staticmethod
    def send_status(channel: Queue, module_name: str, module_status: str, message: str = ''):
        channel.put(StatusReport(origin_module=module_name,
                                 module_status=module_status,
                                 message=message,
                                 date=datetime.now()))

    @classmethod
    def starting(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'STARTING', message)

    @classmethod
    def running(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'RUNNING', message)

    @classmethod
    def stopped(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'STOPPED', message)

    @classmethod
    def failing(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'FAILING', message)

    @classmethod
    def failed(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'FAILED', message)
