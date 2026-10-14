#!/usr/bin/env bash
# Publish reviewed Stage 020 infrastructure through its own Application only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai"
require_env GIT_REPO_URL "reviewed Stage 020 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
revision=$(python3 "$STAGE_APPS" select 020 --ref "$ref" --repo-url "$GIT_REPO_URL" \
  --extra scripts/platform/require-node-sizing.sh --extra scripts/platform/check-operator-policy.py)
stage_gitops="$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai"
app_manifest="$ROOT_DIR/gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai/gpu-machinesets.yaml"
[[ -f "$stage_gitops/gpu-machinesets/machineset-gpu.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSets first (generate-gpu-machineset.sh).' >&2; exit 1; }
export REPO_ROOT
# All prerequisites are read-only and run before the first Application write.
python3 - <<'PY'
import os,sys
sys.path.insert(0,os.environ['REPO_ROOT']+'/scripts/shared');import stage_apps
problems=stage_apps.stage_problems('010')
assert not problems,'Stage 010 must be reconciled: '+'; '.join(problems)
assert '/spec/components/kueue' in stage_apps.delegated('010','DataScienceCluster','default-dsc',group='datasciencecluster.opendatahub.io'),'Stage 010 must delegate Kueue'
PY
oc --request-timeout=10s get csv -A -o json | python3 -c 'import json,sys; x=json.load(sys.stdin); assert any(i["metadata"]["name"].startswith("cert-manager-operator.v1.20.") and i.get("status",{}).get("phase")=="Succeeded" for i in x["items"]), "Provider cert-manager prerequisite unavailable"'
python3 - <<'PY_OWNERSHIP'
import json,subprocess,os,sys
sys.path.insert(0,os.environ['REPO_ROOT']+'/scripts/shared');import stage_apps
def read(kind,name,ns=''):
 cmd=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:cmd+=['-n',ns]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,'Ownership API read failed'
 return json.loads(p.stdout) if p.stdout.strip() else None
for desired in stage_apps.components('020'):
 x=read('application',desired['metadata']['name'],'openshift-gitops')
 if not x:continue
 assert not x['metadata'].get('ownerReferences') and 'sources' not in x['spec'],'Unexpected Application ownership'
 assert x['spec']['source']['repoURL']==os.environ['GIT_REPO_URL'] and x['spec']['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected Application repository or destination'
 assert x['spec']['project']=='rhoai-demo' and x['spec']['source']['path']==desired['spec']['source']['path'],'Unexpected existing Stage 020 Application'
for name in ['openshift-nfd','nvidia-gpu-operator','openshift-kueue-operator']:
 x=read('namespace',name)
 assert not x or not stage_apps.tracking_id(x) or stage_apps.tracked('020',x),'Foreign resource tracking'
x=read('configmap','nvidia-dcgm-exporter-dashboard','openshift-config-managed')
if x:assert not x['metadata'].get('ownerReferences') and stage_apps.tracked('020',x),'Existing NVIDIA dashboard requires a reviewed adoption'
PY_OWNERSHIP
# Every generated GPU MachineSet must still match the active CPU worker it was derived from.
oc kustomize "$stage_gitops/gpu-machinesets" | ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' | python3 -c '
import json,subprocess,sys,copy
pools=[d for d in json.load(sys.stdin) if d["kind"]=="MachineSet"];assert pools,"No generated GPU MachineSets"
def read(kind,name,ns=""):
 cmd=["oc","--request-timeout=10s","get",kind]
 if name:cmd.append(name)
 cmd += ["-o","json"]
 if ns:cmd += ["-n",ns]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=15);assert p.returncode==0,"Provider prerequisite API read failed";return json.loads(p.stdout)
infra=read("infrastructure","cluster");cluster=infra["status"]["infrastructureName"]
assert infra["status"]["platformStatus"]["type"]=="AWS","AWS environment required"
nodes=read("nodes","")["items"];assert nodes and all(n["status"]["nodeInfo"]["architecture"]=="amd64" for n in nodes),"Reviewed native source requires amd64"
for expected in pools:
 name=expected["metadata"]["name"]
 for labels in [expected["metadata"]["labels"],expected["spec"]["selector"]["matchLabels"],expected["spec"]["template"]["metadata"]["labels"]]:assert labels["machine.openshift.io/cluster-api-cluster"]==cluster,name+": generated intent belongs to another cluster"
 assert expected["spec"]["replicas"]==0,name+": declare replicas 0; resume-gpu-demo.sh scales the pool"
 source_name=expected["metadata"]["annotations"]["demo.rhoai.io/source-machineset"]
 source=read("machineset",source_name,"openshift-machine-api");assert source["spec"]["replicas"]>0 and source["status"].get("readyReplicas",0)>0,name+": CPU source pool "+source_name+" is no longer active"
 provider=copy.deepcopy(source["spec"]["template"]["spec"]["providerSpec"]["value"])
 assert provider["placement"]["region"]==infra["status"]["platformStatus"]["aws"]["region"],"Provider region differs from native Infrastructure"
 assert provider.get("capacityReservationId","")=="","CPU capacity reservation is incompatible"
 provider["instanceType"]=expected["spec"]["template"]["spec"]["providerSpec"]["value"]["instanceType"];provider["blockDevices"][0]["ebs"].update(volumeSize=200,volumeType="gp3",encrypted=True)
 assert expected["spec"]["template"]["spec"]["providerSpec"]["value"]==provider,name+": generated AMI/provider references differ from active source; re-run generate-gpu-machineset.sh"
 p=subprocess.run(["oc","--request-timeout=10s","get","machineset",name,"-n","openshift-machine-api","--ignore-not-found","-o","json"],capture_output=True,text=True,timeout=15)
 assert p.returncode==0,"MachineSet ownership API read failed"
 if p.stdout.strip():
  x=json.loads(p.stdout);assert not x["metadata"].get("ownerReferences"),name+": foreign MachineSet owner"
  assert x["metadata"].get("annotations",{}).get("argocd.argoproj.io/tracking-id","").startswith("020-gpu-machinesets:"),name+": existing MachineSet has not been adopted by reviewed Stage 020"
  for key in ["selector","template"]:assert x["spec"][key]==expected["spec"][key],name+": existing GPU provider/template differs from reviewed source"
app=json.loads(subprocess.run(["ruby","-ryaml","-rjson","-e","puts JSON.generate(YAML.load_stream(File.read(ARGV[0])).compact[0])",sys.argv[1]],capture_output=True,text=True,check=True).stdout)
assert sorted(i["name"] for i in app["spec"].get("ignoreDifferences",[]) if i.get("kind")=="MachineSet")==sorted(d["metadata"]["name"] for d in pools),"020-gpu-machinesets must hold a replica exception for every GPU MachineSet (re-run generate-gpu-machineset.sh --write)"
print("PASS "+str(len(pools))+" GPU MachineSets match their active CPU sources and carry replica exceptions")
' "$app_manifest"
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
oc kustomize "$stage_gitops" > "$work/render.yaml"
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(File.read(ARGV[0])))' "$work/render.yaml" | python3 -c '
import json,os,subprocess,sys
sys.path.insert(0,os.environ["REPO_ROOT"]+"/scripts/shared");import stage_apps
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
 assert stage_apps.tracked("020",x) or (expected["kind"]=="Namespace" and not tracking),"Unreviewed existing customer resource"
'
# First change: the component Applications at the reviewed commit; deploy applies, syncs and waits for each.
python3 "$STAGE_APPS" deploy 020 --revision "$revision" --repo-url "$GIT_REPO_URL"
echo 'Stage 020 components reconciled; native Automatic operator reconciliation is bounded below.'
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai" --wait 900
