from pathlib import Path

from unittest import TestCase
from pydantic import ValidationError

import mock
import sys
print(f'\n\n\n {sys.version}\n\n\n')

from nuvlaedge.models.messages import parse_message, NuvlaEdgeMessage


class TestUtils(TestCase):

    @mock.patch.object(Path, 'exists')
    def test_parse_messages(self, mock_exists):
        mock_exists.return_value = False
        with self.assertRaises(FileExistsError):
            parse_message('non_existing_location')

        mock_exists.return_value = True

        opener = mock.mock_open()

        def mocked_open(*args, **kwargs):
            return opener(*args, **kwargs)

        message_data = {'data': 'more_data'}
        with mock.patch.object(Path, 'open', mocked_open):
            with mock.patch("json.load", mock.MagicMock(side_effect=[message_data])):
                with self.assertRaises(ValidationError):
                    parse_message('exists_location')

                message_data = {
                    'sender': 'sender',
                    'data': {},
                }
            with mock.patch("json.load", mock.MagicMock(side_effect=[message_data])):
                self.assertEqual(NuvlaEdgeMessage.model_validate(message_data), parse_message('exists_location'))
