# -*- coding: utf-8 -*-

""" Contains the supervising class for all NuvlaEdge Engine components """

import json
import logging
import os
from datetime import datetime
from threading import Timer

import docker
import docker.models.networks
import docker.errors
import OpenSSL

from nuvlaedge.system_manager.common import utils
from nuvlaedge.common.file_operations import read_file
from nuvlaedge.system_manager.orchestrator.factory import get_coe_client


class ClusterNodeCannotManageDG(Exception):
    pass


class BreakDGManagementCycle(Exception):
    pass


def cluster_workers_cannot_manage(func):
    def wrapper(self, *args):
        if self.is_cluster_enabled and not self.i_am_manager:
            raise ClusterNodeCannotManageDG()
        return func(self, *args)
    return wrapper


class Supervise:
    """ The Supervise class contains all the methods and
    definitions for making sure the NuvlaEdge Engine is running smoothly,
    including all methods for dealing with system disruptions and
    graceful shutdowns
    """

    def __init__(self):
        """ Constructs the Supervise object """

        self.log = logging.getLogger(__name__)
        super().__init__()
        self.coe_client = get_coe_client()
        self.on_stop_docker_image = self.coe_client.infer_on_stop_docker_image()
        self.data_gateway_enabled = os.getenv('NUVLAEDGE_DATA_GATEWAY_ENABLED', 'true').lower() == 'true'
        self.data_gateway_image = os.getenv('NUVLAEDGE_DATA_GATEWAY_IMAGE',
                                            os.getenv('NUVLABOX_DATA_GATEWAY_IMAGE',
                                                      'eclipse-mosquitto:2.0.15-openssl'))
        self.data_gateway_object = None
        self.data_gateway_name = os.getenv('NUVLAEDGE_DATA_GATEWAY_NAME',
                                           os.getenv('NUVLABOX_DATA_GATEWAY_NAME',
                                                     'data-gateway'))
        self.i_am_manager = self.is_cluster_enabled = self.node = None
        self.operational_status = []
        self.agent_dg_failed_connection = 0
        self.lost_quorum_hint = 'possible that too few managers are online'
        self.nuvlaedge_containers = []
        self.nuvlaedge_containers_restarting = {}

    def classify_this_node(self):
        # is it running in cluster mode?
        node_id = self.coe_client.get_node_id()
        is_cluster_enabled = self.coe_client.is_coe_enabled(check_local_node_state=True)

        if not node_id or not is_cluster_enabled:
            self.i_am_manager = self.is_cluster_enabled = False
            return

        # if it got here, there cluster is active
        self.is_cluster_enabled = True

        managers = self.coe_client.get_cluster_managers()
        self.i_am_manager = True if node_id in managers else False

        if self.i_am_manager:
            _update_label_success, err = self.coe_client.set_nuvlaedge_node_label(node_id)
            if err:
                self.operational_status.append((utils.status_degraded, err))

    def is_cert_rotation_needed(self):
        """ Checks whether the API certs are about to expire """

        # certificates to be checked for expiration dates:
        check_expiry_date_on = ["ca.pem", "server-cert.pem", "cert.pem"]

        # if the TLS sync file does not exist, then the compute-api is going to generate the certs by itself, by default
        if not os.path.isfile(utils.tls_sync_file):
            return False

        for file in check_expiry_date_on:
            file_path = f"{utils.data_volume}/{file}"
            content = read_file(file_path)
            if content is None:
                continue

            cert_obj = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, content.encode())

            end_date = cert_obj.get_notAfter().decode()
            formatted_end_date = datetime(int(end_date[0:4]),
                                          int(end_date[4:6]),
                                          int(end_date[6:8]))

            days_left = formatted_end_date - datetime.now()
            # if expiring in less than d days, rotate all
            d = 5
            if days_left.days < d:
                self.log.warning(f"{file_path} is expiring in less than {d} days. Requesting rotation of all certs")
                return True

        return False

    def request_rotate_certificates(self):
        """ Deletes the existing .tls sync file from the shared volume

        By doing this, a new set of credentials shall be automatically created either by the compute-api or the
        kubernetes-credential-manager

        This rotation will force the regeneration of the certificates and consequent recommissioning """

        if os.path.isfile(utils.tls_sync_file):
            os.remove(utils.tls_sync_file)
            self.log.info(f"Removed {utils.tls_sync_file}. "
                          f"Restarting credentials_manager_component")
            self.coe_client.restart_credentials_manager()

    @cluster_workers_cannot_manage
    def launch_data_gateway(self, name: str) -> bool:
        """
        Starts the DG services/containers, depending on the mode

        :param name: name of the dg component

        :return: bool
        """

        # At this stage, the DG network is setup
        # let's create the DG component
        labels = {
            "nuvlaedge.component": "True",
            "nuvlaedge.deployment": "production",
            "nuvlaedge.data-gateway": "True"
        }
        try:
            cmd = "sh -c 'sleep 10; " \
                  "cp /mosquitto-no-auth.conf /mosquitto/config/mosquitto.conf 2>/dev/null; " \
                  "exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf'"
            if self.is_cluster_enabled and self.i_am_manager:
                self.coe_client.client.services.create(self.data_gateway_image,
                                                       name=name,
                                                       hostname=name,
                                                       init=True,
                                                       labels=labels,
                                                       container_labels=labels,
                                                       networks=[utils.nuvlaedge_shared_net],
                                                       constraints=[
                                                           'node.role==manager',
                                                           f'node.labels.{utils.node_label_key}==True'
                                                       ],
                                                       command=cmd)
            elif not self.is_cluster_enabled:
                # Docker standalone mode
                self.coe_client.client.containers.run(self.data_gateway_image,
                                                      name=name,
                                                      hostname=name,
                                                      init=True,
                                                      detach=True,
                                                      labels=labels,
                                                      restart_policy={"Name": "always"},
                                                      network=utils.nuvlaedge_shared_net,
                                                      command=cmd)
        except docker.errors.APIError as e:
            try:
                if '409' in str(e):
                    # already exists
                    self.log.warning(f'Despite the request to launch the Data Gateway, {name} seems to exist already. '
                                     f'Forcing its restart just in case')
                    if self.is_cluster_enabled and self.i_am_manager:
                        self.coe_client.client.services.get(name).force_update()
                    else:
                        self.coe_client.client.containers.get(name).restart()

                    return True
                else:
                    raise e
            except Exception as e:
                self.log.error(f'Unable to launch Data Gateway router {name}: {str(e)}')
                return False

    def find_nuvlaedge_agent(self) -> object or None:
        """
        Connect the NB agent to the DG network

        :return: agent container object or None
        """

        container, err = self.coe_client.find_nuvlaedge_agent_container()

        if err:
            self.operational_status.append((utils.status_degraded, err))
            return None
        return container

    def check_dg_network(self, target_network: docker.DockerClient.networks):
        """
        Makes sure the DG is connected to the right network

        :param target_network: network to be checked (object)
        :return:
        """

        if not self.data_gateway_object:
            self.log.warning('Data Gateway object does not exist. Cannot check its network')
            return

        try:
            if self.is_cluster_enabled:
                current_networks = [vip.get('NetworkID') for vip in self.data_gateway_object.attrs.get('Endpoint', {}).get('VirtualIPs', [])]
            else:
                current_networks = self.data_gateway_object.attrs.get('NetworkSettings', {}).get('Networks', {}).keys()

            if target_network.name not in current_networks and target_network.id not in current_networks:
                self.log.info(f'Adding network {target_network.name} to {self.data_gateway_object.name}')
                if self.is_cluster_enabled:
                    self.data_gateway_object.update(networks=[target_network.name] + current_networks)
                else:
                    target_network.connect(self.data_gateway_object.name)
        except Exception as e:
            self.log.error(f'Cannot add network {target_network.name} to DG {self.data_gateway_object.name}: {str(e)}')

    def manage_docker_data_gateway_network(self, data_gateway_networks: list) \
            -> docker.models.networks.Network | None:
        """
        Assesses the state of the DG network. Creates it if it doesn't exist or runs a sanity check at it if it does

        :param data_gateway_networks: list of Docker networks
        :return: the DG network, or None if the DG mgmt cycle should be interrupted
        """
        if not data_gateway_networks:
            # network doesn't exist, so let's create it as well
            try:
                self.setup_docker_network(utils.nuvlaedge_shared_net)
                raise BreakDGManagementCycle
            except ClusterNodeCannotManageDG:
                # this node can't setup networks
                # However, the network might already exist, we simply don't see it. Try to connect agent to it anyway
                return None
        else:
            # make sure the network driver makes sense, to avoid having a bridge network on a Swarm node
            dg_network = data_gateway_networks[0]
            if self.is_cluster_enabled:
                # if swarm is enabled, a container-based data-gateway doesn't make sense
                bridge_nets = list(filter(lambda o: o.attrs.get('Driver', '') == 'bridge', data_gateway_networks))
                for leftover_bridge_net in bridge_nets:
                    leftover_bridge_net.reload()
                    self.destroy_docker_network(leftover_bridge_net)
                    # if swarm is enabled, a container-based data-gateway doesn't make sense
                    try:
                        self.coe_client.client.containers.get(self.data_gateway_name)
                    except docker.errors.NotFound:
                        pass
                    else:
                        try:
                            self.coe_client.client.api.remove_container(self.data_gateway_name, force=True)
                        except Exception as e:
                            self.log.error(f'Could not remove old {self.data_gateway_name} container: {str(e)}')

                running_nets = list(set(data_gateway_networks) - set(bridge_nets))
                # is there an overlay network as well? if not, reset cycle cause network needs to be recreated
                if not running_nets:
                    return None

                dg_network = running_nets[0]

            return dg_network

    def manage_docker_data_gateway_object(self, data_gateway_network: docker.models.networks.Network) -> None:
        """
        Check the existence of the DG and set self.data_gateway_object

        :param data_gateway_network: the DG network object
        :return:
        """
        self.data_gateway_object = None
        try:
            self.find_data_gateway(self.data_gateway_name)
        except ClusterNodeCannotManageDG:
            # ## 2.1: this means this node is a Swarm worker. It can't manage the DG
            pass
        else:
            # ## 2.2: at this stage, this is either a Swarm manager or a standalone Docker node
            if not self.data_gateway_object:
                launched_dg = False
                self.log.info('Data Gateway not found. Launching it')
                try:
                    launched_dg = self.launch_data_gateway(self.data_gateway_name)
                except ClusterNodeCannotManageDG:
                    # this isn't actually needed, cause we should never get here if ClusterNodeCannotManageDG
                    # due to the above catch...but it doesn't harm, just in case there's a sudden change in the cluster
                    pass
                finally:
                    if not launched_dg:
                        self.operational_status.append((utils.status_degraded, 'Unable to launch Data Gateway'))

                # NOTE: resume on the next cycle
                raise BreakDGManagementCycle
            else:
                # double check DG still has the right network
                self.check_dg_network(data_gateway_network)

    def manage_docker_data_gateway_connect_to_network(self, containers_to_connect: list,
                                                      agent_container_id: str) -> None:
        """
        Connect this node's Agent container (+data source containers) to DG

        :param containers_to_connect: all containers to be connected to the DG network
        :param agent_container_id: ID of the agent container that is also to be connected
        :return:
        """
        for ccont in containers_to_connect:
            if utils.nuvlaedge_shared_net not in \
                    ccont.attrs.get('NetworkSettings', {}).get('Networks', {}).keys():
                self.log.info(f'Connecting ({ccont.name}) '
                              f'to network {utils.nuvlaedge_shared_net}')
                try:
                    self.coe_client.client.api.connect_container_to_network(ccont.id, utils.nuvlaedge_shared_net)
                except Exception as e:
                    # doe Network exist? If so, and agent was not connected, need to break and retry
                    if "notfound" not in str(e).replace(' ', '').lower():
                        if ccont.id == agent_container_id:
                            self.log.error(f'Error while connecting NuvlaEdge Agent to Data Gateway network: {str(e)}')
                            self.operational_status.append((utils.status_degraded,
                                                            f'Data Gateway connection error: {str(e)}'))
                            raise BreakDGManagementCycle
                        # else, this is a data-source container and not as critical
                    err_msg = f'Cannot connect {ccont.name} to Data Gateway network'
                    self.operational_status.append((utils.status_degraded, err_msg))

                    self.log.warning(f'{err_msg}: {str(e)}')

    def manage_docker_data_gateway(self):
        """ Sets the DG service.

        If we need to start or restart the DG or any of its components, we always "return" and resume the DG setup
        on the next cycle

        :return:
        """

        if not self.data_gateway_enabled:
            return

        # ## 1: if the DG network already exists, then chances are that the DG has already been deployed
        dg_networks = self.find_docker_network([utils.nuvlaedge_shared_net])
        try:
            dg_network = self.manage_docker_data_gateway_network(dg_networks)
        except BreakDGManagementCycle:
            return

        # ## 2: DG network exists, but does the DG?
        try:
            self.manage_docker_data_gateway_object(dg_network)
        except BreakDGManagementCycle:
            return

        # ## 3: finally, connect this node's Agent container (+data source containers) to DG
        agent_container = self.find_nuvlaedge_agent()

        if agent_container:
            agent_container_id = agent_container.id
        else:
            self.operational_status.append((utils.status_degraded, 'NuvlaEdge Agent is down'))
            return

        try:
            self.manage_docker_data_gateway_connect_to_network([agent_container], agent_container_id)
        except BreakDGManagementCycle:
            return

        # TODO: unreachable code, try to find another way to detect agent<->dg connection issues (if needed)
        if self.agent_dg_failed_connection > 3:
            # do something after 3 reports
            self.restart_data_gateway()
            self.agent_dg_failed_connection = 0

    def restart_data_gateway(self):
        """
        Simply restarts the DG object

        :return:
        """
        self.log.warning('Agent seems unable to reach the Data Gateway. Restarting the Data Gateway')
        if self.is_cluster_enabled and self.i_am_manager:
            self.data_gateway_object.force_update()
        else:
            self.data_gateway_object.restart()

    @cluster_workers_cannot_manage
    def find_data_gateway(self, name: str) -> bool:
        try:
            if self.is_cluster_enabled and self.i_am_manager:
                # in swarm
                self.data_gateway_object = self.coe_client.client.services.get(name)
            elif not self.is_cluster_enabled and not self.i_am_manager:
                # in single Docker machine
                self.data_gateway_object = self.coe_client.client.containers.get(name)

            return True
        except (docker.errors.NotFound, docker.errors.APIError) as e:
            self.log.warning(f'Unable to look up Data Gateway component {name}: {str(e)}')
            self.data_gateway_object = None
            return False

    def find_docker_network(self, network_names: list) -> object or None:
        """
        Finds networks by name

        :param network_names: names of the networks to list
        :return: Docker network object or None
        """

        return self.coe_client.client.networks.list(names=network_names)

    def destroy_docker_network(self, network: docker.DockerClient.networks):
        """
        Deletes a network locally by disconnecting it from any container in use, and removing it

        :param network: Docker network object
        :return:
        """
        self.log.warning(f'About to destroy Docker network {network.name} with ID {network.id}')

        containers_attached = network.attrs.get('Containers')

        if containers_attached:
            self.log.warning('The following containers need to be detached from the network first: '
                             f'{",".join(list(containers_attached.keys()))}')
            for container_id in containers_attached.keys():
                try:
                    network.disconnect(container_id)
                except docker.errors.NotFound as e:
                    self.log.debug(f'Unable to disconnect container {container_id} from net {network.name}: {str(e)}')
                    continue

                self.log.warning(f'Disconnected container {container_id} from network {network.name}')

        network.remove()

    @cluster_workers_cannot_manage
    def setup_docker_network(self, net_name: str) -> bool:
        """
        Creates a Docker network.
        If driver is overlay, then the network is also attachable and a propagation global service is also launched

        :param net_name: network name
        :return: bool
        """

        labels = {
            "nuvlaedge.network": "True",
            "nuvlaedge.data-gateway": "True"
        }
        self.log.info(f'Creating Data Gateway network {net_name}')
        try:
            if not self.is_cluster_enabled:
                # standalone Docker nodes create bridge network
                self.coe_client.client.networks.create(net_name,
                                                       labels=labels)
                return True
            elif self.is_cluster_enabled and self.i_am_manager:
                # Swarm managers create overlay network
                self.coe_client.client.networks.create(net_name,
                                                       driver="overlay",
                                                       attachable=True,
                                                       options=self.coe_client.dg_encrypt_options,
                                                       labels=labels)
        except docker.errors.APIError as e:
            if '409' in str(e):
                # already exists
                self.log.warning(f'Unexpected conflict (moving on): {str(e)}')
                if not self.is_cluster_enabled:
                    # in this case there's nothing else to do
                    return True
            else:
                self.log.error(f'Unable to create NuvlaEdge network {net_name}: {str(e)}')
                return False

        # if we got here, then we are handling an overlay network, and thus we need the propagation service
        ack_service = None
        try:
            ack_service = self.coe_client.client.services.get(utils.overlay_network_service)
        except docker.errors.NotFound:
            # good, it doesn't exist
            pass
        except docker.errors.APIError as e:
            self.log.error(f'Unable to manage service {utils.overlay_network_service}: {str(e)}')
            return False

        if ack_service:
            # if we got a request to propagate, even though there's already a service, then there might be something
            # wrong with the service. Let's force an update to see if it fixes something
            self.log.warning(f'Network propagation service {utils.overlay_network_service} already exists. '
                             f'Forcing update')
            ack_service.force_update()
            return True

        # otherwise, let's create the global service
        labels = {
            "nuvlaedge.component": "True",
            "nuvlaedge.deployment": "production",
            "nuvlaedge.overlay-network-service": "True",
            "nuvlaedge.data-gateway": "True"
        }
        restart_policy = {
            "condition": "on-failure"
        }

        self.log.info(f'Launching global network propagation service {utils.overlay_network_service}')
        cmd = ["sh",
               "-c",
               f"echo -e '''{json.dumps(self.coe_client.get_node_info(), indent=2)}''' && sleep 300"]

        self.coe_client.client.services.create(self.coe_client.current_image,
                                               command=cmd,
                                               container_labels=labels,
                                               labels=labels,
                                               mode="global",
                                               name=utils.overlay_network_service,
                                               networks=[net_name],
                                               restart_policy=restart_policy,
                                               stop_grace_period=3)

        return True

    def get_project_name(self) -> str:
        """"""
        try:
            container_id = self.coe_client.get_current_container_id()
            myself = self.coe_client.client.containers.get(container_id)
        except docker.errors.NotFound:
            err = 'Cannot find the current container. Cannot proceed'
            self.log.error(err)
            self.operational_status.append((utils.status_degraded, 'System Manager container lookup error'))
            raise RuntimeError(err)

        try:
            project_name = myself.labels['com.docker.compose.project']
        except KeyError:
            self.log.warning(f'Cannot infer Docker Compose project name from the labels in {myself.name}.'
                             f'Trying to infer from container name')
            try:
                project_name = myself.name.split('-')[-3]
            except (IndexError, AttributeError):
                msg = 'Impossible to infer Docker Compose project name!'
                self.log.error(msg)
                self.operational_status.append((utils.status_degraded, msg))
                raise RuntimeError(msg)

        return project_name

    def fix_network_connectivity(self, all_containers: list, target_network: docker.DockerClient.networks) -> None:
        """
        Goes through the list of provided containers, and if they are not connected to the target network, connect them

        :param all_containers: list of containers to fix
        :param target_network: network to attach the container to
        :return:
        """
        for container in all_containers:
            if container.attrs.get('HostConfig', {}).get('NetworkMode', '') == 'host':
                # containers in host mode are not affected
                continue

            if not any(net_id in container.attrs.get('NetworkSettings', {}).get('Networks', {}).keys()
                       for net_id in [target_network.name, target_network.id]):
                self.log.warning(f'Container {container.name} lost its network {target_network.name}.'
                                 f'Reconnecting...')

                raw_service_name = container.labels.get('com.docker.compose.service')
                service_name = [raw_service_name] if raw_service_name else []
                try:
                    target_network.connect(container.name, aliases=service_name)
                except docker.errors.APIError as e:
                    if "already exists in network" in str(e).lower():
                        continue
                    elif "notfound" in str(e).replace(' ', '').lower():
                        self.log.warning(f'Network {target_network.name} ceased to exist '
                                         f'during connectivity check. Nothing to do.')
                        return
                    self.log.error(f'Unable to reconnect {container.name} to network {target_network.name}: {str(e)}')
                    self.operational_status.append((utils.status_degraded,
                                                    'NuvlaEdge containers lost their network connection'))

    def check_nuvlaedge_docker_connectivity(self):
        """
        Makes sure all NBE containers are connected to the original bridge network (at least)

        This is mainly because of a connectivity bug in Docker, whereby docker-compose container loose their
        bridge network when the Swarm state changes:

        https://github.com/docker/compose/issues/8110

        :return:
        """

        try:
            project_name = self.get_project_name()
        except Exception:
            self.log.debug('Errors getting project name', exc_info=True)
            return

        original_project_label = f'com.docker.compose.project={project_name}'
        filters = {
            'label': original_project_label
        }
        original_nb_containers = self.coe_client.client.containers.list(filters=filters)
        self.nuvlaedge_containers = self.coe_client.client.containers.list(filters=filters, all=True)

        filters.update({'driver': 'bridge'})
        original_nb_internal_network = self.coe_client.client.networks.list(filters=filters)

        if not original_nb_containers or not original_nb_internal_network:
            self.operational_status.append((utils.status_degraded, 'Original NuvlaEdge network not found'))
            self.log.warning('Unable to check NuvlaEdge connectivity: original containers/network not found')
            return

        # there should only be 1 original nb internal network, so take the 1st one
        self.fix_network_connectivity(original_nb_containers, original_nb_internal_network[0])

    def heal_created_container(self, container: docker.DockerClient.containers) -> None:
        """
        Takes a container in a created state, and heals it by forcing it to start

        :param container: container object
        :return:
        """
        try:
            self.coe_client.client.api.start(container.id)
        except docker.errors.APIError as e:
            self.log.error(f'Cannot resume container {container.name}. Reason: {str(e)}')

    def heal_exited_container(self, container: docker.DockerClient.containers) -> None:
        """
        Heals a container that has exited unexpectedly
        :param container: container object
        :return:
        """
        attrs = container.attrs
        state = attrs.get('State', {})
        exit_code = state.get('ExitCode', 0)
        if exit_code > 0:
            # is it already restarting?
            if state.get('Restarting', False):
                # nothing to do then
                return

            if attrs.get('HostConfig', {}).get('RestartPolicy', {}).get('Name', 'no').lower() in ['no']:
                return

            # at this stage we simply need to try to restart it
            if (container.name in self.nuvlaedge_containers_restarting and
                not self.nuvlaedge_containers_restarting[container.name].is_alive()) or \
                    container.name not in self.nuvlaedge_containers_restarting:
                self.log.warning(f'Container {container.name} down (code {exit_code}). Scheduling restart')
                self.nuvlaedge_containers_restarting[container.name] = Timer(30,
                                                                             self.restart_container,
                                                                             (container.name, container.id))
                self.nuvlaedge_containers_restarting[container.name].start()

    def docker_container_healer(self):
        """
        Loops through the NB containers and tries to fix the ones that are broken

        :return:
        """

        if not self.nuvlaedge_containers:
            return

        obsolete_containers = set(self.nuvlaedge_containers_restarting) - set([c.name for c in self.nuvlaedge_containers])
        if obsolete_containers:
            # this means we had old restarts for old containers, so let's just clean them up to avoid
            # unnecessary memory pile up
            for cname in obsolete_containers:
                self.nuvlaedge_containers_restarting.pop(cname)

        for container in self.nuvlaedge_containers:
            status = container.status.lower()
            if status in ["paused", "running", "restarting"]:
                continue

            # what to do if:
            # . status is "created"?
            # .. just start the container
            if status == 'created':
                self.heal_created_container(container)

            # . status is "exited"?
            # .. understand why. If exit code is 0, then it exited gracefully...thus it is not broken
            if status == 'exited':
                self.heal_exited_container(container)

    def restart_container(self, name, container_id):
        """
        Restar a container
        :return:
        """

        try:
            self.coe_client.client.api.restart(container_id)
            self.log.info(f'Successfully restarted container {name}')
        except docker.errors.APIError as e:
            self.log.error(f'Failed to heal container {name}. Reason: {str(e)}')
            self.operational_status.append((utils.status_degraded, f'Container {name} is down'))

            if any(w in str(e) for w in ['NotFound', 'network', 'not found']):
                self.log.warning(f'Trying to reset network config for {name}')
                try:
                    self.coe_client.client.api.disconnect_container_from_network(container_id,
                                                                                 utils.nuvlaedge_shared_net)
                except docker.errors.APIError as e2:
                    err_msg = f'Malfunctioning network for {name}: {str(e2)}'
                    self.log.error(f'Cannot recover {name}. {err_msg}')
                    self.operational_status.append((utils.status_degraded, err_msg))

