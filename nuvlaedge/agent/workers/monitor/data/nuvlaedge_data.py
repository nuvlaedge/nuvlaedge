"""
    NuvlaEdge data structures module
"""
from typing import Optional

from pydantic import Field

from nuvlaedge.agent.workers.monitor import BaseDataStructure


class InstallationParametersData(BaseDataStructure):
    """ Provides a standard structure for installation parameters data """

    project_name: Optional[str] = None
    environment: Optional[list[str]] = None
    working_dir: Optional[str] = None
    config_files: Optional[list[str]] = None


class NuvlaEdgeData(BaseDataStructure):
    """ Provides a standard structure for generic NuvlaEdge data """

    nuvlabox_engine_version:   str | None = None
    installation_home:          str | None = Field(None, alias='host-user-home')  # KEEP

    # Host node information
    operating_system:           str | None = None
    architecture:               str | None = None
    hostname:                   str | None = None
    last_boot:                  str | None = None
    container_plugins:          list[str] | None = None

    installation_parameters:    InstallationParametersData | None = None

    components:                 list[str] | None = None
