# Base definition of Nuvla resources used by NuvlaEdge
from nuvlaedge.agent.nuvla.resources.base import (AutoUpdateNuvlaEdgeTrackedResource,
                                                  NuvlaResourceBase)

# nuvlaedge-status resource
from nuvlaedge.agent.nuvla.resources.nuvlaedge_status import (NuvlaEdgeStatusResource,
                                                              AutoNuvlaEdgeStatusResource)

# nuvlaedge resource
from nuvlaedge.agent.nuvla.resources.nuvlaedge_res import (AutoNuvlaEdgeResource,
                                                           NuvlaEdgeResource,
                                                           State)

# credential resource for the VPN credential
from nuvlaedge.agent.nuvla.resources.credential import (CredentialResource, AutoCredentialResource)

# VPN server infrastructure service resource
from nuvlaedge.agent.nuvla.resources.infrastructure_service import (InfrastructureServiceResource,
                                                                    AutoInfrastructureServiceResource)

# Utility class for ID-UUID handling
from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
