#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import mock
import unittest


from nuvlaedge.agent.orchestrator.factory import get_coe_client


class CoeFactoryTestCase(unittest.TestCase):

    @mock.patch('nuvlaedge.agent.orchestrator.docker.DockerClient')
    @mock.patch('nuvlaedge.agent.orchestrator.kubernetes.KubernetesClient')
    @mock.patch('nuvlaedge.agent.orchestrator.factory.os.getenv')
    def test_get_coe_client(self, mock_getenv, mock_k8s, mock_docker):
        # Docker
        mock_getenv.return_value = False
        mock_docker.return_value = 'docker'
        coe_client = get_coe_client()
        self.assertEqual(coe_client, 'docker',
                         'Failed to infer underlying K8s COE and return DockerClient')

        # Kubernetes
        mock_k8s.return_value = 'k8s'
        mock_getenv.return_value = True
        coe_client = get_coe_client()
        self.assertEqual(coe_client, 'k8s',
                         'Failed to infer underlying K8s COE and return KubernetesClient')
