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

    def test_run_stops_need_a_pinned_budget_for_the_selected_model(self):
        import json
        here = Path(__file__).resolve().parent
        table = json.loads((here.parents[1] / 'gitops/stages/060-advanced-app-platform/base/devspaces/model-profiles.json').read_text())
        defaults = json.loads((here / 'scaffold-repo/quarkus-migration-scaffold/run-defaults.json').read_text())
        gaps = SCOPE['run_stop_gaps']
        for model in table['profiles']:
            with self.subTest(model=model):
                self.assertEqual(gaps(table, model, defaults), [])
        missing = copy.deepcopy(table)
        missing['profiles']['qwen3-6-27b'].pop('run_input_token_budget')
        self.assertEqual(gaps(missing, 'qwen3-8-27b-int4', defaults), [])          # only the SELECTED model counts
        self.assertIn('RUN_TOKEN_BUDGET', gaps(missing, 'qwen3-6-27b', defaults)[0])
        for bad in (0, -1, True, '12000000', None):
            other = copy.deepcopy(table)
            other['profiles']['qwen3-8-27b-int4']['run_input_token_budget'] = bad
            with self.subTest(bad=bad):
                self.assertTrue(gaps(other, 'qwen3-8-27b-int4', defaults))
        no_retry = copy.deepcopy(table)
        no_retry['profiles']['qwen3-8-27b-int4']['loop_escalation'].pop('retry_start_turns')
        self.assertIn('retry_start_turns', gaps(no_retry, 'qwen3-8-27b-int4', defaults)[0])
        self.assertIn('RUN_TOKEN_BUDGET', gaps(table, 'unserved-model', defaults)[0])
        self.assertIn('RUN_TOKEN_BUDGET', gaps(None, 'qwen3-8-27b-int4', defaults)[0])
        for key in ('run_input_token_budget', 'no_accepted_checkpoint_minutes'):
            d = copy.deepcopy(defaults)
            d['budget'].pop(key)
            with self.subTest(key=key):
                self.assertEqual(gaps(table, 'qwen3-8-27b-int4', d), ['RUN_STOPS: run-defaults.json budget.%s is not a positive integer' % key])


if __name__ == '__main__':
    unittest.main()
