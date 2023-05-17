""" GPIO Pins module data structure """
from typing import Union, Dict

from nuvlaedge.agent.monitor import BaseDataStructure


class GpioPin(BaseDataStructure):
    """ Single pin data structure """
    pin: Union[int, None]
    bcm: Union[int, None]
    name: Union[str, None]
    mode: Union[str, None]
    voltage: Union[int, None]


class GpioData(BaseDataStructure):
    """ Pin rack description """
    pins: Union[Dict[int, GpioPin], None]
