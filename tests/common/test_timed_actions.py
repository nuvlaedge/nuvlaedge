from unittest import TestCase
from mock import Mock, patch

from nuvlaedge.agent.common.util import timeout
from nuvlaedge.common.timed_actions import ActionHandler, TimedAction


def dummy_function(*args, **kwargs):
    if not args and not kwargs:
        return '0'
    else:
        return f'{args} {kwargs}'


class TestTimedAction(TestCase):

    def setUp(self) -> None:
        self.action = TimedAction(
            name='TestCase',
            period=4,
            action=dummy_function,
            timeout=2,
        )

    def test_execute_action(self):
        def raise_function():
            raise ValueError("Dummy value Error")
        # Test infinite retries
        self.action.action = raise_function
        self.action.max_tries = -1
        self.assertIsNone(self.action._execute_action())
        self.assertEqual(len(self.action.exceptions), 0)

        # Test No retries
        with self.assertRaises(ExceptionGroup):
            self.action.tries = 0
            self.action.max_tries = 0
            self.action._execute_action()

        # Test Default tries
        self.action.tries = 0
        self.action.max_tries = 3
        with self.assertRaises(ExceptionGroup):
            _ = [self.action._execute_action() for i in range(3)]
            self.assertEqual(len(self.action.exceptions), 3)

    def test_update_action(self):
        self.action.remaining_time = 3
        self.action.update_action(2)
        self.assertEqual(1, self.action.remaining_time)

    def test_call(self):
        self.action.remaining_time = 1
        self.assertIsNone(self.action())

        self.action.remaining_time = 0
        self.assertEqual('0', self.action())
        self.assertEqual(self.action.remaining_time, self.action.period)

        self.action.args = [1, 2, 3]
        self.action.kwargs = {'a': 1, 'b': 2}
        self.action.remaining_time = 0
        self.assertEqual("(1, 2, 3) {'a': 1, 'b': 2}", self.action())

    def test_gt_lt(self):
        dummy_action = TimedAction(
            name='Dummy',
            period=4,
            action=dummy_function,
            timeout=2,
            remaining_time=5
        )
        self.assertFalse(self.action > dummy_action)
        self.assertTrue(self.action < dummy_action)

        self.action.remaining_time = 10
        self.assertTrue(self.action > dummy_action)
        self.assertFalse(self.action < dummy_action)


class TestActionHandler(TestCase):

    def setUp(self) -> None:
        self.mock_callable = Mock()
        self.mock_callable.return_value = '1'
        self.mock_callable_bis = Mock()
        self.mock_callable_bis.return_value = '2'
        self.actions_sample = [
            TimedAction(
                name='TestCase',
                period=4,
                action=self.mock_callable,
                timeout=5,
                remaining_time=3),
            TimedAction(
                name='TestCase2',
                period=2,
                action=self.mock_callable_bis,
                timeout=1,
                remaining_time=1)
        ]
        self.handler = ActionHandler(actions=self.actions_sample)

    @patch.object(ActionHandler, '_update')
    @patch('nuvlaedge.common.timed_actions.time')
    def test_actions(self, mock_time, mock_update):
        mock_time.time.return_value = 0
        self.assertEqual([self.actions_sample[1],
                          self.actions_sample[0]],
                         self.handler.actions)
        self.assertEqual(0, self.handler.accessed_time)
        mock_update.assert_called_once()

    def test_add(self):
        dummy_action = TimedAction(
            name='TestCase3',
            period=2,
            action=dummy_function,
            timeout=1,
            remaining_time=1)
        self.handler.add(dummy_action)
        self.assertEqual(3, len(self.handler.actions))

    @patch('nuvlaedge.common.timed_actions.time')
    def test_sleep_time(self, mock_time):
        mock_time.time.return_value = 0
        self.handler.accessed_time = 0
        self.assertEqual(1, self.handler.sleep_time())

        self.handler = ActionHandler([])
        with self.assertRaises(StopIteration):
            self.handler.sleep_time()

    def test_next(self):
        self.assertEqual('2', self.handler.next.action())
        self.mock_callable_bis.assert_called_once()

        self.handler = ActionHandler([])
        with self.assertRaises(StopIteration):
            self.handler.next.action()

    def test_edit_period(self):
        self.handler.edit_period('TestCase', new_period=5)
        self.assertEqual(5, self.handler.actions[1].period)

    def test_actions_summary(self):
        self.assertTrue(len(self.handler.actions_summary().splitlines()) == 4)

    @patch('nuvlaedge.common.timed_actions.logger')
    def test_action_finished(self, mock_logger):
        # Arrange
        last_action = TimedAction(
            name='TestCase2',
            period=2,
            action=self.mock_callable_bis,
            timeout=1,
            remaining_time=1
        )

        # ensure actions are sorted so 'TestCase2' is first
        self.handler._actions = [
            TimedAction(
                name='TestCase',
                period=4,
                action=self.mock_callable,
                timeout=5,
                remaining_time=3),
            last_action
        ]

        # Act
        returned_sleep_time = self.handler.action_finished(1.23, last_action)

        # Assert
        self.assertAlmostEqual(returned_sleep_time, 1.0, places=2)
        self.assertIn("Action TestCase2 completed in 1.23 seconds",
                      [call.args[0] for call in mock_logger.debug.call_args_list])
        self.assertIn("Next action TestCase2 will be run in 1.00 seconds",
                      [call.args[0] for call in mock_logger.info.call_args_list])
