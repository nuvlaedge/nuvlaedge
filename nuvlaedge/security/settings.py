import json

from pydantic import Field

from nuvlaedge.security.constants import DEFAULT_NMAP_DIRECTORY
from nuvlaedge.common.settings_parser import NuvlaConfig


class SecurityConfig(NuvlaConfig):
    external_vulnerabilities_db: str = Field(
        'https://github.com/nuvla/vuln-db/blob/main/databases/all.aggregated.csv.gz?raw=true',
        env='EXTERNAL_CVE_VULNERABILITY_DB')

    external_db_update_interval: int = Field(
        86400,
        env='EXTERNAL_CVE_VULNERABILITY_DB_UPDATE_INTERVAL'
    )

    scan_interval: int = Field(
        1800,
        env='SECURITY_SCAN_INTERVAL'
    )

    slice_size: int = Field(2000, env='DB_SLICE_SIZE')

    vulscan_db_dir: str = Field(DEFAULT_NMAP_DIRECTORY, env='VULSCAN_DB_DIR')

    # Kubernetes Security configuration
    kubernetes_service_host: str = Field('', env='KUBERNETES_SERVICE_HOST')
    namespace: str = Field('nuvlaedge', env='MY_NAMESPACE')
