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

    def test_enforced_allowance_must_fit_the_shared_quota(self):
        # B3 / R2: the paced allowance at the served window, plus the reserve,
        # every other running migration run counted, and the pacer configured
        code = self.fill()
        self.assertIn("budget_gap = rate_budget_gap(q, 262144, runs, 60000000)", code)
        self.assertIn("runs = 1 + 0", code)
        self.assertIn("'MOD' + 'EL_RATE_BUDGET", code)
        self.assertIn("RHOAI3_REQUEST_BUDGET=%d/%d", code)   # request mode (runs pinned before V15-1)
        self.assertIn("is_migration_run", LOCAL)
        self.assertNotIn("QLIMITVAL", code)

    def test_rate_budget_arithmetic(self):
        # The final pacing review: sized at the served 262144 window, 200
        # requests/h no longer fits 60M with the 9M reserve; 190 does. The
        # platform profile itself is the one admitted.
        import json
        ns = {}
        fn = next(n for n in ast.parse(self.fill()).body if isinstance(n, ast.FunctionDef) and n.name == 'rate_budget_gap')
        exec(ast.unparse(fn), ns)
        gap = ns['rate_budget_gap']
        base = {'max_request_tokens': 262144, 'max_output_tokens': 32768, 'reserve_tokens_per_window': 9000000}
        self.assertIn('declared 61428800', gap(dict(base, max_requests_per_window=200), 262144, 1, 60000000))
        self.assertEqual(gap(dict(base, max_requests_per_window=190), 262144, 1, 60000000), '')
        self.assertIn('declared 108614720', gap(dict(base, max_requests_per_window=190), 262144, 2, 60000000))
        # a profile that sizes a request below what the server admits is refused
        self.assertIn('model serves 262144', gap(dict(base, max_requests_per_window=190, max_request_tokens=252768), 262144, 1, 60000000))
        profiles = json.loads((HERE.parents[1] / 'gitops/stages/050-advanced-app-platform/base/devspaces/model-profiles.json').read_text())
        # V15-1: token mode admits by summed run allowances (51M + 9M reserve)
        tok = profiles['profiles']['qwen3-8-27b-int4']['quota']
        self.assertEqual(tok['accounting_mode'], 'token')
        self.assertEqual(gap(tok, 262144, 1, 60000000), '')
        self.assertIn('declared 111000000', gap(tok, 262144, 2, 60000000))
        self.assertIn('model serves 262144', gap(dict(tok, reservation_tokens=131072), 262144, 1, 60000000))
        self.assertIn('does not fit the allowance', gap(dict(tok, token_allowance_per_window=100000), 262144, 1, 60000000))
        self.assertIn('request ceiling', gap(dict(tok, max_requests_per_window=190), 262144, 1, 60000000))
        self.assertEqual(gap(profiles['profiles']['qwen3-6-27b']['quota'], 131072, 1, 20000000), '')

    def test_runtime_settings_match_the_mode(self):
        code = self.fill()
        self.assertIn("'RHOAI3_ACCOUNTING_MODE=token' in env_text", code)
        self.assertIn("'RHOAI3_REQUEST_BUDGET=' not in env_text", code)


class HookRegistrations(unittest.TestCase):
    """The effective managed config must carry the K2 hook fail-closed and,
    when the harness ships it, the terminal post_tool_call observer."""

    def snippet(self):
        code = DeclaredBudget().fill()
        return code[code.index('# The effective hook registrations'):code.index("require(c.get('model'")]

    def check(self, hooks, ships_post):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            if ships_post:
                (root / '.hermes/kernel').mkdir(parents=True)
                (root / '.hermes/kernel/post_tool_call.py').write_text('#!/usr/bin/env python3\n')

            def require(cond, msg):
                if not cond:
                    raise AssertionError(msg)
            exec(self.snippet(), {'require': require, 'root': root, 'c': {'hooks': hooks}})

    def test_registrations(self):
        k2 = {'matcher': 'write|terminal|kanban_complete|complete_task', 'command': '/m/agent-hooks/pre_tool_call.sh',
              'timeout': 5, 'fail_closed': True}
        post = {'matcher': 'terminal', 'command': '/m/agent-hooks/post_tool_call.py', 'timeout': 5}
        self.check({'pre_tool_call': [k2], 'post_tool_call': [post]}, True)
        for hooks, ships, text in (({'pre_tool_call': [dict(k2, fail_closed=False)], 'post_tool_call': [post]}, True, 'fail-closed'),
                                   ({'pre_tool_call': [dict(k2, timeout=60)], 'post_tool_call': [post]}, True, 'fail-closed'),
                                   ({}, True, 'fail-closed'),
                                   ({'pre_tool_call': [k2]}, True, 'post_tool_call observer'),
                                   ({'pre_tool_call': [k2], 'post_tool_call': [post]}, False, 'post_tool_call observer')):
            with self.assertRaises(AssertionError) as cm:
                self.check(hooks, ships)
            self.assertIn(text, str(cm.exception))


class BoardProtocol(unittest.TestCase):
    """The launch refuses an inconsistent, missing or downgraded protocol
    selection instead of launching the serial loop. The remote snippet runs
    here against real governed destinations and the golden selection module."""

    GOLDEN_LIB = HERE / 'scaffold-repo/quarkus-migration-scaffold/.hermes/lib'

    def snippet(self):
        code = DeclaredBudget().fill()
        return code[code.index('# The board protocol:'):code.index("print('PASS: fresh workspace")]

    def dest(self, td, request=None, has_request=True, selected=None, execution=None):
        import json, subprocess
        root, control = td / 'dest', td / 'control'
        root.mkdir()
        control.mkdir()
        decl = {'schema': 'rhoai3.run-budget/v2', 'run_id': 'run-x',
                'run_control': {'contract': 'rhoai3.run-control/v1', 'root': str(control), 'state': str(td / 'state')}}
        if has_request:
            decl['board_protocol'] = request
        (root / 'run-budget.json').write_text(json.dumps(decl))
        g = lambda *a: subprocess.run(['git', '-C', str(root), '-c', 'user.email=t@t', '-c', 'user.name=t', *a],  # noqa: E731
                                      capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        g('add', '-A')
        g('commit', '-qm', 'scaffold')
        doc = {'schema': 'rhoai3.run-control/v1', 'run_id': 'run-x', 'scaffold_commit': g('rev-parse', 'HEAD'),
               'activation': 'pilot', 'authorized_by': 'provision-migration-run:tr'}
        if selected:
            doc['board_protocol'] = selected
        if execution:
            doc['outcome_board'] = {'execution': execution}
        (control / 'contract.json').write_text(json.dumps(doc))
        return root

    def run_snippet(self, root):
        import io, json, subprocess, sys, contextlib
        sys.path.insert(0, str(self.GOLDEN_LIB))
        failures = []

        def require(cond, msg):
            if not cond:
                raise AssertionError(msg)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(self.snippet(), {'require': require, 'root': root, 'subprocess': subprocess, 'json': json})
        return out.getvalue()

    def test_consistent_selections_pass_and_disagreements_refuse(self):
        import tempfile
        cases = (
            (dict(has_request=False), None, 'serial-loop/v1'),                                # v12-v17 runs
            (dict(request='serial-loop/v1'), None, 'serial-loop/v1'),
            (dict(request='outcome-board/v1'), 'PROTOCOL_UNBOUND', None),                      # v17 live shape
            (dict(request='outcome-board/v1', selected='serial-loop/v1'), 'PROTOCOL_DOWNGRADED', None),
            (dict(has_request=False, selected='outcome-board/v1'), 'PROTOCOL_UNREQUESTED', None),
            (dict(request='outcome-board/v1', selected='outcome-board/v1'), 'OUTCOME_EXECUTION_DISABLED', None),
            (dict(request='outcome-board/v1', selected='outcome-board/v1', execution='enabled'), 'AUTHORITY_UNPROTECTED', None),
        )
        for kw, refusal, protocol in cases:
            with tempfile.TemporaryDirectory() as d:
                root = self.dest(Path(d).resolve(), **kw)
                if refusal:
                    with self.assertRaises(AssertionError) as cm:
                        self.run_snippet(root)
                    self.assertIn('BOARD_PROTOCOL: ' + refusal, str(cm.exception), kw)
                else:
                    self.assertIn('PASS: board protocol %s' % protocol, self.run_snippet(root), kw)

if __name__ == '__main__':
    unittest.main()
