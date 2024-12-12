import logging
import os
from datetime import datetime, timedelta
from queue import Queue
from typing import Literal

from pydantic import BaseModel

from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.file_operations import read_file
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class StatusReport(BaseModel):
    origin_module: str
    module_status: Literal['STARTING', 'RUNNING', 'STOPPED', 'WARNING', 'FAILING', 'FAILED', 'UNKNOWN']
    date: datetime
    message: str = ''


class NuvlaEdgeStatusHandler:
    STATUS_TIMEOUT: int = 60*60

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

        if module_name in self.module_reports:
            self.module_reports.pop(module_name)

    def process_status(self):
        temp_status = 'UNKNOWN'
        temp_notes = []

        def time_diff(date: datetime) -> int:
            diff: float = datetime.now().timestamp() - date.timestamp()
            return int(diff)

        to_remove = [name for name, report in self.module_reports.items() if time_diff(report.date) > self.STATUS_TIMEOUT]
        logger.debug(f"Removing modules that have not reported in the last {self.STATUS_TIMEOUT} minutes: {', '.join(to_remove)}")
        for name in to_remove:
            self.module_reports.pop(name)

        for module_name, module_report in self.module_reports.items():

            logger.debug(f"Processing module {module_report}")

            if module_report.module_status in ['FAILING', 'FAILED']:
                logger.debug(f"Module {module_name} is in STOPPED, FAILING or FAILED")
                temp_status = 'DEGRADED'

            if module_report.module_status in ['STOPPED', 'STARTING', 'RUNNING'] and temp_status != 'DEGRADED':
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
        logger.debug("Consuming received status reports")
        while not self.status_channel.empty():
            self.add_module(self.status_channel.get())

        logger.debug(f"Processing {len(self.module_reports)} status reports")
        self.process_status()

    def _get_coe_status(self, coe_client: COEClient) -> None:
        _coe_errors, _ = coe_client.read_system_issues(coe_client.get_node_info())
        if _coe_errors:
            err_msg = "\n".join(_coe_errors)
            logger.warning(f"COE is reporting errors: {err_msg}")
            self.status_channel.put(StatusReport(origin_module='COE',
                                                 module_status='FAILING',
                                                 message=err_msg,
                                                 date=datetime.now()))

    def _get_system_manager_status(self) -> None:
        """
        System Manager is expected to report its status into two files:
         - .status: containing the status of the System Manager
         - .status_notes: containing the notes of the System Manager

        This method reads the content of these files and updates the status and notes of the System Manager
        Returns: None. Status is reported via the status_channel for consistency

        """
        sm_module_name = "System Manager"
        sm_enabled = os.getenv("NUVLAEDGE_SYSTEM_MANAGER_ENABLE", 0)
        if not sm_enabled or not isinstance(sm_enabled, int) or sm_enabled < 1:
            if sm_module_name in self.module_reports:
                self.remove_module(sm_module_name)
            return

        _status: str = read_file(FILE_NAMES.STATUS_FILE)
        # Notes from the System Manager are supposed to already be a multiline string with \n separators
        _notes: str = read_file(FILE_NAMES.STATUS_NOTES)

        match _status:
            case "OPERATIONAL":
                _module_status = "RUNNING"
            case "DEGRADED":
                _module_status = "FAILING"
            case _:
                _module_status = "UNKNOWN"
        logger.debug(f"System Manager status: {_module_status} - {_notes}")
        self.status_channel.put(StatusReport(origin_module=sm_module_name,
                                             module_status=_module_status,
                                             message=_notes if _notes is not None else '',
                                             date=datetime.now()))

    def get_status(self, coe_client: COEClient) -> tuple[str, list[str]]:
        self._get_coe_status(coe_client)
        self._get_system_manager_status()

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

    @classmethod
    def warning(cls, channel: Queue, module_name: str, message: str = ''):
        cls.send_status(channel, module_name, 'WARNING', message)