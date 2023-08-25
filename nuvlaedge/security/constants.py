from nuvlaedge.common.constant_files import FILE_NAMES

DATE_FORMAT: str = '%d-%b-%Y (%H:%M:%S.%f)'
SECURITY_FOLDER = f'{FILE_NAMES.root_fs}/security/'
VULNERABILITIES_DB = f'{SECURITY_FOLDER}/db/'
APIKEY_FILE: str = f'{FILE_NAMES.root_fs}/.activated'

EXTERNAL_DB_UPDATE_FILE: str = f'{SECURITY_FOLDER}/.vuln-db-update'
EXTERNAL_DB_NAMES_FILE: str = f'{SECURITY_FOLDER}/.file_locations'

VULSCAN_OUT_FILE: str = f'{SECURITY_FOLDER}/nmap-vulscan-out-xml'

DEFAULT_NMAP_DIRECTORY = '/usr/share/nmap/scripts/vulscan/'
NMAP_OUTPUT_FILE = f'{SECURITY_FOLDER}/nmap-vulscan-out-xml'

ONLINE_VULSCAN_DB_PREFIX: str = 'cve.csv.'

TIMEOUT_WAIT_TIME: int = 60

RAW_VULNERABILITIES_GZ: str = f'{DEFAULT_NMAP_DIRECTORY}/raw_vulnerabilities.csv.gz'
RAW_VULNERABILITIES: str = f'{DEFAULT_NMAP_DIRECTORY}/raw_vulnerabilities.csv'

