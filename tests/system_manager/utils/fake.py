#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import mock
import random
import kubernetes
from types import SimpleNamespace


def base_pod(name: str=None, phase: str='running'):
    pod = {
        'metadata': {
            'namespace': 'namespace',
            'selfLink': random.randint(100, 999),
            'name': name if name else random.randint(100, 999),
            'uid': name if name else random.randint(100, 999)
        },
        'status': {
            'container_statuses': [
                {
                    'name': 'container1',
                    'ready': True,
                    'restart_count': 1,
                    'state': ''
                },
                {
                    'name': name if name else 'container2',
                    'ready': True,
                    'restart_count': 2,
                    'state': ''
                }
            ],
            'phase': phase
        },
        'spec': {
            'containers': [
                {
                    'name': name if name else random.randint(100, 999)
                }
            ]
        }
    }
    return pod


def mock_kubernetes_pod(name: str=None, phase: str='running'):
    pod = json.loads(json.dumps(base_pod(name, phase)), object_hook=lambda d: SimpleNamespace(**d))
    # add 'state' after serialization cause k8s obj is not serializable
    for x in pod.status.container_statuses:
        x.state = kubernetes.client.V1ContainerState(waiting=True)
    return pod


def mock_kubernetes_node(uid: str=None, ready: bool=True):
    node = {
        'status': {
            'images': [
                'image1',
                'image2'
            ],
            'node_info': {
                'os_image': 'FakeOS',
                'kernel_version': 'fake kernel v0',
                'architecture': 'arm',
                'kubelet_version': 'v1'
            },
            'conditions': [{'last_heartbeat_time': 'time',
                            'last_transition_time': 'time',
                            'message': 'Flannel is running on this node',
                            'reason': 'FlannelIsUp',
                            'status': 'False',
                            'type': 'NetworkUnavailable'},
                           {'last_heartbeat_time': 'time',
                            'last_transition_time': 'time',
                            'message': 'kubelet is posting ready status. AppArmor enabled',
                            'reason': 'KubeletReady',
                            'status': 'True' if ready else 'False',
                            'type': 'Ready'}]
        },
        'metadata': {
            'name': f'{uid} NAME' if uid else random.randint(100, 999),
            'uid': uid if uid else random.randint(100, 999),
            'labels': [],
            'cluster_name': None
        }
    }

    return json.loads(json.dumps(node), object_hook=lambda d: SimpleNamespace(**d))


class Fake(object):
    """Create Mock()ed methods that match another class's methods."""

    @classmethod
    def imitate(cls, *others):
        for other in others:
            for name in other.__dict__:
                try:
                    setattr(cls, name, mock.MagicMock())
                except (TypeError, AttributeError):
                    pass
        return cls


class MockContainer(object):
    def __init__(self, name=None, status='paused', myid=None):
        self.status = status
        self.name = name if name else random.randint(100, 999)
        self.id = random.randint(100, 999) if not myid else myid
        self.labels = {
            'com.docker.compose.project.working_dir': '/workdir',
            'com.docker.compose.project.config_files': 'a.yml,b.yml',
            'com.docker.compose.project': 'nuvlaedge'
        }
        self.attrs = {
            'Config': {
                'Image': 'fake-image'
            },
            'NetworkSettings': {
                'Networks': {
                    'fake-network': {}
                }
            },
            'RestartCount': 1
        }
        self.am_i_alive = True
        self.is_alive_counter = mock.MagicMock()

    def remove(self):
        """ Not implemented """
        pass

    def kill(self):
        """ Not implemented """
        pass

    def is_alive(self):
        self.is_alive_counter()
        return self.am_i_alive


class MockService(object):
    def __init__(self, name, net_id):
        self.name = name
        self.updated = None
        self.attrs = {
            'Endpoint': {
                'VirtualIPs': [
                    {'NetworkID': net_id}
                ]
            }
        }

    def update(self, **kwargs):
        self.updated = True
        pass


class MockNetwork(object):
    def __init__(self, name):
        self.name = name
        self.id = random.randint(100, 999)
        self.attrs = {
            'Containers': {
                'c1': {},
                'c2': {}
            }
        }
        self.remove_counter = mock.MagicMock()
        self.disconnect_counter = mock.MagicMock()
        self.connect_counter = mock.MagicMock()

    def remove(self):
        self.remove_counter()

    def disconnect(self, _id):
        self.disconnect_counter()

    def connect(self, _id, **kwargs):
        self.connect_counter()


class FakeRequestsResponse(object):
    def __init__(self, **kwargs):
        self.status_code = kwargs.get('status_code') if kwargs.get('status_code') else 123
        self.json_response = kwargs.get('json_response') if kwargs.get('json_response') else {'req': 'fake response'}

    def json(self):
        return self.json_response
