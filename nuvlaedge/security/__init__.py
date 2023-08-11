import os
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

    # If the configuration file is given as an env variable, use the default configuration. Overwritten by env variables
    config_file: str = os.getenv('SECURITY_CONFIG_FILE', '')
    if config_file:
        config: SecurityConfig = SecurityConfig.from_toml(Path(config_file))
    else:
        config = SecurityConfig()

    scanner: Security = Security(config)

    logger.info('Starting NuvlaEdge security scan')

    if scanner.config.external_vulnerabilities_db and scanner.nuvla_endpoint and \
            (datetime.utcnow() - scanner.previous_external_db_update).total_seconds() >\
            scanner.config.external_db_update_interval:
        logger.info('Checking for updates on the vulnerability DB')
        scanner.update_vulscan_db()

    logger.info('Running vulnerability scan')
    scanner.run_scan()


if __name__ == '__main__':
    main()
