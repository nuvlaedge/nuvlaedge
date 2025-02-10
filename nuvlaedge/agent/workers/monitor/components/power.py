""" Module containing power report monitor """
import os
import re

from functools import cached_property

from nuvlaedge.common.constants import CTE
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.agent.workers.monitor.data.power_data import PowerData, PowerEntry


@monitor('power_monitor')
class PowerMonitor(Monitor):
    """
        Power monitor class
    """

    _NVIDIA_MODEL: dict = {
        "ina3221x": {
            "channels": 3,
            "boards": {
                "agx_xavier": {
                    "i2c_addresses": ["1-0040", "1-0041"],
                    "channels_path": ["1-0040/iio:device0", "1-0041/iio:device1"]
                },
                "xavier_nx": {
                    "i2c_addresses": ["7-0040"],
                    "channels_path": ["7-0040/iio:device0"]
                },
                "nano": {
                    "i2c_addresses": ["6-0040"],
                    "channels_path": ["6-0040/iio:device0"]
                },
                "tx1": {
                    "i2c_addresses": ["1-0040"],
                    "channels_path": ["1-0040/iio:device0"]
                },
                "tx1_dev_kit": {
                    "i2c_addresses": ["1-0042", "1-0043"],
                    "channels_path": ["1-0042/iio:device2", "1-0043/iio:device3"]
                },
                "tx2": {
                    "i2c_addresses": ["0-0040", "0-0041"],
                    "channels_path": ["0-0040/iio:device0", "0-0041/iio:device1"]
                },
                "tx2_dev_kit": {
                    "i2c_addresses": ["0-0042", "0-0043"],
                    "channels_path": ["0-0042/iio:device2", "0-0043/iio:device3"]
                }
            }
        }
    }

    def __init__(self, name: str, telemetry, enable_monitor: bool = True, period: int = 60):
        super().__init__(name, PowerData, enable_monitor, period)

        self.host_fs: str = CTE.HOST_FS

        if not self.available_power_drivers:
            self.logger.info(f'No power driver supported. Disabling {self.name}')
            self.enabled_monitor = False

    def get_power_path(self, driver):
        return f'{self.host_fs}/sys/bus/i2c/drivers/{driver}'

    @cached_property
    def available_power_drivers(self):
        drivers = []
        for driver in self._NVIDIA_MODEL:
            if os.path.exists(self.get_power_path(driver)):
                drivers.append(driver)
        return drivers

    def get_powers(self, driver: str) -> list[PowerEntry] | None:
        """
        Parses the driver info received and reads the corresponding files to create a
        PowerEntry data structure

        Args:
            driver: driver name to find the power

        Returns:
            A list of PowerEntry with the instant power values
        """
        i2c_fs_path = self.get_power_path(driver)

        powers: list[PowerEntry] = []

        if not os.path.exists(i2c_fs_path):
            self.logger.warning(f'Path {i2c_fs_path} do not exist but it was at initialisation time')
            return []

        i2c_addresses_found = \
            [addr for addr in os.listdir(i2c_fs_path) if
             re.match(r"\d-\d\d\d\d", addr)]
        i2c_addresses_found.sort()
        channels = self._NVIDIA_MODEL[driver]['channels']
        for _, power_info in self._NVIDIA_MODEL[driver]['boards'].items():
            known_i2c_addresses = power_info['i2c_addresses']
            known_i2c_addresses.sort()
            if not set(known_i2c_addresses).issubset(set(i2c_addresses_found)):
                self.logger.debug('i2c address found do not match known i2c address: '
                                  f'{known_i2c_addresses} is not a subset of {i2c_addresses_found}')
                continue

            for metrics_folder_name in power_info['channels_path']:
                metrics_folder_path = f'{i2c_fs_path}/{metrics_folder_name}'
                if not os.path.exists(metrics_folder_path):
                    self.logger.debug(f'Power metric folder do not exists: {metrics_folder_path}')
                    continue

                for channel in range(0, channels):
                    rail_name_file = f'{metrics_folder_path}/rail_name_{channel}'
                    if not os.path.exists(rail_name_file):
                        self.logger.debug(f'Power metric rail file do not exists: {rail_name_file}')
                        continue

                    with open(rail_name_file, encoding='utf-8') as rail_file:
                        try:
                            metric_basename = rail_file.read().split()[0]
                        except IndexError:
                            self.logger.warning(f'Cannot read power metric rail name at '
                                                f'{rail_name_file}')
                            continue

                    rail_current_file = f'{metrics_folder_path}/in_current{channel}_input'
                    rail_voltage_file = f'{metrics_folder_path}/in_voltage{channel}_input'
                    rail_power_file = f'{metrics_folder_path}/in_power{channel}_input'
                    rail_critical_current_limit_file = \
                        f'{metrics_folder_path}/crit_current_limit_{channel}'

                    # (filename, metric name, units)
                    desired_metrics_files = [
                        (rail_current_file, f"{metric_basename}_current", "mA"),
                        (rail_voltage_file, f"{metric_basename}_voltage", "mV"),
                        (rail_power_file, f"{metric_basename}_power", "mW"),
                        (rail_critical_current_limit_file,
                         f"{metric_basename}_critical_current_limit", "mA")
                    ]

                    existing_metrics = os.listdir(metrics_folder_path)

                    if not all(desired_metric[0].split('/')[-1] in existing_metrics
                               for desired_metric in desired_metrics_files):
                        self.logger.debug(
                            'One or more power metric files we need, are missing from the directory. skipping'
                            f'desired_metrics_files: {desired_metrics_files}.'
                            f'existing_metrics: {existing_metrics}.')
                        continue

                    for metric_combo in desired_metrics_files:
                        try:
                            with open(metric_combo[0], encoding='utf-8') as metric_f:
                                powers.append(PowerEntry(
                                    metric_name=metric_combo[1],
                                    energy_consumption=float(metric_f.read().split()[0]),
                                    unit=metric_combo[2]))
                        except (IOError, IndexError, ValueError):
                            self.logger.debug('Failed to get metric combo', exc_info=True)
        return powers

    def update_data(self):

        if not self.data.power_entries:
            self.data.power_entries = {}

        for driver in self.available_power_drivers:
            for it_data in self.get_powers(driver):
                if it_data:
                    self.data.power_entries[it_data.metric_name] = it_data

    def populate_telemetry_payload(self):
        if self.data.power_entries:
            # Only populate the telemetry data if we have power entries
            # None values won't be included when merging the telemetry data
            self.telemetry_data.resources = {
                'power-consumption': [v.dict(exclude_none=True, by_alias=True) for v in self.data.power_entries.values()]
            }
