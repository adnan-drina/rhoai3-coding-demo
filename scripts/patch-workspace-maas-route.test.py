#!/usr/bin/env python3
"""Exercise the operator helper without a cluster or real credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class RoutePatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copy(Path(__file__).with_name('patch-workspace-maas-route.sh'), self.root)
        (self.root / 'lib.sh').write_text(
            'load_env() { export GUARD_LOADED=yes; }\n'
            'check_oc_logged_in() { test "${GUARD_OK:-yes}" = yes; }\n')
        oc = self.root / 'oc'
        oc.write_text('''#!/usr/bin/env python3
import json, os, sys
assert os.environ.get('GUARD_LOADED') == 'yes'
a = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(a) + '\\n')
if a[0] == 'patch':
    pass
elif a[1] == 'gateway':
    print('maas.example.test')
elif a[1] == 'svc':
    print('172.30.1.2')
elif 'started' in a[-1]:
    print(os.environ.get('STARTED', 'false'))
elif 'pod-overrides' in a[-1]:
    print(os.environ.get('OVERRIDES', '{}'))
''')
        oc.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
                    'CALLS': str(self.root / 'calls'), 'STARTED': 'false'}

    def run_patch(self, **env):
        result = subprocess.run(['bash', str(self.root / 'patch-workspace-maas-route.sh'),
                                 'fixture', 'test'], env={**self.env, **env},
                                text=True, capture_output=True)
        calls = self.root / 'calls'
        return result, [json.loads(x) for x in calls.read_text().splitlines()] if calls.exists() else []

    def test_stopped_workspace_uses_guarded_merge(self):
        result, calls = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        patch = next(c for c in calls if c[0] == 'patch')
        self.assertEqual(patch[patch.index('--type') + 1], 'merge')
        payload = json.loads(patch[patch.index('-p') + 1])
        self.assertEqual(payload['spec']['template']['attributes']['pod-overrides']['spec'],
                         {'hostAliases': [{'ip': '172.30.1.2', 'hostnames': ['maas.example.test']}]})

    def test_running_or_unknown_workspace_never_patched(self):
        for started in ('true', ''):
            with self.subTest(started=started):
                result, calls = self.run_patch(STARTED=started)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('stop fixture', result.stdout)
                self.assertFalse(any(c[0] == 'patch' for c in calls))

    def test_guard_failure_prevents_cluster_access(self):
        result, calls = self.run_patch(GUARD_OK='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_existing_route_is_noop_even_when_running(self):
        result, calls = self.run_patch(STARTED='true', OVERRIDES=json.dumps(
            {'spec': {'serviceAccountName': 'fixture-worker',
                      'hostAliases': [{'ip': '172.30.1.2', 'hostnames': ['maas.example.test']}]}}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[0] == 'patch' for c in calls))


if __name__ == '__main__':
    unittest.main()
