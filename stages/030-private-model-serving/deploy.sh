#!/usr/bin/env bash
# Publish native KServe/discovery only; never repoint Stage 010 or seed models.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select the reviewed published branch.' >&2; exit 1; }
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ && "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published branch differs from the reviewed checkout.' >&2; exit 1; }
paths=(gitops/stages/030-private-model-serving gitops/argocd/app-of-apps/030-private-model-serving stages/030-private-model-serving scripts/shared scripts/platform/require-node-sizing.sh scripts/platform/validate-serving-update.py)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish reviewed Stage 030 source first.' >&2; exit 1; }
# Read-only prerequisites precede even sizing and the first Application write.
export GIT_REPO_URL
python3 - "$ROOT_DIR" <<'PY_PREREQUISITE'
import json,os,subprocess,sys
from pathlib import Path
appname='030-private-model-serving'
registry={('Namespace','rhoai-model-registries',''),('ModelRegistry','demo-registry','rhoai-model-registries'),('RoleBinding','demo-registry-rhods-admins','rhoai-model-registries'),('RoleBinding','demo-registry-rhoai-developers','rhoai-model-registries')}
def get(kind,name,ns=None,optional=False):
 args=['oc','--request-timeout=10s','get',kind,name,'-o','json']
 if ns:args+=['-n',ns]
 if optional:args+=['--ignore-not-found']
 p=subprocess.run(args,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,'Prerequisite API read failed'
 return json.loads(p.stdout) if p.stdout.strip() else None
sys.path.insert(0,sys.argv[1]+'/scripts/shared');import stage_apps
problems=stage_apps.stage_problems('010')
assert not problems,'Stage 010 must be reconciled: '+'; '.join(problems)
registry_crd=get('customresourcedefinition','modelregistries.modelregistry.opendatahub.io',optional=True)
assert {'/spec/components/kserve','/spec/components/modelregistry'}<=stage_apps.delegated('010','DataScienceCluster','default-dsc',group='datasciencecluster.opendatahub.io'),'Foundation has not delegated serving/discovery'
assert {'/spec/dashboardConfig/'+field for field in ['agentsCatalog','disableModelCatalog','disableModelRegistry','toolCalling','mcpCatalog','mcpRegistry']}<=stage_apps.delegated('010','OdhDashboardConfig','odh-dashboard-config','redhat-ods-applications','opendatahub.io'),'Foundation discovery visibility is not delegated'
for kind,name,ns in registry:
 lookup={'Namespace':'namespace','ModelRegistry':'modelregistries.modelregistry.opendatahub.io','RoleBinding':'rolebinding'}[kind]
 obj=None if kind=='ModelRegistry' and not registry_crd else get(lookup,name,ns or None,True)
 if not obj:
  continue
 tracking=obj['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','')
 assert tracking.startswith(appname+':'),'Registry is not owned by Stage 030'
 assert not obj['metadata'].get('deletionTimestamp'),'Retained registry resource is terminating'
# Existing deployments must retain their native database contract on every rerun.
mr=get('modelregistries.modelregistry.opendatahub.io','demo-registry','rhoai-model-registries',True) if registry_crd else None
claim=get('pvc','demo-registry-postgres-storage','rhoai-model-registries',True)
credential=subprocess.run(['oc','--request-timeout=10s','get','secret','demo-registry-postgres-credentials','-n','rhoai-model-registries','--ignore-not-found','-o','jsonpath={.metadata.uid} {.metadata.ownerReferences}'],capture_output=True,text=True,timeout=15)
assert credential.returncode==0,'Registry credential metadata read failed'
if mr:
 expected=subprocess.run(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_file(ARGV[0])["spec"])',str(Path(sys.argv[1])/'gitops/stages/030-private-model-serving/private-model-serving/model-discovery/registry/modelregistry-demo.yaml')],capture_output=True,text=True,check=True)
 assert mr['spec']==json.loads(expected.stdout),'Existing registry native spec differs from reviewed source'
 assert claim and not claim['metadata'].get('deletionTimestamp') and claim['status']['phase']=='Bound' and any(o.get('uid')==mr['metadata']['uid'] and o.get('controller') for o in claim['metadata'].get('ownerReferences',[])),'Existing registry database missing or foreign'
 uid,owners=credential.stdout.strip().split(' ',1)
 assert uid and any(o.get('uid')==mr['metadata']['uid'] and o.get('controller') for o in json.loads(owners)),'Existing registry credential missing or foreign'
else:
 assert not claim and not credential.stdout.strip(),'Partial retained registry database forbids clean recreation'
existing=get('application',appname,'openshift-gitops',True)
if existing:
 e=existing['spec'];assert not existing['metadata'].get('ownerReferences') and not e.get('sources'),'Foreign Application ownership'
 assert e['project']=='rhoai-demo' and e['source']['repoURL']==os.environ['GIT_REPO_URL'] and e['source']['path']=='gitops/stages/030-private-model-serving/private-model-serving','Unexpected Stage 030 source'
 assert e['destination']=={'namespace':'openshift-gitops','server':'https://kubernetes.default.svc'},'Unexpected Stage 030 destination'
for ns,name in [('openshift-monitoring','cluster-monitoring-config'),('openshift-user-workload-monitoring','user-workload-monitoring-config')]:
 cm=get('configmap',name,ns,True)
 if cm:assert cm['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith(appname+':'),'Provider monitoring configuration requires a reviewed merge before adoption'
sc=get('storageclass','gp3-csi');assert sc['provisioner']=='ebs.csi.aws.com','Reviewed native monitoring storage class unavailable'
for namespace in ['redhat-ods-applications','openshift-gitops']:get('namespace',namespace)
print('PASS Read-only foundation ownership/delegation and native storage prerequisites')
PY_PREREQUISITE
python3 "$SCRIPT_DIR/preflight-agent-catalog.py"
if [[ -n "$(oc --request-timeout=10s get application 030-private-model-serving -n openshift-gitops --ignore-not-found -o jsonpath='{.metadata.uid}')" ]]; then
  # An existing discovery update must not start deliberately parked GPU capacity.
  python3 "$ROOT_DIR/scripts/platform/validate-serving-update.py" 030
else
  "$ROOT_DIR/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
export GIT_REPO_URL
ruby -ryaml -e 'a=YAML.load_file(ARGV[0]);a["spec"]["source"]["repoURL"]=ENV.fetch("GIT_REPO_URL");a["spec"]["source"]["targetRevision"]=ARGV[1];puts YAML.dump(a)' "$ROOT_DIR/gitops/argocd/app-of-apps/030-private-model-serving/private-model-serving.yaml" "$remote_sha" > "$work/application.yaml"
# Recheck configuration ownership immediately before submitting the Application.
for pair in 'openshift-monitoring cluster-monitoring-config' 'openshift-user-workload-monitoring user-workload-monitoring-config'; do
 read -r namespace name <<< "$pair"
 oc --request-timeout=10s get configmap "$name" -n "$namespace" --ignore-not-found -o json | python3 -c 'import json,sys;s=sys.stdin.read();assert not s.strip() or json.loads(s)["metadata"].get("annotations",{}).get("argocd.argoproj.io/tracking-id","").startswith("030-private-model-serving:"),"Provider configuration appeared: stop for reviewed merge"'
done
# The first modifying action is this stage's own Application.
python3 "$SCRIPT_DIR/preflight-agent-catalog.py"
oc --request-timeout=10s apply -f "$work/application.yaml"
echo 'Stage 030 native serving/discovery Application submitted at the reviewed immutable revision; no models or registry records are created.'
for _ in $(seq 1 120); do
 if oc --request-timeout=10s get application 030-private-model-serving -n openshift-gitops -o json | python3 -c 'import json,sys;x=json.load(sys.stdin);s=x.get("status",{});sys.exit(not(s.get("sync",{}).get("status")=="Synced" and s.get("sync",{}).get("revision")==x["spec"]["source"]["targetRevision"] and s.get("health",{}).get("status")=="Healthy" and s.get("operationState",{}).get("phase")=="Succeeded" and s.get("operationState",{}).get("syncResult",{}).get("revision")==x["spec"]["source"]["targetRevision"] and s.get("operationState",{}).get("syncResult",{}).get("source",{}).get("path")==x["spec"]["source"]["path"]))'; then
  for _ in $(seq 1 120); do
   if "$SCRIPT_DIR/validate.sh"; then exit 0; fi
   sleep 5
  done
  echo "ERROR: native Stage 030 service readiness timed out after Application reconciliation." >&2
  exit 1
 fi
 sleep 5
done
echo 'ERROR: native Stage 030 reconciliation did not complete within the bounded wait.' >&2
exit 1
