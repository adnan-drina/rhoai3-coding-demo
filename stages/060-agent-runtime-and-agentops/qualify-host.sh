#!/usr/bin/env bash
# Opt-in temporary native OpenShell host qualification; not a stage deployment.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
if [[ "${1:-}" != --run || $# -gt 2 ]]; then
    echo "Usage: $0 --run [private-evidence-directory]"
    echo "Creates one temporary restricted CPU Job, records native capabilities, then deletes its owned namespace."
    exit 2
fi
load_env
check_oc_logged_in
# Every API request is bounded, including cleanup.
oc() { command oc --request-timeout=15s "$@"; }
command -v python3 >/dev/null
umask 077
EVIDENCE_DIR="${2:-$(mktemp -d "${TMPDIR:-/tmp}/openshell-qualification.XXXXXX")}"
mkdir -p "$EVIDENCE_DIR"
chmod 700 "$EVIDENCE_DIR"
PROBE_NS="openshell-qualification-$(date +%s)-$$"
NAMESPACE_UID=""
cleanup() {
    local original_status=$?
    trap - EXIT
    if [[ -n "$NAMESPACE_UID" ]]; then
        python3 - "$NAMESPACE_UID" > "$EVIDENCE_DIR/delete-options.json" <<'PY'
import json,sys
print(json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':sys.argv[1]},'propagationPolicy':'Background'}))
PY
        if oc delete --raw "/api/v1/namespaces/$PROBE_NS" -f "$EVIDENCE_DIR/delete-options.json" > "$EVIDENCE_DIR/delete-private.json" 2> "$EVIDENCE_DIR/delete-error-private.log" && oc wait "namespace/$PROBE_NS" --for=delete --timeout=60s > "$EVIDENCE_DIR/cleanup.log" 2>&1; then
            echo "Owned namespace cleanup confirmed."
        else
            echo "Owned namespace cleanup failed; inspect private evidence." >&2
            original_status=1
        fi
    fi
    exit "$original_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Never adopt an existing namespace; API errors fail closed.
existing_namespace="$(oc get namespace "$PROBE_NS" --ignore-not-found -o name)"
[[ -z "$existing_namespace" ]] || { echo "Refusing existing namespace" >&2; exit 1; }
oc create namespace "$PROBE_NS" -o json > "$EVIDENCE_DIR/namespace-private.json"
NAMESPACE_UID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["metadata"]["uid"])' "$EVIDENCE_DIR/namespace-private.json")"
oc get namespace "$PROBE_NS" -o json > "$EVIDENCE_DIR/namespace-private.json"
oc get nodes -o json > "$EVIDENCE_DIR/nodes-private.json"
python3 - "$PROBE_NS" "$EVIDENCE_DIR" "$REPO_ROOT/gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json" <<'PY'
import json,pathlib,sys
ns,folder,pinsfile=sys.argv[1:];p=pathlib.Path(folder)
pins=json.loads(pathlib.Path(pinsfile).read_text())
a=json.loads((p/'namespace-private.json').read_text());annotations=a['metadata']['annotations']
uid=int(annotations['openshift.io/sa.scc.uid-range'].split('/')[0].split('-')[0])
gid=int(annotations.get('openshift.io/sa.scc.supplemental-groups',annotations['openshift.io/sa.scc.uid-range']).split('/')[0].split('-')[0])
assert uid>0 and gid>0
nodes=json.loads((p/'nodes-private.json').read_text())['items']
node=next(x['metadata']['name'] for x in nodes if 'node-role.kubernetes.io/worker' in x['metadata'].get('labels',{}) and not any(k in x['metadata'].get('labels',{}) for k in ('node-role.kubernetes.io/master','node-role.kubernetes.io/control-plane')) and x['metadata'].get('labels',{}).get('kubernetes.io/arch')=='amd64' and not any(t.get('effect') in ('NoSchedule','NoExecute') for t in x['spec'].get('taints',[])) and x['status'].get('allocatable',{}).get('nvidia.com/gpu','0')=='0' and not x['spec'].get('unschedulable') and any(c['type']=='Ready' and c['status']=='True' for c in x['status']['conditions']))
labels={'app.kubernetes.io/name':'openshell-host-qualification','app.kubernetes.io/part-of':'rhoai3-coding-demo'}
spec={'automountServiceAccountToken':False,'restartPolicy':'Never','nodeSelector':{'kubernetes.io/hostname':node},'securityContext':{'runAsNonRoot':True,'runAsUser':uid,'runAsGroup':gid,'seccompProfile':{'type':'RuntimeDefault'},'sysctls':[{'name':'net.ipv4.ip_unprivileged_port_start','value':'0'}]},'containers':[{'name':'probe','image':pins['images']['sandbox']['repository']+'@'+pins['images']['sandbox']['amd64Digest'],'command':['/openshell-sandbox','capability-probe'],'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'20m','memory':'64Mi'},'limits':{'cpu':'200m','memory':'128Mi'}},'volumeMounts':[{'name':'temporary','mountPath':'/tmp'}]}],'volumes':[{'name':'temporary','emptyDir':{'sizeLimit':'8Mi'}}]}
job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':'native-capability-probe','namespace':ns,'labels':labels},'spec':{'backoffLimit':0,'activeDeadlineSeconds':180,'template':{'metadata':{'labels':labels},'spec':spec}}}
(p/'job-private.json').write_text(json.dumps(job)+'\n')
(p/'admission-private.json').write_text(json.dumps({'apiVersion':'v1','kind':'Pod','metadata':{'name':'admission-only','namespace':ns},'spec':spec})+'\n')
(p/'pins.json').write_text(json.dumps(pins)+'\n')
PY
oc create --dry-run=server -f "$EVIDENCE_DIR/admission-private.json" -o json > "$EVIDENCE_DIR/admitted-private.json"
oc create -f "$EVIDENCE_DIR/job-private.json" >> "$EVIDENCE_DIR/create.log"
# The native Job has a hard deadline; stop early on a recorded failure.
probe_deadline=$((SECONDS + 180))
while (( SECONDS < probe_deadline )); do
    oc get job native-capability-probe -n "$PROBE_NS" -o json > "$EVIDENCE_DIR/job-status-private.json"
    state="$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1])).get("status",{}); print("done" if s.get("succeeded") or s.get("failed") else "waiting")' "$EVIDENCE_DIR/job-status-private.json")"
    [[ "$state" != waiting ]] && break
    sleep 3
done
oc get pods -n "$PROBE_NS" -o json > "$EVIDENCE_DIR/pods-private.json"
oc logs job/native-capability-probe -n "$PROBE_NS" > "$EVIDENCE_DIR/native-result.log" 2> "$EVIDENCE_DIR/native-error.log"
python3 - "$EVIDENCE_DIR" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);r=json.loads((p/'native-result.log').read_text())
required=['qualified','capabilities_zero','no_new_privileges','same_uid_self_protection','child_core_limit_zero','landlock_allow_deny','seccomp_notification','seccomp_addfd_send','task_memory_copy','connected_send_fast_path','socket_virtualization','socket_loopback_confinement','dns_relay_bind','udp_dns_round_trip','tcp_dns_round_trip','tcp_allow_round_trip','tcp_deny_round_trip']
assert all(r.get(k) is True for k in required),'Native capability check failed'
assert r['uid']>0 and r['gid']>0 and r['sandbox_dumpable'] is False
assert not any(k in r for k in ('seccomp_listener_mode','wait_killable_recv','task_memory_writes_disabled')),'Obsolete native capability schema'
pods=json.loads((p/'pods-private.json').read_text())['items'];assert len(pods)==1
pod=pods[0];assert pod['status']['phase']=='Succeeded'
job=json.loads((p/'job-status-private.json').read_text());desired=json.loads((p/'job-private.json').read_text())
assert any(o.get('controller') is True and o.get('uid')==job['metadata']['uid'] and o.get('name')=='native-capability-probe' and o.get('kind')=='Job' and o.get('apiVersion')=='batch/v1' for o in pod['metadata'].get('ownerReferences',[]))
assert pod['metadata']['annotations'].get('openshift.io/scc')=='restricted-v2'
expected_identity=desired['spec']['template']['spec']['securityContext']
assert r['uid']==expected_identity['runAsUser'] and r['gid']==expected_identity['runAsGroup']
assert pod['spec']['securityContext']['runAsUser']==r['uid'] and pod['spec']['securityContext']['runAsGroup']==r['gid']
assert pod['spec']['containers'][0]['image']==desired['spec']['template']['spec']['containers'][0]['image']
pins=json.loads((p/'pins.json').read_text())
assert pod['status']['containerStatuses'][0]['imageID']==desired['spec']['template']['spec']['containers'][0]['image']
r.update({'pod_uid':pod['metadata']['uid'],'scc':pod['metadata']['annotations'].get('openshift.io/scc'),'image_digest':pins['images']['sandbox']['amd64Digest'],'source_commit':pins['sourceCommit'],'scope':'one CPU worker/profile; agent server/auth/controller/cross-pod CNI unqualified'})
(p/'receipt.json').write_text(json.dumps(r,indent=2)+'\n')
print('Native host capability PASS; socket loopback confinement verified. Receipt: '+str(p/'receipt.json'))
PY
