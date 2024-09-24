import unittest

from nuvlaedge.agent.nuvla.resources import NuvlaID


class TestNuvlaID(unittest.TestCase):

    def test_nuvla_id(self):
        nuvla_id = NuvlaID('')
        self.assertEqual(nuvla_id.resource, '')
        self.assertEqual(nuvla_id.uuid, '')

        nuvla_id = NuvlaID('nuvlabox/uuid')
        self.assertEqual(nuvla_id.resource, 'nuvlabox')
        self.assertEqual(nuvla_id.uuid, 'uuid')

        nuvla_id = NuvlaID('nuvlaedge/uuid')
        self.assertEqual(nuvla_id.resource, 'nuvlaedge')
        self.assertEqual(nuvla_id.uuid, 'uuid')

        nuvla_id = NuvlaID('uuid')
        self.assertEqual(nuvla_id.resource, '')
        self.assertEqual(nuvla_id.uuid, 'uuid')

        nuvla_id = NuvlaID('525dab27-2bf2-46a7-a744-668850cf3edb')
        self.assertEqual(nuvla_id.resource, '')
        self.assertEqual(nuvla_id.uuid, '525dab27-2bf2-46a7-a744-668850cf3edb')

        nuvla_id = NuvlaID('nuvlabox/bf11c404-7f41-43f8-8337-739996a6d5da')
        self.assertEqual(nuvla_id.resource, 'nuvlabox')
        self.assertEqual(nuvla_id.uuid, 'bf11c404-7f41-43f8-8337-739996a6d5da')

        nuvla_id = NuvlaID('nuvlaedge/913f775e-fa7c-4f90-816b-5a4c51f3bf56')
        self.assertEqual(nuvla_id.resource, 'nuvlaedge')
        self.assertEqual(nuvla_id.uuid, '913f775e-fa7c-4f90-816b-5a4c51f3bf56')

        nuvla_id = NuvlaID('api/nuvlaedge/a7ca6785-0de7-4c92-bc0a-305e23a2dfa6')
        self.assertEqual(nuvla_id.resource, 'api/nuvlaedge')
        self.assertEqual(nuvla_id.uuid, 'a7ca6785-0de7-4c92-bc0a-305e23a2dfa6')

        nuvla_id = NuvlaID('nuvlabox/')
        self.assertEqual(nuvla_id.resource, 'nuvlabox')
        self.assertEqual(nuvla_id.uuid, '')

        nuvla_id = NuvlaID('')
        self.assertFalse(nuvla_id.validate())

        nuvla_id = NuvlaID('uuid')
        self.assertFalse(nuvla_id.validate())

        nuvla_id = NuvlaID('nuvlaedge/')
        self.assertTrue(nuvla_id.validate())

        nuvla_id = NuvlaID('nuvlaedge/uuid')
        self.assertTrue(nuvla_id.validate())

        nuvla_id = NuvlaID('e5b52cfb-3cd1-4cb5-8001-3e24c604f76e')
        self.assertFalse(nuvla_id.validate())

        nuvla_id = NuvlaID('nuvlabox/0e7f9387-e1ec-4cfc-a299-408ac52864ee')
        self.assertTrue(nuvla_id.validate())
