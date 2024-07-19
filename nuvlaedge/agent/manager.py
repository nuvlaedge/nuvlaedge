import logging
from typing import Type

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.agent.worker import Worker


logger: logging.Logger = get_nuvlaedge_logger(__name__)


class WorkerManager:
    """
    Class WorkerManager manages a collection of worker instances.

    Attributes:
        registered_workers (dict[str, Worker]): A dictionary containing registered worker instances.
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

        if worker_type.__class__.__name__ not in self.registered_workers.keys():
            logger.debug(f"Registering worker: {worker_type.__name__} in manager")
            self.registered_workers[worker_type.__name__] = (
                Worker(period=period,
                       worker_type=worker_type,
                       init_params=init_params,
                       actions=actions,
                       initial_delay=initial_delay)
            )
            return True
        else:
            logger.warning(f"Worker {worker_type.__name__} already registered")
            return False

    def heal_workers(self):
        """
        Iterates over the registered workers and restarts any worker that is not running.
        """
        for _, worker in self.registered_workers.items():
            if not worker.is_running:
                logger.info(f"Worker {worker.worker_name} is not running, restarting...")
                # Should we recreate the worker class or just the threads
                worker.reset_worker(start=True)

    def summary(self) -> str:
        """
        Returns a formatted status report for each registered worker.

        The status report includes the total number of errors and the list of error types for each worker.

        """
        _summary: str = (f'Worker Summary:\n{"Name":<20} {"Period":>10} {"Rem. Time":>10} {"Err. Count":>10}'
                         f' {"Errors":>25}\n')

        for _, worker in self.registered_workers.items():
            _summary += worker.worker_summary()

        return _summary

    def start(self):
        """
        Starts all registered workers.

        This method iterates over the `registered_workers` dictionary and starts each worker.

        """
        for name, worker in self.registered_workers.items():
            logger.debug(f"Starting {name} worker...")
            worker.start()

    def stop(self):
        """
        Stops all the registered workers.

        """
        for name, worker in self.registered_workers.items():
            logger.info(f"Stopping {name} worker...")
            worker.stop()

    def edit_period(self, worker_name: str | type, new_period: int):
        """ Updates the period of a registered worker."""
        if isinstance(worker_name, type):
            worker_name = worker_name.__name__

        if worker_name not in self.registered_workers:
            logger.error(f"Worker {worker_name} is not registered on manager, cannot update its period")
            return

        if new_period < 15:
            logger.warning(f"Workers should not have less than 15 seconds of periodic execution, "
                           f"cannot update with {new_period}")
            return

        self.registered_workers[worker_name].edit_period(new_period)

        logger.info(f"Worker {worker_name} period updated to {new_period}")
