""" Module for geolocation data structure reporting """
from pydantic import model_validator

from nuvlaedge.agent.monitor import BaseDataStructure


class GeoLocationData(BaseDataStructure):
    """ Provides a standard structure for GeoLocation data """
    longitude: float | None
    latitude: float | None
    coordinates: list[float] | None
    timestamp: int | None

    @model_validator(mode='after')
    def fill_longitude(cls, values):
        """
        Updates the values of the variable longitude and latitude variables based on
        the inserted coordinates
        Args:
            values: Values of the base model

        Returns:
            Updates values
        """
        if values.get('coordinates') and len(values['coordinates']) == 2:
            values['longitude'] = values['coordinates'][0]
            values['latitude'] = values['coordinates'][1]

        return values
