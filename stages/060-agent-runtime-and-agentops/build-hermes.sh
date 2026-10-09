#!/usr/bin/env bash
# Build the selected fork plus its hash-locked native HTTP dependencies; tag is an output handle, never a runtime pin.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASK_ROOT="$REPO_ROOT"
source "$TASK_ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$TASK_ROOT}"
load_env
check_oc_logged_in
REPO_ROOT="$TASK_ROOT"
REVISION="${RHOAI_STAGE060_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || exit 1
git -C "$REPO_ROOT" ls-remote origin | awk -v revision="$REVISION" '$1 == revision { found=1 } END { exit !found }' || exit 1
git -C "$REPO_ROOT" diff --exit-code "$REVISION" -- "$SCRIPT_DIR/build-hermes.sh" "$SCRIPT_DIR/images/hermes-api" gitops/stages/060-agent-runtime-and-agentops/runtime/hermes-images >/dev/null
python3 - "$REVISION" <<'PY'
import json,subprocess,sys
app='openshell-runtime'
def read(kind,name):
 r=subprocess.run(['oc','--request-timeout=15s','get',kind,name,'-n','ai-agents' if kind!='application' else 'openshift-gitops','-o','json'],capture_output=True,text=True);assert r.returncode==0;return json.loads(r.stdout)
a=read('application',app);s=a['spec'];src={'repoURL':'https://github.com/adnan-drina/rhoai3-coding-demo.git','targetRevision':sys.argv[1],'path':'gitops/stages/060-agent-runtime-and-agentops/runtime'}
assert s['source']==src and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshell'} and not a['metadata'].get('ownerReferences') and not a.get('operation') and not a['metadata'].get('deletionTimestamp')
assert a['status']['sync']['status']=='Synced' and a['status']['sync']['revision']==sys.argv[1]
o=a['status']['operationState'];assert o['phase']=='Succeeded' and o['syncResult']['revision']==sys.argv[1] and o['syncResult']['source']==src
for kind,name,group in [('buildconfig','hermes-runtime-api','build.openshift.io'),('imagestream','hermes-runtime-api','image.openshift.io')]:
 x=read(kind,name);m=x['metadata'];assert not m.get('deletionTimestamp') and not m.get('ownerReferences') and m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')==app+':'+group+'/'+x['kind']+':ai-agents/'+name
PY
CONTEXT="$(mktemp -d "${TMPDIR:-/tmp}/hermes-runtime-api-build.XXXXXX")"
trap 'rm -rf "$CONTEXT"' EXIT
python3 - "$SCRIPT_DIR" "$CONTEXT" <<'PY'
import hashlib,json,pathlib,shutil,sys,urllib.request
src=pathlib.Path(sys.argv[1])/'images/hermes-api';dst=pathlib.Path(sys.argv[2]);meta=json.loads((src/'dependency-source.json').read_text())
for name in ('Dockerfile','requirements.lock','dependency-source.json','verify-packaging.py'):
 shutil.copyfile(src/name,dst/name)
(dst/'wheels').mkdir()
for wheel in meta['wheels']:
 assert wheel['url'].startswith('https://files.pythonhosted.org/') and pathlib.Path(wheel['filename']).name==wheel['filename']
 target=dst/'wheels'/wheel['filename']
 with urllib.request.urlopen(wheel['url'],timeout=30) as response,target.open('wb') as output:
  while block:=response.read(1024*1024):output.write(block)
 assert hashlib.sha256(target.read_bytes()).hexdigest()==wheel['sha256'],'Dependency wheel checksum mismatch'

PY
BUILD="$(oc --request-timeout=120s start-build hermes-runtime-api -n ai-agents --from-dir="$CONTEXT" -o name)"
oc --request-timeout=15s wait "$BUILD" -n ai-agents --for=jsonpath='{.status.phase}'=Complete --timeout=610s
python3 - "$BUILD" <<'PYRESULT'
import json,re,subprocess,sys
def get(kind,name):
 r=subprocess.run(['oc','--request-timeout=15s','get',kind,name,'-n','ai-agents','-o','json'],capture_output=True,text=True);assert r.returncode==0;return json.loads(r.stdout)
b=get('build',sys.argv[1].split('/')[-1]);c=get('buildconfig','hermes-runtime-api');t=get('imagestreamtag','hermes-runtime-api:0.20.5-api');i=get('imagestream','hermes-runtime-api')
assert b['status']['phase']=='Complete' and not b['metadata'].get('deletionTimestamp')
assert any(o.get('uid')==c['metadata']['uid'] and o.get('kind')=='BuildConfig' for o in b['metadata'].get('ownerReferences',[])),'Build ownership mismatch'
assert b['spec']['output']['to']==c['spec']['output']['to']=={'kind':'ImageStreamTag','name':'hermes-runtime-api:0.20.5-api'}
d=b['status']['output']['to']['imageDigest'];assert re.fullmatch('sha256:[0-9a-f]{64}',d),'Missing immutable Build output digest'
assert t['image']['metadata']['name']==d and t['image']['dockerImageReference'].endswith('@'+d),'Tag changed after this Build'
print(i['status']['dockerImageRepository']+'@'+d)
PYRESULT
