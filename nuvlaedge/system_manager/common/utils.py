#!/usr/local/bin/python3.7
# -*- coding: utf-8 -*-

""" Common set of managament methods to be used by
 the different system manager classes """

import os
import logging


data_volume = "/srv/nuvlaedge/shared"
operational_status_file = f'{data_volume}/.status'
operational_status_notes_file = f'{data_volume}/.status_notes'
base_label = "nuvlaedge.component=True"
node_label_key = "nuvlaedge"

compose_project_name = os.getenv('COMPOSE_PROJECT_NAME', 'nuvlaedge')
nuvlaedge_shared_net = compose_project_name + '-shared-network'
nuvlaedge_shared_net_unencrypted = f'{data_volume}/.nuvlabox-shared-net-unencrypted'
overlay_network_service = 'nuvlaedge-ack'

status_degraded = 'DEGRADED'
status_operational = 'OPERATIONAL'
status_unknown = 'UNKNOWN'

tls_sync_file = f"{data_volume}/.tls"

log = logging.getLogger(__name__)


def set_operational_status(status: str, notes: list = []):
    log.debug(f'Write operational status "{status}" to file "{operational_status_file}"')
    with open(operational_status_file, 'w') as s:
        s.write(status)

    try:
        notes_str = '\n'.join(notes)
        log.debug(f'Write operational status notes to file "{operational_status_notes_file}": {notes_str}')
        with open(operational_status_notes_file, 'w') as sn:
            sn.write(notes_str)
    except Exception as e:
        log.warning(f'Failed to write status notes {notes} in {operational_status_notes_file}: {str(e)}')


def status_file_exists() -> bool:
    if os.path.exists(operational_status_file):
        return True

    return False
