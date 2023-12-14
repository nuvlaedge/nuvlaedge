import logging
import random
import threading
import time
from datetime import datetime
from threading import Thread, Event
from typing import Callable, Type


logger: logging.Logger = logging.getLogger(__name__)
random.seed(datetime.now().strftime("%Y%m%d%H%M%S"))


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
                 initial_delay: float | None = None):
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
        self.period: int = period
        self.initial_delay: float = initial_delay if initial_delay else random.randint(4, 8)
        if self.initial_delay > self.period:
            self.initial_delay = self.period

        # Class init Parameters
        self.class_init_parameters: tuple[tuple, dict] = init_params

        # Worker attributes
        self.actions: list[str] = actions
        self.callable_actions: list[Callable[[], None]] = []
        self.worker_type: Type = worker_type
        self.worker: worker_type = self.worker_type(*init_params[0], **init_params[1])

        self.run_thread: Thread | None = None
        self.error_count: int = 0
        self.exceptions: list[Exception] = []
        self.init_actions()

    def init_actions(self):
        """
        Initializes the actions for the worker.

        This method iterates through the list of actions and gathers the corresponding callable functions from the worker.
        It adds the valid callable functions to the `callable_actions` list.

        Returns:
            None

        """
        for a in self.actions:
            c: Callable = getattr(self.worker, a)
            if not isinstance(c, Callable):
                logger.warning(f"Cannot gather function {a} from {self.worker_name}")
                continue
            self.callable_actions.append(c)

    def init_thread(self):
        """
            Initializes and starts a new thread to execute the `run` method.

            This method creates a new thread, sets it to run the `run` method of the current instance, and starts
             the thread. The thread is set as a daemon thread, meaning that it can be terminated when the main program exits.

            Parameters:
                self (object): The current instance.

            Returns:
                None
            """
        self.run_thread = threading.Thread(target=self.run, daemon=True)
        self.run_thread.start()

    def process_exception(self, ex: Exception, is_exit: bool = False):
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
            raise ExceptionGroup(f"Too many errors in {self.worker_name} worker", self.exceptions)

    def reset_worker(self, new_init_params: tuple[tuple, dict] = ()):
        """
        Resets the worker instance with new initialization parameters.

        Args:
            new_init_params (tuple[tuple, dict]): Optional. The new initialization parameters for the worker instance.

        """
        if new_init_params:
            self.class_init_parameters = new_init_params
        self.worker = self.worker_type(*self.class_init_parameters[0],
                                       **self.class_init_parameters[1])

    def run(self):
        """
        Generic worker infinite loop. It will run the actions in the worker class. If the action throws an exception,
        it will be caught and processed. If the exception is a WorkerExitException, it will be raised to the main.

        The execution period is controlled by the period attribute of the class. It is programmed to run every period
        seconds, resting the execution time from the period. If the execution time is greater than the period, it will
        automatically run the next iteration.

        Returns: None

        """
        logger.info(f"Entering main loop of {self.worker_name}")

        # Initially ex_time container the start delay of each worker. Computed here
        ex_time: float = float(self.period) - (float(self.period) - self.initial_delay)

        # Start loop of the worker
        while not self.exit_event.wait(self.period - ex_time):
            start_time = time.perf_counter()
            for action in self.callable_actions:
                try:
                    logger.debug(f"Running {action.__name__} from {self.worker_name}")
                    action()
                    logger.debug(f"Finished {action.__name__} from {self.worker_name}")
                except WorkerExitException as ex:
                    logger.warning(f"Worker {self.worker_name} exiting: {ex}")
                    self.process_exception(ex, is_exit=True)

                except Exception as ex:
                    logger.error(f"Error {ex.__class__.__name__} running action {action.__name__} on class "
                                 f"{self.worker_name}", exc_info=True, )
                    self.process_exception(ex)
                    self.init_thread()

            ex_time = time.perf_counter() - start_time
            logger.info(f"{self.worker_name} worker actions run  in {ex_time}s, next iteration in "
                        f"{self.period - ex_time}")

        logger.info(f"{self.worker_name} exiting loop...")

    def start(self):
        """
        Initializes the thread and starts the worker.

        This method should be called to start the worker thread.

        Returns:
            None

        Example:
            >>> worker = Worker()
            >>> worker.start()
            Worker thread started successfully

        Raises:
            None
        """
        self.init_thread()
        logger.info(f"{self.worker_name} worker started")

    def stop(self):
        """
        Stop method for stopping the execution of the run_thread.

        Returns: None

        """
        self.exit_event.set()
        self.run_thread.join(timeout=self.period)

