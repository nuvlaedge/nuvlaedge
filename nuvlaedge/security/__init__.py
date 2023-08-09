from datetime import datetime
import logging

from pydantic import BaseModel

from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
from nuvlaedge.security.security import Security

logger: logging.Logger = logging.getLogger()


def main():
    parse_arguments_and_initialize_logging('security')
    logger.info('Starting vulnerabilities scan module')

    scanner: Security = Security()

    logger.info('Starting NuvlaEdge security scan')

    if scanner.settings.external_db and scanner.nuvla_endpoint and \
            (datetime.utcnow() - scanner.previous_external_db_update).total_seconds() >\
            scanner.settings.external_db_update_period:
        logger.info('Checking for updates on the vulnerability DB')
        scanner.update_vulscan_db()

    logger.info('Running vulnerability scan')
    scanner.run_scan()


if __name__ == '__main__':
    main()
