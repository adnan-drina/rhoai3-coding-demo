#!/usr/bin/env python3
"""Opt-in bounded native Hermes qualification; --static never contacts a service.

--run uses the existing owned setup-hermes journal and genuine ai-admin session.
One synthetic coding task, one actual application stop, then native stop/start.
No policy/provider/key/template mutation, sandbox deletion, fallback or migration.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

import native_api as api

STAGE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('opencode_verifier', STAGE/'qualify-opencode.py')
oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
NAME, WORKSPACE = 'hermes', 'ai-agents'
MODEL = 'publishers/internal-models/models/qwen3-8-27b-int4'
MODEL_PROVIDER = 'qwen38'
PYTHON = '/opt/hermes-venv/bin/python3.11'
GATES = ('ownedRuntime', 'runtimeInputs', 'authenticatedReady', 'missingKeyDenied', 'wrongKeyDenied',
         'codingTool', 'fixedTest', 'canonicalModel', 'streamedText', 'independentTest',
         'applicationCancelled', 'persistentHistory', 'runningAtEnd')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def created_run(status, value):
    return (status == 202 and isinstance(value, dict) and value.get('status') == 'started' and
            isinstance(value.get('run_id'), str) and bool(re.fullmatch(r'run_[0-9a-f]{32}', value['run_id'])))


def rejected_key(status, value):
    return status == 401 and isinstance(value, dict) and isinstance(value.get('error'), dict) and value['error'].get('code') == 'gateway_auth_failed'


def run_status(status, value, run, session):
    api.need(status == 200 and isinstance(value, dict) and value.get('object') == 'hermes.run' and
             value.get('run_id') == run and value.get('session_id') == session,
             'Exact native run identity/status unavailable')
    return value.get('status')


def cancelled(active, text, stop_status, stop_reply, poll_status, final, run, session, events, requested):
    terminal = any(t >= requested and e.get('run_id') == run and e.get('event') == 'run.cancelled' for t, e in events)
    return (active and text and stop_status == 200 and stop_reply == {'run_id': run, 'status': 'stopping'} and
            poll_status == 200 and isinstance(final, dict) and final.get('object') == 'hermes.run' and
            final.get('run_id') == run and final.get('session_id') == session and
            final.get('status') == 'cancelled' and final.get('last_event') == 'run.cancelled' and terminal)


def runtime_matches(probe, config_hash, startup_hash, listener_hash, real_key_hash):
    return (isinstance(probe, dict) and probe.get('placeholder') is True and probe.get('present') is True and
            probe.get('credentialHash') != real_key_hash and isinstance(probe.get('credentialHash'), str) and
            bool(re.fullmatch(r'[0-9a-f]{64}', probe['credentialHash'])) and
            probe.get('configHash') == config_hash and probe.get('startupHash') == startup_hash and
            probe.get('listenerHash') == listener_hash and probe.get('listenerPrivate') is True and
            probe.get('privateInterpreter') is True)


def terminal_test(messages, command):
    calls = {c.get('id'): c for m in messages if m.get('role') == 'assistant' for c in m.get('tool_calls') or []}
    terminal_calls = [c for c in calls.values() if c.get('function', {}).get('name') == 'terminal']
    if len(terminal_calls) != 1: return False
    matches = []
    for message in messages:
        if message.get('role') != 'tool': continue
        call = calls.get(message.get('tool_call_id'), {})
        function = call.get('function', {})
        if function.get('name') != 'terminal': continue
        try:
            arguments = json.loads(function.get('arguments', '{}'))
            result = json.loads(message.get('content', '{}'))
        except (ValueError, TypeError):
            continue
        if not isinstance(arguments, dict) or not isinstance(result, dict) or arguments.get('command') != command:
            return False
        matches.append(result)
    return len(matches) == 1 and type(matches[0].get('exit_code')) is int and matches[0]['exit_code'] == 0 and 'error' in matches[0] and matches[0]['error'] is None


class Qualification:
    def __init__(self, args):
        self.args = args
        self.identifier = uuid.uuid4().hex[:16]
        self.directory = '/sandbox/workspace/hermes-qualification-' + self.identifier
        self.fixture = self.directory + '/qualification_add.py'
        self.marker = self.directory + '/restart-marker'
        self.command = ('cd ' + self.directory + ' && ' + PYTHON + ' -c "from qualification_add import add; '
                        'assert add(2, 3) == 5; assert add(-2, 2) == 0"')
        self.receipt = {'scope': 'one synthetic native Hermes task, application cancellation and retained history restart',
                        'checks': {}, 'passed': False, 'model': MODEL, 'modelProvider': MODEL_PROVIDER,
                        'ownedFixture': self.fixture, 'ownedMarker': self.marker}
        self.forward_process = None
        self.active_runs = []
        self.stopped = False

    def gate(self, name, value):
        self.receipt['checks'][name] = bool(value); api.need(value, 'Gate failed: ' + name)

    def native(self):
        api.need(not self.journal.is_symlink() and self.journal.stat().st_mode & 0o077 == 0 and fingerprint(json.loads(self.journal.read_text())) == self.journal_hash,
                 'Setup recovery journal changed during qualification')
        value = self.owner.run(['sandbox', 'get', NAME, '-o', 'json'], WORKSPACE)
        api.need(value.get('id') == self.setup.state['sandbox_id'], 'Owned native sandbox identity changed')
        return value

    def identity(self, running=True):
        return api.owned_sandbox_identity(self.setup.bootstrap_env, self.native(), NAME, WORKSPACE,
                                          self.setup.template['image'], running=running)

    def wait_identity(self, running=True):
        end = time.monotonic() + 90
        while True:
            try: return self.identity(running)
            except RuntimeError as error:
                api.need(str(error) in ('Owned native sandbox is starting', 'Owned workload is not Running',
                         'Actual agent image is not ready', 'Stopped sandbox workload remains') and time.monotonic() < end, str(error))
                time.sleep(.5)

    def python(self, program):
        self.native()
        result = subprocess.run(self.owner.command(['sandbox', 'exec', '--name', NAME, '--timeout', '20',
            '--no-tty', '--no-login-shell', '--', PYTHON, '-c', program], WORKSPACE),
            env=self.owner.env, capture_output=True, text=True, timeout=40)
        api.need(result.returncode == 0 and 0 < len(result.stdout) <= 16384, 'Reviewed bounded Hermes probe failed')
        return json.loads(result.stdout.strip().splitlines()[-1])

    def runtime_inputs(self):
        probe = self.python("import os,re,hashlib,json,pathlib;v=os.environ.get('MAAS_API_KEY','');"
            "c=pathlib.Path('/sandbox/state/hermes/config.yaml');s=pathlib.Path('/sandbox/state/start.sh');"
            "k=pathlib.Path('/sandbox/state/auth/server-key');assert all(p.is_file() and not p.is_symlink() for p in (c,s,k));"
            "print(json.dumps({'present':bool(v),'placeholder':bool(re.fullmatch(r'openshell:resolve:env:(?:v[0-9]+_)?MAAS_API_KEY',v)),"
            "'credentialHash':hashlib.sha256(v.encode()).hexdigest(),'configHash':hashlib.sha256(c.read_bytes()).hexdigest(),"
            "'startupHash':hashlib.sha256(s.read_bytes()).hexdigest(),'listenerHash':hashlib.sha256(k.read_text().strip().encode()).hexdigest(),"
            "'listenerPrivate':k.stat().st_mode&0o777==0o600 and k.stat().st_uid==os.getuid(),"
            "'privateInterpreter':os.readlink('/proc/self/exe')==" + repr(PYTHON) + "}))")
        attached = self.owner.run(['sandbox','provider','list',NAME,'-o','json'],WORKSPACE)
        providers = attached.get('providers', [])
        api.need(not attached.get('next_page_token') and len(providers) == 1 and
                 providers[0].get('id') == self.setup.state['provider_id'] and
                 providers[0].get('name') == self.setup.provider and providers[0].get('type') == self.setup.provider and
                 providers[0].get('credential_keys') == ['MAAS_API_KEY'], 'Exact owned provider attachment differs')
        expected = (self.setup.inputs/'config.yaml').read_text().replace('__MAAS_COMMON_HOST__',self.setup.host)
        self.gate('runtimeInputs', runtime_matches(probe, hashlib.sha256(expected.encode()).hexdigest(),
                  hashlib.sha256((self.setup.inputs/'start.sh').read_bytes()).hexdigest(),
                  hashlib.sha256(self.key.encode()).hexdigest(), self.setup.state['key_hash']))

    def request(self, method, path, body=None, key=None, authenticated=True, timeout=20):
        api.need(path.startswith('/') and not path.startswith('//'), 'Unreviewed native HTTP path')
        headers = {'Content-Type': 'application/json'}
        if authenticated: headers['Authorization'] = 'Bearer ' + (self.key if key is None else key)
        request = urllib.request.Request(f'http://127.0.0.1:{self.local}' + path, method=method, headers=headers,
                                        data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.build_opener(oracle.checks.NoRedirect()).open(request, timeout=timeout) as response:
                status, raw = response.status, response.read(2*1024*1024+1)
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read(4096)
        api.need(len(raw) <= 2*1024*1024, 'Bounded native HTTP response exceeded')
        try: return status, json.loads(raw) if raw else None
        except ValueError: return status, None

    def close_forward(self):
        if self.forward_process:
            self.forward_process.terminate()
            try: self.forward_process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.forward_process.kill(); self.forward_process.wait(timeout=5)
            self.forward_process = None

    def forward(self):
        self.close_forward()
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0)); self.local = reserve.getsockname()[1]
        self.forward_process = subprocess.Popen(self.owner.command(['forward', 'service', NAME,
            '--target-port', '8642', '--target-host', '127.0.0.1', '--local', f'127.0.0.1:{self.local}'], WORKSPACE),
            env=self.owner.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.monotonic() + 90
        while time.monotonic() < end:
            api.need(self.forward_process.poll() is None, 'Authenticated native relay closed')
            try:
                code, health = self.request('GET', '/health/detailed', timeout=3)
                if code == 200 and isinstance(health, dict) and health.get('status') == 'ok' and health.get('gateway_state') == 'running' and health.get('platform') == 'hermes-agent': return
            except OSError: pass
            time.sleep(.5)
        api.need(False, 'Authenticated native readiness deadline exceeded')

    def session(self):
        identifier = 'hermes_qualification_' + uuid.uuid4().hex
        code, body = self.request('POST', '/api/sessions', {'id': identifier, 'model': MODEL, 'provider': MODEL_PROVIDER})
        api.need(code == 201 and isinstance(body, dict) and body.get('object') == 'hermes.session' and
                 body.get('session', {}).get('id') == identifier, 'Exact native session creation failed')
        return identifier

    def messages(self, session):
        code, body = self.request('GET', '/api/sessions/' + session + '/messages?limit=30&order=oldest')
        api.need(code == 200 and isinstance(body, dict) and body.get('session_id') == session and
                 isinstance(body.get('data'), list) and body.get('pagination', {}).get('returned') == len(body['data']) and
                 len(body['data']) < 30, 'Exact bounded stored session history unavailable')
        return body['data']

    def events(self, run, seen, errors):
        request = urllib.request.Request(f'http://127.0.0.1:{self.local}/v1/runs/{run}/events',
                                        headers={'Authorization': 'Bearer ' + self.key})
        total = 0
        try:
            with urllib.request.build_opener(oracle.checks.NoRedirect()).open(request, timeout=35) as stream:
                api.need(stream.status == 200 and stream.headers.get_content_type() == 'text/event-stream', 'Native SSE response differs')
                while True:
                    line = stream.readline(65537); total += len(line)
                    api.need(len(line) <= 65536 and total <= 2*1024*1024, 'Native SSE exceeds bounded output')
                    if not line: return
                    if line.startswith(b'data:'):
                        event = json.loads(line[5:])
                        api.need(event.get('run_id') == run, 'Foreign native run event')
                        seen.append((time.monotonic(), event))
        except Exception as error:
            errors.append(type(error).__name__)

    def start(self, session, prompt):
        self.native(); self.setup.check(); self.runtime_inputs()
        code, body = self.request('POST', '/v1/runs', {'input': prompt, 'session_id': session,
                                                    'model': MODEL, 'provider': MODEL_PROVIDER})
        api.need(created_run(code, body), 'Native run creation response differs')
        run = body['run_id']; self.active_runs.append(run)
        seen, errors = [], []
        reader = threading.Thread(target=self.events, args=(run, seen, errors), daemon=True); reader.start()
        return run, reader, seen, errors

    def coding(self):
        self.coding_session = self.session()
        self.receipt['codingSession'] = self.coding_session
        run, reader, events, errors = self.start(self.coding_session,
            'Synthetic qualification only. Use write_file or patch mode=replace with absolute path to fix ' + self.fixture +
            ' so add(a,b) returns their sum. Modify no other files. Run exactly this terminal command once: ' +
            self.command + '. Do not run other commands or use background processes. End with two short sentences explaining the fix.')
        self.receipt['codingRun'] = run
        approvals = 0; handled = set(); end = time.monotonic() + 120
        while time.monotonic() < end:
            for t, event in list(events):
                if event.get('event') != 'approval.request' or t in handled: continue
                allowed = approvals == 0 and event.get('command') == self.command and 'once' in event.get('choices', [])
                code, response = self.request('POST', '/v1/runs/' + run + '/approval', {'choice': 'once' if allowed else 'deny'})
                api.need(allowed and code == 200 and response.get('run_id') == run and response.get('choice') == 'once' and response.get('resolved') == 1,
                         'Unexpected or ambiguous command approval; retained state')
                approvals += 1; handled.add(t)
            code, final = self.request('GET', '/v1/runs/' + run)
            phase = run_status(code, final, run, self.coding_session)
            if phase in ('completed', 'failed', 'cancelled'): break
            api.need(phase in ('queued', 'running', 'waiting_for_approval'), 'Unexpected coding run state')
            time.sleep(.2)
        reader.join(timeout=5)
        self.receipt['approvalRequested'] = approvals > 0
        api.need(phase == 'completed' and not errors and not reader.is_alive(), 'Coding task did not complete within bounded native contract')
        api.need(any(e.get('event') == 'run.completed' for _, e in events), 'Successful terminal SSE event missing')
        stored = self.messages(self.coding_session)
        writes = [c for m in stored if m.get('role') == 'assistant' for c in m.get('tool_calls') or [] if c.get('function', {}).get('name') in ('write_file', 'patch')]
        try: paths = [json.loads(c['function'].get('arguments', '{}')).get('path') for c in writes]
        except (ValueError, TypeError): paths = []
        self.gate('codingTool', bool(writes) and len(paths) == len(writes) and all(path == self.fixture for path in paths) and
                  any(e.get('event') == 'tool.completed' and e.get('tool') in ('write_file', 'patch') and e.get('error') is False for _, e in events))
        self.gate('streamedText', sum(bool(e.get('delta')) for _, e in events if e.get('event') == 'message.delta') >= 2)
        self.gate('fixedTest', terminal_test(stored, self.command))
        code, session = self.request('GET', '/api/sessions/' + self.coding_session)
        usage = final.get('usage', {})
        self.gate('canonicalModel', code == 200 and session.get('session', {}).get('id') == self.coding_session and
                  session['session'].get('model') == MODEL and type(usage.get('output_tokens')) is int and usage['output_tokens'] > 0)
        self.fixture_hash = self.verify_fixture()
        self.receipt['fixtureSha256'] = self.fixture_hash
        self.gate('independentTest', True)

    def seed_fixture(self):
        source = 'def add(a,b):\n return a-b\n'
        self.python("import pathlib,json;d=pathlib.Path(" + repr(self.directory) +
                    ");d.mkdir(mode=0o700);(d/'qualification_add.py').write_text(" + repr(source) + ");print(json.dumps(True))")

    def verify_fixture(self):
        source = self.python("import pathlib,json;p=pathlib.Path(" + repr(self.fixture) + ");assert p.is_file() and not p.is_symlink() and p.stat().st_size<=512;print(json.dumps(p.read_text()))")
        oracle.verify_fixture(source)
        return hashlib.sha256(source.encode()).hexdigest()

    def cancel(self):
        session = self.session()
        run, reader, events, errors = self.start(session, 'Explain Java null checks in three short paragraphs. Do not use tools.')
        self.receipt.update(cancellationSession=session, cancellationRun=run)
        end = time.monotonic() + 30
        while time.monotonic() < end:
            code, status = self.request('GET', '/v1/runs/' + run)
            active = run_status(code, status, run, session) == 'running'
            text = any(e.get('event') == 'message.delta' and e.get('delta') for _, e in events)
            if active and text: break
            api.need(status.get('status') not in ('completed', 'failed', 'cancelled'), 'No active native generation to cancel')
            time.sleep(.1)
        api.need(active and text and not errors, 'Active streaming cancellation precondition missing')
        requested = time.monotonic(); stop_code, reply = self.request('POST', '/v1/runs/' + run + '/stop')
        end = time.monotonic() + 45
        while time.monotonic() < end:
            code, final = self.request('GET', '/v1/runs/' + run)
            phase = run_status(code, final, run, session)
            if phase in ('cancelled', 'completed', 'failed'): break
            api.need(phase in ('running', 'stopping'), 'Unexpected native stop state')
            time.sleep(.1)
        reader.join(timeout=5); settled = time.monotonic(); time.sleep(1)
        late = any(t >= settled and e.get('event') == 'message.delta' and e.get('delta') for t, e in events)
        tools = any(e.get('event') == 'tool.started' for _, e in events)
        self.receipt['cancellation'] = {'activeBeforeStop': active, 'textBeforeStop': bool(text),
            'stopHttp': stop_code, 'terminalStatus': phase, 'lateText': late, 'unexpectedTools': tools}
        self.gate('applicationCancelled', cancelled(active, text, stop_code, reply, code, final, run, session, events, requested) and
                  not errors and not reader.is_alive() and not late and not tools)

    def restart(self):
        baseline = self.identity(); history = fingerprint(self.messages(self.coding_session)); marker = uuid.uuid4().hex
        self.receipt['historySha256BeforeRestart'] = history
        self.python("import pathlib,json;p=pathlib.Path(" + repr(self.marker) + ");assert not p.exists();p.write_text(" + repr(marker) + ");print(json.dumps(True))")
        self.native(); self.close_forward(); self.stopped = True
        self.owner.run(['sandbox', 'stop', NAME], WORKSPACE, structured=False, timeout=120)
        api.need(self.wait_identity(False) == baseline, 'Stopped native sandbox/PVC identity changed')
        self.native(); self.owner.run(['sandbox', 'start', NAME], WORKSPACE, structured=False, timeout=180)
        api.need(self.wait_identity() == baseline, 'Restarted native sandbox/PVC identity changed')
        self.forward(); self.stopped = False
        code, session = self.request('GET', '/api/sessions/' + self.coding_session)
        saved = self.python("import pathlib,json;p=pathlib.Path(" + repr(self.marker) + ");assert not p.is_symlink();print(json.dumps(p.read_text()))")
        self.gate('persistentHistory', code == 200 and session.get('session', {}).get('id') == self.coding_session and
                  fingerprint(self.messages(self.coding_session)) == history and self.verify_fixture() == self.fixture_hash and saved == marker)

    def run(self):
        directory = Path(self.args.state_dir)
        api.need(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Existing private setup state required')
        self.journal = directory/'state.json'
        api.need(self.journal.is_file() and not self.journal.is_symlink() and self.journal.stat().st_mode & 0o077 == 0, 'Private setup journal required')
        spec = importlib.util.spec_from_file_location('hermes_setup', STAGE/'setup-hermes.py')
        setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
        api.need(setup.MODEL_PROVIDER == MODEL_PROVIDER and setup.PYTHON == PYTHON and setup.MODEL == MODEL,
                 'Reviewed Hermes provider/model/interpreter differs')
        self.setup = setup.Setup(self.args)
        def readonly(**fields):
            api.need(all(self.setup.state.get(k) == v for k, v in fields.items()), 'Setup ownership binding changed')
        self.setup.save = readonly
        self.journal_hash = fingerprint(json.loads(self.journal.read_text()))
        api.need(not any(v for k,v in self.setup.state.items() if k.endswith('_pending')), 'Setup has unresolved ownership')
        secret = Path(self.setup.state['server_key_path'])
        api.need(secret.is_file() and not secret.is_symlink() and secret.stat().st_mode & 0o077 == 0 and secret.stat().st_uid == os.getuid() and
                 secret.resolve().is_relative_to(directory.resolve()), 'Private native listener key path differs')
        self.key = secret.read_text().strip(); api.need(len(self.key) >= 32, 'Native listener key is invalid')
        self.setup.preflight()
        for path in (Path(__file__), STAGE/'setup-hermes.py', STAGE/'native_api.py', STAGE/'qualify-opencode.py', STAGE/'qualify-inference.py'):
            api.need(subprocess.check_output(['git','-C',str(setup.ROOT),'show',self.args.revision+':'+str(path.relative_to(setup.ROOT))]) == path.read_bytes(), 'Published qualification dependency differs')
        with api.native_gateway(self.setup.bootstrap_env,self.setup.cli) as admin, api.native_gateway(self.setup.bootstrap_env,self.setup.cli,self.args.persona_home) as owner:
            self.owner = owner; self.setup.admin,self.setup.owner = admin,owner
            try:
                self.setup.inventory(); self.setup.policy_input(); self.setup.check()
                self.receipt['ownedRuntimeIdentity'] = self.wait_identity()
                self.receipt.update(sandboxId=self.setup.state['sandbox_id'], providerId=self.setup.state['provider_id'], keyId=self.setup.state['key_id'])
                self.gate('ownedRuntime', True); self.runtime_inputs()
                self.forward(); self.gate('authenticatedReady', True)
                code, body = self.request('GET', '/health/detailed', authenticated=False); self.gate('missingKeyDenied', rejected_key(code,body))
                code, body = self.request('GET', '/health/detailed', key='synthetic-invalid-key'); self.gate('wrongKeyDenied', rejected_key(code,body))
                self.seed_fixture()
                self.coding(); self.cancel(); self.restart()
                self.setup.check(); self.identity(); self.forward(); self.runtime_inputs(); self.gate('runningAtEnd', True)
                self.receipt['passed'] = all(self.receipt['checks'].get(g) is True for g in GATES)
            finally:
                if self.forward_process:
                    for run in self.active_runs:
                        try: self.request('POST', '/v1/runs/' + run + '/stop', timeout=5)
                        except Exception: pass
                if self.stopped:
                    try:
                        self.native(); owner.run(['sandbox','start',NAME],WORKSPACE,structured=False,timeout=180)
                        self.wait_identity(); self.forward(); self.receipt['checks']['runningAtEnd'] = True
                    except Exception: self.receipt['checks']['runningAtEnd'] = False
                self.close_forward()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True); mode.add_argument('--static',action='store_true'); mode.add_argument('--run',action='store_true')
    parser.add_argument('--revision'); parser.add_argument('--state-dir',default='/private/tmp/060-hermes-state')
    parser.add_argument('--persona-home',default=os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'))
    parser.add_argument('--persona-kubeconfig',default=os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'))
    args=parser.parse_args(); args.apply=False; args.expected_policy_hash=None
    if args.static:
        oracle.verify_fixture('def add(a,b):\n return a+b\n'); print('[OK] Offline Hermes protocol verifier; no cluster/model calls'); return
    api.need(args.revision and args.persona_home and args.persona_kubeconfig, 'Reviewed revision and genuine admin persona required')
    qualification=Qualification(args); directory=Path(args.state_dir)
    api.need(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Existing private recovery directory required')
    fd=os.open(directory/'qualification.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(RuntimeError('Bounded qualification deadline exceeded')))
        signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('Termination requested')))
        signal.alarm(600)
        try: qualification.run()
        except (Exception,KeyboardInterrupt) as error:
            qualification.receipt['failureClass']=type(error).__name__
            if isinstance(error,RuntimeError): qualification.receipt['failure']=str(error)
        finally: signal.alarm(0)
        qualification.receipt['pendingGates']=[g for g in GATES if not qualification.receipt['checks'].get(g)]
        api.private_receipt(directory/('qualification-'+uuid.uuid4().hex+'.json'),qualification.receipt)
        print(json.dumps(qualification.receipt)); api.need(qualification.receipt['passed'],'Qualification incomplete; owned sandbox/key/state retained')


if __name__=='__main__':
    try: main()
    except Exception as error:
        print('[FAIL] '+(str(error) if isinstance(error,RuntimeError) else type(error).__name__)); raise SystemExit(1)
