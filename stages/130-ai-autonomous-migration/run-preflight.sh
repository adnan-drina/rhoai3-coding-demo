#!/usr/bin/env bash
# Read-only launch check for ANY migration run created by the app-migration
# factory after 2026-09-24 (run-budget.json schema v2). Does not reset data,
# mint cards, or install a harness. Historical launch records and retired
# scripts remain available in Git history.
# Required: WORKSPACE (the run: the full project name, never a suffix), POD,
# GOLDEN_CHECKOUT (verified published checkout), GOLDEN_SHA, PLATFORM_SHA (the
# merged platform revision). No isolation campaign is required for each run.
# Existing isolation receipts remain historical evidence, not new-run claims.
# The expected model and wall budget are read from the golden's
# run-defaults.json, so a pin change is made once, in the golden.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/../../scripts/shared/lib.sh"
load_env
check_oc_logged_in
export POD="${POD:?set POD}" GOLDEN_CHECKOUT="${GOLDEN_CHECKOUT:?set GOLDEN_CHECKOUT}"
export GOLDEN_SHA="${GOLDEN_SHA:?set the full published golden commit}"
export PLATFORM_SHA="${PLATFORM_SHA:?set the merged platform commit}"
export WORKSPACE="${WORKSPACE:?set the run: the full project name the factory was given}"
export NS="${NS:-wksp-ai-developer}" CONTAINER="${CONTAINER:-development-tooling}"
python3 - <<'PY'
import hashlib,json,os,re,subprocess,sys
from pathlib import Path

def cmd(*args):
    return subprocess.check_output(args, text=True, timeout=60)
def oc(*args):
    return cmd('oc','--request-timeout=30s',*args)
def need(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_image_bindings(defaults, receipt):
    images = defaults.get('configuration', {}).get('images', {})
    for key in ('databaseImage', 'provisionerImage'):
        expected = images.get(key, '')
        need(isinstance(expected, str) and bool(re.fullmatch(r'.+@sha256:[0-9a-f]{64}', expected)),
             'golden lacks a pinned ' + key)
        need(receipt.get(key) == expected, 'provisioning receipt differs from golden: ' + key)

def check_worker_identity(pod, receipt, default_binding, namespace, workspace):
    expected = workspace + '-worker'
    need(receipt.get('workerServiceAccount') == expected,
         'provisioning receipt does not bind the per-run worker identity')
    need(pod['spec'].get('serviceAccountName') == expected,
         'workspace pod still uses a generated or foreign ServiceAccount')
    for subject in default_binding.get('subjects', []):
        direct = (subject.get('kind') == 'ServiceAccount'
                  and subject.get('name') == expected
                  and subject.get('namespace', namespace) == namespace)
        group = (subject.get('kind') == 'Group' and subject.get('name') in
                 ('system:authenticated', 'system:serviceaccounts',
                  'system:serviceaccounts:' + namespace))
        user = (subject.get('kind') == 'User' and subject.get('name') ==
                'system:serviceaccount:' + namespace + ':' + expected)
        need(not (direct or group or user), 'worker is bound to devworkspace-default-role')

def run_stop_gaps(profile_doc, model, defaults):
    """v32: the token budgets and the stall limit the workspace enforces are pinned: the selected
    model profile's run_input_token_budget (and, with loop escalation, retry_start_turns) and the
    golden's run-level budget.run_input_token_budget and budget.no_accepted_checkpoint_minutes."""
    def positive(v):
        return isinstance(v, int) and not isinstance(v, bool) and v > 0
    prof = ((profile_doc or {}).get('profiles') or {}).get(model) if isinstance(profile_doc, dict) else None
    if not isinstance(prof, dict):
        return ['RUN_TOKEN_BUDGET: no model profile for %s' % model]
    gaps = []
    if not positive(prof.get('run_input_token_budget')):
        gaps.append('RUN_TOKEN_BUDGET: the profile for %s pins no positive run_input_token_budget' % model)
    esc = prof.get('loop_escalation')
    if isinstance(esc, dict) and esc.get('enabled') is True and not positive(esc.get('retry_start_turns')):
        gaps.append('RUN_TOKEN_BUDGET: the profile for %s enables loop_escalation without a positive retry_start_turns' % model)
    budget = (defaults or {}).get('budget') or {}
    for key in ('run_input_token_budget', 'no_accepted_checkpoint_minutes'):
        if not positive(budget.get(key)):
            gaps.append('RUN_STOPS: run-defaults.json budget.%s is not a positive integer' % key)
    return gaps

def worker_kubeconfig_mount_ok(pod, container_name):
    spec = pod['spec']
    worker = next(c for c in spec['containers'] if c['name'] == container_name)
    env = {e['name']: e.get('value') for e in worker.get('env', [])}
    if env.get('KUBECONFIG') != '/home/user/.kube/config':
        return False
    mounts = [m for m in worker.get('volumeMounts', []) if m['mountPath'] == '/home/user/.kube']
    if len(mounts) != 1:
        return False
    volume = next((v for v in spec.get('volumes', []) if v['name'] == mounts[0]['name']), {})
    return 'emptyDir' in volume

def source_mount_ok(pod, container_name):
    spec = pod['spec']
    containers = spec['containers']
    worker = next(c for c in containers if c['name'] == container_name)
    mounts = [m for m in worker.get('volumeMounts', []) if m['mountPath'] == '/projects/legacy']
    if len(mounts) != 1 or not mounts[0].get('readOnly'):
        return False
    source = mounts[0]
    claims = {v['name']: v.get('persistentVolumeClaim', {}).get('claimName') for v in spec['volumes']}
    claim = claims.get(source['name'])
    source_path = source.get('subPath', '').strip('/')
    if not claim or not source_path or source.get('subPathExpr'):
        return False
    for c in containers:
        for m in c.get('volumeMounts', []):
            if claims.get(m['name']) != claim or m.get('readOnly'):
                continue
            parent = m.get('subPath', '').strip('/')
            if m.get('subPathExpr') or not parent or source_path == parent or source_path.startswith(parent + '/') or parent.startswith(source_path + '/'):
                return False
    return True

ns, pod, workspace = (os.environ[k] for k in ('NS','POD','WORKSPACE'))
golden = Path(os.environ['GOLDEN_CHECKOUT'])
sha = os.environ['GOLDEN_SHA']; platform = os.environ['PLATFORM_SHA']
need(bool(re.fullmatch('[0-9a-f]{40}', sha)) and bool(re.fullmatch('[0-9a-f]{40}',platform)), 'full golden/platform commits required')
need(cmd('git','-C',str(golden),'rev-parse','HEAD').strip() == sha, 'golden checkout is not the pin')
need(not cmd('git','-C',str(golden),'status','--porcelain').strip(), 'golden checkout is dirty')
defaults = json.loads((golden / 'run-defaults.json').read_text())
need(defaults.get('schema') == 'rhoai3.run-defaults/v1', 'golden predates run-defaults.json; use the preflight of that run')
# The model this run requested at creation is the one the provisioner pinned in its run control (template parameter
# "model", 2026-10-02); the golden's run-defaults model is only the fallback for a run created before that.
def _pinned_run_model():
    try:
        cm = json.loads(oc('get','configmap',os.environ['WORKSPACE']+'-run-control','-n',os.environ.get('NS','wksp-ai-developer'),'-o','json'))
        return json.loads(cm['data']['profile.json']).get('default_model') or ''
    except Exception:
        return ''
os.environ['EXPECTED_MODEL'] = os.environ.get('EXPECTED_MODEL') or _pinned_run_model() or defaults['configuration']['model']['id']
expected_hours = defaults['budget']['max_wall_hours']
# v32: the selected profile's per-run token budget (the run's pinned run-control copy, else the platform table)
# and the golden's run-level stops are pinned before anything starts.
def _profile_doc():
    for name, key in ((os.environ['WORKSPACE'] + '-run-control', 'profile.json'), ('migration-model-profiles', 'model-profiles.json')):
        try:
            return json.loads(json.loads(oc('get','configmap',name,'-n',os.environ.get('NS','wksp-ai-developer'),'-o','json'))['data'][key])
        except Exception:
            continue
    return None
_stop_gaps = run_stop_gaps(_profile_doc(), os.environ['EXPECTED_MODEL'], defaults)
need(not _stop_gaps, '; '.join(_stop_gaps))
# The operator retired repeated isolation campaigns. Validate this workspace
# against the released defaults and live platform; do not promote old receipts.
app = json.loads(oc('get','application','070-advanced-app-platform','-n','openshift-gitops','-o','json'))
need(app.get('status',{}).get('sync',{}).get('revision') == platform
     and app['status']['sync'].get('status') == 'Synced'
     and app['status'].get('health',{}).get('status') == 'Healthy', 'Stage 050 is not healthy at the selected revision')
tekton = json.loads(oc('get','tektonconfig','config','-o','json'))
need(any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in tekton.get('status',{}).get('conditions',[])), 'TektonConfig is not Ready')
listener = json.loads(oc('get','deployment','el-app-platform-listener','-n','app-platform-build','-o','json'))
need(listener.get('status',{}).get('readyReplicas',0) >= 1
     and listener['status'].get('observedGeneration',0) >= listener['metadata']['generation'], 'webhook dispatcher is not ready')
p = json.loads(oc('get','pod',pod,'-n',ns,'-o','json'))
need(source_mount_ok(p, os.environ['CONTAINER']), 'source mount is writable or has a writable runtime alias')
need(p['metadata'].get('labels',{}).get('controller.devfile.io/devworkspace_name') == workspace, 'actual workspace name mismatch')
# v32 (2026-10-02): the factory wrote a devfile with the PREVIOUS image while the golden pinned the new one, and nothing
# compared them -- a run could start on another runtime. Every ws-080 container runs exactly the golden's pinned image.
_pins = json.loads((golden / '.hermes' / 'pins.json').read_text())['pins']
_want_img = _pins['workspace_overlay']['ws_080']['digest']
_imgs = [cs.get('imageID') or cs.get('image') or '' for cs in (p.get('status') or {}).get('containerStatuses') or []
         if 'rhoai3-ws-080' in (cs.get('image') or '') + (cs.get('imageID') or '')]
need(_imgs and all(i.endswith(_want_img) for i in _imgs),
     'the workspace runs %s, the golden pins %s' % (', '.join(sorted({i.rsplit('@', 1)[-1][:19] for i in _imgs})) or 'no ws-080 image', _want_img[:19]))
receipt = json.loads(oc('get','configmap','migration-run-'+workspace,'-n',ns,'-o','json'))['data']
need(receipt.get('phase') == 'provisioned' and receipt.get('workspace') == workspace
     and receipt.get('namespace') == ns, 'provisioning receipt is not ready for this workspace')
default_binding = json.loads(oc('get','rolebinding','devworkspace-default-rolebinding','-n',ns,'-o','json'))
check_worker_identity(p, receipt, default_binding, ns, workspace)
need(worker_kubeconfig_mount_ok(p, os.environ['CONTAINER']),
     'worker kubeconfig directory lacks its ephemeral mount; late Dashboard token injection is possible')
check_image_bindings(defaults, receipt)
deployment = json.loads(oc('get','deployment',receipt['host'],'-n',ns,'-o','json'))
need(deployment.get('status',{}).get('availableReplicas',0) == 1
     and deployment['spec']['template']['spec']['containers'][0]['image'] == receipt['databaseImage'],
     'assigned database is not available on the pinned image')
for secret in (receipt['workspaceSecret'],receipt['fixtureSecret']):
    doc = json.loads(oc('get','secret',secret,'-n',ns,'-o','json'))
    labels, ann = doc['metadata'].get('labels',{}), doc['metadata'].get('annotations',{})
    need(all(labels.get('controller.devfile.io/'+k) == 'true' for k in ('watch-secret','mount-to-devworkspace'))
         and ann.get('controller.devfile.io/mount-to-devworkspace-include') == workspace
         and ann.get('controller.devfile.io/mount-on-start') == 'true'
         and ann.get('controller.devfile.io/mount-as') == 'env', 'incorrect secret targeting: '+secret)
    container = next(c for c in p['spec']['containers'] if c['name'] == os.environ['CONTAINER'])
    sources = {e.get('valueFrom',{}).get('secretKeyRef',{}).get('name') for e in container.get('env',[])}
    sources |= {e.get('secretRef',{}).get('name') for e in container.get('envFrom',[])}
    need(secret in sources, 'pod does not consume its assigned secret: '+secret)
# The worker must reach MaaS through the gateway's in-cluster Service, not the
# public ELB, which drops silent tool-call streams. The factory stamps a pod
# hostAlias at creation; v12 started without one (it was a manual step) and
# this preflight passed it, so the route is now a launch requirement.
maas_host = oc('get','gateway','maas-default-gateway','-n','openshift-ingress','-o','jsonpath={.spec.listeners[?(@.name=="https")].hostname}').strip()
maas_ip = oc('get','service','maas-gateway-internal','-n','openshift-ingress','-o','jsonpath={.spec.clusterIP}').strip()
need(bool(re.fullmatch(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*', maas_host))
     and bool(re.fullmatch(r'\d+\.\d+\.\d+\.\d+', maas_ip)), 'MaaS gateway host or internal IP unavailable')
# B3: the quota this run will draw on, and who else draws on it. Per-model
# token limits live on the MaaSSubscription every workspace key is minted
# under, so concurrent runs share one bucket.
sub = json.loads(oc('get','maassubscription','devspaces-coding-models','-n','models-as-a-service','-o','json'))
limits = [l for r in sub.get('spec',{}).get('modelRefs',[]) if r.get('name') == os.environ['EXPECTED_MODEL']
          for l in (r.get('tokenRateLimits') or [])]
need(len(limits) == 1, 'devspaces-coding-models declares %d token limits for %s; exactly one is admitted' % (len(limits), os.environ['EXPECTED_MODEL']))
quota_limit, quota_window = int(limits[0]['limit']), str(limits[0]['window'])
# Other consumers of the same allowance: only migration RUNS draw the declared
# per-run demand (their devfile names MIGRATION_RUN_NAME); every other
# consumer of the subscription is covered by the profile's declared reserve.
def is_migration_run(w):
    comps = (w.get('spec',{}).get('template',{}) or {}).get('components') or []
    return any(e.get('name') == 'MIGRATION_RUN_NAME' for c in comps for e in ((c.get('container') or {}).get('env') or []))
dws = json.loads(oc('get','devworkspace','-n',ns,'-o','json')).get('items',[])
# v32 (2026-10-02): the subscription limits are PER MODEL, so another run draws on this allowance only when the
# profile pinned for IT selects the same model (its <run>-run-control profile.json default_model); a run whose pin
# cannot be read still counts (conservative). Before the two-model A/B every run shared one model.
def pinned_model(name):
    try:
        cm = json.loads(oc('get','configmap',name+'-run-control','-n',ns,'-o','json'))
        return json.loads(cm['data']['profile.json']).get('default_model') or ''
    except Exception:
        return ''
quota_others = sum(1 for w in dws if w['metadata']['name'] != workspace and is_migration_run(w)
                   and w.get('status',{}).get('phase') in ('Running','Starting')
                   and pinned_model(w['metadata']['name']) in ('', os.environ['EXPECTED_MODEL']))
model = json.loads(oc('get','llminferenceservice',os.environ['EXPECTED_MODEL'],'-n','internal-models','-o','json'))
need(any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in model.get('status',{}).get('conditions',[])), 'Qwen model is not Ready')
def args_in(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k == 'args' and isinstance(v,list):
                yield v
            else:
                yield from args_in(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from args_in(v)
windows=[]
for args in args_in(model['spec']):
    for i,arg in enumerate(args):
        if arg.startswith('--max-model-len='): windows.append(int(arg.split('=',1)[1]))
        elif arg == '--max-model-len': windows.append(int(args[i+1]))
need(len(set(windows)) == 1, 'served model window absent or ambiguous')
expected={}
for directory in ('.hermes/kernel','.hermes/lib','.hermes/skills','.hermes/planning/schemas','.hermes/planning/catalogs','decided-repairs'):
    need((golden/directory).is_dir(), 'golden missing '+directory)
    for f in (golden/directory).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts and not f.name.startswith('._'):
            expected[f.relative_to(golden).as_posix()] = digest(f)
# The shared defaults the run's declaration binds must be the golden's, byte for byte.
expected['run-defaults.json'] = digest(golden / 'run-defaults.json')
# The remote script prints assertions only, never environment/config values.
remote = '''def require(condition, message):
    if not condition:
        raise AssertionError(message)
import hashlib, json, os, sys, subprocess
from pathlib import Path
root = Path('/projects/modernized')
# Check the CLI credential as well as the admitted pod identity. Do not print
# kubeconfig contents or token values. The replacement Config has one user.
kube = json.loads(subprocess.check_output(['oc', 'config', 'view', '-o', 'json'], text=True))
users = kube.get('users', [])
require(len(users) == 1 and users[0].get('name') == 'current-pod'
        and users[0].get('user') == {'tokenFile': '/var/run/secrets/kubernetes.io/serviceaccount/token'},
        'CLI kubeconfig retains a different credential')
require(subprocess.check_output(['oc', 'whoami'], text=True).strip() == WORKER_IDENTITY,
        'CLI credential is not the per-run worker')
sys.path.insert(0, str(root / '.hermes/lib'))
from planner import run_identity
from planner.yamlite import load_yaml
expected = json.loads(EXPECTED)
require(all(((root / k).is_file() and hashlib.sha256((root / k).read_bytes()).hexdigest() == v for k, v in expected.items())), 'installed harness differs from golden')
v = run_identity.check(root)
require(v.code == run_identity.OK, str(v))
require(not run_identity.fixture_gaps(root), 'fixture variables missing')
import socket
with socket.create_connection((v.observed['host'], v.observed['port']), timeout=5):
    pass
issued = root / 'verification/loop/issued.json'
require(not issued.exists() or not json.loads(issued.read_text()).get('task_id'), 'card already issued')
require(not (root / 'evidence/producers/bootstrap.json').exists(), 'preflight requires a fresh destination before bootstrap')
require(not (root / 'src/main/java').exists(), 'product sources present before bootstrap')
d = load_yaml(root / 'decisions.yaml')
require(d.get('loop', {}).get('unit_formation') == 'v1' and d.get('loop', {}).get('runtime_feedback') == 'v1' and d.get('loop', {}).get('plan_semantics') == 'v1', 'loop flags (unit_formation, runtime_feedback, plan_semantics v1)')
r = d['decided_repairs']
require(hashlib.sha256((root / r['manifest']).read_bytes()).hexdigest() == r['manifest_sha256'], 'repair manifest mismatch')
config = next((p for p in (Path('/etc/hermes/config.yaml'), Path('/projects/.platform/hermes/config.yaml')) if p.is_file()), None)
require(config, 'managed Hermes config missing')
c = load_yaml(config)
# The effective hook registrations (Stage 050 producer): K2 fail-closed with the
# complete terminator in its matcher and a 5 s timeout; the terminal
# post_tool_call observer the harness ships (V17-6b), never fail-closed.
hooks = c.get('hooks') or {}
k2 = [h for h in hooks.get('pre_tool_call') or [] if str(h.get('command', '')).endswith('pre_tool_call.sh')]
require(len(k2) == 1 and k2[0].get('fail_closed') is True and k2[0].get('timeout') == 5
        and 'kanban_complete' in str(k2[0].get('matcher', '')).split('|'),
        'the K2 pre_tool_call hook is not registered fail-closed with a 5 s timeout')
require((root / '.hermes/kernel/post_tool_call.py').is_file()
        and any(h.get('matcher') == 'terminal' and str(h.get('command', '')).endswith('post_tool_call.py')
                and not h.get('fail_closed') for h in hooks.get('post_tool_call') or []),
        'the terminal post_tool_call observer is not shipped or not registered')
# v32: the in-workspace stops (kernel/run_budget.py): the per-run token budget before every tool call
# (fail-open, never fail-closed) and the run-level stops on the dispatcher tick; the launch shim
# (kernel/worker_launch.py) is the dispatcher's HERMES_BIN.
if (root / '.hermes/kernel/run_budget.py').is_file():
    require(any(h.get('matcher') == '.*' and str(h.get('command', '')).endswith('run_budget.py pre-tool')
                and not h.get('fail_closed') for h in hooks.get('pre_tool_call') or []),
            'RUN_TOKEN_BUDGET: the per-run budget hook is not registered (pre_tool_call .* run_budget.py pre-tool)')
    require(any(' tick --root ' in str(h.get('command', '')) and 'run_budget.py' in str(h.get('command', ''))
                for h in hooks.get('on_kanban_dispatch_tick') or []),
            'RUN_STOPS: the run-level stops are not registered on the dispatcher tick (run_budget.py tick)')
if (root / '.hermes/kernel/worker_launch.py').is_file():
    _shim = config.parent / 'bin' / 'hermes-worker-launch'
    _envt = (config.parent / '.env').read_text() if (config.parent / '.env').is_file() else ''
    require(('HERMES_BIN=%s' % _shim) in _envt.splitlines() and _shim.is_file(),
            'RETRY_ESCALATION: the managed .env does not route worker spawns through the launch shim (HERMES_BIN)')
require(c.get('model', {}).get('default') == MODEL, 'worker model mismatch')
import socket
from urllib.parse import urlsplit
require(urlsplit(os.environ.get('MAAS_API_BASE_URL', '')).hostname == MAASHOSTVAL, 'worker MaaS endpoint is not the platform gateway host')
addrs = {a[4][0] for a in socket.getaddrinfo(MAASHOSTVAL, 443, proto=socket.IPPROTO_TCP)}
require(addrs == {MAASIPVAL}, 'MaaS host resolves to %s, not the in-cluster gateway %s: the workspace is on the public ELB path' % (sorted(addrs), MAASIPVAL))
# B3 / R2: the run's ENFORCED allowance (the Hermes pacer, patch 0007, paces
# every model request of the run -- main, each retry, auxiliary, reviewer --
# to max_requests_per_window) at the largest request the SERVER admits (the
# pacer counts requests, not input tokens, so the bound is the served window,
# prompt plus output: vLLM --max-model-len) plus the declared reserve for
# every other consumer, fits the subscription's limit. The profile is the one
# PINNED for this run.
def rate_budget_gap(q, served, runs, limit):
    reserve = int(q['reserve_tokens_per_window'])
    if q.get('accounting_mode') == 'token':
        # V15-1: reserved-and-settled tokens (runtime 0010). Each request
        # reserves reservation_tokens (at least the served window) and is
        # admitted while settled + open + reservation <= the run allowance, so
        # the run can never exceed its allowance; admission sums allowances.
        allowance, reservation = int(q['token_allowance_per_window']), int(q['reservation_tokens'])
        if 'max_requests_per_window' in q:
            return 'a token-mode profile also declares a request ceiling (max_requests_per_window)'
        if reservation < served:
            return 'the profile reserves %d tokens per request and the model serves %d' % (reservation, served)
        if not 0 < reservation <= allowance:
            return 'the reservation %d does not fit the allowance %d' % (reservation, allowance)
        if not 0 < int(q['max_output_tokens']) < reservation:
            return 'the output cap %s does not fit a %d-token request' % (q['max_output_tokens'], reservation)
        total = runs * allowance + reserve
        if total > limit:
            return 'effective %d, declared %d (%d run(s) x %d token allowance + reserve %d)' % (limit, total, runs, allowance, reserve)
        return ''
    per_request = int(q['max_request_tokens'])
    if per_request < served:
        return 'the profile sizes a request at %d tokens and the model serves %d' % (per_request, served)
    if not 0 < int(q['max_output_tokens']) < per_request:
        return 'the output cap %s does not fit a %d-token request' % (q['max_output_tokens'], per_request)
    total = runs * int(q['max_requests_per_window']) * per_request + reserve
    if total > limit:
        return 'effective %d, declared %d (%d run(s) x %d requests x %d tokens + reserve %d)' % (
            limit, total, runs, int(q['max_requests_per_window']), per_request, reserve)
    return ''
prof_path = Path('/etc/rhoai3/run-control/profile.json')
if not prof_path.is_file():
    prof_path = Path('/projects/.platform/hermes/model-profile.json')
prof_doc = json.loads(prof_path.read_text())
prof = prof_doc['profiles'][prof_doc['default_model']]
q = prof['quota']
runs = 1 + QOTHERSVAL
win = '%dh' % (int(q['window_seconds']) // 3600) if int(q['window_seconds']) % 3600 == 0 else '%ds' % int(q['window_seconds'])
require(win == QWINVAL, 'the profile paces per %s and the subscription limits per %s' % (win, QWINVAL))
budget_gap = rate_budget_gap(q, WINDOW, runs, QLIMITVAL)
require(not budget_gap, 'MOD' + 'EL_RATE_BUDGET: %s, quota devspaces-coding-models/%s: %s; profile %s'
        % (prof_doc['default_model'], QWINVAL, budget_gap, prof_path))
env_text = Path('/projects/.platform/hermes/.env').read_text() if Path('/projects/.platform/hermes/.env').is_file() else ''
require(((q.get('accounting_mode') == 'token'
          and 'RHOAI3_ACCOUNTING_MODE=token' in env_text
          and 'RHOAI3_TOKEN_BUDGET=%d/%d' % (int(q.get('token_allowance_per_window') or 0), int(q['window_seconds'])) in env_text
          and 'RHOAI3_TOKEN_RESERVATION=%d' % int(q.get('reservation_tokens') or 0) in env_text
          and 'RHOAI3_REQUEST_BUDGET=' not in env_text)
         or (q.get('accounting_mode') != 'token'
             and 'RHOAI3_REQUEST_BUDGET=%d/%d' % (int(q.get('max_requests_per_window') or 0), int(q['window_seconds'])) in env_text))
        and 'RHOAI3_REQUEST_LEDGER=' in env_text,
        'the worker runtime is not configured to pace this allowance (RHOAI3_REQUEST_BUDGET/LEDGER in the managed .env)')
# B1: the workspace's own startup gate (planner.maas_route) must agree with
# the cluster truth read above: the platform values stamped into this
# workspace name that gateway and address, and TLS verifies through it.
if (root / '.hermes/lib/planner/maas_route.py').is_file():
    require(os.environ.get('RHOAI3_MAAS_HOST') == MAASHOSTVAL and os.environ.get('RHOAI3_MAAS_INTERNAL_IP') == MAASIPVAL,
            'the workspace was stamped with MaaS route %s -> %s, the cluster gateway is %s -> %s: refresh the factory routing input'
            % (os.environ.get('RHOAI3_MAAS_HOST'), os.environ.get('RHOAI3_MAAS_INTERNAL_IP'), MAASHOSTVAL, MAASIPVAL))
    sys.path.insert(0, str(root / '.hermes/lib'))
    from planner.maas_route import route_gaps
    gaps, _rec = route_gaps(dict(os.environ))
    require(not gaps, 'STARTUP_MAAS_ROUTE: %s' % (gaps[0] if gaps else ''))

def leaves(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == 'context_length':
                yield int(v)
            elif isinstance(v, (dict, list)):
                yield from leaves(v)
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v)
# the SELECTED model's limits against the selected model's served window (E-1 v31, 2026-10-01: with
# qwen3-6-27b selected, the still-configured qwen38 provider's 220000 -- below ITS 262144 window --
# was compared with qwen3-6-27b's 131072 and refused a correct config)
_m = c.get('model') or {}
_sel = ((c.get('providers') or {}).get(_m.get('provider')) or {}).get('models', {}).get(_m.get('default'))
windows = list(leaves({'model': _m, 'selected': _sel or {}}))
require(_sel is not None, 'the selected model has no provider entry')
require(windows and all((0 < v < WINDOW for v in windows)), 'context limit must be below served window')
require(c.get('terminal', {}).get('timeout', 0) >= 600, 'terminal timeout')
require(c.get('compression', {}).get('threshold', 0) >= 0.8, 'compression threshold')
# E-1 v31: the pinned profile's compression (absolute trigger, tool-result prune, protected tail) is what the worker runs
_pp = Path('/etc/rhoai3/run-control/profile.json')
if _pp.is_file():
    _pd = json.loads(_pp.read_text())
    _want = ((_pd.get('profiles') or {}).get(_pd.get('default_model')) or {}).get('compression') or {}
    for _k, _v in _want.items():
        require(c.get('compression', {}).get(_k) == _v, 'compression %s is %r, the pinned profile says %r' % (_k, c.get('compression', {}).get(_k), _v))
    # patch 0017: the selected profile's loop escalation and reasoning echo reach the worker config exactly
    _prof = ((_pd.get('profiles') or {}).get(_pd.get('default_model')) or {})
    if _prof.get('loop_escalation'):
        require((_sel or {}).get('loop_escalation') == _prof['loop_escalation'],
                'the selected model entry does not carry the pinned loop_escalation')
    if _prof.get('reasoning_echo'):
        require(_m.get('reasoning_echo') is True, 'model.reasoning_echo is not set for a profile that requires it')
source = Path('/projects/legacy')
require(bool(os.statvfs(source).f_flag & os.ST_RDONLY), 'legacy checkout is writable; require a read-only mount')
source_receipt = source / '.git/rhoai3-source.json'
require(source_receipt.is_file(), 'source clone receipt missing')
origin = json.loads(source_receipt.read_text())
require(origin.get('schema') == 'rhoai3.source-volume/v1' and origin.get('commit') == subprocess.check_output(['git', '-c', 'safe.directory=' + str(source), '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(), 'source clone receipt mismatch')
# The factory declared this run's budget in the destination's initial commit;
# the loader refuses a missing, foreign, stale or rewritten declaration, and a
# history that does not begin at the platform receipt's scaffolding commit.
from planner import run_declaration
d = run_declaration.load(root, expected_run=WORKSPACE_NAME)
require(d.code == run_declaration.OK, str(d))
require(d.budget.get('max_wall_hours') == EXPECTED_HOURS, 'declared wall budget differs from the golden defaults')
# The board protocol: the run request in its initial commit, agreed by the
# read-only run control (outcome_protocol.launch_gaps). A request the installed
# harness cannot honour, a disagreement, a missing selection or a disabled
# outcome board refuses here; the serial loop is never launched instead.
initial = subprocess.check_output(['git', '-C', str(root), 'rev-list', '--max-parents=0', 'HEAD'], text=True).split()
declared = json.loads(subprocess.check_output(['git', '-C', str(root), 'show', initial[0] + ':run-budget.json'], text=True))
try:
    from planner import outcome_protocol
    launch = getattr(outcome_protocol, 'launch_gaps', None)
except ImportError:
    launch = None
if launch is None:
    require(declared.get('board_protocol') in (None, 'serial-loop/v1'),
            'BOARD_PROTOCOL: the run requests %s and the installed harness cannot select it' % declared.get('board_protocol'))
    protocol = 'serial-loop/v1'
else:
    sel, gaps = launch(root)
    require(not gaps, 'BOARD_PROTOCOL: %s' % (outcome_protocol.describe(gaps).splitlines()[0] if gaps else ''))
    protocol = sel.protocol
    if protocol == 'outcome-board/v2':
        # native control: the producer extended the K2 matcher from the same selection and
        # registered NO reconciler (the one native dispatcher promotes dependents itself)
        hk = c.get('hooks') or {}
        m = str((hk.get('pre_tool_call') or [{}])[0].get('matcher', '')).split('|')
        require(all(t in m for t in ('kanban_block', 'kanban_request_review', 'request_review', 'kanban_comment',
                                     'kanban_attach', 'kanban_create', 'kanban_link'))
                and not any('outcome_reconcile.py' in str(h.get('command', '')) for h in hk.get('on_kanban_dispatch_tick') or []),
                'BOARD_PROTOCOL: the managed config lacks the outcome-board/v2 hooks (review/block terminators, '
                'kanban record/graph tools) or registers a reconciler')
    if protocol == 'outcome-board/v1':
        # the producer registered the outcome hooks from the same selection
        hk = c.get('hooks') or {}
        require(any('outcome_reconcile.py' in str(h.get('command', '')) for h in hk.get('on_kanban_dispatch_tick') or [])
                and all(t in str((hk.get('pre_tool_call') or [{}])[0].get('matcher', '')).split('|')
                        for t in ('kanban_block', 'kanban_request_review', 'request_review')),
                'BOARD_PROTOCOL: the managed config lacks the outcome-board hooks (reconciler tick, review/block terminators)')
print('PASS: board protocol %s (requested %s)' % (protocol, declared.get('board_protocol', 'nothing')))
print('PASS: fresh workspace, golden, ownership, credentials, decisions, model, source protection and budget')
'''.replace('EXPECTED_HOURS',repr(expected_hours)).replace('EXPECTED',repr(json.dumps(expected))).replace('MODEL',repr(os.environ['EXPECTED_MODEL'])).replace('WINDOW',str(windows[0])).replace('WORKER_IDENTITY',repr('system:serviceaccount:' + ns + ':' + workspace + '-worker')).replace('WORKSPACE_NAME',repr(workspace)).replace('MAASHOSTVAL',repr(maas_host)).replace('MAASIPVAL',repr(maas_ip)).replace('QLIMITVAL',str(quota_limit)).replace('QWINVAL',repr(quota_window)).replace('QOTHERSVAL',str(quota_others))
subprocess.run(['oc','--request-timeout=60s','exec','-i','-n',ns,pod,'-c',os.environ['CONTAINER'],'--','python3','-'],input=remote,text=True,check=True,timeout=75)
print('PASS: launch preflight for %s; no reset or dispatch performed' % workspace)
PY
