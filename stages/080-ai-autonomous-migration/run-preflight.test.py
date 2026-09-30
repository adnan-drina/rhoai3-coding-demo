#!/usr/bin/env python3
"""Exercise launch identity checks without a cluster or isolation campaign."""
import ast
import copy
import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('run-preflight.sh').read_text()
SOURCE = SCRIPT.split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
TREE = ast.parse(SOURCE)
SCOPE = {'re': re}
exec(compile(ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef)],
                        type_ignores=[]), '<preflight-functions>', 'exec'), SCOPE)


class Preflight(unittest.TestCase):
    def setUp(self):
        self.images = {'databaseImage': 'registry/db@sha256:' + 'a' * 64,
                       'provisionerImage': 'registry/cli@sha256:' + 'b' * 64}
        self.defaults = {'configuration': {'images': self.images}}

    def test_current_receipt_matches_released_images_without_old_campaign(self):
        SCOPE['check_image_bindings'](self.defaults, dict(self.images))
        # An environment variable for old campaigns must not become a launch gate.
        self.assertNotIn('ISOLATION_RECEIPT', SCRIPT)

    def test_foreign_or_missing_receipt_image_refuses(self):
        for key in self.images:
            for value in (None, 'registry/foreign@sha256:' + 'c' * 64, 'registry/tag:latest'):
                receipt = dict(self.images)
                receipt[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(SystemExit):
                    SCOPE['check_image_bindings'](self.defaults, receipt)

    def test_missing_or_unpinned_golden_image_refuses(self):
        for key in self.images:
            for value in (None, 'registry/tag:latest'):
                defaults = copy.deepcopy(self.defaults)
                defaults['configuration']['images'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(SystemExit):
                    SCOPE['check_image_bindings'](defaults, dict(self.images))

    def test_worker_identity_still_refuses_foreign_or_default_role(self):
        workspace, namespace = 'orders-migration', 'wksp-test'
        receipt = {'workerServiceAccount': workspace + '-worker'}
        pod = {'spec': {'serviceAccountName': workspace + '-worker'}}
        check = SCOPE['check_worker_identity']
        check(pod, receipt, {}, namespace, workspace)
        with self.assertRaises(SystemExit):
            check({'spec': {'serviceAccountName': 'workspace-legacy-sa'}}, receipt,
                  {}, namespace, workspace)
        for subject in ({'kind': 'ServiceAccount', 'name': workspace + '-worker', 'namespace': namespace},
                        {'kind': 'Group', 'name': 'system:serviceaccounts:' + namespace},
                        {'kind': 'User', 'name': 'system:serviceaccount:' + namespace + ':' + workspace + '-worker'}):
            with self.subTest(subject=subject), self.assertRaises(SystemExit):
                check(pod, receipt, {'subjects': [subject]}, namespace, workspace)


if __name__ == '__main__':
    unittest.main()
