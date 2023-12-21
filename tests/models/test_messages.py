from pathlib import Path

from unittest import TestCase
from pydantic import ValidationError

import mock
import sys
print(f'\n\n\n {sys.version}\n\n\n')

from nuvlaedge.models.messages import parse_message, NuvlaEdgeMessage


class TestUtils(TestCase):

    @mock.patch('nuvlaedge.models.messages.read_file')
    def test_parse_messages(self, mock_read):
        mock_read.side_effect = [None]
        self.assertIsNone(parse_message('non_existing_location'))
        mock_read.reset_mock(side_effect=True)

        message_data = {
            'sender': 'sender',
            'data': {},
        }
        mock_read.side_effect = [message_data]
        self.assertEqual(NuvlaEdgeMessage.model_validate(message_data), parse_message('exists_location'))
