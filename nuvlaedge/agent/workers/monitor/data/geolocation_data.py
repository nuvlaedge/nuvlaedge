""" Module for geolocation data structure reporting """
from pydantic import model_validator, ConfigDict

from nuvlaedge.agent.workers.monitor import BaseDataStructure


class GeoLocationData(BaseDataStructure):
    """ Provides a standard structure for GeoLocation data """
    longitude:      float | None = None
    latitude:       float | None = None
    coordinates:    list[float] | None = None
    timestamp:      int | None = None

    model_config = ConfigDict(validate_assignment=False,
                              populate_by_name=True)

    @model_validator(mode='after')
    def fill_longitude(self):
        """
        Updates the values of the variable longitude and latitude variables based on
        the inserted coordinates

        Returns:
            Updates values
        """
        if self.coordinates and len(self.coordinates) == 2:
            self.longitude = self.coordinates[0]
            self.latitude = self.coordinates[1]

        return self
