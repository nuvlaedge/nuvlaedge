# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """

import os
import logging
import secrets

from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.common.file_operations import write_file

base_label = "nuvlaedge.component=True"
node_label_key = "nuvlaedge"

compose_project_name = os.getenv('COMPOSE_PROJECT_NAME', 'nuvlaedge')
nuvlaedge_shared_net = compose_project_name + '-shared-network'
nuvlaedge_shared_net_unencrypted = f'{FILE_NAMES.root_fs}/.nuvlabox-shared-net-unencrypted'
overlay_network_service = compose_project_name + '-ack'

status_degraded = 'DEGRADED'
status_operational = 'OPERATIONAL'
status_unknown = 'UNKNOWN'

tls_sync_file = f"{FILE_NAMES.root_fs}/.tls"

log = logging.getLogger(__name__)


def set_operational_status(status: str, notes: list = []):
    log.debug(f'Write operational status "{status}" to file "{FILE_NAMES.STATUS_FILE}"')
    write_file(status, FILE_NAMES.STATUS_FILE)
    try:
        notes_str = '\n'.join(notes)
        log.debug(f'Write operational status notes to file "{FILE_NAMES.STATUS_NOTES}": {notes_str}')
        write_file(notes_str, FILE_NAMES.STATUS_NOTES)

    except Exception as e:
        log.warning(f'Failed to write status notes {notes} in {FILE_NAMES.STATUS_NOTES}: {str(e)}')


def random_choices(sequence, num=1) -> list:
    return [secrets.choice(sequence) for _ in range(num)]
