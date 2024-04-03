"""
Module for the security scanner class
"""
from contextlib import contextmanager
from datetime import datetime
import signal
import logging
import os
import re
from pathlib import Path
from threading import Event
import time
from subprocess import (run,
                        PIPE,
                        STDOUT,
                        Popen,
                        CompletedProcess,
                        TimeoutExpired,
                        SubprocessError,
                        CalledProcessError)

from xml.etree import ElementTree

from nuvlaedge.agent.nuvla.client_wrapper import NuvlaClientWrapper
from nuvlaedge.common.nuvlaedge_base_model import NuvlaEdgeBaseModel
from nuvlaedge.common.constant_files import FILE_NAMES
from nuvlaedge.security.settings import SecurityConfig
import nuvlaedge.security.constants as cte
from nuvlaedge.common.file_operations import read_file, write_file, file_exists_and_not_empty


@contextmanager
def timeout(t_time):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(t_time)

    yield
    # Unregister the signal, so it won't be triggered
    # if the timeout is not reached.
    signal.signal(signal.SIGALRM, signal.SIG_IGN)


def raise_timeout(signum, frame):
    raise TimeoutError(signum, frame)


logger: logging.Logger = logging.getLogger(__name__)


class VulnerabilitiesInfo(NuvlaEdgeBaseModel):
    product: str
    vulnerability_id: str
    vulnerability_score: float | None = None


class Security:
    """ Security wrapper class """
    def __init__(self, config: SecurityConfig):

        self.config: SecurityConfig = config

        self.agent_api_endpoint: str = 'localhost:5080' if not \
            self.config.kubernetes_service_host else f'agent.{self.config.namespace}'

        self.nuvla_endpoint: str = ''
        self.nuvla_endpoint_insecure: bool = False

        self.wait_for_nuvlaedge_ready()
        self.api: NuvlaClientWrapper | None = None
        self.event: Event = Event()

        self.local_db_last_update = None

        self.vulscan_dbs: list = []
        self.previous_external_db_update: datetime = \
            self.get_previous_external_db_update()

        self.offline_vulscan_db: list = []

        if not Path(cte.VULNERABILITIES_DB).exists():
            Path(cte.VULNERABILITIES_DB).mkdir(parents=True)

        if self.config.vulscan_db_dir:
            self.offline_vulscan_db = [db for db in os.listdir(self.config.vulscan_db_dir) if
                                       db.startswith(cte.ONLINE_VULSCAN_DB_PREFIX)]

    def wait_for_nuvlaedge_ready(self):
        """ Waits on a loop for the NuvlaEdge bootstrap and activation to be accomplished

        :return: nuvla endpoint and nuvla endpoint insecure boolean
        """
        with timeout(cte.TIMEOUT_WAIT_TIME):
            logger.info('Waiting for NuvlaEdge to bootstrap')
            while not os.path.exists(cte.APIKEY_FILE):
                time.sleep(5)

            logger.info('Waiting and searching for Nuvla connection parameters '
                        'after NuvlaEdge activation')

            while not os.path.exists(FILE_NAMES.NUVLAEDGE_SESSION):
                time.sleep(5)

    @staticmethod
    def execute_cmd(command: list[str]) -> dict | CompletedProcess | None:
        """ Shell wrapper to execute a command

        @param command: command to execute
        @return: all outputs
        """
        logger.info(f'Executing command {" ".join(command)}')
        try:
            return run(command, stdout=PIPE, stderr=STDOUT, encoding='UTF-8',
                       check=True)

        except OSError as ex:
            logger.error(f"Trying to execute non existent file: {ex}")

        except ValueError as ex:
            logger.error(f"Invalid arguments executed: {ex}")

        except TimeoutExpired as ex:
            logger.error(f"Timeout {ex} expired waiting for command: {command}")

        except SubprocessError as ex:
            logger.error(f"Exception not identified: {ex}")

        return None

    def get_external_db_as_csv(self):
        """
            Updates or gets the local database from the provided URL
        """

        # Download external DB
        download_command: list = ['curl', '-L',
                                  self.config.external_vulnerabilities_db.lstrip('"').rstrip('"'),
                                  '--output', cte.RAW_VULNERABILITIES_GZ]

        # Uncompress external db
        unzip_command: list = ['gzip', '-d', cte.RAW_VULNERABILITIES_GZ]

        # Split file in smaller files
        split_command: list = ['split', '-u', '-l', '20000', '-d',
                               cte.RAW_VULNERABILITIES,
                               '/usr/share/nmap/scripts/vulscan/cve.csv.']

        try:
            # Download full db
            self.execute_cmd(download_command)

            # Uncompress DB
            self.execute_cmd(unzip_command)

            # Split DB
            self.execute_cmd(split_command)

        except CalledProcessError:
            logger.exception('External database update process returned an error')

        else:

            self.vulscan_dbs: list = \
                sorted([f for f in os.listdir(cte.DEFAULT_NMAP_DIRECTORY)
                        if f.startswith(cte.ONLINE_VULSCAN_DB_PREFIX)])

        if os.path.exists(cte.RAW_VULNERABILITIES):
            os.remove(cte.RAW_VULNERABILITIES)

        self.set_previous_external_db_update()

    def set_previous_external_db_update(self):
        """
        Called when the external databased is updated. It updates a local variable and
        persistent file with the update date of the external db
        """
        self.previous_external_db_update = datetime.utcnow()
        if not os.path.exists(cte.SECURITY_FOLDER):
            os.mkdir(cte.SECURITY_FOLDER)
        write_file(content=self.previous_external_db_update.strftime(cte.DATE_FORMAT),
                   file=cte.EXTERNAL_DB_UPDATE_FILE, encoding='utf-8')

    def gather_external_db_file_names(self):
        """
        Tries to find the local split files and updates the local variable containing
        the file names
        """
        it_content: list[str] = os.listdir(cte.DEFAULT_NMAP_DIRECTORY)
        it_content = [f for f in it_content if
                      f.startswith(cte.ONLINE_VULSCAN_DB_PREFIX)]
        self.vulscan_dbs = sorted(it_content)

    def get_previous_external_db_update(self) -> datetime:
        """
        Reads a local file seeking for the date of the last time the db was updated. If
        no file exists, returns the oldest possible date

        Returns: a datetime object containing the last time the local updated
        vulnerabilities database

        """
        logger.info('Retrieving previously updated db date')
        self.gather_external_db_file_names()
        it_date = datetime(1970, 1, 1)
        if not self.vulscan_dbs:
            return it_date
        date_read = read_file(cte.EXTERNAL_DB_UPDATE_FILE, decode_json=False,
                              remove_file_on_error=True, encoding='utf-8')
        if date_read is None:
            return it_date
        it_date = datetime.strptime(date_read,
                                        cte.DATE_FORMAT)
        return it_date

    def update_vulscan_db(self):
        """ Updates the local registry of the vulnerabilities data """
        if self.api is None and file_exists_and_not_empty(FILE_NAMES.NUVLAEDGE_SESSION):
            logger.info("Loading Nuvla session from file to update vulnerabilities DB")
            self.api = NuvlaClientWrapper.from_session_store(FILE_NAMES.NUVLAEDGE_SESSION)
        elif self.api is not None:
            self.api.login_nuvlaedge()
        else:
            logger.warning('No Nuvla session found to update vulnerabilities DB')
            return

        nuvla_vul_db: list = self.api.nuvlaedge_client.search('vulnerability',
                                                              orderby='modified:desc',
                                                              last=1).resources
        # self.api.logout()

        if not nuvla_vul_db:
            logger.warning(f'Nuvla endpoint {self.api.endpoint} does not contain any vulnerability')
            return

        temp_db_last_update = nuvla_vul_db[0].data.get('updated')

        logger.info(f"Nuvla's vulnerability DB was last updated on "
                    f"{temp_db_last_update}")

        if self.local_db_last_update and \
                temp_db_last_update < self.local_db_last_update:
            logger.info('Database recently updated')
            return

        logger.info(f"Fetching and extracting {self.config.external_vulnerabilities_db}")
        self.get_external_db_as_csv()

    @staticmethod
    def extract_product_info(service: dict) -> str:
        prod = f'{service.get("product", "")} {service.get("version", "")}'
        if prod != ' ':
            return prod
        else:
            logger.warning('Cannot extract product info')
            return ''

    @staticmethod
    def clean_output_attribute(output: str) -> list[str]:
        """

        Args:
            output: Raw output of the nmap for a given por vulnerabilities

        Returns: a list of raw vulnerabilities found

        """
        out = re.sub('cve.*.csv.*:\n', '', output).replace(' |nb| \n\n', '')
        return out.split(' |nb| ')

    @staticmethod
    def extract_vulnerability_id(attributes: list[str]) -> str | None:
        try:
            return attributes[0]
        except IndexError:
            logger.error(f'Failed to extract vulnerability ID from {attributes}')
            return None

    @staticmethod
    def extract_vulnerability_score(attributes: list[str]) -> float | None:
        str_score = ''
        try:
            str_score = attributes[2]
            return float(str_score)
        except IndexError:
            logger.warning(f'Score not found in {attributes}')
            return None

        except ValueError:
            logger.warning(f'Found score {str_score} not in proper format')
            return None

    @staticmethod
    def get_attributes_from_element(element: ElementTree.Element, name: str) -> dict:
        try:
            return element.find(name).attrib
        except AttributeError:
            logger.warning(f'Attributes not found for name {name}')
            return {}

    def extract_basic_info_from_xml_port(self, port: ElementTree.Element) \
            -> list[VulnerabilitiesInfo] | None:
        """

        Args:
            port:

        Returns:

        """
        logger.debug('Extraction product info')
        product = self.extract_product_info(
            self.get_attributes_from_element(port, 'service')
        )

        logger.debug('Extracting output info')
        script = self.get_attributes_from_element(port, 'script')

        if not product or not script.get('output'):
            return None

        vulnerabilities = self.clean_output_attribute(script.get('output'))

        logger.info('Extracting vulnerabilities id and score')
        clean_vulns: list[VulnerabilitiesInfo] = []

        for vuln in vulnerabilities:
            vuln_attrs = vuln.split(' |,| ')
            identifier = self.extract_vulnerability_id(vuln_attrs)

            if identifier is None:
                continue

            score = self.extract_vulnerability_score(attributes=vuln_attrs)
            clean_vulns.append(VulnerabilitiesInfo(product=product,
                                                   vulnerability_id=identifier,
                                                   vulnerability_score=score))

        return clean_vulns

    @staticmethod
    def extract_ports_with_vulnerabilities(file: str = cte.VULSCAN_OUT_FILE) \
            -> list[ElementTree.Element]:
        """

        """
        if not os.path.exists(file):
            logger.warning('')
            return []
        ports = ElementTree.parse(cte.VULSCAN_OUT_FILE).\
            getroot().findall('host/ports/port')

        if not ports:
            # No ports extraction either means that no vulnerabilities have been
            # found or something went wrong on the scan
            logger.debug('No ports with vulnerabilities detected (or something '
                         'went wrong on the scan')
            return []

        return ports
    
    def parse_vulscan_xml(self):
        """ Parses the nmap output XML file and gives back the list of formatted
        vulnerabilities

        :return: list of CVE vulnerabilities
        """
        ports = self.extract_ports_with_vulnerabilities()

        vulnerabilities = []
        for port in ports:
            tmp_port = self.extract_basic_info_from_xml_port(port)
            if tmp_port:
                vulnerabilities = vulnerabilities + tmp_port

        return vulnerabilities

    @staticmethod
    def run_cve_scan(cmd):

        with Popen(cmd, stdout=PIPE, stderr=PIPE) as shell_pipe:
            stdout, _ = shell_pipe.communicate()

            if shell_pipe.returncode != 0 or not stdout:
                return False
        return True

    def db_needs_update(self):
        """

        Returns:

        """
        if not self.config.external_vulnerabilities_db or not self.nuvla_endpoint:
            return
        elapsed_time = \
            (datetime.utcnow() - self.previous_external_db_update).total_seconds()
        logger.debug(f'Elapsed time since last db update: {elapsed_time}')

        if elapsed_time > self.config.external_db_update_interval:
            logger.info('Checking for updates on the vulnerability DB')
            self.update_vulscan_db()

    def run_scan(self):
        """
        Iterates the stored files and seeks vulnerabilities by calling the nmap command
        Returns:

        """

        temp_vulnerabilities: list[VulnerabilitiesInfo] = []
        logger.info(f'Running scan on DBs {self.vulscan_dbs}')
        for vulscan_db in self.vulscan_dbs:
            nmap_scan_cmd: list[str] = \
                ['nice', '-n', '15',
                 'nmap',
                 '-sV',
                 '--script', 'vulscan/', '--script-args',
                 f'vulscandb={vulscan_db},vulscanoutput=nuvlaedge-cve,'
                 f'vulscanshowall=1',
                 'localhost',
                 '-oX', cte.VULSCAN_OUT_FILE]

            # 1 - get CVE vulnerabilities
            logger.info(f"Running nmap Vulscan: {nmap_scan_cmd}")
            cve_scan = self.run_cve_scan(nmap_scan_cmd)

            if cve_scan:
                logger.info(f"Parsing nmap scan result from: "
                                 f"{cte.VULSCAN_OUT_FILE}")
                parsed_vulnerabilities = self.parse_vulscan_xml()
                temp_vulnerabilities += parsed_vulnerabilities

        logger.info(f'Found {len(temp_vulnerabilities)} vulnerabilities')
        if temp_vulnerabilities:
            vulnerabilities = [t.model_dump(by_alias=True, exclude_none=True)
                               for t in temp_vulnerabilities]
            write_file(vulnerabilities, FILE_NAMES.VULNERABILITIES_FILE)
