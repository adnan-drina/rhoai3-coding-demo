"""Offline owner-client context and exact failure-cleanup regressions."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

STAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(STAGE))
spec=importlib.util.spec_from_file_location('owner_client',STAGE/'owner-client.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class ContextTest(unittest.TestCase):
    def test_persona_environment_restores_bootstrap_even_on_sdk_failure(self):
        for fail in (False,True):
            client=c.Client.__new__(c.Client)
            def sdk(create=False):
                os.environ.update(KUBECONFIG='private-persona',MLFLOW_TRACKING_URI='https://public.example/mlflow')
                if fail:raise RuntimeError('synthetic failure')
                return '12'
            client.mlflow=sdk
            with self.subTest(fail=fail),patch.dict(os.environ,{'KUBECONFIG':'bootstrap'},clear=True):
                try:
                    with client.sdk(create=True) as experiment:self.assertEqual(experiment,'12')
                except RuntimeError:self.assertTrue(fail)
                self.assertEqual(dict(os.environ),{'KUBECONFIG':'bootstrap'})

    def test_relay_is_ready_before_http_runtime_inputs_and_reconnect_preserves_identity(self):
        client=c.Client.__new__(c.Client);client.runtime='opencode';client.secret='synthetic';client.receipt={'checks':{}}
        calls=[]
        def forward():calls.append('forward')
        def inputs():self.assertIn('forward',calls);calls.append('inputs')
        client.setup=SimpleNamespace(check=lambda:None,state={'sandbox_id':'owned','provider_id':'provider'})
        client.q=SimpleNamespace(forward=forward,runtime_inputs=inputs,request=lambda *a,**k:(401,{}))
        client.identity=lambda:{'sandboxUid':'owned','pvcs':['owned']};client.close=lambda:calls.append('close');client.unchanged=lambda:None
        client.check();self.assertEqual(calls,['forward','inputs','close','forward'])
        self.assertTrue(client.receipt['checks']['ownerRelayReconnected'])

class CleanupTest(unittest.TestCase):
    def client(self,runtime):
        client=c.Client.__new__(c.Client);client.runtime=runtime;client.task_session='owned-session';client.task_verified=False;client.model_started=True;client.receipt={};client.unchanged=lambda:None
        client.protocol=SimpleNamespace(run_status=lambda code,value,run,session: value['status'] if code==200 and value['run_id']==run and value['session_id']==session else (_ for _ in ()).throw(RuntimeError('foreign')))
        return client

    def test_failed_hermes_task_stops_only_exact_new_run_and_observes_terminal(self):
        client=self.client('hermes');calls=[];states=iter(['running','cancelled'])
        def request(method,path,**kwargs):
            calls.append((method,path))
            if method=='POST':return 200,{'run_id':'owned-run','status':'stopping'}
            return 200,{'run_id':'owned-run','session_id':'owned-session','status':next(states)}
        client.q=SimpleNamespace(forward=lambda:None,active_runs=['owned-run'],request=request)
        client.cancel_owned();self.assertEqual(calls,[('GET','/v1/runs/owned-run'),('POST','/v1/runs/owned-run/stop'),('GET','/v1/runs/owned-run')]);self.assertTrue(client.receipt['ownedFailureTaskSettled'])

    def test_unknown_hermes_create_outcome_is_not_false_cleanup_success(self):
        client=self.client('hermes');client.q=SimpleNamespace(forward=lambda:None,active_runs=[])
        with self.assertRaises(RuntimeError):client.cancel_owned()
        self.assertNotIn('ownedFailureTaskSettled',client.receipt)

    def test_failed_opencode_task_aborts_only_new_session_not_agent(self):
        client=self.client('opencode');calls=[]
        def request(method,path,**kwargs):
            calls.append((method,path));return (200,True) if method=='POST' else (200,{})
        client.q=SimpleNamespace(forward=lambda:None,request=request)
        client.cancel_owned();self.assertEqual(calls,[('POST','/session/owned-session/abort'),('GET','/session/status')])
        self.assertTrue(client.receipt['ownedFailureTaskSettled'])

    def test_completed_or_unrequested_task_never_receives_abort(self):
        for started,verified in ((False,False),(True,True)):
            client=self.client('opencode');client.model_started=started;client.task_verified=verified
            client.q=SimpleNamespace(forward=lambda:(_ for _ in ()).throw(AssertionError('unexpected relay')))
            client.cancel_owned();self.assertNotIn('ownedFailureTaskSettled',client.receipt)

if __name__=='__main__':unittest.main()
