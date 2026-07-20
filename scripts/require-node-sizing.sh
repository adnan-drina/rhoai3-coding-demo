#!/usr/bin/env bash
# require-node-sizing.sh — fail fast if the cluster nodes are too small.
#
# WHY: the full demo stack (RHOAI + ODF + GPU + MaaS + model serving) puts heavy,
# sustained load on the control plane and CPU workers. On 2026-07-20 a fresh
# deploy onto the default sandbox m6a.xlarge (4 vCPU / 16 GiB) *control-plane*
# nodes exhausted CPU and memory — kube-apiserver ballooned past 6 GiB, a master
# hit 0% CPU idle / 1.4 GiB free, its kubelet stopped posting status, the node
# died, and masters then failed one after another until etcd quorum was at risk.
# The workers were already m6a.4xlarge and were fine; the control plane was not.
#
# It is on the deploy tooling to catch undersized nodes BEFORE touching the
# cluster, not to let the operator discover it via a cascading control-plane
# outage mid-install. Each stage's deploy.sh calls this first.
#
# Requirement: control-plane and CPU-worker nodes must be m6a.4xlarge-class
# (>= 16 vCPU / >= 60 GiB). GPU nodes are EXEMPT — they are sized by accelerator
# (e.g. g6e.2xlarge = 8 vCPU / 64 GiB) and their vCPU count is intentionally
# lower. Thresholds are overridable via REQUIRED_NODE_VCPU / REQUIRED_NODE_MEM_GIB.
set -euo pipefail

REQUIRED_NODE_VCPU="${REQUIRED_NODE_VCPU:-16}"
REQUIRED_NODE_MEM_GIB="${REQUIRED_NODE_MEM_GIB:-60}"

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'

undersized=$(oc get nodes -o json 2>/dev/null | \
  REQ_CPU="$REQUIRED_NODE_VCPU" REQ_MEM="$REQUIRED_NODE_MEM_GIB" python3 -c '
import json, os, re, sys
req_cpu = int(os.environ["REQ_CPU"]); req_mem = int(os.environ["REQ_MEM"])
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # cannot read nodes -> do not block here; the cluster guard handles auth
for n in data.get("items", []):
    labels = n["metadata"].get("labels", {})
    itype = labels.get("node.kubernetes.io/instance-type", "?")
    # GPU nodes are sized by accelerator, not general vCPU — exempt them.
    if ("nvidia.com/gpu.present" in labels
            or "cluster-api/accelerator" in labels
            or "node-role.kubernetes.io/gpu" in labels
            or itype.startswith(("g", "p"))):
        continue
    is_cp = ("node-role.kubernetes.io/control-plane" in labels
             or "node-role.kubernetes.io/master" in labels)
    role = "control-plane" if is_cp else "worker"
    cap = n["status"].get("capacity", {})
    try:
        cpu = int(cap.get("cpu", "0"))
    except ValueError:
        cpu = 0
    mem = cap.get("memory", "0")
    num = int(re.sub(r"[^0-9]", "", mem) or "0")
    unit = re.sub(r"[0-9]", "", mem)
    gib = num / (1024 * 1024) if unit == "Ki" else num / (1024 * 1024 * 1024)
    if cpu < req_cpu or gib < req_mem:
        print("%-14s %-45s %-14s %2d vCPU / %d GiB" %
              (role, n["metadata"]["name"], itype, cpu, int(gib)))
' || true)

if [[ -n "$undersized" ]]; then
  echo -e "${RED}[ERROR]${NC} Cluster nodes are too small to run the demo — stopping before any changes." >&2
  echo "" >&2
  echo "  The full RHOAI + ODF + GPU + MaaS + model-serving stack overloads the control" >&2
  echo "  plane and CPU workers on small nodes. A deploy onto m6a.xlarge (4 vCPU / 16 GiB)" >&2
  echo "  control-plane nodes exhausts CPU/memory, the kubelet dies, and masters fail one" >&2
  echo "  after another until etcd quorum is at risk." >&2
  echo "" >&2
  echo "  Required: >= ${REQUIRED_NODE_VCPU} vCPU / >= ${REQUIRED_NODE_MEM_GIB} GiB (m6a.4xlarge-class) for" >&2
  echo "  control-plane and CPU worker nodes. GPU nodes (e.g. g6e.2xlarge) are exempt." >&2
  echo "" >&2
  echo "  Undersized nodes found:" >&2
  while IFS= read -r line; do echo "    ${line}" >&2; done <<< "$undersized"
  echo "" >&2
  echo "  Reprovision the environment with m6a.4xlarge (or larger) control-plane AND worker" >&2
  echo "  nodes, then re-run. On RHDP/sandbox, choose the larger control-plane and worker" >&2
  echo "  instance sizing when ordering the environment." >&2
  exit 45
fi

echo -e "${GREEN}[OK]${NC} Node sizing meets the demo minimum (control plane + CPU workers >= ${REQUIRED_NODE_VCPU} vCPU / ${REQUIRED_NODE_MEM_GIB} GiB; GPU nodes exempt)."
