# -*- coding: utf-8 -*-
import time

from mock import Mock, patch
import unittest

from nuvlaedge.agent.monitor.components.geolocation import GeoLocationMonitor
from nuvlaedge.agent.monitor.data.geolocation_data import GeoLocationData


class TestGeoLocationMonitor(unittest.TestCase):

    mock_telemetry = Mock()
    _patch_send_req: str = 'nuvlaedge.agent.monitor.components.geolocation.GeoLocationMonitor.' \
                           'send_request'
    _patch_parse_geo: str = 'nuvlaedge.agent.monitor.components.geolocation.GeoLocationMonitor.' \
                            'parse_geolocation'

    def test_constructor(self):
        it_telemetry = Mock()
        it_telemetry.edge_status.inferred_location = None
        GeoLocationMonitor('geo_test', it_telemetry, True)
        self.assertIsInstance(it_telemetry.edge_status.inferred_location, GeoLocationData)

    def test_send_request(self):
        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)

        self.assertIsNone(test_geo.send_request(''))
        self.assertIsInstance(test_geo.send_request('https://ipinfo.io/json'), dict)

    def test_parse_geolocation(self):
        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)

        # when using a service with "coordinates_key"
        ip_location_service_name = 'ipinfo.io'
        ip_location_service_info = test_geo._LOCATION_SERVICES[
            ip_location_service_name]

        geolocation_response = {
            ip_location_service_info['coordinates_key']: 'one,two'
        }
        self.assertEqual(test_geo.parse_geolocation(ip_location_service_name,
                                                    ip_location_service_info,
                                                    geolocation_response), ['two', 'one'],
                         'Failed to get geolocation from string coordinates_key')

        geolocation_response = {
            ip_location_service_info['coordinates_key']: ['one', 'two']
        }
        self.assertEqual(test_geo.parse_geolocation(ip_location_service_name,
                                                    ip_location_service_info,
                                                    geolocation_response), ['two', 'one'],
                         'Failed to get geolocation from list coordinates_key')

        # else, raise a TypeError
        geolocation_response = {
            ip_location_service_info['coordinates_key']: {}
        }
        self.assertRaises(TypeError, test_geo.parse_geolocation, ip_location_service_name,
                          ip_location_service_info, geolocation_response)

        # and if it is not included in the HTTP response, raise KeyError
        self.assertRaises(KeyError, test_geo.parse_geolocation,
                          ip_location_service_name, ip_location_service_info, {})

        # without a "coordinates_key"
        ip_location_service_name = 'ipapi.co'
        ip_location_service_info = test_geo._LOCATION_SERVICES[
            ip_location_service_name]
        geolocation_response = {
            ip_location_service_info['longitude_key']: 1,
            ip_location_service_info['latitude_key']: 2
        }

        # gets the respective coord keys from the HTTP response
        self.assertEqual(test_geo.parse_geolocation(ip_location_service_name,
                                                    ip_location_service_info,
                                                    geolocation_response), [1, 2],
                         'Failed to get geolocation using longitude and latitude')

        # if altitude also exists, it is also included
        ip_location_service_info['altitude_key'] = 'altitude'
        geolocation_response['altitude'] = 3
        self.assertEqual(
            test_geo.parse_geolocation(
                ip_location_service_name,
                ip_location_service_info,
                geolocation_response),
            [1, 2, 3],
            'Failed to get geolocation using longitude and latitude and altitude')

        # and if such keys are not present in the response, raise keyerror
        self.assertRaises(KeyError, test_geo.parse_geolocation,
                          ip_location_service_name, ip_location_service_info, {})

    def test_update_data(self):
        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)
        # Test period control
        test_geo.is_thread = False
        with patch('time.time') as mocked_time:
            mocked_time.return_value = 0
            test_geo.update_data()
            self.assertIsNone(test_geo.data.coordinates)

        test_geo.is_thread = True
        # Void control
        with patch(self._patch_send_req, autospec=True) as test_send_req:
            test_send_req.return_value = None
            test_geo.update_data()
            self.assertIsNone(test_geo.data.coordinates)

        with patch(self._patch_send_req, autospec=True) as test_send_req,\
                patch(self._patch_parse_geo, autospec=True) as test_parse:
            test_send_req.return_value = None
            test_parse.return_value = 'random_text'
            test_geo.update_data()
            self.assertIsNone(test_geo.data.coordinates)
            self.assertIsNone(test_geo.data.timestamp)

            test_parse.return_value = [-1, -1]
            test_send_req.return_value = 'not_none'
            test_geo.update_data()
            self.assertEqual(test_geo.data.longitude, -1)
            self.assertEqual(test_geo.data.latitude, -1)

        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)
        with patch(self._patch_send_req, autospec=True) as test_send_req, \
                patch(self._patch_parse_geo, autospec=True) as test_parse:
            test_send_req.return_value = 'random_text'
            test_parse.side_effect = TypeError()
            test_geo.update_data()
            self.assertIsNone(test_geo.data.timestamp)

    def test_populate_nb_report(self):
        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)
        body: dict = {}
        with patch(self._patch_send_req, autospec=True) as test_send_req, \
                patch(self._patch_parse_geo, autospec=True) as test_parse:
            test_parse.return_value = [-1, -1]
            test_send_req.return_value = 'not_none'

            test_geo.update_data()
            test_geo.populate_nb_report(body)
            self.assertIn('inferred-location', body)
            self.assertEqual([-1.0, -1.0], body.get('inferred-location', []))

    @patch("time.sleep", side_effect=InterruptedError)
    def test_run(self, _):
        test_geo: GeoLocationMonitor = GeoLocationMonitor('geo_test', self.mock_telemetry,
                                                          True)

        with patch('nuvlaedge.agent.monitor.components.geolocation.GeoLocationMonitor.update_data',
                   autospec=True) as mocked_updater:
            mocked_updater.return_value = 'TEST'
            test_geo.update_data()
            self.assertEqual(mocked_updater.call_count, 1)
            try:
                test_geo.run()
            except InterruptedError:
                ...

