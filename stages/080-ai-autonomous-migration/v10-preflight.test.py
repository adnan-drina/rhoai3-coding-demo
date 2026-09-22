#!/usr/bin/env python3
"""Exercise the shipped remote launch checks; cluster qualification is separate."""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'scaffold-repo/quarkus-migration-scaffold/.hermes/lib'))
from planner import run_identity, yamlite

LOCAL = (HERE / 'v10-preflight.sh').read_text().split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
TREE = ast.parse(LOCAL)
REMOTE = next(n.value for n in ast.walk(TREE) if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value.startswith('def require(condition, message):'))


class Preflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'manifest.json').write_text('{}')
        (self.root / 'code.py').write_text('reviewed')
        (self.root / 'config.yaml').touch()
        (self.root / 'legacy/.git').mkdir(parents=True)
        (self.root / 'legacy/.git/rhoai3-source.json').write_text(json.dumps({'schema':'rhoai3.source-volume/v1','commit':'a'*40}))
        (self.root / 'run-budget.json').write_text(json.dumps({'max_wall_hours':24,'declared_at':'1970-01-01T00:00:01Z'}))
        self.config = {'model':{'default':'qwen3-8-27b-int4'},'provider':{'context_length':110000},
                       'terminal':{'timeout':900},'compression':{'threshold':0.8}}
        self.decisions = {'loop':{'unit_formation':'v1','runtime_feedback':'v1'},'decided_repairs':{
            'manifest':'manifest.json','manifest_sha256':hashlib.sha256(b'{}').hexdigest()}}
        expected = {'code.py':hashlib.sha256(b'reviewed').hexdigest()}
        self.code = REMOTE.replace("'/projects/modernized'",repr(str(self.root))).replace(
            "'/etc/hermes/config.yaml'",repr(str(self.root/'config.yaml'))).replace(
            "'/projects/legacy'",repr(str(self.root/'legacy'))).replace('EXPECTED',repr(json.dumps(expected))).replace('MODEL',repr('qwen3-8-27b-int4')).replace('WINDOW','131072')

    def execute(self, *, writable=False, ownership=True, gaps=()):
        verdict = run_identity.Verdict(run_identity.OK if ownership else run_identity.RECEIPT_MISMATCH,
                                      'binding',observed={'host':'assigned-db','port':5432})
        with patch.object(run_identity,'check',return_value=verdict), \
             patch.object(run_identity,'fixture_gaps',return_value=list(gaps)), \
             patch.object(yamlite,'load_yaml',side_effect=lambda p:self.config if p.name=='config.yaml' else self.decisions), \
             patch('socket.create_connection',return_value=MagicMock()) as connect, \
             patch('os.statvfs',return_value=types.SimpleNamespace(f_flag=0 if writable else os.ST_RDONLY)), \
             patch('subprocess.check_output',side_effect=lambda args, **kw: 'a'*40+'\n' if 'rev-parse' in args else '100\n'), contextlib.redirect_stdout(io.StringIO()):
            try:
                exec(compile(self.code,'preflight-remote','exec'),{})
            finally:
                if not ownership:
                    connect.assert_not_called()

    def test_qualified_fresh_workspace_passes(self):
        self.execute()

    def test_owned_endpoint_required_before_connection(self):
        with self.assertRaisesRegex(AssertionError,'binding'):
            self.execute(ownership=False)

    def test_wrong_model_and_context_refuse(self):
        self.config['model']['default']='qwen3-6-27b'
        with self.assertRaisesRegex(AssertionError,'model'): self.execute()
        self.config['model']['default']='qwen3-8-27b-int4'
        self.config['provider']['context_length']=131072
        with self.assertRaisesRegex(AssertionError,'context'): self.execute()

    def test_late_budget_refuses(self):
        (self.root/'run-budget.json').write_text(json.dumps({'max_wall_hours':24,'declared_at':'1970-01-01T00:03:00Z','declared_before_launch':True}))
        with self.assertRaisesRegex(AssertionError,'budget'): self.execute()

    def test_active_or_bootstrapped_run_refuses(self):
        p=self.root/'verification/loop/issued.json';p.parent.mkdir(parents=True);p.write_text('{"task_id":"t-running"}')
        with self.assertRaisesRegex(AssertionError,'issued'): self.execute()
        p.unlink();p=self.root/'evidence/producers/bootstrap.json';p.parent.mkdir(parents=True);p.write_text('{}')
        with self.assertRaisesRegex(AssertionError,'fresh'): self.execute()

    def test_source_and_credential_gaps_refuse(self):
        with self.assertRaisesRegex(AssertionError,'writable'): self.execute(writable=True)
        with self.assertRaisesRegex(AssertionError,'fixture'): self.execute(gaps=['CREDENTIAL'])

    def test_changed_harness_refuses(self):
        (self.root/'code.py').write_text('changed')
        with self.assertRaisesRegex(AssertionError,'harness'): self.execute()

    def test_runtime_source_aliases_refuse(self):
        ns = {}
        node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'source_mount_ok')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'source-mount', 'exec'), ns)
        check = ns['source_mount_ok']
        source = {'name':'data','mountPath':'/projects/legacy','subPath':'legacy-input','readOnly':True}
        pod = {'spec':{'containers':[{'name':'worker','volumeMounts':[source,{'name':'data','mountPath':'/projects','subPath':'projects'}]}],
                       'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'claim'}}]}}
        self.assertTrue(check(pod, 'worker'))
        pod['spec']['containers'].append({'name':'sidecar','volumeMounts':[{'name':'alias','mountPath':'/raw'}]})
        pod['spec']['volumes'].append({'name':'alias','persistentVolumeClaim':{'claimName':'claim'}})
        self.assertFalse(check(pod, 'worker'))
        pod['spec']['containers'][-1]['volumeMounts'][0]['subPath'] = 'legacy-input/src'
        self.assertFalse(check(pod, 'worker'))
        pod['spec']['containers'].pop()
        source['readOnly'] = False
        self.assertFalse(check(pod, 'worker'))

    def test_missing_source_receipt_refuses(self):
        (self.root / 'legacy/.git/rhoai3-source.json').unlink()
        with self.assertRaisesRegex(AssertionError, 'source clone receipt'): self.execute()


class IsolationLaunchScope(unittest.TestCase):
    def setUp(self):
        nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in ('need','check_isolation')]
        scope = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'isolation-launch', 'exec'), scope)
        self.check = scope['check_isolation']
        self.proof = {'checks': dict.fromkeys([
            'secret_binding','wrong_targets','assignment_removal','receipt_fields','delayed_resources',
            'data_independence','credential_independence','workspace_independence','repository_non_authority',
            'duplicate_delivery','overlapping_retirement','retirement'], 'PASS')}
        self.proof['checks']['workspace_identity'] = 'FAIL'

    def test_known_v10_failure_is_visible_and_preserved(self):
        before = copy.deepcopy(self.proof)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.check(self.proof, 'spring-petclinic-rest-legacy-v10')
        self.assertIn('workspace_identity remains FAIL', output.getvalue())
        self.assertEqual(before, self.proof)

    def test_every_operational_failure_or_gap_still_blocks(self):
        for key in self.proof['checks']:
            if key == 'workspace_identity':
                continue
            for status in ('FAIL', 'INCONCLUSIVE', None):
                proof = copy.deepcopy(self.proof)
                proof['checks'][key] = status
                with self.subTest(key=key, status=status), self.assertRaisesRegex(SystemExit, 'operational isolation'):
                    self.check(proof, 'spring-petclinic-rest-legacy-v10')

    def test_unmeasured_identity_or_other_run_is_not_exempt(self):
        with self.assertRaisesRegex(SystemExit, 'workspace identity'):
            self.check(self.proof, 'another-run')
        for status in (None, 'INCONCLUSIVE'):
            self.proof['checks']['workspace_identity'] = status
            with self.assertRaisesRegex(SystemExit, 'workspace identity'):
                self.check(self.proof, 'spring-petclinic-rest-legacy-v10')
        self.proof['checks']['workspace_identity'] = 'PASS'
        self.check(self.proof, 'another-run')


if __name__ == '__main__':
    unittest.main()
