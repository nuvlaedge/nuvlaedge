# -*- coding: utf-8 -*-

""" NuvlaEdge Activation

It takes care of activating a new NuvlaEdge
"""
import json
import logging
import time

import requests

from nuvla.api.models import CimiResource

from nuvlaedge.common.constant_files import FILE_NAMES

from nuvlaedge.agent.common.nuvlaedge_common import NuvlaEdgeCommon
from nuvlaedge.agent.orchestrator import COEClient


class Activate(NuvlaEdgeCommon):
    """ The Activate class, which includes all methods and
    properties necessary to activate a NuvlaEdge

    Attributes:
        data_volume: path to shared NuvlaEdge data
    """

    def __init__(self,
                 coe_client: COEClient,
                 data_volume: str):
        """
        Constructs an Activation object
        """

        super().__init__(coe_client=coe_client, shared_data_volume=data_volume)

        self.activate_logger: logging.Logger = logging.getLogger(__name__)
        self.user_info = {}
        self.nuvlaedge_resource: CimiResource | None = None

    def activation_is_possible(self):
        """ Checks for any hints of a previous activation
        or any other conditions that might influence the
        first time activation of the NuvlaEdge

        :return boolean and user info is available"""

        try:
            self.user_info = self.read_json_file(FILE_NAMES.ACTIVATION_FLAG)

            self.activate_logger.warning("{} already exists. Re-activation is not possible!".format(FILE_NAMES.ACTIVATION_FLAG))
            self.activate_logger.info("NuvlaEdge credential: {}".format(self.user_info["api-key"]))
            return False, self.user_info
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            # file doesn't exist yet,
            # But maybe the API was provided via env?
            api_key, api_secret = self.get_api_keys()
            if api_key and api_secret:
                self.activate_logger.info(f'Found API key set in environment, with key value {api_key}')
                self.user_info = {
                    "api-key": api_key,
                    "secret-key": api_secret
                }

                self.write_json_to_file(FILE_NAMES.ACTIVATION_FLAG, self.user_info)

                return False, self.user_info

            return True, self.user_info

    def activate(self):
        """ Makes the anonymous call to activate the NuvlaEdge """

        self.activate_logger.info('Activating "{}"'.format(self.nuvlaedge_id))

        try:
            self.user_info = self.api()._cimi_post('{}/activate'.format(self.nuvlaedge_id))
        except requests.exceptions.SSLError:
            self.shell_execute(["timeout", "3s", "/lib/systemd/systemd-timesyncd"])
            self.user_info = self.api()._cimi_post('{}/activate'.format(self.nuvlaedge_id))
        except requests.exceptions.ConnectionError as conn_err:
            self.activate_logger.error("Can not reach out to Nuvla at {}. Error: {}"
                                       .format(self.nuvla_endpoint, conn_err))
            raise

        timeout = 2 #seconds
        maxtrials = 5

        trials = 0
        # Flags that the activation has been done
        while not self.write_json_to_file(FILE_NAMES.ACTIVATION_FLAG, self.user_info):
            trials += 1
            if trials == maxtrials:
                self.logger.error(f'Could not write user info to {FILE_NAMES.ACTIVATION_FLAG}')
                FILE_NAMES.ACTIVATION_FLAG.unlink()
            time.sleep(timeout)

        return self.user_info

    def write_ne_document_file(self):
        """
        Write contextualization file with NE resource content
        """
        self.activate_logger.debug(f'Writing nuvlaedge document to file {FILE_NAMES.CONTEXT}')
        if not self.write_json_to_file(FILE_NAMES.CONTEXT, self.nuvlaedge_resource.data):
            self.activate_logger.error(f'Failed to write nuvlaedge document to file {FILE_NAMES.CONTEXT}')
            return False
        return True

    def read_ne_document_file(self) -> dict:
        """
        Read contextualization file with NE resource content

        :return the content of the file
        """
        self.activate_logger.info(f'NuvlaEdge context file {FILE_NAMES.CONTEXT}')

        current_context = {}
        try:
            current_context = self.read_json_file(FILE_NAMES.CONTEXT)
        except (ValueError, FileNotFoundError):
            self.activate_logger.warning(f"Nuvlaedge document file ({FILE_NAMES.CONTEXT}) doesn't exist or is invalid")
        except Exception as e:
            self.activate_logger.error(f'Failed to read nuvlaedge document file ({FILE_NAMES.CONTEXT}): {e}')

        return current_context

    def fetch_nuvlaedge(self) -> CimiResource:
        """ Retrieve the NuvlaEdge resource from Nuvla """
        self.nuvlaedge_resource = self.api().get(self.nuvlaedge_id)
        return self.nuvlaedge_resource

    def nuvla_login(self):
        self.authenticate(self.api(),
                          self.user_info["api-key"],
                          self.user_info["secret-key"])
