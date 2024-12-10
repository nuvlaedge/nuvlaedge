""" Module for controlling the geolocation of the NuvlaEdge"""
import json
import logging
import time

import datetime
import requests

from nuvlaedge.agent.workers.monitor import Monitor
from nuvlaedge.agent.workers.monitor.components import monitor
from nuvlaedge.agent.workers.monitor.data.geolocation_data import GeoLocationData


@monitor('geolocation_monitor')
class GeoLocationMonitor(Monitor):
    """ Threaded geolocation monitor """

    _LOCATION_SERVICES: dict[str, dict] = {
        "ipinfo.io": {
            "url": "https://ipinfo.io/json",
            "coordinates_key": "loc",
            "longitude_key": None,
            "latitude_key": None,
            "altitude_key": None,
            "ip": "ip"
        },
        "ipapi.co": {
            "url": "https://ipapi.co/json",
            "coordinates_key": None,
            "longitude_key": "longitude",
            "latitude_key": "latitude",
            "altitude_key": None
        }
    }
    # GeoLocation relies on IP-based geolocation on third-party services. The maximum refresh rate is 3 hours
    MAX_REFRESH_RATE: int = 60*60*3

    def __init__(self, name: str, _, enable_monitor: bool = False, period: int = 60):
        # Default threaded monitor
        super().__init__(name, GeoLocationData, enable_monitor, thread_period=period)

        self.last_update: float = 0.0

    def send_request(self, service: str) -> dict | None:
        """
        Sends a get requests to the service parsed as parameter
        Args:
            service:

        Returns:
            A JSON with the processed response
        """
        try:
            self.logger.debug(f"Inferring geolocation with 3rd party service {service}")
            return requests.get(service, allow_redirects=False, timeout=5).json()
        except requests.RequestException as e:
            self.logger.error(f"Could not infer IP-based geolocation from service {service}: {e}")
            return None

    def parse_geolocation(self, service_name: str, service_info: dict,
                          response: dict) -> list:
        """
        Gets the output from the IP-based geolocation request made to the online service,
        parses it, and builds the inferred location, as a list, for the NuvlaEdge Status

        Args:
            service_info: info about the service queried for retrieving the location
            (as in self.ip_geolocation_services.items)
            service_name: name of the online service used to get the location
            response: response from the IP-based geolocation service,in JSON format

        Returns:
            inferred-location attribute

        """
        inferred_location = []
        if service_info['coordinates_key']:
            coordinates = response[service_info['coordinates_key']]
            # note that Nuvla expects [long, lat], and not [lat, long], thus the reversing
            if isinstance(coordinates, str):
                inferred_location = coordinates.split(',')[::-1]
            elif isinstance(coordinates, list):
                inferred_location = coordinates[::-1]
            else:
                self.logger.warning(f"Cannot parse coordinates {coordinates} retrieved "
                                    f"from geolocation service {service_name}")
                raise TypeError
        else:
            longitude = response[service_info['longitude_key']]
            latitude = response[service_info['latitude_key']]

            inferred_location.extend([longitude, latitude])
            if service_info['altitude_key']:
                inferred_location.append(response[service_info['altitude_key']])
        inferred_location = [float(i) if isinstance(i, str) else i for i in inferred_location]
        return inferred_location

    def update_data(self):

        if (time.time() - self.last_update) < self.MAX_REFRESH_RATE:
            return

        for service, info in self._LOCATION_SERVICES.items():
            it_response: dict = self.send_request(info['url'])
            if it_response:
                try:
                    self.data.coordinates = \
                        self.parse_geolocation(service, info, it_response)
                except (TypeError, KeyError):
                    self.logger.error(f'Error parsing coordinates on service {service}')
                    continue

                self.data.timestamp = \
                    int(datetime.datetime.timestamp(datetime.datetime.now()))

                self.last_update = time.time()
                break

    def populate_telemetry_payload(self):
        if self.data.coordinates:
            self.telemetry_data.inferred_location = self.data.coordinates
