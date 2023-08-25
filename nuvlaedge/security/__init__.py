import os
import time
from datetime import datetime
import logging
from pathlib import Path

from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.security.security import Security
from nuvlaedge.security.settings import SecurityConfig

logger: logging.Logger = logging.getLogger()


def main():
    parse_arguments_and_initialize_logging('security')
    logger.info('Starting vulnerabilities scan module')

    # If the configuration file is given as an env variable, use the default
    # configuration. Overwritten by env variables
    config_file: str = os.getenv('SECURITY_CONFIG_FILE', '')
    if config_file:
        config: SecurityConfig = SecurityConfig.from_toml(Path(config_file))
    else:
        config = SecurityConfig()

    scanner: Security = Security(config)
    scanner.db_needs_update()

    logger.info('Starting NuvlaEdge security scan')
    scanner.run_scan()


if __name__ == '__main__':
    main()
