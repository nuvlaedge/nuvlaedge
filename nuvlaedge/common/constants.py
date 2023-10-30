from dataclasses import dataclass


@dataclass(frozen=True)
class Constants:
    # FORMATS
    DATETIME_FORMAT: str = "%m%d%Y%H%M%S"

    # Timeouts
    NETWORK_TIMEOUT: int = 10

    # Intervals
    REFRESH_INTERVAL: int = 60  # Default update interval of nuvlabox-status res
    HEARTBEAT_INTERVAL: int = 15  # Default heartbeat interval

    # Resources names
    PERIPHERAL_RES_NAME: str = 'nuvlabox-peripheral'
    NUVLAEDGE_RES_NAME: str = 'nuvlabox'
    NUVLAEDGE_STATUS_RES_NAME: str = 'nuvlabox-status'

    # Others
    PERIPHERAL_SCHEMA_VERSION: int = 2


CTE: Constants = Constants()
