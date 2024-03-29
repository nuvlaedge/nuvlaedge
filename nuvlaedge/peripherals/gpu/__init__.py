#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""NuvlaEdge Peripheral GPU Manager

This service provides GPU discovery for the NuvlaEdge.

It provides:
    - Nvidia Docker Runtime discovery
    - a list of the devices and libraries needed to use a GPU.
    - checks if Docker is the correct version to use --gpus.
"""

import os
import csv
import json
import re

from shutil import which

import requests
import logging
import docker.errors

from nuvlaedge.agent.common.util import compose_project_name
from nuvlaedge.peripherals.peripheral import Peripheral
from nuvlaedge.common.nuvlaedge_config import parse_arguments_and_initialize_logging

# Increase this version to enforce rebuild (usually when Dockerfile.gpu is updated)
gpu_image_version = '1.1'

docker_socket_file = '/var/run/docker.sock'
build_path = '/opt/nuvlaedge/scripts/gpu/'
dockerfile_path = '/etc/nuvlaedge/scripts/gpu/Dockerfile.gpu'

HOST_PATH = '/host'
HOST_DEV_PATH = f'{HOST_PATH}/dev'
HOST_USR_LIB_PATH = f'{HOST_PATH}/usr/lib'
HOST_ETC_PATH = f'{HOST_PATH}/etc'
HOST_FILES = f'{HOST_ETC_PATH}/nvidia-container-runtime/host-files-for-container.d'
RUNTIME_PATH = f'{HOST_ETC_PATH}/docker'

host_path_prefix = re.compile(r'^' + re.escape(HOST_PATH))

KUBERNETES_SERVICE_HOST = os.getenv('KUBERNETES_SERVICE_HOST')
if KUBERNETES_SERVICE_HOST:
    ORCHESTRATOR = 'kubernetes'
else:
    if os.path.exists(docker_socket_file):
        import docker

        ORCHESTRATOR = 'docker'
    else:
        ORCHESTRATOR = None

logger: logging.Logger = logging.getLogger(__name__)

identifier = 'GPU'


def read_json(json_path):
    """
    JSON reader.
    """

    with open(json_path) as f:
        dic = json.load(f)
        return dic


def get_device_type():
    """
    Gets device type (x86_64, aarch64, arm64)
    """
    return os.uname().machine


def check_cuda():
    """
    Checks if CUDA is installed and returns the version.
    """
    cuda_version = which('nvcc')

    if cuda_version is not None:
        with open(cuda_version + '/version.txt', 'r') as f:
            return f.readline()
    else:
        return False


def nvidia_device(devices):
    """
    Checks if any Nvidia device exist
    """
    nv_devices = []

    for device in devices:
        if device.startswith('nv'):
            nv_devices.append('{}/{}'.format(HOST_DEV_PATH, device))

    return nv_devices


def check_cuda_installation(cuda_version):
    """
    Checks if Cuda is installed.
    """
    if 'libcuda.so' in os.listdir('{}/{}-linux-gnu'.format(HOST_USR_LIB_PATH, cuda_version)):
        return True
    else:
        return False


def build_cuda_core_docker_cli(devices):
    """
    Creates the correct device and volume structures to be passed to docker.
    """
    cli_devices = []
    cli_volumes = {}
    libs = []

    logger.debug(f'build_cuda_core_docker_cli: devices: {devices}')
    device_path = host_path_prefix.sub('', HOST_DEV_PATH)
    usr_lib_path = host_path_prefix.sub('', HOST_USR_LIB_PATH)
    logger.debug(f'build_cuda_core_docker_cli: device path: {device_path}')
    logger.debug(f'build_cuda_core_docker_cli: user lib path: {usr_lib_path}')

    current_devices = ['{}/{}'.format(device_path, i) for i in os.listdir(HOST_DEV_PATH)]

    for device in devices:
        if device in current_devices:
            cli_devices.append('{0}:{0}:rwm'.format(device))

    cuda_version = get_device_type()

    # Due to differences in the implementation of the GPUs by Nvidia, in the Jetson devices, and
    # in the discrete graphics, there is a need for different volumes.

    if cuda_version == 'aarch64':
        libcuda = '{}/{}-linux-gnu/'.format(usr_lib_path, cuda_version)
        etc = '/etc/'
        cli_volumes[etc] = {'bind': etc, 'mode': 'ro'}
        libs.extend([libcuda, etc])
    else:
        libcuda = '{}/{}-linux-gnu/libcuda.so'.format(usr_lib_path, cuda_version)
        libs.extend([libcuda])

    cuda = '/usr/local/cuda'

    libs.extend([cuda])
    cli_volumes[libcuda] = {'bind': libcuda, 'mode': 'ro'}
    cli_volumes[cuda] = {'bind': cuda, 'mode': 'ro'}

    logger.debug(f'build_cuda_core_docker_cli: cli_devices: {cli_devices}')
    logger.debug(f'build_cuda_core_docker_cli: cli_volumes: {cli_volumes}')
    logger.debug(f'build_cuda_core_docker_cli: libs: {libs}')

    return cli_devices, cli_volumes, libs


def get_linux_distribution_name_and_version():
    try:
        with open(f'{HOST_ETC_PATH}/os-release', 'r') as f:
            os_release = f.read()
            names = re.findall(r'''^ID=["']?(.+?)["']?$''', os_release, re.M)
            versions = re.findall(r'''^VERSION_ID=["']?(.+?)["']?$''', os_release, re.M)
            name = names[0] if names else None
            version = versions[0] if versions else None
            return name, version
    except Exception as e:
        logger.error(f'Failed to get the host Linux distribution and its version: {e}')
    return None, None


def cuda_cores(devices, volumes):
    """
    Starts Cuda Core container and returns the output from the container
    """

    client = docker.from_env()

    image = f'{compose_project_name}-gpu-get-cuda-cores:{gpu_image_version}'

    os_dist_name, os_dist_version = get_linux_distribution_name_and_version()
    build_args = {}
    if os_dist_name:
        build_args['DOCKER_IMAGE'] = os_dist_name
    if os_dist_version:
        build_args['DOCKER_IMAGE_TAG'] = os_dist_version

    # Build Image
    if len(client.images.list(image)) == 0:
        logger.info(f'Build CUDA Cores Image "{image}" with following args: {build_args}')
        client.images.build(path=build_path,
                            tag=image,
                            dockerfile=dockerfile_path,
                            buildargs=build_args,
                            rm=True)

    container_name = compose_project_name + '-peripheral-gpu-get-cuda-cores'
    container = ''

    def run():
        logger.info(f'Start container {container_name}')
        logger.debug(f'with devices "{devices}" and volumes "{volumes}"')
        return client.containers.run(image,
                                     name=container_name,
                                     devices=devices,
                                     volumes=volumes,
                                     remove=True)

    try:
        container = run()
    except docker.errors.APIError as e:
        if e.response.status_code == 409:
            client.api.remove_container(container_name, force=True)
            container = run()
    except Exception as e:
        # let's not stop the peripheral manager just because we can't get this property
        logger.error(f'Unable to infer CUDA cores. Reason: {str(e)}')

    return str(container)


def cuda_information(output):
    """
    Gets the output from the container and returns GPU information
    """
    device_information = []
    info = [i.split(":")[1] for i in output.split('\\n')[1:-1]]
    device_information.append({'unit': 'multiprocessors', 'capacity': info[3]})
    device_information.append({'unit': 'cuda-cores', 'capacity': info[4]})
    device_information.append({'unit': info[8].split()[-1], 'capacity': info[8].split()[0]})

    return info[1], device_information


def min_docker_version():
    """
    Checks if the Docker Engine version and the Docker API version are enough to run --gpus.
    """
    docker_version = docker.from_env().version()

    for i in docker_version['Components']:

        if i['Name'] == 'Engine':

            engine_version = int(i['Version'].split('.')[0])
            api_version = float(i['Details']['ApiVersion'])

            if engine_version >= 19 and api_version >= 1.4:
                return True

    return False


def search_runtime(runtime_path, host_files_path):
    """
    Checks if Nvidia Runtime exists, and reads its files.
    """

    if not os.path.isdir(runtime_path):
        logger.warning("Runtime path do not exist or is not a directory")
        return None

    for i in os.listdir(runtime_path):

        if 'daemon.json' in i:
            dic = read_json(f'{runtime_path}/{i}')

            try:
                if 'nvidia' in dic['runtimes'].keys():
                    a = read_runtime_files(host_files_path)

                    return a
                else:
                    return None
            except KeyError:
                logger.exception("Runtimes not configured in Docker configuration")
                return None

    return None


def read_runtime_files(path):
    """
    Checks if the runtime files exist, reads them, and filters the correct information.
    """
    if os.path.isdir(path) and len(os.listdir(path)) > 0:
        filtered_lines = {'devices': [], 'libraries': []}

        for i in os.listdir(path):

            with open(f'{path}/{i}') as csvFile:
                reader = csv.reader(csvFile)

                for line in reader:
                    try:
                        if line[0] == 'lib':
                            filtered_lines['libraries'].append(line[1].strip())

                        elif line[0] == 'dev':
                            filtered_lines['devices'].append(line[1].strip())

                        else:
                            continue
                    except IndexError:
                        continue

        return filtered_lines
    return None


def cuda_cores_information(nv_devices):
    devices, libs, _ = build_cuda_core_docker_cli(nv_devices)
    output = cuda_cores(devices, libs)
    if output != '':
        try:
            name, information = cuda_information(output)
            return name, information
        except Exception as e:
            logger.error(f'Exception in cudaCoresInformation. Reason: {str(e)}')

    return None, None


def flow(**kwargs):
    runtime = search_runtime(kwargs['runtime'], kwargs['host_files_path'])

    runtime_files = {
        'available': True,
        'name': 'Graphics Processing Unit',
        'vendor': 'Nvidia',
        'classes': ['gpu'],
        'identifier': identifier,
        'interface': 'gpu',
        'additional-assets': runtime
    }

    if runtime is not None:

        # GPU is present and able to be used

        # If we are running on Docker, we might be able to fetch additional information about the CUDA cores
        if ORCHESTRATOR == 'docker':
            if min_docker_version():
                logger.info('--gpus is available in Docker...')

            else:
                logger.info('--gpus is not available in Docker, but GPU usage is available')
            name, info = cuda_cores_information(runtime['devices'])

            runtime_files['name'] = name
            runtime_files['resources'] = info

        logger.info(runtime_files)
        return {identifier: runtime_files}

    elif len(nvidia_device(os.listdir(HOST_DEV_PATH))) > 0 and check_cuda_installation(get_device_type()):

        # A GPU is present, and ready to be used, but not with --gpus
        nv_devices = nvidia_device(os.listdir(HOST_DEV_PATH))
        _, _, formatted_libs = build_cuda_core_docker_cli(nv_devices)

        runtime = {'devices': nv_devices, 'libraries': formatted_libs}

        # only for Docker
        if ORCHESTRATOR == 'docker':
            name, info = cuda_cores_information(runtime['devices'])

            runtime_files['name'] = name
            runtime_files['resources'] = info

        runtime_files['additional-assets'] = runtime

        logger.info(runtime_files)
        return {identifier: runtime_files}

    else:

        # GPU is not present or not able to be used.
        logger.info('No viable GPU available.')

        return None


def gpu_check(api_url):
    """ Checks if peripheral already exists """

    logger.info('Checking if GPU already published')

    get_gpus = requests.get(api_url + '?identifier_pattern=' + identifier)

    logger.info(get_gpus.json())

    if not get_gpus.ok or not isinstance(get_gpus.json(), list) or len(get_gpus.json()) == 0:
        logger.info('No GPU published.')
        return True

    logger.info('GPU has already been published.')
    return False


def main():
    global logger
    parse_arguments_and_initialize_logging('GPU Peripheral')

    logger = logging.getLogger(__name__)
    gpu_peripheral: Peripheral = Peripheral('gpu')

    gpu_peripheral.run(flow, runtime=RUNTIME_PATH, host_files_path=HOST_FILES)


def entry():
    main()


if __name__ == "__main__":
    main()
