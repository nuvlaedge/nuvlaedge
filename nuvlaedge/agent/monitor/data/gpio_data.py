""" GPIO Pins module data structure """
from nuvlaedge.agent.monitor import BaseDataStructure


class GpioPin(BaseDataStructure):
    """ Single pin data structure """
    pin: int | None
    bcm: int | None
    name: str | None
    mode: str | None
    voltage: int | None


class GpioData(BaseDataStructure):
    """ Pin rack description """
    pins: dict[int, GpioPin] | None
