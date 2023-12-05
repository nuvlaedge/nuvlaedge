from typing import Optional

from nuvlaedge.agent.nuvla.resources.base import NuvlaResourceBase


class InfrastructureServiceResource(NuvlaResourceBase):
    """ Mainly for VPN Server """
    vpn_ca_certificates:    Optional[str]
    vpn_intermediate_ca:    Optional[str]
    vpn_scope:              Optional[str]
    method:                 Optional[str]
    vpn_common_name_prefix: Optional[str]
    vpn_shared_key:         Optional[str]
    vpn_endpoints:          Optional[list[dict]]
