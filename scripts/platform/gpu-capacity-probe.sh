#!/usr/bin/env bash
# Probe AWS GPU launch capacity (H100 p5.4xlarge, RTX PRO 6000 g7e.2xlarge), one us-east-2 zone at a time.
#
# For each zone: scale its zero-replica <pool> MachineSet to 1, record what AWS
# answers (Running, Failed with reason, or still Provisioning with the
# Machine API's last error), then always scale back to 0 and remove the
# Machine. A Running machine is billed until it is removed; with --gpu the
# probe also waits for the node to advertise nvidia.com/gpu before removing it.
#
# Usage: gpu-capacity-probe.sh [--pool h100|rtxpro6000] [--zones "a b c"] [--timeout-min 10] [--gpu]
# Receipt: tmp/<pool>-capacity-probe-<UTC timestamp>.jsonl (tmp/ is gitignored)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

POOL=h100; ZONES="a b c"; TIMEOUT_MIN=10; GPU=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pool) POOL="$2"; shift 2 ;;
    --zones) ZONES="$2"; shift 2 ;;
    --timeout-min) TIMEOUT_MIN="$2"; shift 2 ;;
    --gpu) GPU=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ "$POOL" =~ ^(h100|rtxpro6000)$ ]] || { echo "Unknown pool: $POOL" >&2; exit 2; }
NS=openshift-machine-api
INFRA="$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')"
RECEIPT="$REPO_ROOT/tmp/$POOL-capacity-probe-$(date -u +%Y%m%dT%H%M%SZ).jsonl"
mkdir -p "$REPO_ROOT/tmp"

machine_of() { oc get machine -n "$NS" -l "machine.openshift.io/cluster-api-machineset=$1" -o name | head -1; }

cleanup() {
  local ms="$1" m
  oc scale machineset "$ms" -n "$NS" --replicas=0 >/dev/null
  for m in $(oc get machine -n "$NS" -l "machine.openshift.io/cluster-api-machineset=$ms" -o name); do
    oc delete "$m" -n "$NS" --wait=false >/dev/null
  done
}

CURRENT=""
trap '[[ -n "$CURRENT" ]] && cleanup "$CURRENT"' EXIT INT TERM

for z in $ZONES; do
  ms="$INFRA-gpu-$POOL-us-east-2$z"
  oc get machineset "$ms" -n "$NS" >/dev/null
  [[ "$(oc get machineset "$ms" -n "$NS" -o jsonpath='{.spec.replicas}')" == 0 ]] || { echo "$ms is not at zero replicas; refusing" >&2; exit 1; }
  CURRENT="$ms"
  start=$(date +%s)
  oc scale machineset "$ms" -n "$NS" --replicas=1 >/dev/null
  echo "$(date -u +%H:%M:%SZ) $ms scaled to 1"
  result=timeout; node=""; gpu=""
  while (( $(date +%s) - start < TIMEOUT_MIN * 60 )); do
    sleep 20
    m="$(machine_of "$ms")"; [[ -n "$m" ]] || continue
    phase="$(oc get "$m" -n "$NS" -o jsonpath='{.status.phase}')"
    if [[ "$phase" == Failed ]]; then result=failed; break; fi
    node="$(oc get "$m" -n "$NS" -o jsonpath='{.status.nodeRef.name}')"
    if [[ "$phase" == Running || -n "$node" ]]; then
      result=running
      [[ "$GPU" == true && -n "$node" ]] || { [[ "$GPU" == true ]] && continue; break; }
      gpu="$(oc get node "$node" -o jsonpath='{.status.allocatable.nvidia\.com/gpu}' 2>/dev/null || true)"
      [[ -n "$gpu" && "$gpu" != 0 ]] && break
    fi
  done
  m="$(machine_of "$ms")"
  detail="{}"
  [[ -n "$m" ]] && detail="$(oc get "$m" -n "$NS" -o json | python3 -c '
import json,sys
m=json.load(sys.stdin);s=m.get("status",{})
conds=[{k:c.get(k) for k in ("type","status","reason","message")} for c in (s.get("providerStatus") or {}).get("conditions",[])]
print(json.dumps({"machine":m["metadata"]["name"],"phase":s.get("phase"),"errorReason":s.get("errorReason"),"errorMessage":s.get("errorMessage"),
 "instanceId":(s.get("providerStatus") or {}).get("instanceId"),"instanceState":(s.get("providerStatus") or {}).get("instanceState"),"providerConditions":conds}))')"
  python3 -c 'import json,sys;d=json.loads(sys.argv[5]);d.update(zone=sys.argv[1],result=sys.argv[2],seconds=int(sys.argv[3]),node=sys.argv[4] or None,gpuAllocatable=sys.argv[6] or None);print(json.dumps(d))' \
    "us-east-2$z" "$result" "$(( $(date +%s) - start ))" "$node" "$detail" "$gpu" | tee -a "$RECEIPT"
  cleanup "$ms"; CURRENT=""
  echo "$(date -u +%H:%M:%SZ) $ms back to 0"
done

# Wait until no probed Machine remains, so nothing keeps billing after the probe.
until [[ -z "$(for z in $ZONES; do machine_of "$INFRA-gpu-$POOL-us-east-2$z"; done)" ]]; do sleep 15; done
echo "No $POOL probe Machines remain. Receipt: $RECEIPT"
