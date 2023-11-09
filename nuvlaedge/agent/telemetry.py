# -*- coding: utf-8 -*-

""" NuvlaEdge Telemetry

It takes care of updating the NuvlaEdge status
resource in Nuvla.
"""

import datetime
import inspect
import json
import logging
import os
from typing import Dict, NoReturn, List
import socket
import time

import psutil
import paho.mqtt.client as mqtt
from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.common import util
from nuvlaedge.agent.common.nuvlaedge_common import NuvlaEdgeCommon
from nuvlaedge.agent.monitor.edge_status import EdgeStatus
from nuvlaedge.agent.monitor.components import get_monitor, active_monitors
from nuvlaedge.agent.monitor import Monitor
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.common.thread_handler import is_thread_creation_needed


class MonitoredDict(dict):
    """
    Subclass of dict that use logging.debug to inform when a change is made.
    """

    def __init__(self, name, *args, **kwargs):
        self.name = name
        dict.__init__(self, *args, **kwargs)
        self._log_caller()
        logging.debug(f'{self.name} __init__: args: {args}, kwargs: {kwargs}')

    def _log_caller(self):
        stack = inspect.stack()
        cls_fn_name = stack[1].function
        caller = stack[2]
        cc = caller.code_context
        code_context = cc[0] if cc and len(cc) >= 1 else ''
        logging.debug(
            f'{self.name}.{cls_fn_name} called by {caller.filename}:{caller.lineno} '
            f'{caller.function} {code_context}')

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self._log_caller()
        logging.debug(f'{self.name} set {key} = {value}')

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__, dict.__repr__(self))

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        self._log_caller()
        logging.debug(f'{self.name} update: args: {args}, kwargs: {kwargs}')
        logging.debug(f'{self.name} updated: {self}')


class Telemetry(NuvlaEdgeCommon):
    """ The Telemetry class, which includes all methods and
    properties necessary to categorize a NuvlaEdge and send all
    data into the respective NuvlaEdge status at Nuvla

    Attributes:
        data_volume: path to shared NuvlaEdge data
    """

    def __init__(self,
                 coe_client: COEClient,
                 data_volume: str,
                 nuvlaedge_status_id: str,
                 excluded_monitors: str = ''):
        """
        Constructs an Telemetry object, with a status placeholder
        """

        super().__init__(coe_client=coe_client,
                         shared_data_volume=data_volume)

        self.logger: logging.Logger = logging.getLogger('Telemetry')
        self.nb_status_id = nuvlaedge_status_id

        self.status_default = {
            'resources': None,
            'status': None,
            'status-notes': None,
            'nuvlabox-api-endpoint': None,
            'operating-system': None,
            'architecture': None,
            'ip': None,
            'last-boot': None,
            'hostname': None,
            'docker-server-version': None,
            'gpio-pins': None,
            'nuvlabox-engine-version': None,
            'inferred-location': None,
            'vulnerabilities': None,
            'node-id': None,
            'cluster-id': None,
            'cluster-managers': None,
            'cluster-nodes': None,
            'cluster-node-role': None,
            'installation-parameters': None,
            'swarm-node-cert-expiry-date': None,
            'host-user-home': None,
            'orchestrator': None,
            'network': None,
            'cluster-join-address': None,
            'temperatures': None,
            'container-plugins': None,
            'kubelet-version': None,
            'current-time': '',
            'id': None,
            'components': None
        }
        self._status = MonitoredDict('Telemetry.status', self.status_default.copy())
        self._status_on_nuvla = MonitoredDict('Telemetry.status_on_nuvla')

        self.mqtt_telemetry = mqtt.Client()

        self.edge_status: EdgeStatus = EdgeStatus()

        self.excluded_monitors: List[str] = excluded_monitors.replace("'", "").split(',')
        self.logger.info(f'Excluded monitors received in Telemetry'
                         f' {self.excluded_monitors}')
        self.monitor_list: Dict[str, Monitor] = {}
        self.initialize_monitors()

    def initialize_monitors(self) -> NoReturn:
        """
        Auxiliary function to extract some control from the class initialization
        It gathers the available monitors and initializes them saving the reference into
        the monitor_list attribute of Telemtry
        """
        for mon in active_monitors:
            if mon.split('_')[0] in self.excluded_monitors:
                continue
            self.monitor_list[mon] = (get_monitor(mon)(mon, self, True))

    @property
    def status_on_nuvla(self):
        return self._status_on_nuvla

    @status_on_nuvla.setter
    def status_on_nuvla(self, value):
        """ Agent status setter """
        self._status_on_nuvla = MonitoredDict('Telemetry.status_on_nuvla', value)
        caller = inspect.stack()[1]
        logging.debug(f'Telemetry.status_on_nuvla setter called by {caller.filename}:'
                      f'{caller.lineno} {caller.function} {caller.code_context}')
        logging.debug(f'Telemetry.status_on_nuvla updated: {value}')

    @property
    def status(self):
        """ Current agent status getter """
        return self._status

    @status.setter
    def status(self, value):
        self._status = MonitoredDict('Telemetry.status', value)
        caller = inspect.stack()[1]
        logging.debug(f'Telemetry.status setter called by '
                      f'{caller.filename}:{caller.lineno} {caller.function} '
                      f'{caller.code_context}')
        logging.debug(f'Telemetry.status updated: {value}')

    def send_mqtt(self, nuvlaedge_status, cpu=None, ram=None, disks=None, energy=None):
        """ Gets the telemetry data and send the stats into the MQTT broker

        :param nuvlaedge_status: full dump of the NB status {}
        :param cpu: tuple (capacity, load)
        :param ram: tuple (capacity, used)
        :param disks: list of {device: partition_name, capacity: value, used: value}
        :param energy: energy consumption metric
        """

        try:
            self.mqtt_telemetry.connect(self.mqtt_broker_host, self.mqtt_broker_port,
                                        self.mqtt_broker_keep_alive)
        except ConnectionRefusedError:
            logging.warning("Connection to NuvlaEdge MQTT broker refused")
            self.mqtt_telemetry.disconnect()
            return
        except socket.timeout:
            logging.warning(f'Timed out while trying to send telemetry to Data Gateway at'
                            f' {self.mqtt_broker_host}')
            return
        except socket.gaierror:
            logging.warning("The NuvlaEdge MQTT broker is not reachable...trying again"
                            " later")
            self.mqtt_telemetry.disconnect()
            return

        os.system(f"mosquitto_pub -h {self.mqtt_broker_host} -t nuvlaedge-status "
                  f"-m '{json.dumps(nuvlaedge_status)}'")

        if cpu:
            # e1 = self.mqtt_telemetry.publish("cpu/capacity", payload=str(cpu[0]))
            # e2 = self.mqtt_telemetry.publish("cpu/load", payload=str(cpu[1]))
            # ISSUE: for some reason, the connection is lost after publishing with
            # paho-mqtt

            # using os.system for now

            os.system(f"mosquitto_pub -h {self.mqtt_broker_host} -t cpu "
                      f"-m '{json.dumps(ram)}'")

        if ram:
            # self.mqtt_telemetry.publish("ram/capacity", payload=str(ram[0]))
            # self.mqtt_telemetry.publish("ram/used", payload=str(ram[1]))
            # same issue as above
            os.system(f"mosquitto_pub -h {self.mqtt_broker_host} -t ram "
                      f"-m '{json.dumps(ram)}'")

        if disks:
            for dsk in disks:
                # self.mqtt_telemetry.publish("disks", payload=json.dumps(dsk))
                # same issue as above
                os.system(f"mosquitto_pub -h {self.mqtt_broker_host} -t disks "
                          f"-m '{json.dumps(dsk)}'")

        if energy:
            # self.mqtt_telemetry.publish("ram/capacity", payload=str(ram[0]))
            # self.mqtt_telemetry.publish("ram/used", payload=str(ram[1]))
            # same issue as above
            os.system(f"mosquitto_pub -h {self.mqtt_broker_host} "
                      f"-t energy -m '{json.dumps(energy)}'")

        # self.mqtt_telemetry.disconnect()

    def set_status_operational_status(self, body: dict, node: dict):
        """
        Gets and sets the operational status and status_notes for the nuvlaedge-status

        :param body: payload for the nuvlaedge-status update request
        :param node: information about the underlying COE node
        """
        operational_status_notes = self.get_operational_status_notes()
        operational_status = self.get_operational_status()

        system_errors, system_warnings = self.coe_client.read_system_issues(node)

        operational_status_notes += system_errors + system_warnings
        if system_errors:
            operational_status = 'DEGRADED'

        if not self.installation_home:
            operational_status_notes.append(
                "HOST_HOME not defined - SSH key management will not be functional")

        body.update({
            "status": operational_status,
            "status-notes": operational_status_notes,
        })

    def update_monitors(self, status_dict):
        """
        Watchdog function for monitor class updating
        Args:
            status_dict: dictionary containing the report for Nuvla to be updated by
            each monitor
        """

        for monitor_name, it_monitor in self.monitor_list.items():
            self.logger.debug(f'Monitor: {it_monitor.name} - '
                              f'Threaded: {it_monitor.is_thread} - '
                              f'Alive: {it_monitor.is_alive()}')

            if it_monitor.is_thread:
                if is_thread_creation_needed(
                        monitor_name,
                        it_monitor,
                        log_not_alive=(logging.INFO, 'Recreating {} thread.'),
                        log_alive=(logging.DEBUG, 'Thread {} is alive'),
                        log_not_exist=(logging.INFO, 'Creating {} thread.')):

                    monitor = get_monitor(monitor_name)(monitor_name, self, True)
                    monitor.start()
                    self.monitor_list[monitor_name] = monitor

            else:
                it_monitor.run_update_data(monitor_name=monitor_name)

        monitor_process_duration = {k: v.last_process_duration for k, v in self.monitor_list.items()}
        self.logger.debug(f'Monitors processing duration: '
                          f'{json.dumps(monitor_process_duration, indent=4)}')

        # Retrieve monitoring data
        for it_monitor in self.monitor_list.values():
            try:
                if it_monitor.updated:
                    it_monitor.populate_nb_report(status_dict)
                else:
                    self.logger.info(f'Data not updated yet in monitor '
                                     f'{it_monitor.name}')
            except Exception as ex:
                self.logger.exception(f'Error retrieving data from monitor '
                                      f'{it_monitor.name}.', ex)

    def get_status(self):
        """ Gets several types of information to populate the NuvlaEdge status """

        status_for_nuvla = self.status_default.copy()
        # Update monitor objects
        self.update_monitors(status_for_nuvla)

        node_info = self.coe_client.get_node_info()
        # - STATUS attrs
        self.set_status_operational_status(status_for_nuvla, node_info)

        # - CURRENT TIME attr
        status_for_nuvla['current-time'] = \
            datetime.datetime.utcnow().isoformat().split('.')[0] + 'Z'

        # Publish the telemetry into the Data Gateway
        all_status = status_for_nuvla.copy()
        try:
            # Try to retrieve data if available
            self.send_mqtt(
                status_for_nuvla,
                status_for_nuvla.get('resources', {}).get('cpu', {}).get('raw-sample'),
                status_for_nuvla.get('resources', {}).get('ram', {}).get('raw-sample'),
                status_for_nuvla.get('resources', {}).get('disks', []))

            # get all status for internal monitoring
            all_status.update({
                "cpu-usage": psutil.cpu_percent(),
                "cpu-load": status_for_nuvla.get('resources', {}).get('cpu', {}).get('load'),
                "disk-usage": psutil.disk_usage("/")[3],
                "memory-usage": psutil.virtual_memory()[2],
                "cpus": status_for_nuvla.get('resources', {}).get('cpu', {}).get('capacity'),
                "memory": status_for_nuvla.get('resources', {}).get('ram', {}).get('capacity'),
                "disk": int(psutil.disk_usage('/')[0] / 1024 / 1024 / 1024)
            })
        except AttributeError as ex:
            self.logger.warning('Resources information not ready yet.')
            self.logger.debug(ex, exc_info=True)

        return status_for_nuvla, all_status

    @staticmethod
    def diff(previous_status, current_status):
        """
        Compares the previous status with the new one and discover the minimal changes
        """

        items_changed_or_added = {}
        attributes_to_delete = set(previous_status.keys()) - set(current_status.keys())

        for key, value in current_status.items():
            if value is None:
                attributes_to_delete.add(key)
            elif value != previous_status.get(key):
                items_changed_or_added[key] = value

        return items_changed_or_added, attributes_to_delete

    def update_status(self):
        """ Runs a cycle of the categorization, to update the NuvlaEdge status """
        new_status, all_status = self.get_status()
        self.logger.debug(f'Updating nuvla status on time '
                          f'{new_status.get("current-time")}')

        # write all status into the shared volume for the other
        # components to re-use if necessary
        util.atomic_write(FILE_NAMES.NUVLAEDGE_STATUS_FILE,
                          json.dumps(all_status), encoding='UTF-8')

        self.status.update(new_status)

    def get_vpn_ip(self):
        """ Discovers the NuvlaEdge VPN IP  """

        if FILE_NAMES.VPN_IP_FILE.exists() and FILE_NAMES.VPN_IP_FILE.stat().st_size != 0:
            with FILE_NAMES.VPN_IP_FILE.open('r') as vpn_file:
                return vpn_file.read().splitlines()[0]
        else:
            logging.warning("Cannot infer the NuvlaEdge VPN IP!")
            return None
