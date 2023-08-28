from unittest import TestCase
from mock import Mock, patch

from nuvlaedge.common.timed_actions import ActionHandler, TimedAction


def dummy_function():
    return '0'


class TestTimedAction(TestCase):

    def setUp(self) -> None:
        self.action = TimedAction(
            name='TestCase',
            period=4,
            action=dummy_function
        )

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

    def test_gt_lt(self):
        dummy_action = TimedAction(
            name='Dummy',
            period=4,
            action=dummy_function,
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
                remaining_time=3),
            TimedAction(
                name='TestCase2',
                period=2,
                action=self.mock_callable_bis,
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
