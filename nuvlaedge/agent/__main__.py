import logging
import socket

from nuvlaedge.common.nuvlaedge_logging import set_logging_configuration

if __name__ == '__main__':
    set_logging_configuration(debug=True, log_level=logging.INFO, log_path='/var/log/nuvlaedge')

from nuvlaedge.agent import main
from nuvlaedge.common.constants import CTE

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info('Setting up agent from main.py')
    socket.setdefaulttimeout(CTE.NETWORK_TIMEOUT)
    main()
