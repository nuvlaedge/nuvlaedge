#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" NuvlaEdge System Manager service

checks requirements and supervises all internal components of the NuvlaEdge

Arguments:

"""
import logging
import os
import signal
import sys
import time
from argparse import ArgumentParser

from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging
import nuvlaedge.system_manager.requirements as MinReq
from nuvlaedge.system_manager.common import utils
from nuvlaedge.system_manager.supervise import Supervise

__copyright__ = "Copyright (C) 2021 SixSq"
__email__ = "support@sixsq.com"

log = logging.getLogger(__name__)
self_sup = Supervise()


def log_threads_stackstraces():
    import sys
    import threading
    import traceback
    import faulthandler

    print_args = dict(file=sys.stderr, flush=True)

    print("\nfaulthandler.dump_traceback()", **print_args)
    faulthandler.dump_traceback()

    print("\nthreading.enumerate()", **print_args)
    for th in threading.enumerate():
        print(th, **print_args)
        traceback.print_stack(sys._current_frames()[th.ident])
    print(**print_args)


def signal_usr1(signum, frame):
    log_threads_stackstraces()


class GracefulShutdown:

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        log.info('Starting on-stop graceful shutdown of the NuvlaEdge...')
        self_sup.container_runtime.launch_nuvlaedge_on_stop(self_sup.on_stop_docker_image)
        sys.exit(0)


on_stop = GracefulShutdown()


def requirements_check(sw_rq: MinReq.SoftwareRequirements,
                       system_rq: MinReq.SystemRequirements,
                       operational_status: list):
    """
    Checks if the NuvlaEdge requirements are met

    :param sw_rq: instance of MinReq.SoftwareRequirements
    :param system_rq: instance of MinReq.SystemRequirements
    :param operational_status: list of tuples (status, status_notes)

    :return:
    """
    sw_rq.not_met = []
    system_rq.not_met = []
    meet_sw_rq = sw_rq.check_sw_requirements()
    meet_hw_rq = system_rq.check_all_hw_requirements()
    if not meet_sw_rq or not meet_hw_rq:
        not_met = sw_rq.not_met + system_rq.not_met
        not_met_msg = "\n\t* " + "\n\t* ".join(not_met) if not_met else ''
        err_msg = f"System does not meet the minimum requirements! {not_met_msg} \n"
        log.warning(err_msg)

        op_status = utils.status_operational if MinReq.SKIP_MINIMUM_REQUIREMENTS else utils.status_degraded
        operational_status.append((op_status, err_msg))

    operational_status += sw_rq.check_sw_optional_requirements()

    if not utils.status_file_exists():
        utils.set_operational_status(utils.status_operational)

        peripherals = '{}/.peripherals'.format(utils.data_volume)

        try:
            # Dynamically create directory for peripheral managers
            os.mkdir(peripherals)
            log.info("Successfully created peripherals directory")
        except FileExistsError:
            log.info("Directory " + peripherals + " already exists")


def main():
    system_requirements = MinReq.SystemRequirements()
    software_requirements = MinReq.SoftwareRequirements()

    while True:
        self_sup.operational_status = []
        requirements_check(software_requirements, system_requirements, self_sup.operational_status)

        # refresh this node's status, to capture any changes in the COE/Cluster configuration
        self_sup.classify_this_node()

        # certificate rotation check
        if self_sup.is_cert_rotation_needed():
            log.info("Rotating NuvlaEdge certificates...")
            self_sup.request_rotate_certificates()

        if self_sup.container_runtime.orchestrator != 'kubernetes':
            # in k8s there are no switched from uncluster - cluster, so there's no need for connectivity check
            self_sup.check_nuvlaedge_docker_connectivity()

            # the Data Gateway comes out of the box for k8s installations
            self_sup.manage_docker_data_gateway()

            # in k8s everything runs as part of a Dep (restart policies are in place), so there's nothing to fix
            self_sup.docker_container_healer()

        log.debug(f'Operational status checks: {self_sup.operational_status}')

        statuses = [s[0] for s in self_sup.operational_status]
        status_notes = [s[-1] for s in self_sup.operational_status]

        if utils.status_degraded in statuses:
            utils.set_operational_status(utils.status_degraded, status_notes)
        elif all([x == utils.status_operational for x in statuses]) or not self_sup.operational_status:
            utils.set_operational_status(utils.status_operational, status_notes)
        else:
            utils.set_operational_status(utils.status_unknown, status_notes)

        time.sleep(15)


def entry():
    signal.signal(signal.SIGUSR1, signal_usr1)

    parse_arguments_and_initialize_logging('System Manager')

    sys.exit(main())


if __name__ == '__main__':
    entry()
