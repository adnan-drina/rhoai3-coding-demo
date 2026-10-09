"""Offline rejection tests for independent verification and exact approvals."""
import importlib.util
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path
import sys
import unittest

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE))
spec = importlib.util.spec_from_file_location('qualify_opencode', STAGE/'qualify-opencode.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class IndependentTest(unittest.TestCase):
    def test_harmless_correct_fixture(self):
        q.verify_fixture('def add(a,b):\n return a+b\n')

    def test_buggy_fixture_rejected(self):
        with self.assertRaises(RuntimeError):
            q.verify_fixture('def add(a,b):\n return a-b\n')

    def test_side_effects_rejected_before_execution(self):
        for source in ("import os\ndef add(a,b):\n return a+b\n",
                       "def add(a,b):\n return __import__('os').system('false')\n",
                       "def add(a,b):\n return a+b\nadd(1,2)\n"):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                q.verify_fixture(source)

    def test_oversized_fixture_rejected(self):
        with self.assertRaises(RuntimeError):
            q.verify_fixture('def add(a,b):\n return a+b\n'+' ' * 512)


class ExactApprovalTest(unittest.TestCase):
    def setUp(self):
        self.request = {'id': 'per-fixed', 'sessionID': 'ses-fixed', 'permission': 'bash',
                        'metadata': {'command': q.TEST_COMMAND},
                        'tool': {'messageID': 'msg-fixed', 'callID': 'call-fixed'}}
        self.messages = [{'parts': [{'type': 'tool', 'tool': 'bash', 'messageID': 'msg-fixed',
                          'callID': 'call-fixed', 'state': {'input': {'command': q.TEST_COMMAND}}}]}]

    def test_exact_owned_command(self):
        self.assertTrue(q.exact_permission(self.request, 'ses-fixed', self.messages))

    def test_suffix_commands_rejected(self):
        self.request['metadata']['command'] += '; echo extra'
        self.assertFalse(q.exact_permission(self.request, 'ses-fixed', self.messages))

    def test_tool_input_mismatch_rejected(self):
        self.messages[0]['parts'][0]['state']['input']['command'] = 'python3 -c "print(0)"'
        self.assertFalse(q.exact_permission(self.request, 'ses-fixed', self.messages))

    def test_foreign_session_tool_or_message_rejected(self):
        self.assertFalse(q.exact_permission(self.request, 'ses-other', self.messages))
        for field in ('messageID', 'callID'):
            with self.subTest(field=field):
                self.request['tool'][field] = 'foreign'
                self.assertFalse(q.exact_permission(self.request, 'ses-fixed', self.messages))
                self.request['tool'][field] = {'messageID': 'msg-fixed', 'callID': 'call-fixed'}[field]
        self.request['permission'] = 'external_directory'
        self.assertFalse(q.exact_permission(self.request, 'ses-fixed', self.messages))


class AbortContractTest(unittest.TestCase):
    def test_fresh_idle_event_proves_documented_map_omission(self):
        events = [(12, 'session.status', 'ses-own', {'status': {'type': 'idle'}})]
        normalized = q.abort_statuses(200, {}, events, 'ses-own', 11)
        outcome = {'status': 200, 'reply': {'info': {'error': {'name': 'MessageAbortedError'}}}}
        self.assertTrue(q.checks.cancelled(True, True, 200, True, outcome, 200, normalized, 'ses-own'))
        outcome['reply']['info']['error']['name'] = 'APIError'
        self.assertFalse(q.checks.cancelled(True, True, 200, True, outcome, 200, normalized, 'ses-own'))

    def test_missing_stale_foreign_idle_or_failed_status_remains_unknown(self):
        for events in ([], [(10, 'session.idle', 'ses-own', {})], [(12, 'session.idle', 'ses-other', {})]):
            with self.subTest(events=events):
                self.assertEqual(q.abort_statuses(200, {}, events, 'ses-own', 11), {})
        self.assertEqual(q.abort_statuses(500, {}, [(12, 'session.idle', 'ses-own', {})], 'ses-own', 11), {})
        self.assertIsNone(q.abort_statuses(200, None, [(12, 'session.idle', 'ses-own', {})], 'ses-own', 11))
        busy = {'ses-own': {'type': 'busy'}}
        self.assertEqual(q.abort_statuses(200, busy, [(12, 'session.idle', 'ses-own', {})], 'ses-own', 11), busy)


class RemainingAdmissionTest(unittest.TestCase):
    def setUp(self):
        pending = ['applicationAbort', 'persistentRestart', 'runningAtEnd']
        self.receipt = {'passed': False, 'pendingGates': pending, 'failure': 'Gate failed: applicationAbort',
                        'checks': {g: g not in pending for g in q.GATES},
                        'ownedFixture': '/sandbox/workspace/qualification-0123456789abcdef/qualification_add.py',
                        'ownedMarker': '/sandbox/state/opencode-qualification-0123456789abcdef'}

    def test_exact_passed_coding_case(self):
        self.assertEqual(q.remaining_fixture(self.receipt),
                         ('/sandbox/workspace/qualification-0123456789abcdef', '/sandbox/state/opencode-qualification-0123456789abcdef'))

    def test_other_failure_or_unpassed_coding_rejected(self):
        for field, value in (('failure', 'Gate failed: independentTest'), ('pendingGates', ['applicationAbort']), ('passed', True)):
            candidate = dict(self.receipt, **{field: value})
            with self.subTest(field=field), self.assertRaises(RuntimeError): q.remaining_fixture(candidate)
        candidate = copy.deepcopy(self.receipt); candidate['checks']['codingTool'] = False
        with self.assertRaises(RuntimeError): q.remaining_fixture(candidate)

    def test_arbitrary_fixture_or_marker_rejected(self):
        for field, value in (('ownedFixture', '/sandbox/workspace/user-project/qualification_add.py'),
                             ('ownedFixture', '/sandbox/workspace/qualification-0123456789abcdef/../user.py'),
                             ('ownedMarker', '/sandbox/state/user-marker')):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                q.remaining_fixture(dict(self.receipt, **{field: value}))


class ForeignDenialTest(unittest.TestCase):
    def test_pinned_native_nonmember_denial(self):
        stderr = ("The caller does not have permission to execute the specified operation. "
                  "message: not a member of workspace 'openshell-developer'; ask a platform admin")
        self.assertTrue(q.foreign_workspace_denied(1, stderr))
        self.assertFalse(q.foreign_workspace_denied(0, stderr))
        self.assertFalse(q.foreign_workspace_denied(1, stderr.replace('openshell-developer', 'foreign-other')))

    def test_not_found_and_transport_errors_are_inconclusive(self):
        for stderr in ('Some requested entity was not found; sandbox not found',
                       'connection refused', 'The caller does not have permission to execute the specified operation',
                       "not a member of workspace 'openshell-developer'"):
            with self.subTest(stderr=stderr):
                self.assertFalse(q.foreign_workspace_denied(1, stderr))


class RuntimeOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.runtime = q.Qualification(SimpleNamespace())
        self.runtime.native = lambda: {'id': 'native-owned', 'phase': 'Ready'}
        self.runtime.deployment = SimpleNamespace(bootstrap_env={}, template={'image': 'registry@sha256:pinned'})
        self.sandboxes = {'items': [{'metadata': {'uid': 'sandbox-owned', 'labels': {'openshell.ai/sandbox-id': 'native-owned'}},
                                    'spec': {'volumeClaimTemplates': [{}]}}]}
        self.pods = {'items': [{'metadata': {'ownerReferences': [{'uid': 'sandbox-owned', 'controller': True}],
                     'annotations': {'openshift.io/scc': 'restricted-v2'}},
                     'spec': {'serviceAccountName': 'openshell-sandbox', 'automountServiceAccountToken': False,
                              'containers': [{'name': 'agent', 'image': 'registry@sha256:pinned'}],
                              'volumes': [{'persistentVolumeClaim': {'claimName': 'owned-claim'}}]},
                     'status': {'phase': 'Running', 'containerStatuses': [{'name': 'agent', 'ready': True, 'imageID': 'registry@sha256:pinned'}]}}]}
        self.pvcs = {'items': [{'metadata': {'name': 'owned-claim', 'uid': 'pvc-owned',
                                 'ownerReferences': [{'uid': 'sandbox-owned'}]}, 'status': {'phase': 'Bound'}}]}

    def verify(self, settle=False):
        with patch.object(q, 'setup', SimpleNamespace(DIGEST='sha256:pinned')), \
             patch.object(q, 'oc', side_effect=[json.dumps(self.sandboxes), json.dumps(self.pods), json.dumps(self.pvcs)]):
            return self.runtime.settled_resources() if settle else self.runtime.resources()

    def test_valid_owned_runtime(self):
        self.assertEqual(self.verify(), {'sandboxUid': 'sandbox-owned', 'pvcs': [('owned-claim', 'pvc-owned')]})

    def test_native_starting_waits_without_executing(self):
        self.runtime.native = Mock(side_effect=[{'id': 'native-owned', 'phase': 'Starting'},
                                               {'id': 'native-owned', 'phase': 'Ready'}])
        with patch.object(q.time, 'sleep'):
            self.assertEqual(self.verify(settle=True)['sandboxUid'], 'sandbox-owned')
        self.assertEqual(self.runtime.native.call_count, 2)

    def test_native_terminal_error_fails_immediately(self):
        self.runtime.native = Mock(return_value={'id': 'native-owned', 'phase': 'Error'})
        with patch.object(q.time, 'sleep') as sleep, self.assertRaises(RuntimeError):
            self.verify(settle=True)
        sleep.assert_not_called()

    def test_foreign_controller_rejected(self):
        self.pods['items'][0]['metadata']['ownerReferences'][0]['uid'] = 'foreign'
        with self.assertRaises(RuntimeError): self.verify()

    def test_foreign_mounted_claim_rejected(self):
        self.pods['items'][0]['spec']['volumes'][0]['persistentVolumeClaim']['claimName'] = 'foreign'
        with self.assertRaises(RuntimeError): self.verify()

    def test_wrong_actual_image_rejected(self):
        self.pods['items'][0]['status']['containerStatuses'][0]['imageID'] = 'registry@sha256:foreign'
        with self.assertRaises(RuntimeError): self.verify()


if __name__ == '__main__':
    unittest.main()
