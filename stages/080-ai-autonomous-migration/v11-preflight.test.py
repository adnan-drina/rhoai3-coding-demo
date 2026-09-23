#!/usr/bin/env python3
"""v11 isolation launch scope: every named check must PASS, including identity."""
import ast
import copy
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = (HERE / 'v11-preflight.sh').read_text().split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
TREE = ast.parse(LOCAL)


class IsolationLaunchScope(unittest.TestCase):
    def setUp(self):
        nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in ('need', 'check_isolation')]
        scope = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'isolation-launch', 'exec'), scope)
        self.check = scope['check_isolation']
        self.proof = {'checks': dict.fromkeys([
            'secret_binding', 'wrong_targets', 'assignment_removal', 'receipt_fields', 'delayed_resources',
            'data_independence', 'credential_independence', 'workspace_independence', 'repository_non_authority',
            'duplicate_delivery', 'overlapping_retirement', 'retirement', 'workspace_identity'], 'PASS')}

    def test_all_thirteen_pass(self):
        self.check(self.proof, 'spring-petclinic-rest-legacy-v11')
        self.check(self.proof, 'iso-v11-final')

    def test_v10_identity_failure_is_not_inherited(self):
        self.proof['checks']['workspace_identity'] = 'FAIL'
        with self.assertRaisesRegex(SystemExit, 'operational isolation|workspace identity'):
            self.check(self.proof, 'spring-petclinic-rest-legacy-v11')
        with self.assertRaisesRegex(SystemExit, 'operational isolation|workspace identity'):
            self.check(self.proof, 'spring-petclinic-rest-legacy-v10')

    def test_every_named_gap_blocks(self):
        for key in self.proof['checks']:
            for status in ('FAIL', 'INCONCLUSIVE', None):
                proof = copy.deepcopy(self.proof)
                proof['checks'][key] = status
                with self.subTest(key=key, status=status), self.assertRaisesRegex(SystemExit, 'operational isolation|workspace identity'):
                    self.check(proof, 'spring-petclinic-rest-legacy-v11')


if __name__ == '__main__':
    unittest.main()
