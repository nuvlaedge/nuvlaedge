#!/usr/local/bin/python
# -*- coding: utf-8 -*-

""" NuvlaEdge On-Stop

To be executed on every stop or full shutdown of the NBE, in order to ensure a proper cleanup of dangling resources

"""

import docker
import docker.errors
import logging
import socket
import sys
import time

logging.basicConfig(format='%(levelname)s - %(module)s - L%(lineno)s: %(message)s', level='INFO')


def main():
    docker_client = docker.from_env()
    if len(sys.argv) > 1 and "paused".startswith(sys.argv[1].lower()):
        logging.info('Pausing myself...')
        my_hostname = socket.gethostname()
        try:
            myself = docker_client.containers.get(my_hostname)
        except docker.errors.NotFound:
            logging.error(f'Cannot find this container by hostname: {my_hostname}. Cannot proceed')
            raise

        myself.pause()
    else:
        logging.info('Starting NuvlaEdge deep cleanup')

        try:
            docker_client.containers.prune(filters={'label': 'nuvlaedge.on-stop'})
        except Exception as ex:
            logging.debug(f'Expect exception pruning containers {ex}')
            pass
        else:
            logging.info('Pruned old on-stop containers')

        info = docker_client.info()

        swarm_info = info.get('Swarm', {})

        node_id = swarm_info.get('NodeID')

        local_node_state = swarm_info.get('LocalNodeState', 'inactive')

        is_swarm_enabled = True if node_id and local_node_state != "inactive" else False

        remote_managers = [rm.get('NodeID') for rm in swarm_info.get('RemoteManagers')] if swarm_info.get('RemoteManagers') else []
        i_am_manager = True if node_id in remote_managers else False

        # local data-source (DG) containers must go
        data_source_containers = docker_client.containers.list(filters={'label': 'nuvlaedge.data-source-container'})
        for ds_container in data_source_containers:
            logging.info(f'Stopping data source container {ds_container.name}')
            try:
                ds_container.stop()
            except Exception as e:
                logging.error(f'Unable to stop data source container {ds_container.name}: {str(e)}')

        network_driver = 'bridge'
        cluster_managers = []
        if i_am_manager:
            network_driver = 'overlay'
            cluster_nodes = docker_client.nodes.list()

            # remove label
            label = 'nuvlaedge'
            node = docker_client.nodes.get(node_id)
            node_spec = node.attrs['Spec']
            node_labels = node_spec.get('Labels', {})
            node_labels.pop(label)
            node_spec['Labels'] = node_labels
            logging.info(f'Removing node label {label} from this node ({node_id})')
            node.update(node_spec)

            # if len(cluster_manager_nodes) = 1, then this is the last manager and the DG services will cease to exist
            cluster_managers = [node for node in cluster_nodes if node.attrs.get('Spec', {}).get('Role') == 'manager'
                                and node.attrs.get('Status', {}).get('State') == 'ready']

        # delete DG - only on the last Swarm manager or a standalone Docker machine
        if (i_am_manager and len(cluster_managers) == 1) or not is_swarm_enabled:
            logging.info('This NuvlaEdge was either the last cluster manager or a standalone node')
            if i_am_manager:
                dg_components = docker_client.services.list(filters={'label': 'nuvlaedge.data-gateway'})
            else:
                dg_components = docker_client.containers.list(filters={'label': 'nuvlaedge.data-gateway'})
            for dg_svc in dg_components:
                logging.info(f'Deleting component {dg_svc.name}')
                try:
                    if i_am_manager:
                        dg_svc.remove()
                    else:
                        dg_svc.remove(force=True)
                except docker.errors.NotFound:
                    # maybe the service has been removed in the meantime
                    continue
                except Exception as e:
                    logging.debug(f'Exception {e} removing component {dg_svc.name}')
                    logging.warning(f'Unable to remove component {dg_svc.name}. Trying a second time')
                    time.sleep(5)
                    try:
                        if i_am_manager:
                            dg_svc.remove()
                        else:
                            dg_svc.remove(force=True)
                    except Exception as e:
                        logging.debug(f'Exception {e} retrying removal of component {dg_svc.name}')
                        logging.error(f'Cannot remove {dg_svc.name}')

            logging.info('Preparing to delete additional NuvlaEdge networks')
            custom_networks = docker_client.networks.list(filters={'label': 'nuvlaedge.network',
                                                                   'driver': network_driver})
            for network in custom_networks:
                network.reload()
                if network.attrs.get('Containers'):
                    for attached_container in network.attrs.get('Containers').keys():
                        logging.info(f'Disconnecting container {attached_container} from network {network.name}')
                        try:
                            network.disconnect(attached_container)
                        except docker.errors.NotFound:
                            continue

                logging.info(f'Removing network {network.name}')
                try:
                    network.remove()
                except docker.errors.NotFound:
                    # maybe the net has been removed in the meantime
                    continue
                except Exception as e:
                    logging.debug(f'Exception {e} while trying to remove network {network.name}')
                    logging.warning(f'Unable to remove network {network.name}. Trying a second time')
                    time.sleep(5)
                    try:
                        network.remove()
                    except Exception as e:
                        logging.debug(f'Exception {e} retrying removal of network {network.name}')
                        logging.error(f'Cannot remove {network.name}')


if __name__ == '__main__':
    main()
