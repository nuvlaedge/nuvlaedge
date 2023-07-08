# -*- coding: utf-8 -*-

""" NuvlaEdge Activation

It takes care of activating a new NuvlaEdge
"""

import logging
import requests

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
                 container_runtime: COEClient,
                 data_volume: str):
        """
        Constructs an Activation object
        """

        super().__init__(container_runtime=container_runtime,
                         shared_data_volume=data_volume)

        self.activate_logger: logging.Logger = logging.getLogger(__name__)
        self.user_info = {}

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
        except FileNotFoundError:
            # file doesn't exist yet,
            # But maybe the API was provided via env?
            api_key, api_secret = self.get_api_keys()
            if api_key and api_secret:
                self.activate_logger.info(f'Found API key set in environment, with key'
                                          f' value {api_key}')
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

        # Flags that the activation has been done
        self.write_json_to_file(FILE_NAMES.ACTIVATION_FLAG, self.user_info)

        return self.user_info

    def create_nb_document_file(self, nuvlaedge_resource: dict) -> dict:
        """ Writes contextualization file with NB resource content

        :param nuvlaedge_resource: nuvlaedge resource data
        :return copy of the old NB resource context which is being overwritten
        """

        self.activate_logger.info('Managing NB context file {}'.format(FILE_NAMES.CONTEXT))

        try:
            current_context = self.read_json_file(FILE_NAMES.CONTEXT)
        except (ValueError, FileNotFoundError):
            self.activate_logger.warning("Writing {} for the first "
                                         "time".format(FILE_NAMES.CONTEXT))
            current_context = {}

        self.write_json_to_file(FILE_NAMES.CONTEXT, nuvlaedge_resource)

        return current_context

    def get_nuvlaedge_info(self):
        """ Retrieves the respective resource from Nuvla """

        return self.api().get(self.nuvlaedge_id).data

    def update_nuvlaedge_resource(self) -> tuple:
        """ Updates the static information about the NuvlaEdge

        :return: current and old NuvlaEdge resources
        """

        self.authenticate(self.api(), self.user_info["api-key"], self.user_info["secret-key"])
        nuvlaedge_resource = self.get_nuvlaedge_info()

        old_nuvlaedge_resource = self.create_nb_document_file(nuvlaedge_resource)

        return nuvlaedge_resource, old_nuvlaedge_resource
