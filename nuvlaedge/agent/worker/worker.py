import logging
import pprint
import threading
import time
from threading import Thread, Event
from typing import Callable, Type


logger: logging.Logger = logging.getLogger(__name__)

class WorkerExitException(Exception):
    """ Triggered by the workers when they cannot run due to system configuration changes and want to force and exit """


class AgentWorker:

    def __init__(self,
                 period: int,
                 worker_type: Type,
                 init_params: tuple[tuple, dict],
                 actions: list[str]):
        super().__init__(daemon=True)
        self.worker_name: str = worker_type.__name__

        # Thread control
        self.exit_event: Event = Event()
        self.period: int = period

        # Class init Parameters
        self.class_init_parameters: tuple[tuple, dict] = init_params

        # Worker attributes
        self.actions: list[str] = actions
        self.callable_actions: list[Callable[[], None]] = []
        self.worker_type: Type = worker_type
        self.worker: worker_type = self.worker_type(*init_params[0], **init_params[1])

        self.run_thread: Thread = ...
        self.error_count: int = 0
        self.exceptions: list[Exception] = []

    def init_actions(self):

        for a in self.actions:
            c: Callable = getattr(self.worker, a)
            if not isinstance(c, Callable):
                logger.warning(f"Cannot gather function {a} from {self.worker_name}")
                continue
            self.callable_actions.append(c)

    def init_thread(self):
        self.run_thread = threading.Thread(target=self.run, daemon=True)
        self.run_thread.start()

    def process_exception(self, ex: Exception, is_exit: bool = False):
        self.error_count += 1
        self.exceptions.append(ex)
        if ex and is_exit:
            raise ExceptionGroup(f"Exit requested from worker {self.worker_name}, raising all",
                                 __exceptions=self.exceptions)

        if self.error_count > 10:
            raise ExceptionGroup(f"Too many errors in {self.worker_name} worker",
                                 __exceptions=self.exceptions)

    def reset_worker(self, new_init_params: tuple[tuple, dict] = ()):
        if new_init_params:
            self.class_init_parameters = new_init_params
        self.worker = self.worker_type(*self.class_init_parameters[0],
                                       **self.class_init_parameters[1])

    def run(self):
        ex_time: float = float(self.period)

        while not self.exit_event.wait(self.period - ex_time):
            start_time = time.perf_counter()
            for action in self.callable_actions:
                try:
                    action()
                except WorkerExitException as ex:
                    logger.warning(f"Worker {self.worker_name} exiting: {ex}")
                    self.process_exception(ex, is_exit=True)

                except Exception as ex:
                    logger.error(f"Error {ex.__class__.__name__} running action {action.__name__} on class")
                    self.process_exception(ex)
                    self.init_thread()

            ex_time = time.perf_counter() - start_time
            logger.info(f"{self.worker_name} worker actions run  in {ex_time}s")

    def start(self):
        self.init_thread()
        logger.info(f"{self.worker_name} worker started")

    def stop(self):
        self.exit_event.set()
        logging.info(f"Waiting {self.period} for running worker {self.worker_name} to finish")
        self.run_thread.join(timeout=self.period)

