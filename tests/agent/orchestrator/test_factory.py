#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import mock
import unittest

from nuvlaedge.agent.orchestrator.factory import get_coe_client


class CoeFactoryTestCase(unittest.TestCase):

    @mock.patch('nuvlaedge.agent.orchestrator.docker.DockerClient.__init__')
    @mock.patch('nuvlaedge.agent.orchestrator.kubernetes.KubernetesClient.__init__')
    def test_get_coe_client(self, mock_k8s, mock_docker):
        from nuvlaedge.agent.orchestrator.docker import DockerClient
        from nuvlaedge.agent.orchestrator.kubernetes import KubernetesClient

        # Docker
        mock_docker.return_value = None
        coe_client = get_coe_client()
        self.assertIsInstance(coe_client, DockerClient,
                              'Failed to infer underlying K8s COE and return DockerClient')
        self.assertEqual(coe_client.ORCHESTRATOR, 'docker')

        # Kubernetes
        os.environ['KUBERNETES_SERVICE_HOST'] = 'something'
        mock_k8s.return_value = None
        coe_client = get_coe_client()
        self.assertIsInstance(coe_client, KubernetesClient,
                              'Failed to infer underlying K8s COE and return KubernetesClient')
        self.assertEqual(coe_client.ORCHESTRATOR, 'kubernetes')
