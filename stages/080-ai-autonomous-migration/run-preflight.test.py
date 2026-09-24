#!/usr/bin/env python3
"""run-preflight.sh: the v11 launch checks, for any run, with the budget read
through the factory declaration instead of a golden-carried timestamp."""
import ast
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXT = (HERE / 'run-preflight.sh').read_text()
LOCAL = TEXT.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
V11 = (HERE / 'v11-preflight.sh').read_text().split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
REMOTE = LOCAL.split("remote = '''", 1)[1].split("'''", 1)[0]
SUBSTITUTE = LOCAL.split("remote = '''", 1)[1].split("'''", 1)[1].split('\n', 1)[0]


def functions(source):
    return {n.name: ast.unparse(n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


class RunAgnostic(unittest.TestCase):
    def test_the_run_is_required_and_never_defaulted(self):
        self.assertIn('export WORKSPACE="${WORKSPACE:?', TEXT)
        # No run is named: not a project, not a suffix label. (check_isolation's
        # message about the v10-only deferral is inherited verbatim from v11.)
        self.assertNotRegex(TEXT, r'legacy-v\d|-v1[0-9]\b|["\']v1[0-9]["\']')
        self.assertNotIn('EXPECTED_MODEL:-', TEXT)          # the model pin comes from the golden defaults

    def test_isolation_and_pod_checks_are_the_v11_checks(self):
        # v11-preflight.test.py exercises these; this script must carry them unchanged.
        mine, v11 = functions(LOCAL), functions(V11)
        for name in ('check_isolation', 'check_worker_identity', 'worker_kubeconfig_mount_ok', 'source_mount_ok'):
            self.assertEqual(mine[name], v11[name], name)


class DeclaredBudget(unittest.TestCase):
    def fill(self, workspace='orders-modernization', hours=24):
        # Apply the script's own substitution chain to the remote template.
        chain = SUBSTITUTE.replace("'''", '', 1)
        values = {'expected_hours': hours, 'expected': {}, 'ns': 'wksp-ai-developer', 'workspace': workspace,
                  'maas_host': 'maas.example', 'maas_ip': '172.30.250.250',
                  'quota_limit': 60000000, 'quota_window': '1h', 'quota_others': 0,
                  'windows': [262144], 'json': __import__('json'),
                  'os': type('os', (), {'environ': {'EXPECTED_MODEL': 'qwen3-8-27b-int4'}})}
        return eval('REMOTE' + chain, {'REMOTE': REMOTE, 'repr': repr, 'str': str, **values})

    def test_budget_is_the_loader_verdict_for_this_run(self):
        code = self.fill('orders-modernization', 24)
        ast.parse(code)
        self.assertIn("run_declaration.load(root, expected_run='orders-modernization')", code)
        self.assertIn('d.code == run_declaration.OK', code)
        self.assertIn("d.budget.get('max_wall_hours') == 24", code)
        self.assertNotIn("budget['declared_at']", code)       # no golden-carried timestamp is read
        self.assertNotRegex(code, r'\b(EXPECTED_HOURS|WORKSPACE_NAME|WORKER_IDENTITY|MAASHOSTVAL|MAASIPVAL)\b')

    def test_workspace_must_be_on_the_in_cluster_maas_route(self):
        code = self.fill()
        self.assertIn("socket.getaddrinfo('maas.example', 443", code)
        self.assertIn("== {'172.30.250.250'}", code)
        self.assertIn("urlsplit(os.environ.get('MAAS_API_BASE_URL', '')).hostname == 'maas.example'", code)
        self.assertIn("oc('get','service','maas-gateway-internal'", LOCAL)

    def test_preflight_runs_the_workspace_startup_route_gate(self):
        # B1: the Operator preflight and the workspace startup check are one rule
        code = self.fill()
        self.assertIn("from planner.maas_route import route_gaps", code)
        self.assertIn("os.environ.get('RHOAI3_MAAS_HOST') == 'maas.example'", code)
        self.assertIn("os.environ.get('RHOAI3_MAAS_INTERNAL_IP') == '172.30.250.250'", code)

    def test_declared_demand_must_fit_the_shared_quota(self):
        # B3: worst case per request, every running workspace counted
        code = self.fill()
        self.assertIn("per_request = int(prof['context_length']) + int(prof['max_tokens'])", code)
        self.assertIn("runs = 1 + 0", code)
        self.assertIn("require(runs * demand <= 60000000,", code)
        self.assertIn("'MOD' + 'EL_RATE_BUDGET", code)
        self.assertNotIn("QLIMITVAL", code)

    def test_shared_defaults_must_match_the_golden(self):
        self.assertIn("expected['run-defaults.json'] = digest(golden / 'run-defaults.json')", LOCAL)
        self.assertIn("defaults['budget']['max_wall_hours']", LOCAL)
        self.assertIn("defaults['configuration']['model']['id']", LOCAL)


if __name__ == '__main__':
    unittest.main(verbosity=1)
