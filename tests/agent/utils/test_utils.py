from mock import Mock, patch, mock_open
import unittest

from nuvlaedge.agent.common.util import execute_cmd


class TestUtils(unittest.TestCase):

    def test_execute_cmd(self):
        with patch('nuvlaedge.agent.common.util.run') as mock_run:
            # Test Selection flag
            execute_cmd(['some'], method_flag=True)
            mock_run.assert_called_once()

        with patch('nuvlaedge.agent.common.util.Popen') as mock_run:
            mock_run.return_value.__enter__.return_value.communicate.return_value = \
                ('Out', 'NoError')
            mock_run.return_value.__enter__.return_value.returncode = 0
            execute_cmd(['some'], method_flag=False)
            mock_run.assert_called_once()

            expected_return = {'stdout': 'Out',
                               'stderr': 'NoError',
                               'returncode': 0}
            self.assertEqual(execute_cmd(['some'], method_flag=False), expected_return)
