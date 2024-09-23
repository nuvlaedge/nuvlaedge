from dataclasses import dataclass

from nuvlaedge.common.file_operations import read_file


@dataclass(frozen=True)
class Constants:
    # FORMATS
    DATETIME_FORMAT: str = "%m%d%Y%H%M%S"  # Used for file names in the broker

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
    MACHINE_ID: str = ''

    # Timed actions retries
    TIMED_ACTIONS_TRIES: int = 3

    # NuvlaEdge Constants
    FALLBACK_IMAGE = 'sixsq/nuvlaedge:latest'

    # COE Constants
    DOCKER_SOCKET_FILE_DEFAULT = '/var/run/docker.sock'

    DATA_GATEWAY_ENDPOINT = 'data-gateway'
    DATA_GATEWAY_PORT: int = 1883
    DATA_GATEWAY_PING_INTERVAL: int = 90


host_fs = "/rootfs"


def _get_machine_id(root_fs=''):
    for machine_id_filepath in [f'{root_fs}/etc/machine-id', '/etc/machine-id']:
        machine_id = read_file(machine_id_filepath, decode_json=False, warn_on_missing=True)
        if machine_id:
            return machine_id
    return ''


CTE: Constants = Constants(HOST_FS=host_fs, MACHINE_ID=_get_machine_id(host_fs))
