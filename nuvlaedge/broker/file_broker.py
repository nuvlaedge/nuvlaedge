import json
import logging
import re
from pathlib import Path
from datetime import datetime

import filelock

from nuvlaedge.models.messages import NuvlaEdgeMessage
from nuvlaedge.broker import NuvlaEdgeBroker
from nuvlaedge.common.constants import CTE
from nuvlaedge.common.constant_files import FILE_NAMES


class MessageFormatError(Exception):
    ...


class FileBroker(NuvlaEdgeBroker):
    FILE_PATTERN = '[a-zA-Z0-9]*_[a-zA-Z0-9]*.json$'
    BUFFER_NAME = 'buffer'

    def __init__(self, root_path: str = FILE_NAMES.root_fs):
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

        self.root_path: Path = Path(root_path)
        self.logger.warning(f'Root path {self.root_path}')

    def decode_message_from_file_name(self, file_name):
        if not re.match(self.FILE_PATTERN, file_name):
            raise MessageFormatError(f'Filename {file_name} not following the message '
                                     f'pattern {self.FILE_PATTERN}')

        file_name = file_name.replace('.json', '')
        message: list = file_name.split('_')

        return datetime.strptime(message[0], CTE.DATETIME_FORMAT), message[1]

    @staticmethod
    def compose_file_name(sender):
        str_now = datetime.now().strftime(CTE.DATETIME_FORMAT)
        file_name = f'{str_now}_{sender}.json'
        return file_name

    def consume(self, channel: str) -> list[NuvlaEdgeMessage]:

        channel = self.root_path / Path(channel)
        self.logger.debug(f'Consuming from channel {channel}')
        if not channel.is_dir():
            self.logger.warning(f'Channel {channel} is not a directory')
            return []

        if not channel.exists():
            self.logger.warning(f'No channel registered as {channel}')
            return []

        if not any(channel.iterdir()):
            return []

        # Lock the channel to prevent overlapping
        with filelock.FileLock(channel / (channel.name + '.lock')):

            channel = channel / self.BUFFER_NAME
            messages: list = []

            for message in channel.iterdir():
                self.logger.debug(f'Message {message.name}')
                message_time, sender = self.decode_message_from_file_name(message.name)

                with message.open(mode='r') as file:
                    messages.append(NuvlaEdgeMessage(
                        data=json.load(file),
                        sender=sender,
                        time=message_time
                    ))
                message.unlink()

            return messages

    def create_channel(self, channel: Path):
        """

        :param channel:
        :return:
        """
        channel_buffer: Path = channel / self.BUFFER_NAME
        channel_buffer.mkdir(exist_ok=True, parents=True)

    def publish_from_data(self, channel: Path, data: dict, sender: str) -> bool:
        return self.publish_from_message(
            channel,
            NuvlaEdgeMessage(
                sender=sender,
                data=data
            )
        )

    @staticmethod
    def write_file(file_name: Path, data: dict):
        with file_name.open('w') as file:
            json.dump(data, file)

    def publish_from_message(self, channel: Path, message: NuvlaEdgeMessage) -> bool:
        self.logger.info(f'Writing message to {channel / self.BUFFER_NAME / self.compose_file_name(message.sender)}')
        self.write_file(
            channel / self.BUFFER_NAME / self.compose_file_name(message.sender),
            message.data
        )
        return True

    def publish(self, channel: str, data: dict | NuvlaEdgeMessage, sender: str = '') -> bool:

        channel = self.root_path / Path(channel)
        self.create_channel(channel)

        if not channel.exists():
            self.logger.warning(f'Folder {channel} does not exists and cannot be used as a channel, create it First')
            return False

        if not channel.is_dir():
            self.logger.warning(f'Channel {channel} is not a directory')
            return False

        self.logger.debug(f'Publishing from {sender} towards channel {channel}')
        with filelock.FileLock(channel / (channel.name + '.lock')):
            if isinstance(data, dict):
                if not sender:
                    raise ValueError('Sender must be assigned when publishing from a dictionary')
                return self.publish_from_data(channel, data, sender)

            else:
                return self.publish_from_message(channel, data)
        return False
