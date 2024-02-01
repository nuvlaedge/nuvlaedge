import logging
import threading
import time
from threading import Thread, Event
from typing import Callable, Type

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class WorkerExitException(Exception):
    """ Triggered by the workers when they cannot run due to system configuration changes and want to force and exit """


class Worker:
    """
    Worker class. The constructor receives the following parameters:
        - period: int, the period of execution of the worker
        - worker_type: Type, the class of the worker
        - init_params: tuple, the parameters to initialize the worker class
        - actions: list, the list of actions to run in the worker class

    The worker is a wrapper that will run the actions of the worker type class in a thead. The period of execution is
    defined by the period parameter. The worker will run the actions every period seconds.
    """
    def __init__(self,
                 period: int,
                 worker_type: Type,
                 init_params: tuple[tuple, dict],
                 actions: list[str],
                 initial_delay: float = 0.0):
        """
        Initializes an instance of the class.

        Args:
            period (int): The time interval (in seconds) between each execution of the worker's actions.
            worker_type (Type): The type of the worker. Must be a subclass of `Worker`.
            init_params (tuple[tuple, dict]): The initialization parameters to pass to the worker's constructor.
                The first element of the tuple is a tuple of arguments, and the second element is a dictionary of keyword arguments.
            actions (list[str]): The list of action names that the worker will perform.
            initial_delay (float | None): The initial delay (in seconds) before the worker starts executing actions.
                If not provided, a random delay between 4 and 8 seconds will be used.

        """
        self.worker_name: str = worker_type.__name__

        # Thread control
        self.exit_event: Event = Event()
        self._period: int = period

        # Here we initialise the variables so that the first execution aligned with the desired initial delay
        self._exec_start_time: float = 0.0
        self._exec_finish_time: float = 0.0
        self._initial_delay: float = initial_delay

        # Class init Parameters
        self.class_init_parameters: tuple[tuple, dict] = init_params

        # Worker attributes
        self.actions: list[str] = actions
        self.callable_actions: list[Callable[[], None]] = []
        self.worker_type: Type = worker_type
        self.worker_instance: worker_type = self.worker_type(*init_params[0], **init_params[1])

        self.run_thread: Thread | None = None
        self.error_count: int = 0
        self.exceptions: list[Exception] = []
        self._init_actions()

    @property
    def remaining_time(self) -> float:
        """
        Returns the remaining time for the next execution of the worker's actions.

        Returns:
            float: The remaining time in seconds.
        """
        return (self._exec_finish_time + self._period - self.last_execution_duration) - time.time()

    @property
    def last_execution_duration(self) -> float:
        """
        Returns the time it took to execute the worker's actions.

        Returns:
            float: The execution time in seconds.
        """
        return self._exec_finish_time - self._exec_start_time

    @property
    def is_running(self) -> bool:
        """
        Returns whether the worker is currently running.

        Returns:
            bool: True if the worker is running, False otherwise.
        """

        return (self.run_thread is not None and
                self.run_thread.ident is not None and
                self.run_thread.is_alive())

    def _init_actions(self):
        """
        Initializes the actions for the worker.

        This method iterates through the list of actions and gathers the corresponding callable functions from the worker.
        It adds the valid callable functions to the `callable_actions` list.

        Returns:
            None

        """
        for a in self.actions:
            c: Callable = getattr(self.worker_instance, a)
            if not isinstance(c, Callable):
                logger.warning(f"Cannot gather function {a} from {self.worker_name}")
                continue
            self.callable_actions.append(c)

    def _init_thread(self):
        """ Initializes the worker thread and starts it.

        This method creates a new thread for the worker and sets it to daemon mode.
        The target of the thread is the `run` method of the worker.
        After initializing the thread, it immediately starts it.
        """
        self.run_thread = threading.Thread(target=self.run, daemon=True)
        self.run_thread.start()

    def _process_exception(self, ex: Exception, is_exit: bool = False):
        """
        Process an exception that occurred during the worker's execution.

        Args:
            ex (Exception): The exception that occurred.
            is_exit (bool, optional): Flag indicating whether an exit is requested. Defaults to False.

        Raises:
            ExceptionGroup: If an exit is requested and there are exceptions, raise an ExceptionGroup.
            ExceptionGroup: If there are more than 10 errors, raise an ExceptionGroup.
        """
        self.error_count += 1
        self.exceptions.append(ex)
        if ex and is_exit:
            raise ExceptionGroup(f"Exit requested from worker {self.worker_name}, raising all", self.exceptions)

        if self.error_count > 10:
            logger.error(f"Error limit reached in {self.worker_name} worker, raising all")
            for e in self.exceptions:
                logger.exception(e)
            raise ExceptionGroup(f"Too many errors in {self.worker_name} worker", self.exceptions)

    def reset_worker(self, new_init_params: tuple[tuple, dict] = ()):
        """
        Resets the worker instance with new initialization parameters.

        Args:
            new_init_params (tuple[tuple, dict]): Optional. The new initialization parameters for the worker instance.

        """
        if new_init_params:
            self.class_init_parameters = new_init_params
        self.worker_instance = self.worker_type(*self.class_init_parameters[0],
                                                **self.class_init_parameters[1])

    def edit_period(self, new_period: int):
        """
        Edits the period of the worker.

        Args:
            new_period (int): The new period of execution for the worker.

        """
        self._period = new_period

    def run(self):
        """
        Generic worker infinite loop. It will run the actions in the worker class. If the action throws an exception,
        it will be caught and processed. If the exception is a WorkerExitException, it will be raised to the main.

        The execution period is controlled by the period attribute of the class. It is programmed to run every period
        seconds, resting the execution time from the period. If the execution time is greater than the period, it will
        automatically run the next iteration.

        Returns: None

        """
        logger.info(f"Starting {self.worker_name} worker")

        _wait_time: float = self._initial_delay
        self._initial_delay = -1.0
        logger.debug(f"Initial delay for {self.worker_name} is {_wait_time}s")

        # Start loop of the worker
        while not self.exit_event.wait(_wait_time):
            # Register the time at the start of the execution
            self._exec_start_time = time.time()
            for action in self.callable_actions:
                try:
                    logger.debug(f"Running {action.__name__} from {self.worker_name}...")
                    action()
                    logger.debug(f"Running {action.__name__} from {self.worker_name}... Success")

                # Catch the exception that allows workers to exit themselves
                except WorkerExitException as ex:
                    logger.warning(f"Worker {self.worker_name} exiting: {ex}")
                    self._process_exception(ex, is_exit=True)

                # Catch all other exceptions and store them
                except Exception as ex:
                    logger.error(f"Error {ex.__class__.__name__} running action {action.__name__} on class "
                                 f"{self.worker_name}", exc_info=True, )
                    self._process_exception(ex)

            # Store the time of the end of the execution
            self._exec_finish_time = time.time()
            logger.debug(f"{self.worker_name} worker actions run  in {self._exec_finish_time-self._exec_start_time}s,"
                         f" next iteration in {self.remaining_time}s")
            _wait_time = self.remaining_time

        logger.warning(f"{self.worker_name} exiting loop...")

    def worker_summary(self) -> str:
        """ Returns a formatted status report for the worker. """
        return (f'{self.worker_name:<20} {self._period:>10} {self.remaining_time:>10.2f} {self.error_count:>10} '
                f'{" ".join([e.__class__.__name__ for e in self.exceptions]):>25}\n')

    def start(self):
        """ Initializes the thread and starts the worker.

        This method should be called to start the worker thread.
        """
        self._init_thread()
        logger.debug(f"{self.worker_name} worker started")

    def stop(self):
        """ Stop method for stopping the execution of the run_thread. """
        self.exit_event.set()
        self.run_thread.join(timeout=self._period)

