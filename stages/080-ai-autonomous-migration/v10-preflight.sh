#!/usr/bin/env bash
# Read-only launch check. Does not reset data, mint cards, or install a harness.
# Required: POD, GOLDEN_CHECKOUT (verified published checkout), GOLDEN_SHA,
# PLATFORM_SHA (the merged platform revision), ISOLATION_RECEIPT (local JSON).
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
export WORKSPACE="${WORKSPACE:-spring-petclinic-rest-legacy-v10}"
export NS="${NS:-wksp-ai-developer}" CONTAINER="${CONTAINER:-development-tooling}"
export EXPECTED_MODEL="${EXPECTED_MODEL:-qwen3-8-27b-int4}"
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
            if m.get('subPathExpr') or not parent or source_path == parent or source_path.startswith(parent + '/'):
                return False
    return True

ns, pod, workspace = (os.environ[k] for k in ('NS','POD','WORKSPACE'))
golden = Path(os.environ['GOLDEN_CHECKOUT'])
sha = os.environ['GOLDEN_SHA']; platform = os.environ['PLATFORM_SHA']
need(bool(re.fullmatch('[0-9a-f]{40}', sha)) and bool(re.fullmatch('[0-9a-f]{40}',platform)), 'full golden/platform commits required')
need(cmd('git','-C',str(golden),'rev-parse','HEAD').strip() == sha, 'golden checkout is not the pin')
need(not cmd('git','-C',str(golden),'status','--porcelain').strip(), 'golden checkout is dirty')
proof = json.loads(Path(os.environ['ISOLATION_RECEIPT']).read_text())
required = {'secret_binding','wrong_targets','assignment_removal','receipt_fields','delayed_resources',
            'data_independence','credential_independence','workspace_independence','repository_non_authority',
            'duplicate_delivery','overlapping_retirement','retirement','workspace_identity'}
need(proof.get('schema') == 'rhoai3.run-isolation/v1' and proof.get('platform_commit') == platform
     and proof.get('golden_commit') == sha, 'isolation receipt does not bind the selected revisions')
need(all(proof.get('checks',{}).get(k) == 'PASS' for k in required), 'isolation demonstration incomplete')
files = proof.get('evidence',[])
need(bool(files), 'isolation receipt has no retained evidence')
for row in files:
    p = Path(os.environ['ISOLATION_RECEIPT']).parent / row['path']
    need(p.is_file() and digest(p) == row['sha256'], 'isolation evidence missing or changed')
app = json.loads(oc('get','application','050-advanced-app-platform','-n','openshift-gitops','-o','json'))
need(app.get('status',{}).get('sync',{}).get('revision') == platform
     and app['status']['sync'].get('status') == 'Synced'
     and app['status'].get('health',{}).get('status') == 'Healthy', 'Stage 050 is not healthy at the qualified revision')
p = json.loads(oc('get','pod',pod,'-n',ns,'-o','json'))
need(source_mount_ok(p, os.environ['CONTAINER']), 'source mount is writable or has a writable runtime alias')
need(p['metadata'].get('labels',{}).get('controller.devfile.io/devworkspace_name') == workspace, 'actual workspace name mismatch')
receipt = json.loads(oc('get','configmap','migration-run-'+workspace,'-n',ns,'-o','json'))['data']
need(receipt.get('phase') == 'provisioned' and receipt.get('workspace') == workspace
     and receipt.get('namespace') == ns, 'provisioning receipt is not ready for this workspace')
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
# The remote script prints assertions only, never environment/config values.
remote = '''def require(condition, message):
    if not condition:
        raise AssertionError(message)
import hashlib, json, os, sys, subprocess
from pathlib import Path
root = Path('/projects/modernized')
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
budget = json.loads((root / 'run-budget.json').read_text())
import datetime
first = int(subprocess.check_output(['git', '-C', str(root), 'log', '--reverse', '--format=%ct'], text=True).splitlines()[0])
declared = datetime.datetime.fromisoformat(budget['declared_at'].replace('Z', '+00:00')).timestamp()
require(budget.get('max_wall_hours') == 24 and declared < first, 'budget must be declared before destination creation')
print('PASS: fresh workspace, golden, ownership, credentials, decisions, model, source protection and budget')
'''.replace('EXPECTED',repr(json.dumps(expected))).replace('MODEL',repr(os.environ['EXPECTED_MODEL'])).replace('WINDOW',str(windows[0]))
subprocess.run(['oc','--request-timeout=60s','exec','-i','-n',ns,pod,'-c',os.environ['CONTAINER'],'--','python3','-'],input=remote,text=True,check=True,timeout=75)
print('PASS: v10 launch preflight; no reset or dispatch performed')
PY
