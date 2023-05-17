#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import mock
import unittest

from nuvlaedge.agent.orchestrator.factory import get_container_runtime


class CoeFactoryTestCase(unittest.TestCase):

    @mock.patch('nuvlaedge.agent.orchestrator.docker.DockerClient.__init__')
    @mock.patch('nuvlaedge.agent.orchestrator.kubernetes.KubernetesClient.__init__')
    def test_get_container_runtime(self, mock_k8s, mock_docker):
        from nuvlaedge.agent.orchestrator.docker import DockerClient
        from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient

        # Docker
        mock_docker.return_value = None
        container_runtime = get_container_runtime()
        self.assertIsInstance(container_runtime, DockerClient,
                              'Failed to infer underlying K8s COE and return DockerClient')
        self.assertEqual(container_runtime.ORCHESTRATOR, 'docker')

        # Kubernetes
        os.environ['KUBERNETES_SERVICE_HOST'] = 'something'
        mock_k8s.return_value = None
        container_runtime = get_container_runtime()
        self.assertIsInstance(container_runtime, KubernetesClient,
                              'Failed to infer underlying K8s COE and return KubernetesClient')
        self.assertEqual(container_runtime.ORCHESTRATOR, 'kubernetes')
