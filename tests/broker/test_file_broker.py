import filelock

from datetime import datetime
from pathlib import Path

from unittest import TestCase
import mock

from nuvlaedge.broker.file_broker import FileBroker, MessageFormatError
from nuvlaedge.common.constants import DATETIME_FORMAT
from nuvlaedge.models.messages import NuvlaEdgeMessage


class TestFileBroker(TestCase):
    def setUp(self) -> None:
        self.test_broker: FileBroker = FileBroker(root_path='/tmp/common_tests/')

    def test_decode_message_from_file_name(self):

        # Test standard formatting without errors
        sample_date: str = datetime.now().strftime(DATETIME_FORMAT)
        sample_sender = 'sender'
        sample_name: str = f'{sample_date}_{sample_sender}.json'
        self.assertEqual(self.test_broker.decode_message_from_file_name(sample_name),
                         (datetime.strptime(sample_date, DATETIME_FORMAT), sample_sender),
                         'Failed')

        # Test regex comparison
        with self.assertRaises(MessageFormatError) as context:
            self.test_broker.decode_message_from_file_name('non')
            self.assertTrue('Filename non' in context.exception)

    @mock.patch('nuvlaedge.broker.file_broker.datetime')
    def test_compose_file_name(self, mock_datetime):
        dummy_date = datetime.now()
        mock_datetime.now.return_value = dummy_date
        sender = 'sender'
        self.assertEqual(self.test_broker.compose_file_name(sender),
                         f'{dummy_date.strftime(DATETIME_FORMAT)}_{sender}.json')

    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'iterdir')
    @mock.patch.object(Path, 'is_dir')
    @mock.patch.object(Path, 'unlink')
    def test_consume(self, mock_unlink, mock_dir, mock_iterdir, mock_exists):
        # Test non folder channel
        mock_dir.return_value = False
        self.assertEqual(self.test_broker.consume('my_file.txt'), [])

        # Test non existing channel
        mock_dir.return_value = True
        mock_exists.return_value = False
        self.assertEqual(self.test_broker.consume('myfolder'), [])

        # Test empty channel
        mock_exists.return_value = True
        mock_iterdir.return_value = []
        self.assertEqual(self.test_broker.consume('myfolder'), [])

        with mock.patch.object(filelock.FileLock, '__enter__'):
            with self.assertRaises(MessageFormatError):
                mock_iterdir.return_value = [Path('me')]
                self.test_broker.consume('myfolder')

            opener = mock.mock_open()

            def mocked_open(*args, **kwargs):
                return opener(*args, **kwargs)
            message_data = {'data': 'more_data'}
            with mock.patch.object(Path, 'open', mocked_open):
                with mock.patch("json.load", mock.MagicMock(side_effect=[message_data])):
                    mock_iterdir.return_value = [Path(FileBroker.compose_file_name('sender'))]
                    self.assertEqual(self.test_broker.consume('myfolder')[0].data, message_data)

                    mock_unlink.assert_called_once()

    @mock.patch.object(Path, 'mkdir')
    def test_create_channel(self, mock_mkdir):
        self.test_broker.create_channel(Path('channel'))
        mock_mkdir.assert_called_once()

    def test_publish_from_data(self):
        with mock.patch.object(FileBroker, 'publish_from_message') as mock_pub:
            mock_pub.return_value = True
            self.assertTrue(self.test_broker.publish_from_data(Path('channel'), {}, 'sender'))

            mock_pub.return_value = False
            self.assertFalse(self.test_broker.publish_from_data(Path('channel'), {}, 'sender'))

    def test_write_file(self):
        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.dump", mock.MagicMock()) as mock_dump:
                self.test_broker.write_file(Path('file'), {})
                mock_dump.assert_called_once()

    def test_publish_from_message(self):
        with mock.patch.object(FileBroker, 'write_file') as mock_write:
            self.assertTrue(self.test_broker.publish_from_message(Path('channel'),
                                                                  NuvlaEdgeMessage(sender='', data={})))
            mock_write.assert_called_once()

    @mock.patch.object(Path, 'exists')
    @mock.patch.object(Path, 'is_dir')
    def test_publish(self, mock_isdir, mock_exists):
        with mock.patch.object(FileBroker, 'create_channel'):
            mock_exists.return_value = False
            self.assertFalse(self.test_broker.publish('channel', {}, ''))

            mock_exists.return_value = True
            mock_isdir.return_value = False
            self.assertFalse(self.test_broker.publish('channel', {}, ''))

            mock_isdir.return_value = True
            with mock.patch.object(filelock.FileLock, '__enter__'):
                with self.assertRaises(ValueError):
                    self.test_broker.publish('channel', {}, '')

                with mock.patch.object(FileBroker, 'publish_from_data') as mock_from_data, \
                        mock.patch.object(FileBroker, 'publish_from_message') as mock_from_message:
                    mock_from_data.return_value = True
                    self.assertTrue(self.test_broker.publish('channel', {}, 'sender'))
                    mock_from_data.assert_called_once()
                    mock_from_message.assert_not_called()

                with mock.patch.object(FileBroker, 'publish_from_data') as mock_from_data, \
                        mock.patch.object(FileBroker, 'publish_from_message') as mock_from_message:
                    mock_from_message.return_value = True
                    self.assertTrue(self.test_broker.publish('channel',
                                                             NuvlaEdgeMessage(sender='', data={}),
                                                             ''))
                    mock_from_message.assert_called_once()
                    mock_from_data.assert_not_called()
