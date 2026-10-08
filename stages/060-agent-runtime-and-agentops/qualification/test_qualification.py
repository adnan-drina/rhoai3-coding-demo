"""Offline failure tests. No cluster, gateway, credentials or model calls."""
import importlib.util
import json
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('qualification', Path(__file__).parents[1] / 'qualify-inference.py')
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def result(code=0, data=None, error=''):
    return subprocess.CompletedProcess([], code, json.dumps(data) if data is not None else '', error)


class QualificationTests(unittest.TestCase):
    def run_object(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return q.Run(folder.name)

    def test_profile_absence_requires_successful_typed_catalog(self):
        run = self.run_object()
        run.admin = lambda *args: result(data=[])
        self.assertFalse(run.profile_present())
        run.admin = lambda *args: result(data=[{'id': run.profile}])
        self.assertTrue(run.profile_present())
        # Exact sanitized first-run error: CLI renders the typed gRPC code as prose.
        errors = ["code: 'Some requested entity was not found', message: \"provider profile not found\"",
                  'Unauthenticated', 'Unavailable', 'timeout', 'connection refused', 'unknown flag']
        for error in errors:
            run.admin = lambda *args, error=error: result(1, error=error)
            with self.assertRaises(q.Failure):
                run.profile_present()
        run.admin = lambda *args: result(data={'profiles': []})
        with self.assertRaises(q.Failure):
            run.profile_present()

    def test_curated_subject_and_normal_role_required(self):
        membership = {'members': [{'subject': 'curated-id', 'role': 'user'}]}
        identity = {'subject': 'curated-id', 'display_name': 'ai-developer', 'roles': ['openshell-user']}
        q.verify_persona(identity, membership)
        for modified in [dict(identity, subject='foreign-id'), dict(identity, roles=['openshell-user', 'openshell-platform-admin'])]:
            with self.assertRaises(q.Failure):
                q.verify_persona(modified, membership)

    def test_generic_part_events_cannot_prove_streaming(self):
        events = [(1, 'message.updated', 's', {'info': {'id': 'm', 'role': 'assistant'}}),
                  (2, 'message.part.updated', 's', {'part': {'id': 'p', 'messageID': 'm', 'type': 'text'}})]
        self.assertEqual(q.text_deltas(events, 's'), [])
        events.append((3, 'message.part.delta', 's', {'messageID': 'm', 'partID': 'p', 'field': 'text', 'delta': 'x'}))
        self.assertEqual(q.text_deltas(events, 's'), [3])
        events[-1][3]['field'] = 'reasoning'
        self.assertEqual(q.text_deltas(events, 's'), [])

    def test_final_assistant_identity_and_budget(self):
        info = {'role': 'assistant', 'providerID': 'qwen38', 'modelID': q.MODEL, 'tokens': {'output': 30}}
        self.assertTrue(q.generated_output(200, info, 20))
        for changed in [dict(info, role='user'), dict(info, modelID='other'), dict(info, tokens={'output': 129}),
                        dict(info, tokens={'output': float('nan')}), dict(info, tokens={'output': True})]:
            self.assertFalse(q.generated_output(200, changed, 20))

    def test_abort_true_and_missing_status_are_not_cancellation(self):
        outcome = {'status': 200, 'reply': {'info': {'error': {'name': 'MessageAbortedError'}}}}
        self.assertTrue(q.cancelled(True, True, 200, True, outcome, 200, {'s': {'type': 'idle'}}, 's'))
        for status, states in [(500, {'s': {'type': 'idle'}}), (200, {}), (200, None)]:
            self.assertFalse(q.cancelled(True, True, 200, True, outcome, status, states, 's'))
        self.assertFalse(q.cancelled(True, True, 200, True, dict(outcome, transport='TimeoutError'), 200, {'s': {'type': 'idle'}}, 's'))

    def test_foreign_provider_id_is_never_deleted(self):
        run = self.run_object()
        run.save_state(runId=run.run_id, provider=True, providerId='own')
        run.resource = lambda *args: {'id': 'foreign'}
        run.admin = lambda *args: self.fail('Foreign provider must not be deleted')
        self.assertFalse(run.cleanup())
        self.assertTrue(run.state_path.exists())

    def test_profile_import_failure_does_not_delete_name(self):
        run = self.run_object()
        run.save_state(runId=run.run_id, profilePending=True)
        run.admin = lambda *args: self.fail('Unproven profile must not be deleted')
        self.assertFalse(run.cleanup())
        run.finish(q.Failure('Import response lost'), False)
        self.assertTrue(run.state_path.exists())

    def test_concurrent_policy_change_is_not_overwritten(self):
        run = self.run_object()
        run.save_state(runId=run.run_id, policy=True, policyHashBefore='before', policyHashApplied='applied', originalPolicy={'network_policies': {}})
        run.global_policy_hash = lambda: 'concurrent'
        run.admin = lambda *args: self.fail('Concurrent policy must not be overwritten')
        self.assertFalse(run.cleanup())

    def test_restored_hash_mismatch_retains_journal(self):
        run = self.run_object()
        original = {'network_policies': {}, 'landlock': {'compatibility': 'hard_requirement'}}
        run.save_state(runId=run.run_id, policy=True, policyHashBefore='before', policyHashApplied='applied', originalPolicy=original)
        hashes = iter(['applied', 'wrong'])
        run.global_policy_hash = lambda: next(hashes)
        def admin(args):
            self.assertEqual(json.loads(Path(args[-1]).read_text()), original)
            return result()
        run.admin = admin
        self.assertFalse(run.cleanup())
        run.finish(None, False)
        self.assertTrue(run.state_path.exists())

    def test_every_cleanup_step_runs_after_failure(self):
        run = self.run_object()
        run.save_state(runId=run.run_id, provider=True, providerId='own', keyId='key')
        run.resource = lambda *args: (_ for _ in ()).throw(q.Failure('Read failed'))
        run.maas_api, run.persona_token = 'https://invalid.example', 'offline'
        with patch.object(q, 'http', return_value=(200, {'status': 'revoked'})) as revoke:
            self.assertFalse(run.cleanup())
            revoke.assert_called_once()
        self.assertTrue(run.evidence['cleanup']['keyRevoked'])

    def test_main_exception_and_interrupt_always_cleanup(self):
        for error in [RuntimeError('offline'), KeyboardInterrupt()]:
            run = self.run_object()
            with patch.object(run, 'prepare', side_effect=error), patch.object(run, 'cleanup', return_value=False) as cleanup, \
                 patch.object(run, 'finish') as finish, patch.object(q, 'Run', return_value=run), \
                 patch.object(sys, 'argv', ['qualify-inference.py', '--run', str(run.dir)]):
                with self.assertRaises(SystemExit):
                    q.main()
                cleanup.assert_called_once()
                finish.assert_called_once()

    def test_sigterm_and_deadline_enter_cleanup(self):
        for sig in (signal.SIGTERM, signal.SIGALRM):
            run = self.run_object()
            with patch.object(run, 'prepare', side_effect=lambda: signal.raise_signal(sig)), \
                 patch.object(run, 'cleanup', return_value=False) as cleanup, patch.object(run, 'finish'), \
                 patch.object(q, 'Run', return_value=run), patch.object(sys, 'argv', ['q', '--run', str(run.dir)]):
                with self.assertRaises(SystemExit):
                    q.main()
                cleanup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
