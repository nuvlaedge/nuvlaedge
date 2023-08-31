from unittest import TestCase
from mock import Mock, patch

import nuvlaedge
from nuvlaedge import agent


class TestAgentMain(TestCase):

    def setUp(self) -> None:
        ...

    @patch.object(nuvlaedge.agent, 'parse_arguments_and_initialize_logging')
    @patch.object(nuvlaedge.agent, 'main')
    def test_entry(self, mock_main, mock_parser):
        agent.entry()
        mock_main.assert_called_once()
        mock_parser.assert_called_once()

    def test_preflight_check(self):
        ...

    def test_main(self):
        ...