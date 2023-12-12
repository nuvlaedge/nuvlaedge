from queue import Queue
from unittest import TestCase
from unittest.mock import Mock, patch

from nuvlaedge.agent.workers.commissioner import Commissioner
from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.agent.orchestrator import COEClient


class TestCommissioner(TestCase):
    def setUp(self):
        self.mock_coe = Mock(spec=COEClient)
        self.mock_nuvla_client = Mock(spec=NuvlaClientWrapper)
        self.mock_queue = Mock(spec=Queue)

        self.test_commissioner = Commissioner(self.mock_coe, self.mock_nuvla_client, self.mock_queue)

    def test_build_nuvlaedge_endpoint(self):
        self.test_commissioner.coe_client.get_api_ip_port.return_value = 'address', 'port'





