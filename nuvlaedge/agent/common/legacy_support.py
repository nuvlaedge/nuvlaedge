import logging

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaEdgeSession, NuvlaApiKeyTemplate
from nuvlaedge.agent.nuvla.resources import NuvlaID
from nuvlaedge.common.file_operations import read_file, write_file, copy_file
from nuvlaedge.common.constant_files import FILE_NAMES, LEGACY_FILES


logger: logging.Logger = logging.getLogger()


def _extract_nuvla_configuration() -> tuple[str, bool]:
    _endpoint = 'nuvla.io'
    _insecure = True

    nuvla_conf = read_file(LEGACY_FILES.NUVLAEDGE_NUVLA_CONFIGURATION)
    if nuvla_conf is None:
        logger.error("No Nuvla configuration found")
        return _endpoint, _insecure

    try:
        nuvla_conf = nuvla_conf.split('\n')
        _endpoint = nuvla_conf[0].replace("NUVLA_ENDPOINT=", "")
        _insecure = bool(nuvla_conf[1].replace("NUVLA_ENDPOINT_INSECURE=", "").lower())

    except Exception as e:
        logger.debug(f"Error reading Nuvla configuration: {e}, returning default values")
        return 'nuvla.io', True

    return _endpoint, _insecure


def _extract_credentials() -> tuple[str, str]:
    credentials = read_file(LEGACY_FILES.ACTIVATION_FLAG, decode_json=True)
    return credentials.get('api-key', ''), credentials.get('secret-key', '')


def _build_nuvlaedge_session():
    """ Extracts data from the legacy configuration and builds the new session file

    We need to extract the session data from the legacy configuration and build the new session file. The required data
    is:
        - endpoint
        - insecure
        - credentials
        - nuvlaedge-uuid

    Returns:
        None
    """
    # Nuvla information extracted from .nuvla-configuration
    endpoint, insecure = _extract_nuvla_configuration()

    # Extract credentials
    api_key, secret_key = _extract_credentials()

    # Extract nuvlaedge-uuid
    context = read_file(LEGACY_FILES.CONTEXT, decode_json=True)
    nuvlaedge_uuid = context.get('id', '')
    nuvlaedge_status_uuid = context.get('nuvlabox-status', None)

    # Build the new session file
    session = NuvlaEdgeSession(endpoint=endpoint,
                               insecure=insecure,
                               credentials=NuvlaApiKeyTemplate(key=api_key, secret=secret_key),
                               nuvlaedge_uuid=NuvlaID(nuvlaedge_uuid) if nuvlaedge_uuid else None,
                               nuvlabox_status_uuid=NuvlaID(nuvlaedge_status_uuid) if nuvlaedge_status_uuid else None
                               )

    # Write the session file
    write_file(session, FILE_NAMES.NUVLAEDGE_SESSION)


def _build_vpn_config():
    """ Extract data from legacy configuration and build the new VPN configuration """
    # Extract keys and csr
    copy_file(LEGACY_FILES.VPN_KEY_FILE, FILE_NAMES.VPN_KEY_FILE)
    copy_file(LEGACY_FILES.VPN_CSR_FILE, FILE_NAMES.VPN_CSR_FILE)

    # Extract the VPN configuration
    copy_file(LEGACY_FILES.VPN_CLIENT_CONF_FILE, FILE_NAMES.VPN_CLIENT_CONF_FILE)

    # Copy the VPN credential structure and let the handler recreate the session
    copy_file(LEGACY_FILES.VPN_CREDENTIAL, FILE_NAMES.VPN_CREDENTIAL)

    # Copy VPN IP address file
    copy_file(LEGACY_FILES.VPN_IP_FILE, FILE_NAMES.VPN_IP_FILE)


def _need_legacy_config_transformation():
    if FILE_NAMES.root_fs.exists() and FILE_NAMES.NUVLAEDGE_SESSION.exists():
        logger.info("New root file system structure found, assuming new configuration format already in place")
        return False

    if not LEGACY_FILES.ACTIVATION_FLAG.exists():
        logger.debug("No legacy activation flag found, couldn't find legacy configuration, nor new. "
                     "NuvlaEdge must be new")
        return False

    logger.info("Legacy root file system structure found, assuming legacy configuration format, transformation needed")

    # Start by creating the new root file system structure
    FILE_NAMES.root_fs.mkdir(parents=True, exist_ok=True)
    FILE_NAMES.PERIPHERALS_FOLDER.mkdir(parents=True, exist_ok=True)
    FILE_NAMES.VPN_FOLDER.mkdir(parents=True, exist_ok=True)

    return True


def transform_legacy_config_if_needed():

    if not _need_legacy_config_transformation():
        logger.info("Configuration up to date with new format")
        return

    # There is no way of being sure if the commissioning data is really the last one,
    # so we act as if the NuvlaEdge was never commissioned before and let the agent
    # update all the commissioning data.
    logger.info('Transforming legacy configuration to new format')

    # Extract the NuvlaEdge session data
    _build_nuvlaedge_session()

    # Extract the VPN configuration. The VPN configuration (if exists) is required to be parsed
    # to prevent the recreation of the keys
    _build_vpn_config()


