"""Offline native Hermes protocol and independent result rejection tests."""
import copy
import importlib.util
import json
import io
from contextlib import redirect_stdout
from email.message import Message
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import sys
import unittest

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE))
spec = importlib.util.spec_from_file_location('hermes_qualification', STAGE/'qualify-hermes.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


class ProtocolTest(unittest.TestCase):
    def test_exact_accepted_run_not_an_openai_reply(self):
        reply = {'run_id': 'run_'+'a'*32, 'status': 'started'}
        self.assertTrue(q.created_run(202, reply))
        for code, value in ((200, reply), (202, {'run_id': 'foreign', 'status': 'started'}),
                            (202, {'run_id': 7, 'status': 'started'}), (202, {'choices': []}), (202, None)):
            with self.subTest(value=value): self.assertFalse(q.created_run(code, value))

    def test_public_health_is_not_authentication_denial(self):
        self.assertTrue(q.rejected_key(401, {'error': {'code': 'gateway_auth_failed'}}))
        for code, value in ((200, {'status': 'ok'}), (503, {'error': {'code': 'gateway_auth_failed'}}),
                            (401, {'error': {'code': 'model_auth_error'}}), (401, {'error': []}), (401, None)):
            with self.subTest(value=value): self.assertFalse(q.rejected_key(code, value))

    def test_installed_inputs_require_placeholder_private_listener_and_exact_hashes(self):
        probe=dict(placeholder=True,present=True,credentialHash='a'*64,configHash='config',startupHash='start',
                   listenerHash='listener',listenerPrivate=True,privateInterpreter=True)
        self.assertTrue(q.runtime_matches(probe,'config','start','listener','b'*64))
        for field,value in (('placeholder',False),('present',False),('credentialHash','b'*64),
                            ('configHash','drift'),('startupHash','drift'),('listenerHash','foreign'),
                            ('listenerPrivate',False),('privateInterpreter',False)):
            with self.subTest(field=field):
                self.assertFalse(q.runtime_matches(dict(probe,**{field:value}),'config','start','listener','b'*64))

    def test_poll_identity_is_owned_run_and_session(self):
        value = {'object': 'hermes.run', 'run_id': 'r', 'session_id': 's', 'status': 'running'}
        self.assertEqual(q.run_status(200, value, 'r', 's'), 'running')
        for code, changed in ((404, value), (200, dict(value, run_id='other')), (200, dict(value, session_id='other')), (200, {})):
            with self.subTest(value=changed), self.assertRaises(RuntimeError): q.run_status(code, changed, 'r', 's')


class FixtureAndStreamTest(unittest.TestCase):
    def test_native_seed_is_real_broken_python_and_test_uses_private_interpreter(self):
        qualification=q.Qualification(SimpleNamespace())
        self.assertIn(q.PYTHON+' -c ', qualification.command)
        self.assertNotIn('/usr/bin/python', qualification.command)
        with tempfile.TemporaryDirectory() as directory:
            qualification.directory=str(Path(directory)/'owned-fixture')
            def local_reviewed_probe(program):
                with redirect_stdout(io.StringIO()): exec(program, {})
            qualification.python=local_reviewed_probe
            qualification.seed_fixture()
            source=(Path(qualification.directory)/'qualification_add.py').read_text()
            compile(source, '<synthetic-fixture>', 'exec')
            with self.assertRaises(RuntimeError): q.oracle.verify_fixture(source)
            with self.assertRaises(FileExistsError): qualification.seed_fixture()

    def test_single_run_sse_accepts_deltas_and_rejects_foreign_or_malformed_data(self):
        qualification=q.Qualification(SimpleNamespace())
        qualification.local=1;qualification.key='synthetic-test-key'
        for raw, accepted in ((b': heartbeat\ndata: {"event":"message.delta","run_id":"r","delta":"public"}\n\n', True),
                              (b'data: {"event":"message.delta","run_id":"foreign","delta":"public"}\n', False),
                              (b'data: invalid-json\n', False)):
            stream=io.BytesIO(raw);stream.status=200;stream.headers=Message();stream.headers['Content-Type']='text/event-stream'
            opener=SimpleNamespace(open=lambda *args, **kwargs:stream)
            seen,errors=[],[]
            with self.subTest(raw=raw),patch.object(q.urllib.request,'build_opener',return_value=opener):
                qualification.events('r',seen,errors)
                self.assertEqual(not errors,accepted)
                self.assertEqual(bool(seen),accepted)


class CancellationTest(unittest.TestCase):
    def setUp(self):
        self.final = {'object': 'hermes.run', 'run_id': 'r', 'session_id': 's', 'status': 'cancelled', 'last_event': 'run.cancelled'}
        self.reply = {'run_id': 'r', 'status': 'stopping'}
        self.events = [(12, {'event': 'run.cancelled', 'run_id': 'r'})]

    def qualifies(self, **overrides):
        args = dict(active=True, text=True, stop_status=200, stop_reply=self.reply, poll_status=200,
                    final=self.final, run='r', session='s', events=self.events, requested=11)
        args.update(overrides); return q.cancelled(**args)

    def test_actual_terminal_event_and_settled_status(self):
        self.assertTrue(self.qualifies())

    def test_stop_acceptance_is_not_cancellation(self):
        for changed in (dict(self.final,status='stopping'),dict(self.final,status='completed'),dict(self.final,status='failed')):
            with self.subTest(status=changed['status']): self.assertFalse(self.qualifies(final=changed))
        self.assertFalse(self.qualifies(events=[]))
        self.assertFalse(self.qualifies(active=False))
        self.assertFalse(self.qualifies(text=False))

    def test_stale_foreign_or_failed_transport_cannot_pass(self):
        for args in ({'events':[(10,{'event':'run.cancelled','run_id':'r'})]},
                     {'events':[(12,{'event':'run.cancelled','run_id':'other'})]},
                     {'poll_status':404},{'stop_status':500},{'final':dict(self.final,session_id='other')},
                     {'stop_reply':{'run_id':'r','status':'cancelled'}}):
            with self.subTest(args=args): self.assertFalse(self.qualifies(**args))


class CodingEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.messages = [{'role':'assistant','tool_calls':[{'id':'call','function':{'name':'terminal','arguments':json.dumps({'command':'fixed test'})}}]},
                         {'role':'tool','tool_call_id':'call','tool_name':'terminal','content':json.dumps({'exit_code':0,'error':None})}]

    def test_exact_linked_successful_test(self):
        self.assertTrue(q.terminal_test(self.messages,'fixed test'))

    def test_foreign_tool_changed_command_or_failed_exit_rejected(self):
        for field, value in (('tool_call_id','foreign'),('content',json.dumps({'exit_code':1,'error':None})),
                             ('content',json.dumps({'exit_code':False,'error':None})),('content','[]')):
            messages=copy.deepcopy(self.messages); messages[1][field]=value
            with self.subTest(field=field,value=value): self.assertFalse(q.terminal_test(messages,'fixed test'))
        self.assertFalse(q.terminal_test(self.messages,'different test'))
        self.assertFalse(q.terminal_test(self.messages+[self.messages[1]],'fixed test'))
        extra=copy.deepcopy(self.messages);extra[0]['tool_calls'].append({'id':'extra','function':{'name':'terminal','arguments':json.dumps({'command':'unreviewed command'})}})
        self.assertFalse(q.terminal_test(extra,'fixed test'))

    def test_independent_fixture_rejects_bug_or_arbitrary_code(self):
        q.oracle.verify_fixture('def add(a,b):\n return a+b\n')
        for source in ('def add(a,b):\n return a-b\n', 'import os\ndef add(a,b):\n return a+b\n'):
            with self.subTest(source=source), self.assertRaises(RuntimeError): q.oracle.verify_fixture(source)

    def test_history_fingerprint_detects_changed_tool_result(self):
        original=q.fingerprint(self.messages)
        changed=copy.deepcopy(self.messages);changed[1]['content']=json.dumps({'exit_code':1,'error':None})
        self.assertNotEqual(original,q.fingerprint(changed))


if __name__=='__main__': unittest.main()
