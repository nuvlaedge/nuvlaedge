"""
    NuvlaEdge data structures module
"""
from typing import Optional

from pydantic import Field

from nuvlaedge.agent.workers.monitor import BaseDataStructure


class InstallationParametersData(BaseDataStructure):
    """ Provides a standard structure for installation parameters data """

    project_name: Optional[str] = Field(None, alias='project-name')
    environment: Optional[list[str]] = None
    working_dir: Optional[str] = Field(None, alias='working-dir')
    config_files: Optional[list[str]] = Field(None, alias='config-files')


class NuvlaEdgeData(BaseDataStructure):
    """ Provides a standard structure for generic NuvlaEdge data """

    nuvlaedge_engine_version:   str | None = Field(None, alias='nuvlabox-engine-version')
    installation_home:          str | None = Field(None, alias='host-user-home')

    # Host node information
    operating_system:           str | None = Field(None, alias='operating-system')
    architecture:               str | None = None
    hostname:                   str | None = None
    last_boot:                  str | None = Field(None, alias='last-boot')
    container_plugins:          list[str] | None = Field(None, alias='container-plugins')

    installation_parameters:    InstallationParametersData | None = Field(None, alias='installation-parameters')

    components:                 list[str] | None = None
