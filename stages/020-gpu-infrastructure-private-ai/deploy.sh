#!/usr/bin/env bash
# Publish reviewed Stage 020 infrastructure through its own Application only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select a reviewed published revision.' >&2; exit 1; }
command -v python3 >/dev/null
command -v ruby >/dev/null
command -v git >/dev/null
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR: revision must resolve to one published branch.' >&2; exit 1; }
[[ "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs from reviewed checkout.' >&2; exit 1; }
paths=(gitops/stages/020-gpu-infrastructure-private-ai gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai.yaml stages/020-gpu-infrastructure-private-ai scripts/shared scripts/platform/require-node-sizing.sh)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish all reviewed Stage 020 source before deploying.' >&2; exit 1; }
overlay="$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment"
[[ -f "$overlay/machineset-gpu.yaml" && -f "$overlay/application-patch.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSet and Application patch first.' >&2; exit 1; }
# All prerequisites are read-only and run before the first Application write.
foundation=$(oc --request-timeout=10s get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops -o json)
python3 - "$foundation" <<'PY'
import json,sys
x=json.loads(sys.argv[1]); s=x.get('status',{}); spec=x['spec']
assert s.get('sync',{}).get('status')=='Synced' and s.get('health',{}).get('status')=='Healthy','Stage 010 must be Synced/Healthy'
assert 'RespectIgnoreDifferences=true' in spec['syncPolicy']['syncOptions'],'Stage 010 must respect delegated fields'
assert any(i.get('kind')=='DataScienceCluster' and i.get('name')=='default-dsc' and '/spec/components/kueue' in i.get('jsonPointers',[]) for i in spec.get('ignoreDifferences',[])),'Stage 010 must delegate Kueue'
PY
oc --request-timeout=10s get csv -A -o json | python3 -c 'import json,sys; x=json.load(sys.stdin); assert any(i["metadata"]["name"].startswith("cert-manager-operator.v1.20.") and i.get("status",{}).get("phase")=="Succeeded" for i in x["items"]), "Provider cert-manager prerequisite unavailable"'
python3 - <<'PY_OWNERSHIP'
import json,subprocess,os
app='020-gpu-infrastructure-private-ai'
for kind,name,ns in [('application',app,'openshift-gitops'),('namespace','openshift-nfd',''),('namespace','nvidia-gpu-operator',''),('namespace','openshift-kueue-operator','')]:
 cmd=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:cmd+=['-n',ns]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,'Ownership API read failed'
 if not p.stdout.strip():continue
 x=json.loads(p.stdout);a=x['metadata'].get('annotations',{});tracking=a.get('argocd.argoproj.io/tracking-id','')
 assert not tracking or tracking.startswith(app+':'),'Foreign resource tracking'
 if kind=='application':
  assert not x['metadata'].get('ownerReferences') and 'sources' not in x['spec'],'Unexpected Application ownership'
  assert x['spec']['source']['repoURL']==os.environ['GIT_REPO_URL'] and x['spec']['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected Application repository or destination'
  assert x['spec']['project']=='rhoai-demo' and x['spec']['source']['path']=='gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment','Unexpected existing Stage 020 Application'
p=subprocess.run(['oc','--request-timeout=10s','get','configmap','nvidia-dcgm-exporter-dashboard','-n','openshift-config-managed','--ignore-not-found','-o','json'],capture_output=True,text=True,timeout=15)
assert p.returncode==0,'Dashboard ownership read failed'
if p.stdout.strip():
 x=json.loads(p.stdout);assert not x['metadata'].get('ownerReferences') and x['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith(app+':'),'Existing NVIDIA dashboard requires a reviewed adoption'
PY_OWNERSHIP
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$overlay/machineset-gpu.yaml" | python3 -c '
import json,subprocess,sys,copy
expected=json.load(sys.stdin);name=expected["metadata"]["name"]
def read(kind,name,ns=""):
 cmd=["oc","--request-timeout=10s","get",kind]
 if name:cmd.append(name)
 cmd += ["-o","json"]
 if ns:cmd += ["-n",ns]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=15);assert p.returncode==0,"Provider prerequisite API read failed";return json.loads(p.stdout)
infra=read("infrastructure","cluster");cluster=infra["status"]["infrastructureName"]
assert infra["status"]["platformStatus"]["type"]=="AWS","AWS environment required"
for labels in [expected["metadata"]["labels"],expected["spec"]["selector"]["matchLabels"],expected["spec"]["template"]["metadata"]["labels"]]:assert labels["machine.openshift.io/cluster-api-cluster"]==cluster,"Generated intent belongs to another cluster"
source_name=expected["metadata"]["annotations"]["demo.rhoai.io/source-machineset"]
source=read("machineset",source_name,"openshift-machine-api");assert source["spec"]["replicas"]>0 and source["status"].get("readyReplicas",0)>0,"CPU source pool is no longer active"
provider=copy.deepcopy(source["spec"]["template"]["spec"]["providerSpec"]["value"])
assert provider["placement"]["region"]==infra["status"]["platformStatus"]["aws"]["region"],"Provider region differs from native Infrastructure"
assert provider.get("capacityReservationId","")=="","CPU capacity reservation is incompatible"
provider["instanceType"]="g6e.2xlarge";provider["blockDevices"][0]["ebs"].update(volumeSize=200,volumeType="gp3",encrypted=True)
assert expected["spec"]["template"]["spec"]["providerSpec"]["value"]==provider,"Generated AMI/provider references differ from active source"
nodes=read("nodes","")["items"];assert nodes and all(n["status"]["nodeInfo"]["architecture"]=="amd64" for n in nodes),"Reviewed native source requires amd64"

p=subprocess.run(["oc","--request-timeout=10s","get","machineset",name,"-n","openshift-machine-api","--ignore-not-found","-o","json"],capture_output=True,text=True,timeout=15)
assert p.returncode==0,"MachineSet ownership API read failed"
if p.stdout.strip():
 x=json.loads(p.stdout);assert not x["metadata"].get("ownerReferences"),"Foreign MachineSet owner"
 assert x["metadata"].get("annotations",{}).get("argocd.argoproj.io/tracking-id","").startswith("020-gpu-infrastructure-private-ai:"),"Existing MachineSet has not been adopted by reviewed Stage 020"
 for key in ["selector","template"]:assert x["spec"][key]==expected["spec"][key],"Existing GPU provider/template differs from reviewed source"
'
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
oc kustomize "$overlay" > "$work/render.yaml"
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(File.read(ARGV[0])))' "$work/render.yaml" | python3 -c '
import json,subprocess,sys
for expected in json.load(sys.stdin):
 if expected["kind"]=="MachineSet":continue
 m=expected["metadata"];cmd=["oc","--request-timeout=10s","get",expected["kind"],m["name"],"--ignore-not-found","-o","json"]
 if m.get("namespace"):cmd += ["-n",m["namespace"]]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
 if p.returncode and expected["kind"] in {"NodeFeatureDiscovery","ClusterPolicy","ResourceFlavor","ClusterQueue","LocalQueue","WorkloadPriorityClass","HardwareProfile"} and ("no matches for kind" in p.stderr or ("the server doesn"+chr(39)+"t have a resource type") in p.stderr):continue
 assert p.returncode==0,"Customer resource ownership API read failed"
 if not p.stdout.strip():continue
 x=json.loads(p.stdout);assert not x["metadata"].get("ownerReferences"),"Foreign customer resource owner"
 tracking=x["metadata"].get("annotations",{}).get("argocd.argoproj.io/tracking-id","")
 assert tracking.startswith("020-gpu-infrastructure-private-ai:") or (expected["kind"]=="Namespace" and not tracking),"Unreviewed existing customer resource"
'
# Compose the exact-name MachineSet replica exception into the Application.
ruby -ryaml -rjson -e 'a=YAML.load_file(ARGV[0]);p=YAML.load_file(ARGV[1]); a["spec"]["ignoreDifferences"]=p["spec"]["ignoreDifferences"];a["spec"]["source"]["repoURL"]=ENV.fetch("GIT_REPO_URL");a["spec"]["source"]["targetRevision"]=ARGV[2];puts YAML.dump(a)' "$ROOT_DIR/gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai.yaml" "$overlay/application-patch.yaml" "$remote_sha" > "$work/application.yaml"
oc --request-timeout=10s apply -f "$work/application.yaml"
echo 'Stage 020 Application submitted. Manual InstallPlans require exact reviewed CSV approval; run validate.sh after native reconciliation.'

# Approve only the initial exact CSV in an InstallPlan owned by its named Subscription.
python3 - <<'PY_APPROVAL'
import json,subprocess,time
selected=[('openshift-nfd','nfd','nfd.4.22.0-202609212027'),('nvidia-gpu-operator','gpu-operator-certified','gpu-operator-certified.v26.7.1'),('openshift-kueue-operator','kueue-operator','kueue-operator.v1.4.2')]
def read(kind,name,ns):
 p=subprocess.run(['oc','--request-timeout=10s','get',kind,name,'-n',ns,'-o','json'],capture_output=True,text=True,timeout=15)
 return json.loads(p.stdout) if p.returncode==0 else None
for ns,name,csv in selected:
 for attempt in range(100):
  sub=read('subscription',name,ns)
  if sub and sub.get('status',{}).get('installedCSV')==csv:
   installed=read('csv',csv,ns)
   if installed and installed.get('status',{}).get('phase')=='Succeeded':break
  if sub and sub.get('status',{}).get('installPlanRef',{}).get('name'):
   assert sub['spec']['installPlanApproval']=='Manual','Unexpected approval policy'
   ip=read('installplan',sub['status']['installPlanRef']['name'],ns)
   if ip and not ip['spec'].get('approved'):
    assert any(o.get('uid')==sub['metadata']['uid'] and o.get('kind')=='Subscription' for o in ip['metadata'].get('ownerReferences',[])),'InstallPlan owner mismatch'
    assert ip['spec'].get('clusterServiceVersionNames')==[csv],'InstallPlan includes unreviewed CSVs'
    p=subprocess.run(['oc','--request-timeout=10s','patch','installplan',ip['metadata']['name'],'-n',ns,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/resourceVersion','value':ip['metadata']['resourceVersion']},{'op':'replace','path':'/spec/approved','value':True}])],capture_output=True,timeout=15)
    assert p.returncode==0,'Reviewed InstallPlan approval failed'
  time.sleep(3)
 else:raise SystemExit('Timed out waiting for selected native operator: '+name)
 print('Selected native operator Succeeded: '+name)
PY_APPROVAL
