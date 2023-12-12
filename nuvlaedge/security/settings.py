import json

from pydantic import Field

from nuvlaedge.security.constants import DEFAULT_NMAP_DIRECTORY
from nuvlaedge.common.settings_parser import NuvlaEdgeBaseSettings


class SecurityConfig(NuvlaEdgeBaseSettings):
    external_vulnerabilities_db: str = Field(
        'https://github.com/nuvla/vuln-db/blob/main/databases/all.aggregated.csv.gz?raw=true',
        alias='EXTERNAL_CVE_VULNERABILITY_DB')

    external_db_update_interval: int = Field(
        86400,
        alias='EXTERNAL_CVE_VULNERABILITY_DB_UPDATE_INTERVAL'
    )

    scan_interval: int = Field(
        1800,
        alias='SECURITY_SCAN_INTERVAL'
    )

    slice_size: int = Field(2000, alias='DB_SLICE_SIZE')

    vulscan_db_dir: str = DEFAULT_NMAP_DIRECTORY

    # Kubernetes Security configuration
    kubernetes_service_host: str = ''
    namespace: str = Field('nuvlaedge', alias='MY_NAMESPACE')
