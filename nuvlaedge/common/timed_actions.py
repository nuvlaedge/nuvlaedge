import datetime
import logging
import time
import uuid
from dataclasses import dataclass


logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class TimedAction:
    name: str
    action: callable
    period: int
    remaining_time: float = 0  # Allow configurability for delayed starts
    uuid: str = uuid.uuid4()

    def __call__(self, *args, **kwargs):
        if self.remaining_time > 0:
            logger.debug(f'Action {self.name} not ready, time remaining: '
                         f'{self.remaining_time}s')
            return
        ret = self.action(*args, **kwargs)
        self.remaining_time = self.period
        return ret

    def update_action(self, elapsed_time: float):
        self.remaining_time = self.remaining_time - elapsed_time

    def __gt__(self, other):
        return self.remaining_time > other.remaining_time

    def __lt__(self, other):
        return self.remaining_time < other.remaining_time


class ActionHandler:

    def __init__(self, actions: list[TimedAction]):
        self._actions: list[TimedAction] = actions
        self.accessed_time: float = time.time()

    @property
    def actions(self) -> list:
        temp_time = time.time()
        self._update(temp_time - self.accessed_time)
        self.accessed_time = temp_time
        self._actions = sorted(self._actions)
        return self._actions

    def add(self, action: TimedAction):
        self.actions.append(action)

    @property
    def next(self) -> TimedAction:
        try:
            return self.actions[0]
        except IndexError:
            raise StopIteration('No Actions registered')

    def sleep_time(self) -> float:
        try:
            next_sleep = self.actions[0].remaining_time
            return next_sleep if next_sleep >= 0 else 0
        except IndexError:
            raise StopIteration('No Actions registered')

    def _update(self, elapsed_time: float):
        [e.update_action(elapsed_time) for e in self._actions]

    def edit_period(self, action_id: str, new_period: int):
        for e in self._actions:
            if e.uuid == action_id or e.name == action_id:
                e.period = new_period
