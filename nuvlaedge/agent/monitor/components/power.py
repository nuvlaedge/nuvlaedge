""" Module containing power report monitor """
import os
import re

from nuvlaedge.agent.monitor import Monitor
from nuvlaedge.agent.monitor.components import monitor
from nuvlaedge.agent.monitor.data.power_data import PowerData, PowerEntry


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

    def __init__(self, name: str, telemetry, enable_monitor: bool):
        super().__init__(name, PowerData, enable_monitor)

        self.host_fs: str = telemetry.hostfs

        if not telemetry.edge_status.power:
            telemetry.edge_status.power = self.data

    def get_power(self, driver: str) -> PowerEntry | None:
        """
        Parses the driver info received and reads the corresponding files to create a
        PowerEntry data structure

        Args:
            driver: driver name to find the power

        Returns:
            An Power entry with the instant power values
        """
        i2c_fs_path = f'{self.host_fs}/sys/bus/i2c/drivers/{driver}'

        if not os.path.exists(i2c_fs_path):
            return None

        i2c_addresses_found = \
            [addr for addr in os.listdir(i2c_fs_path) if
             re.match(r"\d-\d\d\d\d", addr)]
        i2c_addresses_found.sort()
        channels = self._NVIDIA_MODEL[driver]['channels']
        for _, power_info in self._NVIDIA_MODEL[driver]['boards'].items():
            known_i2c_addresses = power_info['i2c_addresses']
            known_i2c_addresses.sort()
            if i2c_addresses_found != known_i2c_addresses:
                continue

            for metrics_folder_name in power_info['channels_path']:
                metrics_folder_path = f'{i2c_fs_path}/{metrics_folder_name}'
                if not os.path.exists(metrics_folder_path):
                    continue

                for channel in range(0, channels):
                    rail_name_file = f'{metrics_folder_path}/rail_name_{channel}'
                    if not os.path.exists(rail_name_file):
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
                        # one or more power metric files we need, are missing from the
                        # directory, skip them
                        continue

                    for metric_combo in desired_metrics_files:
                        try:
                            with open(metric_combo[0], encoding='utf-8') as metric_f:

                                return PowerEntry(
                                    metric_name=metric_combo[1],
                                    energy_consumption=float(metric_f.read().split()[0]),
                                    unit=metric_combo[2])
                        except (IOError, IndexError, ValueError):
                            return

    def update_data(self):

        if not self.data.power_entries:
            self.data.power_entries = {}

        for drive in self._NVIDIA_MODEL:
            it_data: PowerEntry = self.get_power(drive)
            if it_data:
                self.data.power_entries[it_data.metric_name] = it_data

    def populate_nb_report(self, nuvla_report: dict):
        ...
