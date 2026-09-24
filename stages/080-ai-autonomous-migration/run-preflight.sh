#!/usr/bin/env bash
# Read-only launch check for ANY migration run created by the app-migration
# factory after 2026-09-24 (run-budget.json schema v2). Does not reset data,
# mint cards, or install a harness. v10-preflight.sh and v11-preflight.sh stay
# as the records of those launches; their runs carry self-contained budgets.
# Required: WORKSPACE (the run: the full project name, never a suffix), POD,
# GOLDEN_CHECKOUT (verified published checkout), GOLDEN_SHA, PLATFORM_SHA (the
# merged platform revision), ISOLATION_RECEIPT (local JSON).
# The expected model and wall budget are read from the golden's
# run-defaults.json, so a pin change is made once, in the golden.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/../../scripts/lib.sh"
load_env
check_oc_logged_in
export POD="${POD:?set POD}" GOLDEN_CHECKOUT="${GOLDEN_CHECKOUT:?set GOLDEN_CHECKOUT}"
export GOLDEN_SHA="${GOLDEN_SHA:?set the full published golden commit}"
export PLATFORM_SHA="${PLATFORM_SHA:?set the qualified platform commit}"
export ISOLATION_RECEIPT="${ISOLATION_RECEIPT:?set the retained live demonstration receipt}"
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

def check_isolation(proof, workspace):
    required = {'secret_binding','wrong_targets','assignment_removal','receipt_fields','delayed_resources',
                'data_independence','credential_independence','workspace_independence','repository_non_authority',
                'duplicate_delivery','overlapping_retirement','retirement','workspace_identity'}
    need(all(proof.get('checks',{}).get(k) == 'PASS' for k in required), 'operational isolation demonstration incomplete')
    identity = proof.get('checks',{}).get('workspace_identity')
    need(identity == 'PASS', 'workspace identity missing, unmeasured, or failed; v10-only FAIL deferral does not apply')

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
os.environ['EXPECTED_MODEL'] = os.environ.get('EXPECTED_MODEL') or defaults['configuration']['model']['id']
expected_hours = defaults['budget']['max_wall_hours']
proof = json.loads(Path(os.environ['ISOLATION_RECEIPT']).read_text())
need(proof.get('schema') == 'rhoai3.run-isolation/v1' and proof.get('platform_commit') == platform
     and proof.get('golden_commit') == sha, 'isolation receipt does not bind the selected revisions')
check_isolation(proof, workspace)
files = proof.get('evidence',[])
need(bool(files), 'isolation receipt has no retained evidence')
for row in files:
    p = Path(os.environ['ISOLATION_RECEIPT']).parent / row['path']
    need(p.is_file() and digest(p) == row['sha256'], 'isolation evidence missing or changed')
app = json.loads(oc('get','application','050-advanced-app-platform','-n','openshift-gitops','-o','json'))
need(app.get('status',{}).get('sync',{}).get('revision') == platform
     and app['status']['sync'].get('status') == 'Synced'
     and app['status'].get('health',{}).get('status') == 'Healthy', 'Stage 050 is not healthy at the qualified revision')
tekton = json.loads(oc('get','tektonconfig','config','-o','json'))
need(any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in tekton.get('status',{}).get('conditions',[])), 'TektonConfig is not Ready')
listener = json.loads(oc('get','deployment','el-app-platform-listener','-n','app-platform-build','-o','json'))
need(listener.get('status',{}).get('readyReplicas',0) >= 1
     and listener['status'].get('observedGeneration',0) >= listener['metadata']['generation'], 'webhook dispatcher is not ready')
p = json.loads(oc('get','pod',pod,'-n',ns,'-o','json'))
need(source_mount_ok(p, os.environ['CONTAINER']), 'source mount is writable or has a writable runtime alias')
need(p['metadata'].get('labels',{}).get('controller.devfile.io/devworkspace_name') == workspace, 'actual workspace name mismatch')
receipt = json.loads(oc('get','configmap','migration-run-'+workspace,'-n',ns,'-o','json'))['data']
need(receipt.get('phase') == 'provisioned' and receipt.get('workspace') == workspace
     and receipt.get('namespace') == ns, 'provisioning receipt is not ready for this workspace')
default_binding = json.loads(oc('get','rolebinding','devworkspace-default-rolebinding','-n',ns,'-o','json'))
check_worker_identity(p, receipt, default_binding, ns, workspace)
need(worker_kubeconfig_mount_ok(p, os.environ['CONTAINER']),
     'worker kubeconfig directory lacks its ephemeral mount; late Dashboard token injection is possible')
for key in ('databaseImage','provisionerImage'):
    need(bool(re.fullmatch(r'.+@sha256:[0-9a-f]{64}',receipt.get(key,''))), 'unpinned '+key)
    need(receipt[key] == proof.get('images',{}).get(key), 'image differs from isolation qualification: '+key)
deployment = json.loads(oc('get','deployment',receipt['host'],'-n',ns,'-o','json'))
need(deployment.get('status',{}).get('availableReplicas',0) == 1
     and deployment['spec']['template']['spec']['containers'][0]['image'] == receipt['databaseImage'],
     'assigned database is not available on the qualified image')
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
model = json.loads(oc('get','llminferenceservice',os.environ['EXPECTED_MODEL'],'-n','models-as-a-service','-o','json'))
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
require(d.get('loop', {}).get('unit_formation') == 'v1' and d.get('loop', {}).get('runtime_feedback') == 'v1', 'loop flags')
r = d['decided_repairs']
require(hashlib.sha256((root / r['manifest']).read_bytes()).hexdigest() == r['manifest_sha256'], 'repair manifest mismatch')
config = next((p for p in (Path('/etc/hermes/config.yaml'), Path('/projects/.platform/hermes/config.yaml')) if p.is_file()), None)
require(config, 'managed Hermes config missing')
c = load_yaml(config)
require(c.get('model', {}).get('default') == MODEL, 'worker model mismatch')
import socket
from urllib.parse import urlsplit
require(urlsplit(os.environ.get('MAAS_API_BASE_URL', '')).hostname == MAASHOSTVAL, 'worker MaaS endpoint is not the platform gateway host')
addrs = {a[4][0] for a in socket.getaddrinfo(MAASHOSTVAL, 443, proto=socket.IPPROTO_TCP)}
require(addrs == {MAASIPVAL}, 'MaaS host resolves to %s, not the in-cluster gateway %s: the workspace is on the public ELB path' % (sorted(addrs), MAASIPVAL))

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
windows = list(leaves(c))
require(windows and all((0 < v < WINDOW for v in windows)), 'context limit must be below served window')
require(c.get('terminal', {}).get('timeout', 0) >= 600, 'terminal timeout')
require(c.get('compression', {}).get('threshold', 0) >= 0.8, 'compression threshold')
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
print('PASS: fresh workspace, golden, ownership, credentials, decisions, model, source protection and budget')
'''.replace('EXPECTED_HOURS',repr(expected_hours)).replace('EXPECTED',repr(json.dumps(expected))).replace('MODEL',repr(os.environ['EXPECTED_MODEL'])).replace('WINDOW',str(windows[0])).replace('WORKER_IDENTITY',repr('system:serviceaccount:' + ns + ':' + workspace + '-worker')).replace('WORKSPACE_NAME',repr(workspace)).replace('MAASHOSTVAL',repr(maas_host)).replace('MAASIPVAL',repr(maas_ip))
subprocess.run(['oc','--request-timeout=60s','exec','-i','-n',ns,pod,'-c',os.environ['CONTAINER'],'--','python3','-'],input=remote,text=True,check=True,timeout=75)
print('PASS: launch preflight for %s; no reset or dispatch performed' % workspace)
PY
