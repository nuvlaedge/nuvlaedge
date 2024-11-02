"""
    Gathers all the available monitors, imports them and exposes them to be instantiated
    by Telemetry classs
"""
import glob
from os.path import dirname, basename, isfile
from typing import Dict

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger


modules = glob.glob(dirname(__file__) + "/*.py")
file_logger = get_nuvlaedge_logger("monitors")


class Monitors:
    """
    Wrapper class for available monitors

        monitors: Currently registered and imported monitors
    """
    active_monitors: Dict = {}

    @classmethod
    def get_monitor(cls, monitor_name: str):
        """
        Returns a monitor class provided a name
        Args:
            monitor_name: monitor to retrieve

        Returns:

        """
        return cls.active_monitors.get(monitor_name)

    @classmethod
    def register_monitor(cls, monitor_name: str, p_monitor):
        """
        Registers a new monitor module provided a name and the module
        Args:
            monitor_name: Monitor name to be registered
            p_monitor: Monitor module to be registered
        """

        file_logger.debug(f'Distribution {monitor_name} registered')
        cls.active_monitors[monitor_name] = p_monitor

    @classmethod
    def monitor(cls, monitor_name: str = None):
        """
        Tries to register the monitor name provided by name
        Args:
            monitor_name: monitor to be created and registered

        Returns: Monitor class

        """
        def decorator(monitor_class):
            _monitor_name = monitor_name or monitor_class.__name__

            setattr(monitor_class, 'monitor_name', _monitor_name)

            if _monitor_name in cls.active_monitors:
                file_logger.error(f'Monitor {_monitor_name} is already defined')
            else:
                cls.register_monitor(_monitor_name, monitor_class)

            return monitor_class
        return decorator


monitor = Monitors.monitor
get_monitor = Monitors.get_monitor
register_monitor = Monitors.register_monitor
active_monitors = Monitors.active_monitors


for m in modules:
    if isfile(m) and not m.endswith('___init__.py'):
        __all__ = [basename(m)[:-3]]
        try:
            from . import *
        except ModuleNotFoundError:
            file_logger.exception(f'Module {__all__[0]} not fount')
