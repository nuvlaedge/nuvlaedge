from dataclasses import dataclass


@dataclass(frozen=True)
class Constants:
    # FORMATS
    DATETIME_FORMAT: str = "%m%d%Y%H%M%S"
    NUVLA_TIMESTAMP_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"

    # Timeouts
    NETWORK_TIMEOUT: int = 10

    # Intervals
    REFRESH_INTERVAL: int = 60  # Default update interval of nuvlabox-status res
    HEARTBEAT_INTERVAL: int = 20  # Default heartbeat interval

    # Resources names
    PERIPHERAL_RES_NAME: str = 'nuvlabox-peripheral'
    NUVLAEDGE_RES_NAME: str = 'nuvlabox'
    NUVLAEDGE_STATUS_RES_NAME: str = 'nuvlabox-status'

    # Others
    PERIPHERAL_SCHEMA_VERSION: int = 2

    # Host System Paths
    HOST_FS: str = "/rootfs"
    SWARM_NODE_CERTIFICATE: str = f"{HOST_FS}/var/lib/docker/swarm/certificates/swarm-node.crt"

    # Timed actions retries
    TIMED_ACTIONS_TRIES: int = 3

    # NuvlaEdge Constants
    FALLBACK_IMAGE = 'sixsq/nuvlaedge:latest'

    # COE Constants
    DOCKER_SOCKET_FILE_DEFAULT = '/var/run/docker.sock'


CTE: Constants = Constants()
