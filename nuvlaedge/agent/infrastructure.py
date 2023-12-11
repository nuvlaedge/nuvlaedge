#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" NuvlaEdge Infrastructure

It takes care of updating the NuvlaEdge infrastructure services
and respective credentials in Nuvla
"""

import json
import logging
import os
import time
from datetime import datetime
from os import path

import docker
import docker.errors as docker_err
import requests
from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.common import util
from nuvlaedge.agent.common.nuvlaedge_common import NuvlaEdgeCommon
from nuvlaedge.agent.orchestrator import COEClient
from nuvlaedge.agent.telemetry import Telemetry


class Infrastructure(NuvlaEdgeCommon):
    """ The Infrastructure class includes all methods and
    properties necessary update the infrastructure services
    and respective credentials in Nuvla, whenever the local
    configurations change

    """

    def __init__(self,
                 coe_client: COEClient,
                 data_volume: str,
                 telemetry: Telemetry,
                 refresh_period: int = 15):
        """
        Constructs an Infrastructure object, with a status placeholder

        :param data_volume: shared volume
        """
        super(Infrastructure, self).__init__(coe_client=coe_client,
                                             shared_data_volume=data_volume)

        self.logger: logging.Logger = logging.getLogger(__name__)

        self.telemetry_instance = telemetry

        self.ssh_flag = f"{data_volume}/.ssh"
        self.refresh_period = refresh_period

    @staticmethod
    def write_file(file, content, is_json=False):
        """ Static method to write to file

        :param file: full path to file
        :param content: content of the file
        :param is_json: tells if the content is to be processed as JSON
        """

        if is_json:
            content = json.dumps(content)

        util.atomic_write(file, content)

    def swarm_token_diff(self, current_manager_token, current_worker_token):
        """ Checks if the Swarm tokens have changed

        :param current_manager_token: current swarm manager token
        :param current_worker_token: current swarm worker token
        :return true or false
        """

        manager_token_file = f"{self.data_volume}/{self.swarm_manager_token_file}"
        worker_token_file = f"{self.data_volume}/{self.swarm_worker_token_file}"

        try:
            open(worker_token_file).readlines()[0].replace('\n', '')
            open(manager_token_file).readlines()[0].replace('\n', '')
        except (FileNotFoundError, IndexError):
            self.logger.info("Docker Swarm tokens not registered yet...registering")
            self.write_file(manager_token_file, current_manager_token)
            self.write_file(worker_token_file, current_worker_token)
            return True

        return False

    def get_tls_keys(self):
        """ Finds and returns the Container orchestration API client TLS keys """

        try:
            with FILE_NAMES.CA.open('r') as file:
                client_ca = file.read()
            with FILE_NAMES.CERT.open('r') as file:
                client_cert = file.read()
            with FILE_NAMES.KEY.open('r') as file:
                client_key = file.read()

        except (FileNotFoundError, IndexError):
            self.logger.debug("Container orchestration API TLS keys have not been set yet!")
            return []

        return client_ca, client_cert, client_key

    def do_commission(self, payload):
        """ Perform the operation

        :param payload: commissioning payload
        :return
        """

        if not payload:
            self.logger.debug("Tried commissioning with empty payload. Nothing to do")
            return

        self.logger.info(f"Commissioning the NuvlaEdge... ({payload})")
        try:
            self.api()._cimi_post(self.nuvlaedge_id+"/commission", json=payload)
        except Exception as e:
            self.logger.error(f"Could not commission with payload {payload}: {e}")
            return False

        if "vpn-csr" in payload:
            # get the respective VPN credential that was just created
            with FILE_NAMES.CONTEXT.open('r') as file:
                vpn_server_id = json.load(file).get("vpn-server-id")

            searcher_filter = self.build_vpn_credential_search_filter(vpn_server_id)

            attempts = 0
            credential_id = None
            while attempts <= 20:
                self.logger.info("Getting VPN credential from Nuvla...")
                try:
                    credential_id = self.api().search("credential",
                                                      filter=searcher_filter,
                                                      last=1).resources[0].id
                    break
                except IndexError:
                    self.logger.exception("Cannot find VPN credential in Nuvla after commissioning")
                    time.sleep(2)
                except Exception as ex:
                    self.logger.info(f"Exception finding VPN credential in Nuvla: {ex}")

                attempts += 1

            if not credential_id:
                self.logger.warning("Failing to provide necessary values for NuvlaEdge VPN client")
                return None

            vpn_credential = self.api()._cimi_get(credential_id)
            # save_vpn_credential
            vpn_server = self.api()._cimi_get(vpn_server_id)

            vpn_conf_endpoints = ''
            for connection in vpn_server["vpn-endpoints"]:
                vpn_conf_endpoints += \
                    "\n<connection>\nremote {} {} {}\n</connection>\n".format(
                        connection["endpoint"],
                        connection["port"],
                        connection["protocol"])

            vpn_fields = {
                "vpn-intermediate-ca": "\n".join(vpn_credential["vpn-intermediate-ca"]),
                "vpn-certificate": vpn_credential["vpn-certificate"],
                "vpn-ca-certificate": vpn_server["vpn-ca-certificate"],
                "vpn-intermediate-ca-is": "\n".join(vpn_server["vpn-intermediate-ca"]),
                "vpn-shared-key": vpn_server["vpn-shared-key"],
                "vpn-common-name-prefix": vpn_server["vpn-common-name-prefix"],
                "vpn-endpoints-mapped": vpn_conf_endpoints
            }

            return vpn_fields

        return True

    def needs_commission(self, current_conf):
        """ Check whether the current commission data structure
        has changed wrt to the previous one

        :param current_conf: current commissioning data
        :return commissioning payload
        """

        try:
            with FILE_NAMES.COMMISSIONING_FILE.open('r') as file:
                old_conf = json.load(file)
                if current_conf == old_conf:
                    return {}
                else:
                    diff_conf = {}
                    for key, value in current_conf.items():
                        if key in old_conf and old_conf[key] == value:
                            continue

                        diff_conf[key] = value

                    return diff_conf
        except FileNotFoundError:
            self.logger.info("Auto-commissioning the NuvlaEdge for the first time..")
            return current_conf

    def commission_vpn(self):
        """ (re)Commissions the NB via the agent API

        :return: True on success, False otherwise
        """
        self.logger.info('Starting VPN commissioning...')

        vpn_csr, vpn_key = self.prepare_vpn_certificates()

        if not vpn_key or not vpn_csr:
            return False

        try:
            vpn_conf_fields = self.do_commission({"vpn-csr": vpn_csr})
        except Exception as e:
            self.logger.error(f'Unable to setup VPN connection: {str(e)}')
            return False

        if not vpn_conf_fields:
            self.logger.error('Invalid response from VPN commissioning... cannot continue')
            return False

        self.logger.info(f'VPN configuration fields: {vpn_conf_fields}')

        self.vpn_interface_name = f'vpn_{self.nuvlaedge_id[8:]}'

        vpn_values = {
            'vpn_certificate': vpn_conf_fields['vpn-certificate'],
            'vpn_intermediate_ca': vpn_conf_fields['vpn-intermediate-ca'],
            'vpn_ca_certificate': vpn_conf_fields['vpn-ca-certificate'],
            'vpn_intermediate_ca_is': vpn_conf_fields['vpn-intermediate-ca-is'],
            'vpn_shared_key': vpn_conf_fields['vpn-shared-key'],
            'vpn_common_name_prefix': vpn_conf_fields['vpn-common-name-prefix'],
            'vpn_endpoints_mapped': vpn_conf_fields['vpn-endpoints-mapped'],
            'vpn_interface_name': self.vpn_interface_name,
            'nuvlaedge_vpn_key': vpn_key,
            'vpn_extra_config': self.vpn_config_extra
        }

        self.write_vpn_conf(vpn_values)
        return True

    def prepare_vpn_certificates(self):

        cmd = ['openssl', 'req', '-batch', '-nodes', '-newkey', 'ec', '-pkeyopt',
               'ec_paramgen_curve:secp521r1',
               '-keyout', self.vpn_key_file,
               '-out', self.vpn_csr_file,
               '-subj', f'/CN={self.nuvlaedge_id.split("/")[-1]}']

        r = self.shell_execute(cmd)

        if r.get('returncode', -1) != 0:
            self.logger.error(f'Cannot generate certificates for VPN connection: '
                              f'{r.get("stdout")} | {r.get("stderr")}')
            return None, None

        try:
            wait = 0
            while not os.path.exists(self.vpn_csr_file) and \
                    not os.path.exists(self.vpn_key_file):
                if wait > 25:
                    # appr 5 sec
                    raise TimeoutError
                wait += 1
                time.sleep(0.2)

            with open(self.vpn_csr_file) as csr:
                vpn_csr = csr.read()

            with open(self.vpn_key_file) as key:
                vpn_key = key.read()
        except TimeoutError:
            self.logger.error(f'Unable to lookup {self.vpn_key_file} and {self.vpn_csr_file}')
            return None, None

        return vpn_csr, vpn_key

    def get_nuvlaedge_capabilities(self, commissioning_dict: dict):
        """ Finds the NuvlaEdge capabilities and adds them to the NB commissioning payload

        :param commissioning_dict: the commission payload, as a dict, to be changed in
        case there are capabilities
        :return:
        """

        # NUVLA_JOB_PULL if job-engine-lite has been deployed with the NBE
        commissioning_dict['capabilities'] = ['NUVLA_HEARTBEAT']
        if self.coe_client.has_pull_job_capability():
            commissioning_dict['capabilities'].append('NUVLA_JOB_PULL')

    def compute_api_is_running(self) -> bool:
        """
        Check if the compute-api endpoint is up and running

        Only valid for Docker installations

        :return: True or False
        """

        if self.coe_client.ORCHESTRATOR not in ['docker', 'swarm']:
            return False

        compute_api_url = f'https://{util.compute_api}:{util.COMPUTE_API_INTERNAL_PORT}'
        self.logger.debug(f'Trying to reach compute API using {compute_api_url} address')
        try:
            if self.coe_client.client.containers.get(util.compute_api).status != 'running':
                return False
        except (docker_err.NotFound, docker_err.APIError, TimeoutError) as ex:
            self.logger.debug(f"Compute API container not found {ex}")
            return False

        try:
            requests.get(compute_api_url, timeout=3)

        except requests.exceptions.SSLError:
            # this is expected. It means it is up, we just weren't authorized
            self.logger.debug("Compute API up and running with security")

        except (requests.exceptions.ConnectionError, TimeoutError) as ex:
            # Can happen if the Compute API takes longer than normal on start
            self.logger.info(f'Compute API not ready yet: {ex}')
            return False

        return True

    @staticmethod
    def get_local_nuvlaedge_status() -> dict:
        """
        Reads the local nuvlaedge-status file

        Returns:
            dict: content of the file, or empty dict in case it doesn't exist
        """

        try:
            with open(FILE_NAMES.NUVLAEDGE_STATUS_FILE) as ns:
                return json.load(ns)
        except FileNotFoundError:
            return {}

    def get_node_role_from_status(self) -> str or None:
        """
        Look up the local nuvlaedge-status file and take the cluster-node-role value from
        there

        :return: node role
        """

        return self.get_local_nuvlaedge_status().get('cluster-node-role')

    @staticmethod
    def read_commissioning_file() -> dict:
        """
        Reads the current content of the commissioning file from the local shared volume

        :return: last commissioning content
        """
        try:
            with FILE_NAMES.COMMISSIONING_FILE.open('r') as file:
                commission_payload = json.load(file)
        except FileNotFoundError:
            commission_payload = {}

        return commission_payload

    def needs_cluster_commission(self) -> dict:
        """
        Checks if the commissioning needs to carry cluster information

        :return: commission-ready cluster info
        """

        cluster_info = self.coe_client.get_cluster_info(
            default_cluster_name=f'cluster_{self.nuvlaedge_id}')

        node_info = self.coe_client.get_node_info()
        node_id = self.coe_client.get_node_id(node_info)

        # we only commission the cluster when the NuvlaEdge status
        # has already been updated with its "node-id"
        nuvlaedge_status = self.get_local_nuvlaedge_status()

        if not cluster_info:
            # it is not a manager but...
            if node_id and node_id == nuvlaedge_status.get('node-id'):
                # it is a worker, and NB status is aware of that, so we can update
                # the cluster with it
                return {
                    "cluster-worker-id": node_id,
                }
            else:
                return {}

        if nuvlaedge_status.get('node-id') in cluster_info.get('cluster-managers', []) \
                and node_id == nuvlaedge_status.get('node-id'):
            return cluster_info

        return {}

    def get_compute_endpoint(self, vpn_ip: str) -> tuple:
        """
        Find the endpoint and port of the Compute API

        :returns tuple (api_endpoint, port)
        """
        coe_api_ip, coe_api_port = self.coe_client.get_api_ip_port()

        api_endpoint = None
        if vpn_ip:
            api_endpoint = f"https://{vpn_ip}:{coe_api_port}"
        elif coe_api_ip and coe_api_port:
            api_endpoint = f"https://{coe_api_ip}:{coe_api_port}"

        return api_endpoint, coe_api_port

    def needs_partial_decommission(self, minimum_payload: dict, full_payload: dict,
                                   old_payload: dict):
        """
        For workers, sets the "remove" attr to instruct the partial decommission

        :param minimum_payload: base commissioning payload for request
        :param full_payload: full payload
        :param old_payload: payload from previous commissioning
        :return:
        """

        if self.get_node_role_from_status() != "worker":
            return

        full_payload['removed'] = \
            self.coe_client.get_partial_decommission_attributes()
        if full_payload['removed'] != old_payload.get('removed', []):
            minimum_payload['removed'] = full_payload['removed']

        # remove the keys from the commission payload, to avoid confusion on the server
        # side
        for attr in minimum_payload.get('removed', []):
            try:
                full_payload.pop(attr)
                minimum_payload.pop(attr)
            except KeyError:
                pass

    @staticmethod
    def commissioning_attr_has_changed(current: dict, old: dict, attr_name: str,
                                       payload: dict,
                                       compare_with_nb_resource: bool = False):
        """
        Compares the current attribute value with the old one, and if different, adds it
        to the commissioning payload

        Args:
            current (dict): current commissioning attributes
            old (dict): previous commissioning attributes
            attr_name (str): name of the attribute to be compared
            payload (dict): minimum commissioning payload
            compare_with_nb_resource (bool): if True, will lookup the local .context file
            and check if attr has changed. NOTE: this flag make the check ignore whatever
            the previous commission was
        """

        if compare_with_nb_resource:
            with FILE_NAMES.CONTEXT.open('r') as file:
                # overwrite the old commissioning value with the one from the NB resource
                # (source of truth)
                old_value = json.load(file).get(attr_name)
                if old_value:
                    old[attr_name] = old_value

        if isinstance(current[attr_name], str):
            if current[attr_name] != old.get(attr_name):
                payload[attr_name] = current[attr_name]
        elif isinstance(current[attr_name], list):
            if sorted(current[attr_name]) != sorted(old.get(attr_name, [])):
                payload[attr_name] = current[attr_name]

    def try_commission(self):
        """ Checks whether any of the system configurations have changed
        and if so, returns True or False """
        cluster_join_tokens = self.coe_client.get_join_tokens()
        cluster_info = self.needs_cluster_commission()

        # initialize the commissioning payload
        commission_payload = cluster_info.copy()
        old_commission_payload = self.read_commissioning_file()
        minimum_commission_payload = {} if cluster_info.items() <= old_commission_payload.items() \
                                     else cluster_info.copy()

        my_vpn_ip = self.telemetry_instance.get_vpn_ip()
        api_endpoint, _ = self.get_compute_endpoint(my_vpn_ip)
        infra_service = self.coe_client.define_nuvla_infra_service(api_endpoint,
                                                                   *self.get_tls_keys())

        # 1st time commissioning the IS, so we need to also pass the keys, even if they
        # haven't changed
        infra_diff = {k: v for k, v in infra_service.items() if v != old_commission_payload.get(k)}

        if self.coe_client.infra_service_endpoint_keyname in \
                old_commission_payload:
            minimum_commission_payload.update(infra_diff)
        else:
            minimum_commission_payload.update(infra_service)

        commission_payload.update(infra_service)

        # FIXME: ATM, it isn't clear whether these will make sense for k8s. If
        #  they do, then this block should be moved to an abstractmethod of the
        #  COEClient.
        if len(cluster_join_tokens) > 1:
            self.swarm_token_diff(cluster_join_tokens[0], cluster_join_tokens[1])
            commission_payload.update({
                self.coe_client.join_token_manager_keyname: cluster_join_tokens[0],
                self.coe_client.join_token_worker_keyname: cluster_join_tokens[1]
            })

            self.commissioning_attr_has_changed(
                commission_payload,
                old_commission_payload,
                self.coe_client.join_token_manager_keyname,
                minimum_commission_payload)
            self.commissioning_attr_has_changed(
                commission_payload,
                old_commission_payload,
                self.coe_client.join_token_worker_keyname,
                minimum_commission_payload)

        self.get_nuvlaedge_capabilities(commission_payload)
        # capabilities should always be commissioned when infra is also being commissioned
        if any(k in minimum_commission_payload for k in infra_service):
            minimum_commission_payload['capabilities'] = \
                commission_payload.get('capabilities', [])
        else:
            self.commissioning_attr_has_changed(
                commission_payload, old_commission_payload,
                "capabilities", minimum_commission_payload,
                compare_with_nb_resource=True)

        # if this node is a worker, them we must force remove some assets
        self.needs_partial_decommission(minimum_commission_payload, commission_payload,
                                        old_commission_payload)

        if self.do_commission(minimum_commission_payload):
            self.write_file(FILE_NAMES.COMMISSIONING_FILE,
                            commission_payload,
                            is_json=True)

    def build_vpn_credential_search_filter(self, vpn_server_id):
        """ Simply build the API query for searching this NuvlaEdge's VPN credential

        :param vpn_server_id: ID of the VPN server
        :return str
        """

        return f'method="create-credential-vpn-nuvlabox" and ' \
               f'vpn-common-name="{self.nuvlaedge_id}" and parent="{vpn_server_id}"'

    def validate_local_vpn_credential(self, online_vpn_credential: dict):
        """
        When the VPN credential exists in Nuvla, this function checks whether the local
        copy of that credential matches. If it does not, issue a VPN recommissioning

        :param online_vpn_credential: VPN credential resource received from Nuvla
        :return:
        """
        local_vpn_credential = {}

        with FILE_NAMES.VPN_CREDENTIAL.open('r') as file:
            try:
                local_vpn_credential = json.load(file)
            except Exception as e:
                self.logger.error(f'Failed to read vpn credential files ({e}). Recommissioning.')
                self.commission_vpn()
                FILE_NAMES.VPN_CREDENTIAL.unlink(True)
                return

        if online_vpn_credential['updated'] != local_vpn_credential['updated']:
            self.logger.warning(f"VPN credential has been modified in Nuvla at "
                                f"{online_vpn_credential['updated']}. Recommissioning")
            # Recommission
            self.commission_vpn()
            FILE_NAMES.VPN_CREDENTIAL.unlink(True)

        elif not util.file_exists_and_not_empty(FILE_NAMES.VPN_CLIENT_CONF_FILE):
            self.logger.warning("OpenVPN configuration not available. Recommissioning")

            # Recommission
            self.commission_vpn()
            FILE_NAMES.VPN_CREDENTIAL.unlink(True)

        # else, do nothing because nothing has changed

    def check_vpn_client_state(self):
        exists = None
        running = None
        try:
            running = self.coe_client.is_vpn_client_running()
            exists = True
        except docker.errors.NotFound:
            exists = False
        return exists, running

    def fix_vpn_credential_mismatch(self, online_vpn_credential: dict):
        """
        When a VPN credential exists in Nuvla but not locally, there is a mismatch to be
        investigated. This function will double-check the local VPN client state,
        re-commission the VPN credential if needed, and finally save the right VPN
        credential locally for future reference

        :param online_vpn_credential: VPN credential resource received from Nuvla
        :return:
        """
        vpn_client_exists, vpn_client_running = self.check_vpn_client_state()

        if vpn_client_running and self.telemetry_instance.get_vpn_ip():
            # just save a copy of the VPN credential locally
            self.write_file(FILE_NAMES.VPN_CREDENTIAL, online_vpn_credential, is_json=True)
            self.logger.info(f"VPN client is currently running. "
                             f"Saving VPN credential locally at {FILE_NAMES.VPN_CREDENTIAL}")
        elif vpn_client_exists:
            # there is a VPN credential in Nuvla, but not locally, and the VPN client
            # is not running maybe something went wrong, just recommission
            self.logger.warning("VPN client is either not running or missing its configuration. "
                                "Forcing VPN recommissioning...")
            self.commission_vpn()

    def watch_vpn_credential(self, vpn_is_id=None):
        """ Watches the VPN credential in Nuvla for changes

        :param vpn_is_id: VPN server ID
        """

        if not vpn_is_id:
            return

        vpn_client_exists, _ = self.check_vpn_client_state()
        if not vpn_client_exists:
            self.logger.info("VPN client container doesn't exist. Do nothing")
            return

        search_filter = self.build_vpn_credential_search_filter(vpn_is_id)
        self.logger.debug("Watching VPN credential in Nuvla...")
        try:
            credential_id = self.api().search("credential",
                                              filter=search_filter,
                                              last=1).resources[0].id
            self.logger.debug("Found VPN credential ID %s" % credential_id)
        except IndexError:
            credential_id = None

        if not credential_id:
            # If a VPN credential cannot be found on Nuvla, then it is either in the
            # process of being created or it has been removed from Nuvla
            self.logger.info("VPN server is set but cannot find VPN credential in Nuvla. "
                             "Commissioning VPN...")

            if util.file_exists_and_not_empty(FILE_NAMES.VPN_CREDENTIAL):
                self.logger.warning("NOTE: VPN credential exists locally, so it was removed from Nuvla")

            self.commission_vpn()
        else:
            vpn_credential_nuvla = self.api()._cimi_get(credential_id)

            # IF there is a VPN credential in Nuvla:
            #  - if we also have one locally, BUT is different, then recommission
            if util.file_exists_and_not_empty(FILE_NAMES.VPN_CREDENTIAL):
                self.validate_local_vpn_credential(vpn_credential_nuvla)
            else:
                # - IF we don't have it locally, but there's one in Nuvla, then:
                #     - IF the vpn-client is already running, then all is good, just
                #     save the VPN credential locally
                self.logger.warning("VPN credential exists in Nuvla, but not locally")
                self.fix_vpn_credential_mismatch(vpn_credential_nuvla)

    def set_immutable_ssh_key(self):
        """
        Takes a public SSH key from env and adds it to the installing host user.
        This is only done once, at installation time.

        :return:
        """

        if path.exists(self.ssh_flag):
            self.logger.debug("Immutable SSH key has already been processed at "
                              "installation time")
            with open(self.ssh_flag) as sshf:
                original_ssh_key = sshf.read()
                if self.ssh_pub_key != original_ssh_key:
                    self.logger.warning(f'Received new SSH key but the original '
                                        f'{original_ssh_key} is immutable.Ignoring')
            return

        event = {
            "category": "action",
            "content": {
                "resource": {
                    "href": self.nuvlaedge_id
                },
                "state": "Unknown problem while setting immutable SSH key"
            },
            "severity": "high",
            "timestamp": datetime.utcnow().strftime(self.nuvla_timestamp_format)
        }

        if self.ssh_pub_key and self.installation_home:
            ssh_folder = f"{self.hostfs}{self.installation_home}/.ssh"
            if not path.exists(ssh_folder):
                event['content']['state'] = f"Cannot set immutable SSH key because " \
                                            f"{ssh_folder} does not exist"

                self.push_event(event)
                return

            with FILE_NAMES.CONTEXT.open('r') as file:
                nb_owner = json.load(file).get('owner')

            event_owners = [nb_owner, self.nuvlaedge_id] if nb_owner \
                else [self.nuvlaedge_id]
            event['acl'] = {'owners': event_owners}

            self.logger.info(f'Setting immutable SSH key {self.ssh_pub_key} for {self.installation_home}')
            try:
                with util.timeout(10):
                    if not self.coe_client.install_ssh_key(self.ssh_pub_key,
                                                           self.installation_home):
                        return
            except Exception as e:
                msg = f'An error occurred while setting immutable SSH key: {str(e)}'
                self.logger.error(msg)
                event['content']['state'] = msg
                self.push_event(event)

            self.write_file(self.ssh_flag, self.ssh_pub_key)

    def run(self):
        """
        Threads the commissioning cycles, so that they don't interfere with the main
        telemetry cycle
        """
        while True:
            try:
                self.try_commission()
            except RuntimeError:
                self.logger.exception('Error while trying to commission NuvlaEdge')
            time.sleep(self.refresh_period)
