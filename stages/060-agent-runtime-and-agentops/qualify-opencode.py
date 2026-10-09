#!/usr/bin/env python3
"""Opt-in bounded qualification of the existing persistent OpenCode sandbox.

--static is offline. --run requires the reviewed setup journal, exact published
revision and genuine ai-admin sessions. It retains the key, sandbox, fixture and
sessions; never creates/deletes sandboxes or changes policy/provider/template.
Only sanitized gate results leave memory. A failed gate preserves recovery state.
"""
import argparse
import ast
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from native_api import native_gateway, need, oc, private_receipt

STAGE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inference_checks', STAGE / 'qualify-inference.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
setup = None
NAME, WORKSPACE = 'opencode', 'ai-agents'
MODEL = 'publishers/internal-models/models/qwen3-8-27b-int4'
DIRECTORY = '/sandbox/workspace'
TEST_COMMAND = 'python3 -c "from qualification_add import add; assert add(2, 3) == 5; assert add(-2, 2) == 0"'
GATES = ('ownedRuntime', 'authenticatedHealth', 'invalidPasswordDenied', 'missingPasswordDenied',
         'placeholderNotRealKey', 'codingTool', 'exactTestApproval', 'generatedModel', 'streamedDeltas',
         'independentTest', 'applicationAbort', 'filesystemDenied', 'egressDenied',
         'foreignWorkspaceDenied', 'persistentRestart', 'runningAtEnd')


def verify_fixture(source):
    """Only execute an exact, harmless AST; independent tests are local-owned."""
    need(len(source.encode()) <= 512, 'Fixture exceeds bounded size')
    tree = ast.parse(source)
    expected = ast.parse('def add(a, b):\n    return a + b\n')
    need(ast.dump(tree, include_attributes=False) == ast.dump(expected, include_attributes=False),
         'Independent fixture structure differs')
    scope = {'__builtins__': {}}
    exec(compile(tree, '<synthetic-fixture>', 'exec'), scope)
    need(all(scope['add'](a, b) == result for a, b, result in ((2, 3, 5), (-2, 2, 0), (0, 0, 0), (7, -3, 4))),
         'Independent synthetic test failed')


def exact_permission(request, session, messages):
    if request.get('sessionID') != session or request.get('permission') != 'bash' or request.get('metadata', {}).get('command') != TEST_COMMAND:
        return False
    tool = request.get('tool', {})
    return any(p.get('type') == 'tool' and p.get('tool') == 'bash' and
               p.get('messageID') == tool.get('messageID') and p.get('callID') == tool.get('callID') and
               p.get('state', {}).get('input', {}).get('command') == TEST_COMMAND
               for m in messages for p in m.get('parts', []))


def foreign_workspace_denied(returncode, diagnostic):
    """Pinned CLI PermissionDenied rendering plus exact native nonmember scope."""
    return (returncode != 0 and 'does not have permission' in diagnostic.lower() and
            bool(re.search(r"not a member of workspace ['\"]?openshell-developer['\"]?(?:[;\s]|$)", diagnostic)))


def idle_after_abort(events, session, started):
    return any(t >= started and sid == session and
               (kind == 'session.idle' or (kind == 'session.status' and properties.get('status', {}).get('type') == 'idle'))
               for t, kind, sid, properties in events)


def abort_statuses(status_http, statuses, events, session, started):
    # Pinned 1.18.16 emits idle, then removes idle sessions from this map.
    # Absence alone is inconclusive; require this session's fresh idle event.
    if status_http == 200 and isinstance(statuses, dict) and session not in statuses and idle_after_abort(events, session, started):
        return dict(statuses, **{session: {'type': 'idle'}})
    return statuses


def remaining_fixture(receipt):
    pending = ['applicationAbort', 'persistentRestart', 'runningAtEnd']
    need(receipt.get('passed') is False and receipt.get('pendingGates') == pending and
         receipt.get('failure') == 'Gate failed: applicationAbort', 'Receipt is outside the exact remaining-gates case')
    need(all(receipt.get('checks', {}).get(g) is True for g in GATES if g not in pending), 'Prior coding receipt lacks a passed required gate')
    match = re.fullmatch(r'/sandbox/workspace/qualification-([0-9a-f]{16})/qualification_add\.py', receipt.get('ownedFixture', ''))
    need(match and receipt.get('ownedMarker') == '/sandbox/state/opencode-qualification-' + match[1], 'Prior owned fixture/marker paths differ')
    return str(Path(receipt['ownedFixture']).parent), receipt['ownedMarker']


def read_only_setup(args):
    global setup
    spec = importlib.util.spec_from_file_location('opencode_setup', STAGE / 'setup-opencode.py')
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    deployment = setup.Setup(args)
    def save(**fields):
        need(all(deployment.state.get(k) == v for k, v in fields.items()), 'Recovery binding changed; qualification refused')
    deployment.save = save
    return deployment


class Qualification:
    def __init__(self, args):
        self.args = args
        self.run_id = uuid.uuid4().hex[:16]
        self.directory = DIRECTORY + '/qualification-' + self.run_id
        self.marker = '/sandbox/state/opencode-qualification-' + self.run_id
        self.receipt = {'scope': 'one synthetic coding task, actual abort and persistent restart; no migration/catalog/tracing claim',
                        'checks': {}, 'passed': False, 'pendingGates': list(GATES),
                        'ownedFixture': self.directory + '/qualification_add.py', 'ownedMarker': self.marker}
        self.sessions, self.process = [], None
        self.stop, self.events = threading.Event(), []
        self.event_error = None
        self.stopped = False

    def gate(self, name, condition):
        self.receipt['checks'][name] = bool(condition)
        need(condition, 'Gate failed: ' + name)
        self.receipt['pendingGates'] = [g for g in GATES if not self.receipt['checks'].get(g)]

    def native(self):
        need(not self.journal.is_symlink() and self.journal.stat().st_mode & 0o077 == 0 and hashlib.sha256(self.journal.read_bytes()).hexdigest() == self.journal_hash, 'Recovery journal changed during qualification')
        value = self.owner.run(['sandbox', 'get', NAME, '-o', 'json'], WORKSPACE)
        need(value['id'] == self.deployment.state['sandbox_id'], 'Sandbox identity changed; lifecycle refused')
        return value

    def python(self, program):
        # Reviewed probe code only; no agent-generated command is executed here.
        self.native()
        result = subprocess.run(self.owner.command(['sandbox', 'exec', '--name', NAME, '--timeout', '20',
            '--no-tty', '--no-login-shell', '--', '/usr/bin/python3', '-c', program], WORKSPACE),
            env=self.owner.env, capture_output=True, text=True, timeout=40)
        need(result.returncode == 0 and len(result.stdout) <= 16384, 'Bounded native sandbox probe failed')
        return json.loads(result.stdout.strip().splitlines()[-1])

    def resources(self, running=True):
        native = self.native(); sid = native['id']
        if running:
            if native.get('phase') in ('Starting', 'Provisioning'):
                raise RuntimeError('Owned native sandbox is starting')
            need(native.get('phase') == 'Ready', 'Owned native sandbox is not Ready; terminal or unexpected lifecycle state')
        else:
            need(native.get('phase') == 'Stopped', 'Owned native sandbox did not reach Stopped')
        resources = json.loads(oc(self.deployment.bootstrap_env, 'get', 'sandboxes', '-n', WORKSPACE, '-o', 'json'))
        matches = [r for r in resources['items'] if r['metadata'].get('labels', {}).get('openshell.ai/sandbox-id') == sid]
        need(len(matches) == 1, 'Exact owned Kubernetes Sandbox is ambiguous')
        resource = matches[0]
        pods = json.loads(oc(self.deployment.bootstrap_env, 'get', 'pods', '-n', WORKSPACE, '-o', 'json'))['items']
        pods = [p for p in pods if any(o.get('uid') == resource['metadata']['uid'] and o.get('controller') for o in p['metadata'].get('ownerReferences', []))]
        if running:
            need(len(pods) == 1 and pods[0]['status']['phase'] == 'Running', 'Owned workload is not Running')
            pod = pods[0]
            need(pod['metadata'].get('annotations', {}).get('openshift.io/scc') == 'restricted-v2' and
                 pod['spec'].get('serviceAccountName') == 'openshell-sandbox' and
                 pod['spec'].get('automountServiceAccountToken') is False, 'Native restricted workload identity differs')
            agents = [c for c in pod['spec']['containers'] if c.get('name') == 'agent']
            need(len(agents) == 1 and agents[0].get('image') == self.deployment.template['image'], 'Owned immutable workload image differs')
            actual = [c for c in pod['status'].get('containerStatuses', []) if c.get('name') == 'agent']
            need(len(actual) == 1 and actual[0].get('ready') is True, 'Actual agent image is not ready')
            need(actual[0].get('imageID', '').endswith(setup.DIGEST), 'Actual immutable agent image differs')
        else:
            need(not pods, 'Stopped sandbox workload remains')
        claims = resource['spec'].get('volumeClaimTemplates', [])
        need(claims, 'Native sandbox lacks persistent storage')
        pvcs = json.loads(oc(self.deployment.bootstrap_env, 'get', 'pvc', '-n', WORKSPACE, '-o', 'json'))['items']
        owned = [p for p in pvcs if any(o.get('uid') == resource['metadata']['uid'] for o in p['metadata'].get('ownerReferences', []))]
        need(len(owned) == len(claims) and all(p['status']['phase'] == 'Bound' for p in owned), 'Owned PVC identity is ambiguous')
        if running:
            mounted = {v['persistentVolumeClaim']['claimName'] for v in pod['spec'].get('volumes', []) if 'persistentVolumeClaim' in v}
            need(mounted == {p['metadata']['name'] for p in owned}, 'Mounted PVC is outside owned persistent storage')
        return {'sandboxUid': resource['metadata']['uid'], 'pvcs': sorted((p['metadata']['name'], p['metadata']['uid']) for p in owned)}

    def settled_resources(self, running=True):
        end = time.monotonic() + 90
        while True:
            try: return self.resources(running)
            except RuntimeError as error:
                need(str(error) in ('Owned native sandbox is starting', 'Owned workload is not Running', 'Actual agent image is not ready', 'Stopped sandbox workload remains') and time.monotonic() < end, str(error))
                time.sleep(.5)

    def url(self, path):
        return f'http://127.0.0.1:{self.local}{path}' + ('&' if '?' in path else '?') + 'directory=' + urllib.parse.quote(self.directory, safe='')

    def request(self, method, path, body=None, password=None, authenticated=True, timeout=20):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Basic ' + base64.b64encode(('opencode:' + (self.password if password is None else password)).encode()).decode()
        request = urllib.request.Request(self.url(path), headers=headers, method=method,
                                        data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.build_opener(checks.NoRedirect()).open(request, timeout=timeout) as response:
                status, data = response.status, response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            status, data = error.code, error.read(4096)
        need(len(data) <= 2 * 1024 * 1024, 'OpenCode response exceeds bound')
        try:
            return status, json.loads(data) if data else None
        except ValueError:
            return status, None

    def forward(self):
        self.close_forward()
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0)); self.local = reserve.getsockname()[1]
        self.process = subprocess.Popen(self.owner.command(['forward', 'service', NAME, '--target-port', '4096',
            '--target-host', '127.0.0.1', '--local', f'127.0.0.1:{self.local}'], WORKSPACE),
            env=self.owner.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.monotonic() + 90
        while time.monotonic() < end:
            need(self.process.poll() is None, 'Authenticated relay closed')
            try:
                status, health = self.request('GET', '/global/health', timeout=3)
                if status == 200 and health.get('healthy') is True and health.get('version') == '1.18.16': return
            except OSError:
                pass
            time.sleep(.5)
        need(False, 'Authenticated health deadline exceeded')

    def close_forward(self):
        if self.process:
            self.process.terminate()
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=5)
            self.process = None

    def read_events(self):
        request = urllib.request.Request(self.url('/event'), headers={'Authorization': 'Basic ' + base64.b64encode(('opencode:' + self.password).encode()).decode()})
        total = 0
        try:
            with urllib.request.build_opener(checks.NoRedirect()).open(request, timeout=30) as stream:
                while not self.stop.is_set():
                    line = stream.readline(65537); total += len(line)
                    need(len(line) <= 65536 and total <= 2 * 1024 * 1024, 'Event stream exceeds bound')
                    if not line: return
                    if line.startswith(b'data:'):
                        event = json.loads(line[5:]); p = event.get('properties', {})
                        sid = p.get('sessionID') or p.get('part', {}).get('sessionID') or p.get('info', {}).get('sessionID')
                        self.events.append((time.monotonic(), event.get('type', ''), sid, p))
        except Exception as error:
            if not self.stop.is_set(): self.event_error = type(error).__name__

    def session(self):
        status, session = self.request('POST', '/session', {})
        need(status == 200 and session.get('id'), 'Synthetic session creation failed')
        self.sessions.append(session['id']); return session['id']

    def prompt(self, session, text, permissions=False):
        result = {}
        body = {'model': {'providerID': 'qwen38', 'modelID': MODEL}, 'parts': [{'type': 'text', 'text': text}]}
        if not permissions: body['tools'] = {name: False for name in ('bash', 'edit', 'write', 'apply_patch', 'read', 'glob', 'grep', 'list', 'task', 'webfetch', 'websearch', 'skill', 'question', 'todowrite')}
        def worker():
            try: result['status'], result['reply'] = self.request('POST', '/session/' + session + '/message', body, timeout=120)
            except Exception as error: result['transport'] = type(error).__name__
        thread = threading.Thread(target=worker, daemon=True); thread.start()
        return thread, result

    def messages(self, session):
        status, messages = self.request('GET', '/session/' + session + '/message?limit=30')
        need(status == 200 and isinstance(messages, list), 'Owned session evidence unavailable')
        return messages

    def coding(self):
        self.coding_session = self.session()
        thread, result = self.prompt(self.coding_session,
            'Synthetic qualification only. Fix qualification_add.py so add returns the sum using an actual edit, write or apply_patch tool. '
            'Then run exactly this bash command once: ' + TEST_COMMAND + '. Do not run other commands or modify other files. '
            'Finish with two short sentences explaining the fix.', permissions=True)
        approved = set(); end = time.monotonic() + 120
        while thread.is_alive() and time.monotonic() < end:
            status, requests = self.request('GET', '/permission')
            need(status == 200 and isinstance(requests, list), 'Native permission inventory unavailable')
            for request in requests:
                if request.get('sessionID') != self.coding_session: continue
                allowed = not approved and exact_permission(request, self.coding_session, self.messages(self.coding_session))
                code, answer = self.request('POST', '/permission/' + request['id'] + '/reply', {'reply': 'once' if allowed else 'reject'})
                need(code == 200 and answer is True, 'One-time native permission reply failed')
                need(allowed, 'Unreviewed tool permission requested; rejected')
                approved.add(request['id'])
            time.sleep(.2)
        need(not thread.is_alive() and result.get('status') == 200 and not result.get('transport'), 'Coding task deadline/transport failed')
        self.verify_coding(len(approved) == 1)

    def verify_coding(self, approved_once):
        messages = self.messages(self.coding_session)
        parts = [p for m in messages for p in m.get('parts', [])]
        self.gate('codingTool', any(p.get('type') == 'tool' and p.get('tool') in ('edit', 'write', 'apply_patch') and p.get('state', {}).get('status') == 'completed' for p in parts))
        self.gate('exactTestApproval', approved_once and any(p.get('tool') == 'bash' and p.get('state', {}).get('status') == 'completed' and p.get('state', {}).get('input', {}).get('command') == TEST_COMMAND and p.get('state', {}).get('metadata', {}).get('exit') == 0 for p in parts))
        assistants = [m['info'] for m in messages if m.get('info', {}).get('role') == 'assistant']
        self.gate('generatedModel', 0 < len(assistants) <= 4 and all(i.get('providerID') == 'qwen38' and i.get('modelID') == MODEL and not i.get('error') and type(i.get('tokens', {}).get('output')) in (int, float) and 0 <= i['tokens']['output'] <= 1024 for i in assistants) and any(i['tokens']['output'] > 0 for i in assistants))
        if not self.args.remaining_from:
            self.gate('streamedDeltas', len(checks.text_deltas(self.events, self.coding_session)) >= 2 and not self.event_error)
        source = self.python("import pathlib,json; p=pathlib.Path(" + repr(self.directory + '/qualification_add.py') + "); assert p.is_file() and not p.is_symlink() and p.stat().st_size<=512; print(json.dumps(p.read_text()))")
        verify_fixture(source); self.fixture_hash = hashlib.sha256(source.encode()).hexdigest()
        if self.args.remaining_from:
            need(self.fixture_hash == self.args.fixture_hash, 'Retained fixture differs from independently supplied resume hash')
        self.receipt['fixtureSha256'] = self.fixture_hash
        self.gate('independentTest', True)

    def abort(self):
        session = self.session(); thread, outcome = self.prompt(session, 'Explain a Java null check in a short paragraph. Do not use tools.')
        end = time.monotonic() + 30
        while thread.is_alive() and not checks.text_deltas(self.events, session) and time.monotonic() < end: time.sleep(.1)
        code, statuses = self.request('GET', '/session/status')
        generating = thread.is_alive() and code == 200 and statuses.get(session, {}).get('type') == 'busy'
        text = bool(checks.text_deltas(self.events, session))
        need(generating and text, 'No active streamed application generation to abort')
        aborted_at = time.monotonic()
        status, aborted = self.request('POST', '/session/' + session + '/abort')
        thread.join(timeout=45); code, statuses = self.request('GET', '/session/status')
        settled = time.monotonic(); time.sleep(1)
        fresh_idle = idle_after_abort(self.events, session, aborted_at)
        late_text = bool(checks.text_deltas(self.events, session, settled))
        self.receipt['abortEvidence'] = {'busyBeforeAbort': generating, 'assistantTextBeforeAbort': text,
            'abortHttp': status, 'abortAccepted': aborted is True, 'promptReturned': not thread.is_alive(),
            'promptHttp': outcome.get('status'), 'messageAbortedError': ((outcome.get('reply') or {}).get('info', {}).get('error') or {}).get('name') == 'MessageAbortedError',
            'statusHttp': code, 'statusMapContainsSession': isinstance(statuses, dict) and session in statuses,
            'freshIdleEvent': fresh_idle, 'lateText': late_text, 'eventTransportHealthy': not self.event_error}
        normalized = abort_statuses(code, statuses, self.events, session, aborted_at)
        self.gate('applicationAbort', fresh_idle and not thread.is_alive() and checks.cancelled(generating, text, status, aborted, outcome, code, normalized, session) and not late_text and not self.event_error)

    def runtime_inputs(self):
        probe = self.python("import os,hashlib,json;v=os.environ.get('MAAS_API_KEY','');print(json.dumps({'present':bool(v),'placeholder':bool(__import__('re').fullmatch(r'openshell:resolve:env:(?:v[0-9]+_)?MAAS_API_KEY',v)),'hash':hashlib.sha256(v.encode()).hexdigest(),'config':hashlib.sha256(open('/sandbox/workspace/opencode.json','rb').read()).hexdigest(),'startup':hashlib.sha256(open('/sandbox/state/start.sh','rb').read()).hexdigest()}))")
        attached = self.owner.run(['sandbox', 'provider', 'list', NAME, '-o', 'json'], WORKSPACE)
        need(not attached.get('next_page_token') and len(attached['providers']) == 1 and attached['providers'][0].get('name') == setup.PROVIDER and attached['providers'][0].get('type') == setup.PROVIDER and attached['providers'][0].get('credential_keys') == ['MAAS_API_KEY'], 'Exact owned provider attachment differs')
        code, effective = self.request('GET', '/config/providers')
        need(code == 200 and isinstance(effective, dict) and len(effective.get('providers', [])) == 1, 'Effective agent provider is ambiguous')
        provider = effective['providers'][0]; credential = provider.get('options', {}).get('apiKey', '')
        self.gate('placeholderNotRealKey', provider.get('id') == 'qwen38' and list(provider.get('models', {})) == [MODEL] and
                  bool(re.fullmatch(r'openshell:resolve:env:(?:v[0-9]+_)?MAAS_API_KEY', credential)) and
                  hashlib.sha256(credential.encode()).hexdigest() == probe['hash'] and probe['present'] and probe['placeholder'] and probe['hash'] != self.deployment.state['key_hash'])
        expected = (setup.INPUTS / 'config.json').read_text().replace('__MAAS_COMMON_HOST__', self.deployment.host)
        need(probe['config'] == hashlib.sha256(expected.encode()).hexdigest() and probe['startup'] == hashlib.sha256((setup.INPUTS/'start.sh').read_bytes()).hexdigest(), 'Installed startup/config differs from reviewed input')

    def confinement(self):
        self.runtime_inputs()
        denied = self.python("import json,os,socket\nr={}\n"
            "for name,path,flags in [('read','/root/.opencode-qualification',os.O_RDONLY),('write','/etc/.opencode-qualification',os.O_WRONLY|os.O_CREAT|os.O_EXCL)]:\n"
            " try:\n  fd=os.open(path,flags,0o600);os.close(fd);r[name]=False\n"
            " except OSError as e:r[name]=e.errno in (1,13)\n"
            "for name,host,port in [('internet','1.1.1.1',443),('metadata','169.254.169.254',80),('wrongBinary'," + repr(self.deployment.host) + ",443)]:\n"
            " s=socket.socket();s.settimeout(5)\n"
            " try:s.connect((host,port));r[name]=False\n"
            " except OSError as e:r[name]=e.errno in (1,13)\n"
            " finally:s.close()\nprint(json.dumps(r))")
        self.gate('filesystemDenied', denied['read'] and denied['write'])
        self.gate('egressDenied', denied['internet'] and denied['metadata'] and denied['wrongBinary'])
        foreign = subprocess.run(self.owner.command(['sandbox', 'list', '-o', 'json'], 'openshell-developer'), env=self.owner.env, capture_output=True, text=True, timeout=30)
        self.gate('foreignWorkspaceDenied', foreign_workspace_denied(foreign.returncode, foreign.stderr))

    def restart(self):
        self.stop.set()
        baseline = self.resources()
        history = setup.digest(self.messages(self.coding_session))
        marker = uuid.uuid4().hex
        self.python("import pathlib,json;p=pathlib.Path(" + repr(self.marker) + ");assert not p.exists();p.write_text(" + repr(marker) + ");print(json.dumps(True))")
        self.native(); self.close_forward(); self.stopped = True
        self.owner.run(['sandbox', 'stop', NAME], WORKSPACE, structured=False, timeout=120)
        need(self.settled_resources(running=False) == baseline, 'Stopped native/PVC identity changed')
        self.native(); self.owner.run(['sandbox', 'start', NAME], WORKSPACE, structured=False, timeout=180)
        self.settled_resources(); self.forward(); self.stopped = False
        persisted = self.python("import pathlib,hashlib,json;p=pathlib.Path(" + repr(self.marker) + ");f=pathlib.Path(" + repr(self.directory + '/qualification_add.py') + ");assert not p.is_symlink() and not f.is_symlink();print(json.dumps({'marker':p.read_text(),'fixture':hashlib.sha256(f.read_bytes()).hexdigest()}))")
        self.gate('persistentRestart', self.resources() == baseline and persisted == {'marker': marker, 'fixture': self.fixture_hash} and setup.digest(self.messages(self.coding_session)) == history)

    def run(self):
        directory = Path(self.args.state_dir)
        need(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Private setup recovery directory required')
        journal = directory / 'state.json'
        need(journal.is_file() and not journal.is_symlink() and journal.stat().st_mode & 0o077 == 0, 'Private existing recovery journal required')
        self.journal, self.journal_hash = journal, hashlib.sha256(journal.read_bytes()).hexdigest()
        self.receipt['recoveryJournalSha256'] = self.journal_hash
        if self.args.remaining_from:
            prior = Path(self.args.remaining_from)
            need(prior.parent.resolve() == directory.resolve() and re.fullmatch(r'qualification-[0-9a-f]{32}\.json', prior.name) and
                 prior.is_file() and not prior.is_symlink() and prior.stat().st_mode & 0o077 == 0 and prior.stat().st_uid == os.getuid(), 'Continuation requires exact owner-only receipt in setup state directory')
            raw = prior.read_bytes(); receipt = json.loads(raw)
            need(receipt.get('scope') == self.receipt['scope'], 'Prior qualification scope differs')
            self.directory, self.marker = remaining_fixture(receipt)
            self.coding_session = self.args.coding_session
            self.receipt.update(checks={g: receipt['checks'].get(g, False) for g in GATES},
                                ownedFixture=self.directory + '/qualification_add.py', ownedMarker=self.marker,
                                resumedReceiptSha256=hashlib.sha256(raw).hexdigest(),
                                hashGuard='fixture hash independently supplied at continuation; no earlier hash claim',
                                retainedCodingEvidence='owner-only prior receipt and current session/tool/model/AST readback; no coding replay')
        self.deployment = read_only_setup(self.args)
        need(self.deployment.state and not any(v for k, v in self.deployment.state.items() if k.endswith('_pending')), 'Setup has pending ownership gates')
        password = directory / 'upload/state/auth/server-password'
        need(password.is_file() and not password.is_symlink() and password.stat().st_mode & 0o077 == 0, 'Private listener credential required')
        self.password = password.read_text(); need(len(self.password) >= 32, 'Listener credential is invalid')
        self.deployment.preflight()
        for path in (Path(__file__), STAGE/'setup-opencode.py'):
            need(subprocess.check_output(['git','-C',str(setup.ROOT),'show',self.args.revision+':'+str(path.relative_to(setup.ROOT))]) == path.read_bytes(), 'Published qualification dependency differs')
        with native_gateway(self.deployment.bootstrap_env, self.deployment.cli) as admin, native_gateway(self.deployment.bootstrap_env, self.deployment.cli, self.args.persona_home) as owner:
            self.owner = owner; self.deployment.admin, self.deployment.owner = admin, owner
            try:
                self.deployment.inventory(); self.deployment.policy_input(); self.deployment.check()
                native = self.native()
                need(native.get('name') == NAME and native.get('policy') == self.deployment.intended, 'Owned logical runtime or effective policy differs')
                self.settled_resources(); self.gate('ownedRuntime', True)
                if not self.args.remaining_from:
                    self.python("import pathlib,json; d=pathlib.Path(" + repr(self.directory) + "); d.mkdir(mode=0o700); p=d/'qualification_add.py'; p.write_text('def add(a, b):\\n    return a - b\\n'); print(json.dumps(True))")
                self.forward(); self.gate('authenticatedHealth', True)
                self.gate('invalidPasswordDenied', self.request('GET', '/global/health', password='synthetic-invalid-password')[0] == 401)
                self.gate('missingPasswordDenied', self.request('GET', '/global/health', authenticated=False)[0] == 401)
                if self.args.remaining_from:
                    self.runtime_inputs()
                else:
                    self.confinement()
                reader = threading.Thread(target=self.read_events, daemon=True); reader.start()
                end = time.monotonic() + 10
                while not self.events and not self.event_error and time.monotonic() < end: time.sleep(.1)
                need(self.events and not self.event_error, 'Authenticated SSE transport unavailable')
                if self.args.remaining_from:
                    code, retained = self.request('GET', '/session/' + self.coding_session)
                    need(code == 200 and retained.get('id') == self.coding_session and retained.get('directory') == self.directory, 'Retained session is outside exact owned fixture directory')
                    self.verify_coding(True)
                else:
                    self.coding()
                self.abort(); self.restart()
                self.deployment.check(); self.resources(); self.forward(); self.runtime_inputs(); self.gate('runningAtEnd', True)
                self.receipt['passed'] = not self.receipt['pendingGates']
            finally:
                self.stop.set()
                for session in self.sessions:
                    if self.process:
                        try: self.request('POST', '/session/' + session + '/abort', timeout=5)
                        except Exception: pass
                if self.stopped:
                    try:
                        self.native(); owner.run(['sandbox', 'start', NAME], WORKSPACE, structured=False, timeout=180)
                        self.forward(); self.resources(); self.receipt['checks']['runningAtEnd'] = True
                    except Exception:
                        self.receipt['checks']['runningAtEnd'] = False
                self.close_forward()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--static', action='store_true'); mode.add_argument('--run', action='store_true')
    parser.add_argument('--remaining-from', help='Exact private failed-abort receipt; resumes cancellation/restart only')
    parser.add_argument('--coding-session', help='Exact retained coding session for --remaining-from')
    parser.add_argument('--fixture-hash', help='Independent SHA256 of retained fixture read at continuation')
    parser.add_argument('--revision')
    parser.add_argument('--state-dir', default='/private/tmp/060-opencode-state')
    parser.add_argument('--persona-home', default=os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'))
    parser.add_argument('--persona-kubeconfig', default=os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'))
    args = parser.parse_args(); args.apply = False; args.expected_policy_hash = None
    if args.static:
        verify_fixture('def add(a, b):\n    return a + b\n')
        config = json.loads((STAGE/'opencode/config.json').read_text())
        need(config['permission']['bash'] == 'ask' and config['permission']['webfetch'] == 'deny' and config['enabled_providers'] == ['qwen38'] and config['provider']['qwen38']['models'][MODEL]['limit']['output'] == 1024 and config.get('agent', {}).get('build', {}).get('steps') == 4, 'Reviewed bounded provider/config differs')
        print('[OK] Static inputs and independent fixture verifier passed; no cluster or inference calls')
        return
    need(args.revision and args.persona_home and args.persona_kubeconfig, 'Exact revision and genuine private ai-admin sessions required')
    need(not args.remaining_from or (args.coding_session and re.fullmatch(r'ses_[A-Za-z0-9]+', args.coding_session) and args.fixture_hash and re.fullmatch(r'[0-9a-f]{64}', args.fixture_hash)), 'Continuation requires exact coding session and independent fixture hash')
    need(args.remaining_from or not (args.coding_session or args.fixture_hash), 'Continuation inputs require --remaining-from')
    qualification = Qualification(args)
    directory = Path(args.state_dir)
    need(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, 'Existing private setup state required')
    descriptor = os.open(directory/'qualification.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(RuntimeError('Bounded qualification deadline exceeded')))
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('Termination requested')))
        signal.alarm(600)
        try:
            qualification.run()
        except (Exception, KeyboardInterrupt) as error:
            # Foreign/native error bodies and private inputs are never printed.
            qualification.receipt['failureClass'] = type(error).__name__
            if isinstance(error, RuntimeError): qualification.receipt['failure'] = str(error)
            qualification.receipt['pendingGates'] = [g for g in GATES if not qualification.receipt['checks'].get(g)]
        finally:
            signal.alarm(0)
        private_receipt(directory/('qualification-'+uuid.uuid4().hex+'.json'), qualification.receipt)
        print(json.dumps(qualification.receipt))
        need(qualification.receipt['passed'], 'Qualification incomplete; preserved setup state and retained key')


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('[FAIL] ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
        raise SystemExit(1)
