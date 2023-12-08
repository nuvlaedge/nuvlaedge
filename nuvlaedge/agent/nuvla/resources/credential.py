from typing import Optional

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase


class CredentialResource(NuvlaResourceBase):
    method:                 Optional[str] = None
    vpn_certificate:        Optional[str] = None
    vpn_certificate_owner:  Optional[str] = None
    vpn_common_name:        Optional[NuvlaID] = None
    vpn_intermediate_ca:    Optional[str] = None
