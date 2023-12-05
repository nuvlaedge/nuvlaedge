from typing import Optional

from base import NuvlaResourceBase
from nuvla_id import NuvlaID


class CredentialResource(NuvlaResourceBase):
    method:                 Optional[str] = None
    vpn_certificate:        Optional[str] = None
    vpn_certificate_owner:  Optional[str] = None
    vpn_common_name:        Optional[NuvlaID] = None
    vpn_intermediate_ca:    Optional[str] = None
