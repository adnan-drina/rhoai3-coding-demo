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
gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment/machineset-gpu.yaml.

Environment overrides:
  RHOAI_GPU_INSTANCE_TYPE      default: g6e.2xlarge
  RHOAI_GPU_MACHINESET_REPLICAS default: 2
  RHOAI_GPU_MACHINESET_OUTPUT default: gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment/machineset-gpu.yaml
  RHOAI_SOURCE_WORKER_MACHINESET required explicit source MachineSet name
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

REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env >&2
check_oc_logged_in >&2
SOURCE_MACHINESET="${SOURCE_MACHINESET:-${RHOAI_SOURCE_WORKER_MACHINESET:-}}"
[[ -n "$SOURCE_MACHINESET" ]] || { echo "ERROR: select an active CPU worker MachineSet with --source." >&2; exit 1; }
for cmd in oc jq ruby; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done

GPU_INSTANCE_TYPE="${RHOAI_GPU_INSTANCE_TYPE:-g6e.2xlarge}"
GPU_REPLICAS="${RHOAI_GPU_MACHINESET_REPLICAS:-2}"
# Root volume sized for large modelcar images: a 100GB worker default hits
# kubelet DiskPressure mid-pull (~36GB qwen modelcar + base images) and image
# GC thrashes the pull. 200GB matches the two-model coding demo.
GPU_VOLUME_SIZE="${RHOAI_GPU_VOLUME_SIZE:-200}"
GPU_VOLUME_TYPE="${RHOAI_GPU_VOLUME_TYPE:-gp3}"
OUTPUT_PATH="${RHOAI_GPU_MACHINESET_OUTPUT:-gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment/machineset-gpu.yaml}"

if ! [[ "$GPU_REPLICAS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: RHOAI_GPU_MACHINESET_REPLICAS must be an integer." >&2
  exit 1
fi

MACHINESETS_JSON=$(oc get machinesets -n openshift-machine-api -o json --request-timeout=10s)

SOURCE_JSON=$(jq --arg name "$SOURCE_MACHINESET" -c '
  .items[] | select(.metadata.name == $name)
' <<<"$MACHINESETS_JSON")

if [[ -z "$SOURCE_JSON" || "$SOURCE_JSON" == "null" ]]; then
  echo "ERROR: source MachineSet not found: $SOURCE_MACHINESET" >&2
  exit 1
fi

# Require an active CPU worker pool with a consistent native AWS identity.
jq -e '
 .spec.replicas > 0 and .status.readyReplicas > 0
 and .spec.template.metadata.labels["machine.openshift.io/cluster-api-machine-role"] == "worker"
 and (.metadata.labels["cluster-api/accelerator"] // "") != "nvidia-gpu"
 and .spec.template.spec.providerSpec.value.kind == "AWSMachineProviderConfig"
 and (.spec.template.spec.providerSpec.value.instanceType | test("^[mc][0-9]+[a-z]*\\."))
 and (.spec.template.spec.providerSpec.value.capacityReservationId // "") == ""
 and (.spec.template.spec.providerSpec.value.ami.id | type == "string")
 and (.spec.template.spec.providerSpec.value.placement.region | length > 0)
 and (.spec.template.spec.providerSpec.value.placement.availabilityZone | length > 0)
' <<<"$SOURCE_JSON" >/dev/null || { echo "ERROR: source is not an active native AWS CPU worker pool." >&2; exit 1; }
[[ "$GPU_INSTANCE_TYPE" == g6e.2xlarge && "$GPU_REPLICAS" == 2 && "$GPU_VOLUME_SIZE" == 200 && "$GPU_VOLUME_TYPE" == gp3 ]] || { echo "ERROR: this reviewed topology requires two g6e.2xlarge workers with 200Gi gp3 disks." >&2; exit 1; }
INFRA_JSON=$(oc --request-timeout=10s get infrastructure cluster -o json)
NODES_JSON=$(oc --request-timeout=10s get nodes -o json)
jq -e '.status.platformStatus.type == "AWS"' <<<"$INFRA_JSON" >/dev/null
jq -e '.items | length > 0 and all(.[]; .status.nodeInfo.architecture == "amd64")' <<<"$NODES_JSON" >/dev/null || { echo "ERROR: reviewed source requires an amd64 cluster." >&2; exit 1; }
CLUSTER_ID=$(jq -r '.metadata.labels["machine.openshift.io/cluster-api-cluster"] // .spec.selector.matchLabels["machine.openshift.io/cluster-api-cluster"] // empty' <<<"$SOURCE_JSON")
[[ "$CLUSTER_ID" == "$(jq -r '.status.infrastructureName' <<<"$INFRA_JSON")" ]] || { echo "ERROR: source provider cluster identity differs from Infrastructure." >&2; exit 1; }
AZ=$(jq -r '.spec.template.spec.providerSpec.value.placement.availabilityZone // empty' <<<"$SOURCE_JSON")

if [[ -z "$CLUSTER_ID" || -z "$AZ" ]]; then
  echo "ERROR: source MachineSet is missing cluster id or AWS availability zone." >&2
  exit 1
fi

GPU_NAME="${CLUSTER_ID}-gpu-${AZ}"

GENERATED_JSON=$(jq \
  --arg name "$GPU_NAME" \
  --arg source "$SOURCE_MACHINESET" \
  --arg cluster "$CLUSTER_ID" \
  --arg instance "$GPU_INSTANCE_TYPE" \
  --argjson replicas "$GPU_REPLICAS" \
  --argjson volsize "$GPU_VOLUME_SIZE" \
  --arg voltype "$GPU_VOLUME_TYPE" '
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
  | .metadata.annotations = ({
      "argocd.argoproj.io/sync-options": "Prune=false,Delete=false",
      "demo.rhoai.io/source-machineset": $source,
      "machine.openshift.io/GPU": "1",
      "machine.openshift.io/memoryMb": "65536",
      "machine.openshift.io/vCPU": "8"
    })
  | .metadata.labels = ({
      "app.kubernetes.io/part-of": "gpu-infra",
      "app.kubernetes.io/name": "aws-gpu-machineset",
      "app.kubernetes.io/component": "gpu-worker",
      "app.kubernetes.io/managed-by": "argocd",
      "cluster-api/accelerator": "nvidia-gpu",
      "machine.openshift.io/cluster-api-cluster": $cluster
    })
  | .spec.template.metadata |= {labels: .labels}
  | .spec.template.spec.metadata |= {labels: .labels}
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.encrypted = true
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
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.volumeSize = $volsize
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.volumeType = $voltype
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
  python3 - "$ROOT_DIR" "$GPU_NAME" <<'PY_PATCH'
import json,pathlib,sys,subprocess
root=pathlib.Path(sys.argv[1]); name=sys.argv[2]
p=root/'gitops/stages/020-gpu-infrastructure-private-ai/overlays/environment/application-patch.yaml'
data=json.dumps({'apiVersion':'argoproj.io/v1alpha1','kind':'Application','metadata':{'name':'020-gpu-infrastructure-private-ai','namespace':'openshift-gitops'},'spec':{'ignoreDifferences':[{'group':'machine.openshift.io','kind':'MachineSet','name':name,'namespace':'openshift-machine-api','jsonPointers':['/spec/replicas']}] }},indent=2)
p.write_text(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts YAML.dump(JSON.parse(STDIN.read))'],input=data,text=True))
app=root/'gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai.yaml'
a=json.loads(subprocess.check_output(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(app)],text=True))
a['spec']['ignoreDifferences']=json.loads(data)['spec']['ignoreDifferences']
app.write_text(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts YAML.dump(JSON.parse(STDIN.read))'],input=json.dumps(a),text=True))
PY_PATCH
  echo "  Review native provider identifiers, AMI compatibility, disk and retention before publishing."
else
  printf "%s\n" "$GENERATED_YAML"
  echo >&2
  echo "Preview generated from source MachineSet $SOURCE_MACHINESET." >&2
  echo "Re-run with --write to replace $OUTPUT_PATH." >&2
fi
