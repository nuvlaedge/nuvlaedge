""" GPIO Pins module data structure """
from nuvlaedge.agent.workers.monitor import BaseDataStructure


class GpioPin(BaseDataStructure):
    """ Single pin data structure """
    pin:        int | None = None
    bcm:        int | None = None
    name:       str | None = None
    mode:       str | None = None
    voltage:    int | None = None


class GpioData(BaseDataStructure):
    """ Pin rack description """
    pins:       dict[int, GpioPin] | None = None
