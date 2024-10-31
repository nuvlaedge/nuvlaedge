"""
This file gathers general utilities demanded by most of the classes such as a command executor
"""

import base64
import hashlib
import os
import logging
import signal

from contextlib import contextmanager
from subprocess import (Popen, run, PIPE, TimeoutExpired,
                        SubprocessError, STDOUT, CompletedProcess)

from nuvlaedge.common.constants import CTE
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger

from pyaes import AESModeOfOperationCBC as _Cbc, Encrypter as _Enc, Decrypter as _Dec


base_label = 'nuvlaedge.component=True'
default_project_name = 'nuvlaedge'
compose_project_name = os.getenv('COMPOSE_PROJECT_NAME', default_project_name)
compute_api_service_name = 'compute-api'
compute_api = compose_project_name + '-' + compute_api_service_name
job_engine_service_name = 'job-engine-lite'
vpn_client_service_name = 'vpn-client'
fallback_image = CTE.FALLBACK_IMAGE

COMPUTE_API_INTERNAL_PORT = 5000


logger: logging.Logger = get_nuvlaedge_logger(__name__)


def extract_nuvlaedge_version(image_name: str) -> str:
    try:
        # First, try to extract the version form the image name
        return image_name.split(':')[-1]
    except Exception as ex:
        logger.info(f'Cannot extract nuvlaedge version from image {image_name}', exc_info=ex)

    try:
        import pkg_resources
        return pkg_resources.get_distribution("nuvlaedge").version
    except Exception as ex:
        logger.warning('Cannot retrieve NuvlaEdge version', exc_info=ex)
        return ''


def str_if_value_or_none(value):
    return str(value) if value else None


def execute_cmd(command: list[str], method_flag: bool = True) -> dict | CompletedProcess | None:
    """
    Shell wrapper to execute a command
    Args:
        command: command to execute
        method_flag: flag to switch between run and Popen command execution

    Returns: all outputs

    """

    try:
        if method_flag:
            return run(command, stdout=PIPE, stderr=STDOUT, encoding='UTF-8')

        with Popen(command, stdout=PIPE, stderr=PIPE) as shell_pipe:
            stdout, stderr = shell_pipe.communicate()

            return {'stdout': stdout,
                    'stderr': stderr,
                    'returncode': shell_pipe.returncode}

    except ValueError as ex:
        logger.error(f"Invalid arguments executed: {ex}")

    except TimeoutExpired as ex:
        logger.error(f"Timeout {ex} expired waiting for command: {command}")

    except SubprocessError as ex:
        logger.error(f"Exception not identified: {ex}")

    except OSError as ex:
        logger.error(f"Trying to execute non existent file: {ex}")

    return None


def raise_timeout(signum, frame):
    raise TimeoutError


@contextmanager
def timeout(time):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(time)

    try:
        yield
    finally:
        # Unregister the signal, so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


# pragma: no cover
VPN_CONFIG_TEMPLATE: str = """client

dev ${vpn_interface_name}
dev-type tun
nobind

# Certificate Configuration
# CA certificate
<ca>
${vpn_ca_certificate}
${vpn_intermediate_ca_is}
${vpn_intermediate_ca}
</ca>

# Client Certificate
<cert>
${vpn_certificate}
</cert>

# Client Key
<key>
${nuvlaedge_vpn_key}
</key>

# Shared key
<tls-crypt>
${vpn_shared_key}
</tls-crypt>

remote-cert-tls server

verify-x509-name "${vpn_common_name_prefix}" name-prefix

script-security 2
up /opt/nuvlaedge/scripts/vpn-client/get_ip.sh

auth-nocache
auth-retry nointeract

ping 60
ping-restart 120
compress lz4

${vpn_endpoints_mapped}

${vpn_extra_config}
"""


def nuvla_support_new_container_stats(nuvla_client):

    def get_attrs(data, prefix=''):
        keys = []
        for d in data:
            name = d.get('name', '?')
            if prefix:
                name = prefix + '.' + name
            keys.append(name)
            ct = d.get('child-types')
            if ct:
                keys += get_attrs(ct, name)
        return keys

    try:
        resp = nuvla_client.nuvlaedge_client.get('resource-metadata/nuvlabox-status-2')
        attrs = get_attrs(resp.data['attributes'])
        return 'resources.container-stats.item.cpu-usage' in attrs
    except Exception as e:
        logger.error(f'Failed to find if Nuvla support new container stats. Defaulting to False: {e}')
        return False


def _irs_key(base, suffix=''):
    base = base.rsplit('/', 1)[-1] if base else ''
    return hashlib.sha256((base + ':' + suffix).encode()).digest()


def get_irs(base, k, s):
    rand = os.urandom(16)
    enc = _Enc(_Cbc(_irs_key(base), rand))
    return base64.b64encode(rand + enc.feed(k + ':' + s) + enc.feed())


def _from_irs(base, irs, suffix=''):
    data = base64.b64decode(irs)
    dec = _Dec(_Cbc(_irs_key(base, suffix), data[:16]))
    return tuple((dec.feed(data[16:]) + dec.feed()).decode().split(':', 1))


def from_irs(base, irs, suffix=''):
    try:
        return _from_irs(base, irs, suffix)
    except Exception:
        msg = 'Failed to decode irs'
        logger.error(msg)
        logger.debug(msg, exc_info=True)
        raise RuntimeError(msg) from None

