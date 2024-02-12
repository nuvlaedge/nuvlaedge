import logging
import dotenv

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaEdgeSession, NuvlaApiKeyTemplate
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.common.file_operations import read_file, write_file
from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger
from nuvlaedge.common.constant_files import FILE_NAMES, LEGACY_FILES, LegacyFileConstants


logger: logging.Logger = logging.getLogger(__name__)


def _build_commissioning_data():
    ...


def _extract_nuvla_configuration() -> tuple[str, bool]:
    _endpoint = 'nuvla.io'
    _verify = True

    nuvla_conf = read_file(LEGACY_FILES.NUVLAEDGE_NUVLA_CONFIGURATION)
    if nuvla_conf is None:
        logger.error("No Nuvla configuration found")
        return _endpoint, _verify

    try:
        nuvla_conf = nuvla_conf.split('\n')
        _endpoint = nuvla_conf[0].replace("NUVLA_ENDPOINT=", "")
        _verify = bool(nuvla_conf[1].replace("NUVLA_ENDPOINT_INSECURE=", "").lower())

    except Exception as e:
        logger.debug(f"Error reading Nuvla configuration: {e}, returning default values")
        return 'nuvla.io', True

    return _endpoint, _verify


def _extract_credentials() -> tuple[str, str]:
    credentials = read_file(LEGACY_FILES.CREDENTIALS, decode_json=True)
    return credentials.get('api-key', ''), credentials.get('secret-key', '')


def _build_nuvlaedge_session():
    """ Extracts data from the legacy configuration and builds the new session file

    We need to extract the session data from the legacy configuration and build the new session file. The required data
    is:
        - endpoint
        - verify
        - credentials
        - nuvlaedge-uuid

    Returns:
        None
    """
    # Nuvla information extracted from .nuvla-configuration
    endpoint, verify = _extract_nuvla_configuration()

    # Extract credentials
    api_key, secret_key = _extract_credentials()

    # Extract nuvlaedge-uuid
    context = read_file(LEGACY_FILES.CONTEXT, decode_json=True)
    nuvlaedge_uuid = context.get('id', '')
    nuvlaedge_status_uuid = context.get('nuvlabox-status', None)

    # Build the new session file
    session = NuvlaEdgeSession(endpoint=endpoint,
                               verify=verify,
                               credentials=NuvlaApiKeyTemplate(key=api_key, secret=secret_key),
                               nuvlaedge_uuid=NuvlaID(nuvlaedge_uuid),
                               nuvlabox_status_uuid=NuvlaID(nuvlaedge_status_uuid) if nuvlaedge_status_uuid else None
                               )

    # Write the session file
    write_file(session, FILE_NAMES.NUVLAEDGE_SESSION)


def _build_vpn_config():
    ...


def _need_legacy_config_transformation():
    if FILE_NAMES.root_fs.exists():
        logger.info("New root file system structure found, assuming new configuration format already in place")
        return False
    logger.info("Legacy root file system structure found, assuming legacy configuration format, transformation needed")

    # Start by creating the new root file system structure
    FILE_NAMES.root_fs.mkdir(parents=True)
    FILE_NAMES.PERIPHERALS_FOLDER.mkdir(parents=True)
    FILE_NAMES.VPN_FOLDER.mkdir(parents=True)

    return True


def transform_legacy_config():

    if not _need_legacy_config_transformation():
        logger.debug("Configuration up to date with new format")
        return

    logger.info('Transforming legacy configuration to new format')

