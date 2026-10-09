"""Offline native Hermes protocol and independent result rejection tests."""
import copy
import importlib.util
import json
import io
import os
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

    def test_pinned_attachment_schema_omits_id_but_keeps_exact_authority(self):
        value={'next_page_token':'','providers':[{'name':'hermes-maas-qwen38','type':'hermes-maas-qwen38',
               'credential_keys':['MAAS_API_KEY'],'config_keys':['maas_key_id','owner']}]}
        self.assertTrue(q.attachment_matches(value,'hermes-maas-qwen38'))
        reversed_keys=copy.deepcopy(value);reversed_keys['providers'][0]['config_keys'].reverse()
        self.assertTrue(q.attachment_matches(reversed_keys,'hermes-maas-qwen38'))
        for field,changed in (('name','foreign'),('type','custom'),('credential_keys',[]),
                              ('credential_keys',['MAAS_API_KEY','OTHER_KEY']),('config_keys',['owner']),('config_keys',['maas_key_id','owner','owner']),('id','unsupported')):
            drift=copy.deepcopy(value);drift['providers'][0][field]=changed
            with self.subTest(field=field,changed=changed): self.assertFalse(q.attachment_matches(drift,'hermes-maas-qwen38'))
        for drift in (dict(value,next_page_token='more'),dict(value,providers=[]),dict(value,providers=value['providers']*2)):
            self.assertFalse(q.attachment_matches(drift,'hermes-maas-qwen38'))

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


class ConfinementTest(unittest.TestCase):
    def test_exact_permission_denial_never_generic_connectivity_failure(self):
        for number in (1,13): self.assertTrue(q.permission_denied({'errno':number}))
        for number in (None,2,17,110,111,False): self.assertFalse(q.permission_denied({'errno':number}))

    def test_inspected_rest_denial_requires_native_route_binary_and_policy(self):
        body={'error':'policy_denied','policy':'hermes_maas','layer':'l7','protocol':'rest',
              'method':'GET','path':'/v1/chat/completions','host':'public.example','port':443,'binary':q.PYTHON}
        body['rule_missing']=dict(type='rest_allow',**{k:v for k,v in body.items() if k not in ('error','policy','protocol')})
        value={'status':403,'policyHeader':'hermes_maas','body':body}
        self.assertTrue(q.inspected_denial(value,'GET','/v1/chat/completions','public.example','hermes_maas'))
        for field,changed in (('error','middleware_failed'),('binary','/usr/bin/python3.11'),('path','/v1/models'),('layer','http_response_pre_return')):
            drift=copy.deepcopy(value);drift['body'][field]=changed
            with self.subTest(field=field):self.assertFalse(q.inspected_denial(drift,'GET','/v1/chat/completions','public.example','hermes_maas'))
        for drift in (dict(value,status=401),dict(value,policyHeader=None),{'transportFailure':'TimeoutError'}):
            self.assertFalse(q.inspected_denial(drift,'GET','/v1/chat/completions','public.example','hermes_maas'))

    def test_unexpected_write_cleans_only_its_exact_created_probe_and_still_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            original_open,original_stat,original_unlink=os.open,os.lstat,os.unlink
            paths={p:str(Path(directory)/str(i)) for i,p in enumerate(('/opt/hermes-venv/.hermes-confinement-owned123','/etc/.hermes-confinement-owned123'))}
            removed=[]
            def opened(path,flags,mode=0o777):
                if path=='/root/.hermes-confinement-owned123':raise PermissionError(13,'reviewed synthetic denial')
                return original_open(paths[path],flags,mode)
            def unlinked(path):removed.append(path);original_unlink(paths[path])
            socket_probe=SimpleNamespace(settimeout=lambda *a:None,connect=lambda *a:(_ for _ in ()).throw(PermissionError(13,'synthetic denial')),close=lambda:None)
            output=io.StringIO()
            connection=SimpleNamespace(request=lambda *a,**k:(_ for _ in ()).throw(TimeoutError()),close=lambda:None)
            with patch.object(os,'open',side_effect=opened),patch.object(os,'lstat',side_effect=lambda path:original_stat(paths[path])),\
                 patch.object(os,'unlink',side_effect=unlinked),patch.object(q.socket,'socket',return_value=socket_probe),\
                 patch('http.client.HTTPSConnection',return_value=connection),redirect_stdout(output):
                exec(q.confinement_program('owned123','public.example'),{})
            result=json.loads(output.getvalue())
            self.assertEqual(set(removed),set(paths))
            self.assertFalse(list(Path(directory).iterdir()))
            for key in ('privateWrite','systemWrite'):
                self.assertTrue(result[key]['cleaned'])
                self.assertFalse(q.permission_denied(result[key]))

    def test_supplement_selects_no_coding_gates_and_program_has_bounded_syntax(self):
        qualification=q.Qualification(SimpleNamespace(confinement_only=True))
        self.assertEqual(qualification.gates,q.CONFINEMENT_GATES)
        self.assertNotIn('codingTool',qualification.gates)
        self.assertNotIn('ownedFixture',qualification.receipt)
        compile(q.confinement_program('owned123','public.example'),'<reviewed-probe>','exec')


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
