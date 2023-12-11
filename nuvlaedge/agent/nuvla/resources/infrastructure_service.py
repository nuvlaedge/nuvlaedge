from typing import Optional

from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase


class InfrastructureServiceResource(NuvlaResourceBase):
    """ Mainly for VPN Server """
    vpn_ca_certificate:    Optional[str] = None
    vpn_intermediate_ca:    Optional[list[str]] = None
    vpn_scope:              Optional[str] = None
    method:                 Optional[str] = None
    vpn_common_name_prefix: Optional[str] = None
    vpn_shared_key:         Optional[str] = None
    vpn_endpoints:          Optional[list[dict]] = None
