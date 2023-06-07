"""
    NuvlaEdge data structures module
"""
from typing import Optional

from pydantic import Field

from nuvlaedge.agent.monitor import BaseDataStructure


class InstallationParametersData(BaseDataStructure):
    """ Provides a standard structure for installation parameters data """

    project_name: Optional[str] = Field(alias='project-name')
    environment: Optional[list[str]]
    working_dir: Optional[str] = Field(alias='working-dir')
    config_files: Optional[list[str]] = Field(alias='config-files')


class NuvlaEdgeData(BaseDataStructure):
    """ Provides a standard structure for generic NuvlaEdge data """

    # Node unique ID provided by Nuvla
    id: str | None

    nuvlaedge_engine_version: str | None = Field(alias='nuvlabox-engine-version')
    installation_home: str | None = Field(alias='host-user-home')

    # Host node information
    operating_system: str | None = Field(alias='operating-system')
    architecture: str | None
    hostname: str | None
    last_boot: str | None = Field(alias='last-boot')
    container_plugins: list[str] | None = Field(alias='container-plugins')

    installation_parameters: InstallationParametersData | None = Field(alias='installation-parameters')

    components: list[str] | None
