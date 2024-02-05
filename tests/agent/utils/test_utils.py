import signal
from subprocess import SubprocessError, TimeoutExpired

from mock import Mock, patch, mock_open
import unittest

from nuvlaedge.agent.common.util import execute_cmd, extract_nuvlaedge_version, str_if_value_or_none, raise_timeout, \
    timeout


class TestUtils(unittest.TestCase):

    @patch('nuvlaedge.agent.common.util.logging.Logger.error')
    def test_execute_cmd(self, mock_error):
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

        # Test OSError
        with patch('nuvlaedge.agent.common.util.run') as mock_run:
            mock_run.side_effect = OSError('mock_exception')
            self.assertEqual(execute_cmd(['some'], method_flag=True), None)
            mock_error.assert_called_once_with('Trying to execute non existent file: mock_exception')
            mock_error.reset_mock()

        # Test ValueError
        with patch('nuvlaedge.agent.common.util.run') as mock_run:
            mock_run.side_effect = ValueError('value_exception')
            self.assertEqual(execute_cmd(['some'], method_flag=True), None)
            mock_error.assert_called_once_with('Invalid arguments executed: value_exception')
            mock_error.reset_mock()

        # Test TimeoutExpired
        with patch('nuvlaedge.agent.common.util.run') as mock_run:
            mock_run.side_effect = TimeoutExpired('time_exception', 0.1)
            self.assertEqual(execute_cmd(['some'], method_flag=True), None)
            mock_error.assert_called_once_with("Timeout Command 'time_exception' timed out after 0.1 seconds "
                                               "expired waiting for command: ['some']")
            mock_error.reset_mock()

        # Test SubprocessError
        with patch('nuvlaedge.agent.common.util.run') as mock_run:
            mock_run.side_effect = SubprocessError('mock_exception')
            self.assertEqual(execute_cmd(['some'], method_flag=True), None)
            mock_error.assert_called_once_with("Exception not identified: mock_exception")
            mock_error.reset_mock()

    def test_extract_nuvlaedge_version(self):
        # Test with correct image name
        self.assertEqual('latest', extract_nuvlaedge_version('nuvlaedge:latest'))

        # Test with incorrect image name
        self.assertEqual('nuvlaedge', extract_nuvlaedge_version('nuvlaedge'))

        # Test with incorrect image name and pkg_resources error
        with patch('nuvlaedge.agent.common.util.pkg_resources.get_distribution') as mock_pkg:
            with patch('nuvlaedge.agent.common.util.logging.Logger.warning') as mock_warning:
                mock_pkg.side_effect = Exception('mock_exception')
                self.assertEqual('', extract_nuvlaedge_version([None]))
                mock_warning.assert_called_once_with('Cannot retrieve NuvlaEdge version', exc_info=mock_pkg.side_effect)

    def test_str_if_value_or_none(self):
        self.assertEqual(None, str_if_value_or_none(None))
        self.assertEqual('test', str_if_value_or_none('test'))

    def test_raise_timeout(self):
        with self.assertRaises(TimeoutError):
            raise_timeout(0, 0)

    @patch('nuvlaedge.agent.common.util.signal.signal')
    def test_timeout(self, mock_signal):
        with timeout(5):
            mock_signal.assert_called_with(signal.SIGALRM, raise_timeout)

        with timeout(5):
            pass
        mock_signal.assert_called_with(signal.SIGALRM, signal.SIG_IGN)
