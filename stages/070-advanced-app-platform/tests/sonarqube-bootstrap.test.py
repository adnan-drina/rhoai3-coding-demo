#!/usr/bin/env python3
"""Credential preservation and refusal tests for the native Sonar setup Job."""
import base64
import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('sonar', ROOT /
    'gitops/stages/070-advanced-app-platform/070-sonarqube/bootstrap-admin.py')
sonar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sonar)


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.row = None
        self.accepted = 'admin'
        self.calls = []

    def oc(self, *args, data=None):
        self.calls.append(args[0])
        if args[0] == 'get': return copy.deepcopy(self.row)
        if args[0] == 'create':
            self.row = copy.deepcopy(data)
            self.row['data'] = {k: base64.b64encode(v.encode()).decode()
                                for k, v in self.row.pop('stringData').items()}
        if args[0] == 'patch': self.row['metadata']['annotations'].update(data['metadata']['annotations'])
        return copy.deepcopy(self.row)

    def request(self, path, password, data=None):
        self.calls.append('rotate')
        self.assertIsNotNone(self.row, 'credential must be durable before the first mutation')
        self.assertEqual(self.accepted, 'admin')
        self.accepted = data['password']
        return 204, b''

    def run_bootstrap(self):
        with patch.object(sonar, 'oc', self.oc), patch.object(sonar, 'valid', lambda p: p == self.accepted), \
             patch.object(sonar, 'request', self.request):
            return sonar.ensure_admin()

    def test_password_policy_persist_before_rotation_and_idempotence(self):
        value = self.run_bootstrap()
        self.assertGreaterEqual(len(value), 12)
        for predicate in (str.isupper, str.islower, str.isdigit, lambda c: not c.isalnum()):
            self.assertTrue(any(predicate(c) for c in value))
        self.assertLess(self.calls.index('create'), self.calls.index('rotate'))
        self.assertEqual(self.row['metadata']['annotations'][sonar.PHASE], 'ready')
        self.assertEqual(self.run_bootstrap(), value)
        self.assertEqual(self.calls.count('create'), 1)
        self.assertEqual(self.calls.count('rotate'), 1)

    def test_interrupt_after_rotation_reuses_pending_credential(self):
        self.run_bootstrap()
        self.row['metadata']['annotations'][sonar.PHASE] = 'pending'
        self.calls = []
        self.assertEqual(self.run_bootstrap(), self.accepted)
        self.assertNotIn('rotate', self.calls)

    def test_storage_failure_sends_no_password_change(self):
        with patch.object(sonar, 'oc', side_effect=[None, RuntimeError('storage unavailable')]), \
             patch.object(sonar, 'request') as request, self.assertRaises(RuntimeError):
            sonar.ensure_admin()
        request.assert_not_called()

    def test_http_failure_preserves_the_pending_value(self):
        with patch.object(sonar, 'oc', self.oc), patch.object(sonar, 'valid', lambda p: p == 'admin'), \
             patch.object(sonar, 'request', return_value=(400, b'not logged')), self.assertRaises(RuntimeError):
            sonar.ensure_admin()
        pending = copy.deepcopy(self.row)
        self.assertEqual(self.row['metadata']['annotations'][sonar.PHASE], 'pending')
        value = self.run_bootstrap()
        self.assertEqual(base64.b64decode(pending['data']['password']).decode(), value)

    def test_unknown_existing_credential_is_not_reset(self):
        self.run_bootstrap()
        self.accepted = 'admin'
        self.calls = []
        with self.assertRaises(RuntimeError): self.run_bootstrap()
        self.assertNotIn('rotate', self.calls)

    def test_unreachable_authentication_is_not_rotation(self):
        with patch.object(sonar, 'oc', self.oc), patch.object(sonar, 'valid', side_effect=TimeoutError), \
             patch.object(sonar, 'request') as request, self.assertRaises(TimeoutError):
            sonar.ensure_admin()
        self.assertEqual(self.row['metadata']['annotations'][sonar.PHASE], 'pending')
        request.assert_not_called()


if __name__ == '__main__': unittest.main()
