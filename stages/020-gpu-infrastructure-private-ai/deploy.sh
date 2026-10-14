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
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select a reviewed published revision.' >&2; exit 1; }
command -v python3 >/dev/null
command -v ruby >/dev/null
command -v git >/dev/null
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR: revision must resolve to one published branch.' >&2; exit 1; }
[[ "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs from reviewed checkout.' >&2; exit 1; }
paths=(gitops/stages/020-gpu-infrastructure-private-ai gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai stages/020-gpu-infrastructure-private-ai scripts/shared scripts/platform/require-node-sizing.sh scripts/platform/check-operator-policy.py)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish all reviewed Stage 020 source before deploying.' >&2; exit 1; }
stage_gitops="$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai"
[[ -f "$stage_gitops/gpu-machinesets/machineset-gpu.yaml" && -f "$stage_gitops/gpu-machinesets/application-patch.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSet and Application patch first.' >&2; exit 1; }
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
assert not read('application','020-gpu-infrastructure-private-ai','openshift-gitops'),'Retired single Stage 020 Application still exists; finish the component move (docs/OPERATIONS.md)'
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
patch=json.loads(subprocess.run(["ruby","-ryaml","-rjson","-e","puts JSON.generate(YAML.load_file(ARGV[0]))",sys.argv[1]],capture_output=True,text=True,check=True).stdout)
assert sorted(i["name"] for i in patch["spec"]["ignoreDifferences"])==sorted(d["metadata"]["name"] for d in pools),"application-patch.yaml must hold a replica exception for every GPU MachineSet"
print("PASS "+str(len(pools))+" GPU MachineSets match their active CPU sources and carry replica exceptions")
' "$stage_gitops/gpu-machinesets/application-patch.yaml"
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
# The component Applications at one revision; the exact-name MachineSet replica exceptions go on 020-gpu-machinesets.
python3 "$ROOT_DIR/scripts/shared/stage_apps.py" applications 020 --revision "$remote_sha" --repo-url "$GIT_REPO_URL" > "$work/components.json"
ruby -ryaml -rjson -e 'apps=JSON.parse(File.read(ARGV[0]));p=YAML.load_file(ARGV[1])
pools=apps["items"].find{|a| a["metadata"]["name"]=="020-gpu-machinesets"} or abort "ERROR: MachineSet component is missing."
pools["spec"]["ignoreDifferences"]=p["spec"]["ignoreDifferences"];puts JSON.generate(apps)' "$work/components.json" "$stage_gitops/gpu-machinesets/application-patch.yaml" > "$work/applications.json"
oc --request-timeout=10s apply -f "$work/applications.json"
python3 "$ROOT_DIR/scripts/shared/stage_apps.py" sync 020  # an unchanged render gets no automatic sync operation
echo 'Stage 020 component Applications submitted; native Automatic operator reconciliation is bounded below.'
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai" --wait 900
