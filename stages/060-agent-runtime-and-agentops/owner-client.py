#!/usr/bin/env python3
"""Owner-only native client proof; no developer grants or public listener."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import native_api as api

STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parents[1]


def load(name):
    path=STAGE/(name+'.py');spec=importlib.util.spec_from_file_location(name.replace('-','_'),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def private(path, directory=None):
    path=Path(path)
    api.need(path.is_file() and not path.is_symlink() and path.stat().st_uid==os.getuid() and
             path.stat().st_mode&0o077==0, 'Owner-only regular client input required')
    if directory:api.need(path.resolve().is_relative_to(Path(directory).resolve()), 'Client secret outside own state directory')
    return path


class Client:
    def __init__(self, args, runtime):
        self.args,self.runtime=args,runtime
        options=argparse.Namespace(**vars(args));options.state_dir=str(Path(args.state_root)/('060-'+runtime+'-state'))
        options.apply=False;options.expected_policy_hash=None;options.remaining_from=None
        directory=Path(options.state_dir)
        api.need(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode&0o077==0,'Existing owner state required')
        self.journal=private(directory/'state.json');self.original=self.journal.read_bytes()
        setup_module=load('setup-'+runtime);self.setup=setup_module.Setup(options)
        api.need(self.setup.state and not any(v for k,v in self.setup.state.items() if k.endswith('_pending')),'Owned setup is incomplete')
        def readonly(**fields):api.need(all(self.setup.state.get(k)==v for k,v in fields.items()),'Client cannot advance setup ownership')
        self.setup.save=readonly
        self.protocol=load('qualify-'+runtime);self.protocol.setup=setup_module;self.q=self.protocol.Qualification(options)
        self.new_directory=self.q.directory;self.q.directory='/sandbox/workspace'
        secret=private(directory/'upload/state/auth'/self.setup.listener_filename,directory)
        self.secret=secret.read_text().strip();api.need(len(self.secret)>=32,'Private listener credential invalid')
        self.q.journal=self.journal
        if runtime=='opencode':
            self.q.deployment=self.setup;self.q.password=self.secret
            self.q.journal_hash=hashlib.sha256(self.original).hexdigest()
        else:
            self.q.setup=self.setup;self.q.key=self.secret;self.q.journal_hash=fingerprint(self.setup.state)
        self.task_session=None;self.task_verified=False;self.model_started=False
        self.receipt={'runtime':runtime,'workspace':'ai-agents','ownerOnly':True,'modelRequests':0,'checks':{}}

    def unchanged(self):api.need(self.journal.read_bytes()==self.original,'Owner recovery journal changed')

    def identity(self):
        self.unchanged();native=self.q.native()
        return api.owned_sandbox_identity(self.setup.bootstrap_env,native,self.runtime,'ai-agents',self.setup.template['image'])

    def close(self):
        if self.runtime=='opencode':self.q.close_forward()
        else:self.q.close_forward()

    def check(self):
        self.setup.check();before=self.identity();self.q.forward();self.q.runtime_inputs()
        path='/global/health' if self.runtime=='opencode' else '/health/detailed'
        code,body=self.q.request('GET',path,authenticated=False);api.need(code==401,'Missing listener authentication not denied')
        kwargs={'password':'synthetic-wrong-password'} if self.runtime=='opencode' else {'key':'synthetic-wrong-key'}
        code,body=self.q.request('GET',path,**kwargs);api.need(code==401,'Wrong listener authentication not denied')
        self.close();self.q.forward();api.need(self.identity()==before,'Client reconnect changed retained identity')
        self.unchanged();self.receipt.update(nativeId=self.setup.state['sandbox_id'],providerId=self.setup.state['provider_id'],identity=before)
        self.receipt['checks'].update(authenticatedReady=True,missingAuthDenied=True,wrongAuthDenied=True,ownerRelayReconnected=True,retainedIdentity=True)

    def mlflow(self, create=False):
        ml=json.loads(api.oc(self.setup.bootstrap_env,'get','mlflows.mlflow.opendatahub.io','mlflow','-o','json'))
        api.need(ml['status']['version']=='3.14.0' and any(v.get('type')=='Available' and v.get('status')=='True' for v in ml['status']['conditions']),'Native MLflow is not the reviewed ready version')
        uri=ml['status']['url']
        from urllib.parse import urlparse
        address=urlparse(uri)
        api.need(address.scheme=='https' and address.hostname and address.path.rstrip('/')=='/mlflow' and not address.username and not address.password and not address.query and not address.fragment,'Native MLflow route is invalid')
        # Derive the only SDK destination from the guarded cluster resource,
        # before loading the verified owner's kubeconfig into the auth plugin.
        os.environ.update(KUBECONFIG=self.args.persona_kubeconfig,MLFLOW_TRACKING_URI=uri,
                          MLFLOW_TRACKING_AUTH='kubernetes-namespaced',MLFLOW_WORKSPACE='ai-agents',
                          MLFLOW_TRACKING_INSECURE_TLS='false',MLFLOW_ENABLE_ASYNC_TRACE_LOGGING='false',
                          MLFLOW_ENABLE_OTLP_EXPORTER='false',MLFLOW_DISABLE_TELEMETRY='true',
                          MLFLOW_HTTP_REQUEST_TIMEOUT='15',MLFLOW_HTTP_REQUEST_MAX_RETRIES='1')
        for name in ('MLFLOW_TRACKING_TOKEN','MLFLOW_TRACKING_USERNAME','MLFLOW_TRACKING_PASSWORD'):
            api.need(not os.environ.get(name),'Unreviewed alternate SDK credential supplied')
        import mlflow
        api.need(mlflow.__version__=='3.14.0','Matching external SDK required')
        mlflow.set_workspace('ai-agents');api.need(mlflow.get_workspace('ai-agents').name=='ai-agents','Native MLflow workspace unavailable')
        experiment=mlflow.get_experiment_by_name('agent-runtime-traces')
        if experiment is None:
            api.need(create,'Reviewed trace experiment must already exist')
            identifier=mlflow.create_experiment('agent-runtime-traces',tags={'stage':'060','capture.scope':'native-api-client-observation'})
            experiment=mlflow.get_experiment(identifier)
        api.need(experiment and experiment.lifecycle_stage=='active' and experiment.name=='agent-runtime-traces','Trace experiment differs')
        return experiment.experiment_id

    def _trace_task(self, experiment):
        trace_module=load('selected_task_trace');before=self.identity()
        self.close();self.q.directory=self.new_directory
        if self.runtime=='hermes':self.q.seed_fixture()
        else:
            source='def add(a,b):\n return a-b\n'
            self.q.python("import pathlib,json;d=pathlib.Path("+repr(self.q.directory)+
                          ");d.mkdir(mode=0o700);(d/'qualification_add.py').write_text("+repr(source)+
                          ");print(json.dumps(True))")
        self.q.forward();self.q.runtime_inputs()
        session=self.q.session();self.task_session=session;self.receipt.update(sessionId=session,taskPending=True);original_session=self.q.session;used=[]
        def exact_session():
            api.need(not used,'Selected task cannot create another session');used.append(session);return session
        self.q.session=exact_session
        binding={'experiment_id':experiment,'source_revision':self.args.revision,'image_digest':self.setup.image_digest,
                 'sandbox_id':self.setup.state['sandbox_id'],'provider_id':self.setup.state['provider_id'],
                 'session_id':session,'model':self.setup.model,'subscription':self.setup.subscription}
        reader=None
        with trace_module.selected_task_trace(self.runtime,binding) as trace:
            if self.runtime=='opencode':
                class Observed(list):
                    def append(inner,item):
                        super().append(item);trace.observe({'type':item[1],'properties':item[3]})
                self.q.events=Observed();self.q.stop.clear()
                reader=threading.Thread(target=self.q.read_events,daemon=True);reader.start()
                end=time.monotonic()+10
                while not self.q.events and not self.q.event_error and time.monotonic()<end:time.sleep(.1)
                api.need(self.q.events and not self.q.event_error,'Selected task SSE unavailable')
            else:
                original_events=self.q.events
                def observed_events(run,seen,errors):
                    trace.bind_run(run)
                    class Observed:
                        def append(inner,item):seen.append(item);trace.observe(item[1])
                    original_events(run,Observed(),errors)
                self.q.events=observed_events
            try:self.model_started=True;self.q.coding()
            finally:
                self.q.session=original_session
                if reader:self.q.stop.set();reader.join(timeout=5)
            trace.complete({'passed':True,'fixture_sha256':self.q.fixture_hash});self.task_verified=True;self.receipt['taskPending']=False
        history=fingerprint(self.q.messages(session));self.close();self.q.forward()
        api.need(fingerprint(self.q.messages(session))==history and self.identity()==before,'Selected session/history changed on reconnect')
        self.q.runtime_inputs();self.setup.check();self.unchanged()
        self.receipt.update(modelRequests='one selected synthetic task',sessionId=session,fixtureSha256=self.q.fixture_hash,
                            historySha256=history,trace=trace.receipt)
        self.receipt['checks'].update(realTaskToolOutcome=True,selectedSessionReconnect=True)
        return trace.receipt

    @contextmanager
    def sdk(self, create=False):
        keys=('KUBECONFIG','MLFLOW_TRACKING_URI','MLFLOW_TRACKING_AUTH','MLFLOW_WORKSPACE',
              'MLFLOW_TRACKING_INSECURE_TLS','MLFLOW_ENABLE_ASYNC_TRACE_LOGGING','MLFLOW_ENABLE_OTLP_EXPORTER',
              'MLFLOW_DISABLE_TELEMETRY','MLFLOW_HTTP_REQUEST_TIMEOUT','MLFLOW_HTTP_REQUEST_MAX_RETRIES')
        previous={key:os.environ.get(key) for key in keys}
        try:yield self.mlflow(create=create)
        finally:
            for key,value in previous.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value

    def trace_task(self):
        with self.sdk(create=True) as experiment:return self._trace_task(experiment)

    def cancel_owned(self):
        if not self.task_session or self.task_verified or not self.model_started:return
        self.unchanged();self.q.forward();end=time.monotonic()+30
        if self.runtime=='opencode':
            code,accepted=self.q.request('POST','/session/'+self.task_session+'/abort',timeout=5)
            api.need(code==200 and accepted is True,'Owned session abort not acknowledged')
            while time.monotonic()<end:
                code,status=self.q.request('GET','/session/status',timeout=5)
                if code==200 and isinstance(status,dict) and (self.task_session not in status or status[self.task_session].get('type')=='idle'):break
                time.sleep(.2)
            else:raise RuntimeError('Owned session abort did not settle')
        else:
            api.need(len(self.q.active_runs)==1,'Selected run creation outcome unknown; preserve exact session for recovery')
            for run in self.q.active_runs:
                code,value=self.q.request('GET','/v1/runs/'+run,timeout=5)
                phase=self.protocol.run_status(code,value,run,self.task_session)
                if phase not in ('completed','cancelled','failed'):
                    code,value=self.q.request('POST','/v1/runs/'+run+'/stop',timeout=5)
                    api.need(code==200 and value.get('run_id')==run and value.get('status')=='stopping','Owned run stop not acknowledged')
                    while time.monotonic()<end:
                        code,value=self.q.request('GET','/v1/runs/'+run,timeout=5)
                        if self.protocol.run_status(code,value,run,self.task_session) in ('completed','cancelled','failed'):break
                        time.sleep(.2)
                    else:raise RuntimeError('Owned run stop did not settle')
        self.receipt['ownedFailureTaskSettled']=True

    @contextmanager
    def connected(self):
        self.setup.preflight()
        with api.native_gateway(self.setup.bootstrap_env,self.setup.cli) as admin,api.native_gateway(self.setup.bootstrap_env,self.setup.cli,self.args.persona_home) as owner:
            self.setup.admin,self.setup.owner=admin,owner;self.q.owner=owner
            self.setup.inventory();self.setup.policy_input();self.setup.check()
            failed=True
            try:yield self;failed=False
            finally:
                try:
                    if failed:self.cancel_owned()
                finally:self.close();self.unchanged()


def source_guard(revision):
    import re
    api.need(bool(re.fullmatch(r'[0-9a-f]{40}',revision)),'Immutable published client revision required')
    for name in ('owner-client.py','client-requirements.txt','selected_task_trace.py','qualify-opencode.py','qualify-hermes.py'):
        path=STAGE/name;api.need(subprocess.check_output(['git','-C',str(ROOT),'show',revision+':'+str(path.relative_to(ROOT))])==path.read_bytes(),'Published client dependency differs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--check',action='store_true');mode.add_argument('--trace',action='store_true');mode.add_argument('--readback')
    parser.add_argument('--revision',required=True)
    parser.add_argument('--persona-home',required=True);parser.add_argument('--persona-kubeconfig',required=True)
    parser.add_argument('--state-root',default='/private/tmp');parser.add_argument('--receipt',required=True)
    args=parser.parse_args();source_guard(args.revision);results=[]
    if args.readback:
        receipt=json.loads(private(args.readback).read_text());client=Client(args,receipt['runtime'])
        with client.connected():
            with client.sdk(create=False):result=load('selected_task_trace').readback_trace(receipt,forbidden_values=(client.secret,client.setup.user_token))
        api.private_receipt(Path(args.receipt),result);print(json.dumps(result));return
    for runtime in ('opencode','hermes'):
        client=Client(args,runtime)
        with client.connected():
            client.check()
            if args.trace:
                trace=client.trace_task();temporary=Path(args.state_root)/('060-'+runtime+'-selected-trace-'+uuid.uuid4().hex+'.json');api.private_receipt(temporary,trace)
        if args.trace:
            stored=temporary.with_suffix('.stored.json');command=[sys.executable,str(Path(__file__)),'--readback',str(temporary),'--revision',args.revision,'--persona-home',args.persona_home,'--persona-kubeconfig',args.persona_kubeconfig,'--state-root',args.state_root,'--receipt',str(stored)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=90);api.need(result.returncode==0,'Fresh stored trace retrieval/scan failed');client.receipt['storedTrace']=json.loads(private(stored).read_text())
        results.append(client.receipt)
    receipt={'scope':'ai-admin workspace-independent owner client; no developer/DevSpaces provisioning','agents':results,'passed':True,'modelRequests':'one selected task per agent' if args.trace else 0}
    api.private_receipt(Path(args.receipt),receipt);print(json.dumps(receipt))


if __name__=='__main__':
    try:main()
    except Exception:print('[FAIL] Owner client proof failed; owned runtime/state preserved');raise SystemExit(1)
