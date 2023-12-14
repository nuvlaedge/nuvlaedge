import logging
from typing import Type

from nuvlaedge.agent.worker import Worker


logger: logging.Logger = logging.getLogger(__name__)


class WorkerManager:
    """
    Class WorkerManager manages a collection of worker instances.

    Attributes:
        registered_workers (dict[str, Worker]): A dictionary containing registered worker instances.

    Methods:
        add_worker(period: int, worker_type: Type, init_params: tuple[tuple, dict], actions: list[str],
                   initial_delay: float | None = None) -> None:
            Adds a worker to the manager's collection of registered workers.

            Args:
                period (int): The interval between each execution of the worker's actions.
                worker_type (Type): The type of worker to be added.
                init_params (tuple[tuple, dict]): The parameters required to initialize the worker.
                actions (list[str]): The list of actions to be performed by the worker.
                initial_delay (float | None): The optional initial delay before starting the worker. Defaults to None.

        status_report() -> dict:
            Generates and returns a report on the status of the registered workers.

            Returns:
                dict: A dictionary containing the status report of each worker.

        start() -> None:
            Starts all the registered workers.

        stop() -> None:
            Stops all the registered workers.
    """
    def __init__(self):
        self.registered_workers: dict[str, Worker] = {}

    def add_worker(self,
                   period: int,
                   worker_type: Type,
                   init_params: tuple[tuple, dict],
                   actions: list[str],
                   initial_delay: float | None = None) -> bool:
        """
        Adds a worker to the manager.

        Args:
            period (int): The time period in seconds at which the worker will execute its actions.
            worker_type (Type): The class of the worker to be added.
            init_params (tuple[tuple, dict]): The initialization parameters required to create an instance of the worker class.
            actions (list[str]): The list of actions that the worker will perform.
            initial_delay (float | None, optional): An optional initial delay in seconds before the worker starts performing actions. Defaults to None.
        """
        if worker_type.__class__.__name__ not in self.registered_workers:
            logger.info(f"Registering worker: {worker_type.__name__} in manager")
            self.registered_workers[worker_type.__name__] = (
                Worker(period=period,
                       worker_type=worker_type,
                       init_params=init_params,
                       actions=actions,
                       initial_delay=initial_delay)
            )
            return True
        else:
            logger.info(f"Worker {worker_type.__name__} already registered")
            return False

    def status_report(self):
        """
        Returns a formatted status report for each registered worker.

        The status report includes the total number of errors and the list of error types for each worker.

        """
        for name, worker in self.registered_workers.items():
            logger.info(f"Worker {name} errors: \n"
                        f"\t Total errors: {worker.error_count} \n"
                        f"\t Error types: {[e.__class__.__name__ for e in worker.exceptions]}")

    def start(self):
        """
        Starts all registered workers.

        This method iterates over the `registered_workers` dictionary and starts each worker.

        """
        for name, worker in self.registered_workers.items():
            logger.info(f"Starting {name} worker...")
            worker.start()

    def stop(self):
        """
        Stops all the registered workers.

        """
        for name, worker in self.registered_workers.items():
            logger.info(f"Stopping {name} worker...")
            worker.stop()
