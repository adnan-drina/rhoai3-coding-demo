#!/usr/bin/env bash
# generate-gpu-machineset.sh - derive a Stage 020 AWS GPU MachineSet from a
# live worker MachineSet in the currently guarded OpenShift environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

WRITE=false
SOURCE_MACHINESET="${RHOAI_SOURCE_WORKER_MACHINESET:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write)
      WRITE=true
      shift
      ;;
    --source)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --source requires a MachineSet name." >&2
        exit 1
      fi
      SOURCE_MACHINESET="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  ./020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh [--source <worker-machineset>] [--write]

By default, prints a generated GPU MachineSet to stdout. With --write, replaces
gitops/stages/020-gpu-infrastructure-private-ai/base/machineset/base/machineset-gpu.yaml.

Environment overrides:
  RHOAI_GPU_INSTANCE_TYPE      default: g6e.2xlarge
  RHOAI_GPU_MACHINESET_REPLICAS default: 1
  RHOAI_GPU_MACHINESET_OUTPUT default: gitops/stages/020-gpu-infrastructure-private-ai/base/machineset/base/machineset-gpu.yaml
  RHOAI_SOURCE_WORKER_MACHINESET optional source MachineSet name
EOF
      exit 0
      ;;
    *)
      if [[ -z "$SOURCE_MACHINESET" ]]; then
        SOURCE_MACHINESET="$1"
        shift
      else
        echo "ERROR: unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

SOURCE_MACHINESET="${SOURCE_MACHINESET:-${RHOAI_SOURCE_WORKER_MACHINESET:-}}"

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set. Set it in .env." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match guard." >&2
  exit 1
fi

for cmd in oc jq ruby; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
done

GPU_INSTANCE_TYPE="${RHOAI_GPU_INSTANCE_TYPE:-g6e.2xlarge}"
GPU_REPLICAS="${RHOAI_GPU_MACHINESET_REPLICAS:-1}"
OUTPUT_PATH="${RHOAI_GPU_MACHINESET_OUTPUT:-gitops/stages/020-gpu-infrastructure-private-ai/base/machineset/base/machineset-gpu.yaml}"

if ! [[ "$GPU_REPLICAS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: RHOAI_GPU_MACHINESET_REPLICAS must be an integer." >&2
  exit 1
fi

MACHINESETS_JSON=$(oc get machinesets -n openshift-machine-api -o json --insecure-skip-tls-verify=true)

if [[ -z "$SOURCE_MACHINESET" ]]; then
  SOURCE_MACHINESET=$(jq -r '
    .items[]
    | select((.metadata.labels["cluster-api/accelerator"] // "") != "nvidia-gpu")
    | select((.metadata.labels["machine.openshift.io/cluster-api-machine-role"] // .spec.template.metadata.labels["machine.openshift.io/cluster-api-machine-role"] // "") == "worker")
    | .metadata.name
  ' <<<"$MACHINESETS_JSON" | sort | head -n 1)
fi

if [[ -z "$SOURCE_MACHINESET" ]]; then
  echo "ERROR: could not find a non-GPU worker MachineSet. Pass --source <name>." >&2
  exit 1
fi

SOURCE_JSON=$(jq --arg name "$SOURCE_MACHINESET" -c '
  .items[] | select(.metadata.name == $name)
' <<<"$MACHINESETS_JSON")

if [[ -z "$SOURCE_JSON" || "$SOURCE_JSON" == "null" ]]; then
  echo "ERROR: source MachineSet not found: $SOURCE_MACHINESET" >&2
  exit 1
fi

CLUSTER_ID=$(jq -r '.metadata.labels["machine.openshift.io/cluster-api-cluster"] // .spec.selector.matchLabels["machine.openshift.io/cluster-api-cluster"] // empty' <<<"$SOURCE_JSON")
AZ=$(jq -r '.spec.template.spec.providerSpec.value.placement.availabilityZone // empty' <<<"$SOURCE_JSON")

if [[ -z "$CLUSTER_ID" || -z "$AZ" ]]; then
  echo "ERROR: source MachineSet is missing cluster id or AWS availability zone." >&2
  exit 1
fi

GPU_NAME="${CLUSTER_ID}-gpu-${AZ}"

GENERATED_JSON=$(jq \
  --arg name "$GPU_NAME" \
  --arg cluster "$CLUSTER_ID" \
  --arg instance "$GPU_INSTANCE_TYPE" \
  --argjson replicas "$GPU_REPLICAS" '
  del(
    .metadata.creationTimestamp,
    .metadata.generation,
    .metadata.managedFields,
    .metadata.ownerReferences,
    .metadata.resourceVersion,
    .metadata.uid,
    .status
  )
  | .metadata.name = $name
  | .metadata.namespace = "openshift-machine-api"
  | .metadata.annotations = ((.metadata.annotations // {}) + {
      "machine.openshift.io/GPU": "1",
      "machine.openshift.io/memoryMb": "65536",
      "machine.openshift.io/vCPU": "8"
    })
  | .metadata.labels = ((.metadata.labels // {}) + {
      "app.kubernetes.io/part-of": "gpu-infra",
      "app.kubernetes.io/name": "aws-gpu-machineset",
      "app.kubernetes.io/component": "gpu-worker",
      "cluster-api/accelerator": "nvidia-gpu",
      "machine.openshift.io/cluster-api-cluster": $cluster
    })
  | .spec.replicas = $replicas
  | .spec.selector.matchLabels["machine.openshift.io/cluster-api-cluster"] = $cluster
  | .spec.selector.matchLabels["machine.openshift.io/cluster-api-machineset"] = $name
  | .spec.template.metadata.labels = ((.spec.template.metadata.labels // {}) + {
      "cluster-api/accelerator": "nvidia-gpu",
      "machine.openshift.io/cluster-api-cluster": $cluster,
      "machine.openshift.io/cluster-api-machine-role": "worker",
      "machine.openshift.io/cluster-api-machine-type": "worker",
      "machine.openshift.io/cluster-api-machineset": $name,
      "node-role.kubernetes.io/gpu": ""
    })
  | .spec.template.spec.metadata.labels = ((.spec.template.spec.metadata.labels // {}) + {
      "cluster-api/accelerator": "nvidia-gpu",
      "node-role.kubernetes.io/gpu": ""
    })
  | .spec.template.spec.providerSpec.value.instanceType = $instance
  | .spec.template.spec.taints = [
      {
        "effect": "NoSchedule",
        "key": "nvidia-gpu-only"
      }
    ]
' <<<"$SOURCE_JSON")

GENERATED_YAML=$(ruby -rjson -ryaml -e '
  data = JSON.parse(STDIN.read)
  puts YAML.dump(data).sub(/\A---\n/, "")
' <<<"$GENERATED_JSON")

if [[ "$WRITE" == "true" ]]; then
  mkdir -p "$(dirname "$ROOT_DIR/$OUTPUT_PATH")"
  printf "%s\n" "$GENERATED_YAML" >"$ROOT_DIR/$OUTPUT_PATH"
  echo "✓ Wrote $OUTPUT_PATH from source MachineSet $SOURCE_MACHINESET"
  echo "  Review providerSpec, render with kustomize, then deploy Stage 020."
else
  printf "%s\n" "$GENERATED_YAML"
  echo >&2
  echo "Preview generated from source MachineSet $SOURCE_MACHINESET." >&2
  echo "Re-run with --write to replace $OUTPUT_PATH." >&2
fi
