import logging
import time
from typing import Optional, Any

from nuvla.api import Api
from nuvla.api.models import CimiCollection

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from .nuvla_id import NuvlaID
from .base import AutoUpdateNuvlaEdgeTrackedResource, NuvlaResourceBase

logger: logging.Logger = get_nuvlaedge_logger(__name__)


class CredentialResource(NuvlaResourceBase):
    """
    This is a partial implementation of the Credential Resource Spec of Nuvla.
    It is only used for NuvlaEdge VPN
    """

    method:                 Optional[str] = None
    vpn_certificate:        Optional[str] = None
    vpn_certificate_owner:  Optional[str] = None
    vpn_common_name:        Optional[NuvlaID] = None
    vpn_intermediate_ca:    Optional[list[str]] = None


class AutoCredentialResource(CredentialResource,
                             AutoUpdateNuvlaEdgeTrackedResource):

    _VPN_CREDENTIAL_FILTER_TEMPLATE: str = ('method="create-credential-vpn-nuvlabox" and '
                                            'vpn-common-name="{nuvlaedge_uuid}" and '
                                            'parent="{vpn_server_id}"')
    _nuvlaedge_id: NuvlaID | None = None
    _vpn_server_id: NuvlaID | None = None

    def __init__(self, nuvlaedge_id: NuvlaID, vpn_server_id: NuvlaID, nuvla_client: Api, **data: Any):
        super().__init__(nuvla_client, **data)
        self._nuvlaedge_id = nuvlaedge_id
        self._vpn_server_id = vpn_server_id

    def _sync(self):
        """ Syncs the VPN credential from NuvlaEdge.

        This method is called by the AutoUpdateNuvlaEdgeTrackedResource class.
        The access to the VPN credential is done through the search using a filter with the NuvlaEdge UUID and the
         VPN server ID.
        """
        _filter = self._VPN_CREDENTIAL_FILTER_TEMPLATE.format(nuvlaedge_uuid=self._nuvlaedge_id,
                                                              vpn_server_id=self._vpn_server_id)

        creds: CimiCollection = self._nuvla_client.search(resource_type="credential",
                                                          filter=_filter,
                                                          last=1)

        if creds.count >= 1:
            cred_data: dict = creds.resources[0].data
            logger.debug(f"VPN credential found in NuvlaEdge with id: {cred_data.get('id')}")
            self._update_fields(cred_data)
            self._is_synced = True
            self._last_update_time = time.perf_counter()

        else:
            logger.debug("VPN credential not found (or present) in Nuvla")

