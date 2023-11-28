import pprint

from nuvlaedge.agent.nuvla.resources.nuvla_id import NuvlaID
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings


class AgentSettings(NuvlaEdgeBaseSettings):
    compose_project_name: str = "nuvlaedge"
    nuvlaedge_uuid: NuvlaID
    nuvlaedge_log_level: str = "INFO"


pprint.pp(AgentSettings())
