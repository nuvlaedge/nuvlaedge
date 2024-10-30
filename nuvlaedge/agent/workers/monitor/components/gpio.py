"""
    GpioMonitor.py
"""
import logging
from subprocess import SubprocessError, CompletedProcess

from nuvlaedge.agent.common.util import execute_cmd
from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.agent.workers.monitor.data.gpio_data import GpioData, GpioPin


@monitor('gpio')
class GpioMonitor(Monitor):
    """
    Monitor class to read GPIO pins for system-on-board devices
    """
    # GPIO Commands
    _GPIO_VERSION_COMMAND: list[str] = ['gpio', '-v']

    # GPIO parser configuration
    _gpio_expected_attr: list[dict[str, any]] = [
        {"position": None, "type": int, "attribute": "BCM"},
        {"position": None, "type": str, "attribute": "NAME"},
        {"position": None, "type": str, "attribute": "MODE"},
        {"position": None, "type": int, "attribute": "VOLTAGE"}]
    _needed_indexes_len: int = 5
    _first_pin_indexes = [1, 3, 4, 5, 6]
    _second_pin_indexes = [14, 11, 10, 9, 8]

    # Class constructor
    def __init__(self, name: str, telemetry, enable_monitor: bool = True):
        super().__init__(name, GpioData, enable_monitor)

        # Check GPIO availability
        if not self.gpio_availability():
            self.logger.info(f'gpio not supported. Disabling {self.name}')
            self.enabled_monitor = False

        if self.enabled_monitor and not telemetry.edge_status.gpio_pins:
            telemetry.edge_status.gpio_pins = self.data

    def gpio_availability(self) -> bool:
        """
        Check if the GPIO monitor can run in the current host device.

        Returns: True if available, false otherwise

        """
        try:
            return execute_cmd(self._GPIO_VERSION_COMMAND) is not None
        except (SubprocessError, FileNotFoundError):
            return False

    def parse_pin_cell(self, indexes: list, line: str) -> GpioPin | None:
        """
        Parses one cell of the output from gpio readall, which has 2 pins

        @param indexes: the index numbers for the values of BCM, Name, Mode, V and
        Physical (in this order)
        @param line: line to be parsed

        @returns a GPIO dict obj with the parsed pin
        """
        if len(indexes) < self._needed_indexes_len:
            self.logger.error(f"Missing indexes needed to parse GPIO pin: {indexes}. "
                              f"Need {self._needed_indexes_len}")
            return None

        gpio_values: list[str] = line.split('|')
        gpio_pin: GpioPin = GpioPin()

        try:
            gpio_pin.pin = int(gpio_values[indexes[-1]])
            # if we can get the physical pin, we can move on. Pin is the only mandatory
            # attribute

            for i, exp in enumerate(self._gpio_expected_attr):
                try:
                    cast_value = exp["type"](gpio_values[indexes[i]].rstrip().lstrip())
                    if cast_value or cast_value == 0:
                        setattr(gpio_pin, exp["attribute"].lower(), cast_value)
                    else:
                        continue
                except ValueError:
                    self.logger.debug(
                        f"No suitable {exp['attribute']} value for pin {gpio_pin.pin}")
                    continue

            return gpio_pin
        except (ValueError, IndexError):
            self.logger.warning(
                f"Unable to get GPIO pin status on {gpio_values}, index {indexes[-1]}")
            return None

        except KeyError:
            # if there's any other issue while doing so, it means the provided argument
            # is not valid
            self.logger.error(f"Invalid list of indexes {indexes} for GPIO pin in {line}. "
                              f"Cannot parse this pin")
            return None

    def parse_pin_line(self, pin_line: str) -> \
            tuple[GpioPin | None, GpioPin | None]:
        """
        Intermediary call function to parse side by side pins to Tuple
        Args:
            pin_line: Line containing two followed pins

        Returns:
            Tuple containing GPIOPin data structures
        """
        return self.parse_pin_cell(self._first_pin_indexes, pin_line), \
               self.parse_pin_cell(self._second_pin_indexes, pin_line)

    def gather_gpio_lines(self) -> list[str]:
        """
        Executes a readall command and performs a preliminary cleanup of the data
        @return: a list of lines with the current configuration of the GPIO ports
        """
        command: list[str] = ["gpio", "readall"]
        clean_gpio_lines: list[str]
        try:
            gpio_out: CompletedProcess = execute_cmd(command)
            clean_gpio_lines = gpio_out.stdout.splitlines()[3:-3]
            return clean_gpio_lines
        except SubprocessError as ex:
            self.logger.error(f"Subprocess class error: {ex}")

        except FileNotFoundError as ex:
            self.logger.error(f"No command {ex} found, GPIO monitor shouldn't be active if the command is not present")
        return []

    def update_data(self):
        """
        Uses the GPIO utility to scan and get the current status of all GPIO pins in the
        device. It then parses the output and gives back a list of pins

        @returns list of JSONs, i.e. [{pin: 1, name: GPIO. 1, bcm: 4, mode: IN},
        {pin: 7, voltage: 0, mode: ALT1}]
        """
        if not self.data.pins:
            self.data.pins = {}

        new_lines: list[str] = self.gather_gpio_lines()

        for pin_line in new_lines:
            pin_1, pin_2 = self.parse_pin_line(pin_line)

            if pin_1:
                self.data.pins[pin_1.pin] = pin_1
            if pin_2:
                self.data.pins[pin_2.pin] = pin_2

    def populate_nb_report(self, nuvla_report: dict):
        data = self.data.model_dump(exclude_none=True, by_alias=True)
        nuvla_report['gpio-pins'] = data.get('pins')
