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
app_manifest="$ROOT_DIR/gitops/applications/020-gpu-machinesets.yaml"
[[ -f "$stage_gitops/020-gpu-machinesets/machineset-gpu.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSets first (generate-gpu-machineset.sh).' >&2; exit 1; }
# All prerequisites are read-only and run before the first Application write.
python3 "$STAGE_APPS" status 010 >/dev/null || { echo "ERROR: Stage 010 must be reconciled first" >&2; exit 1; }
python3 "$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io |
  grep -qx /spec/components/kueue || { echo "ERROR: Stage 010 must delegate /spec/components/kueue" >&2; exit 1; }
oc --request-timeout=10s get csv -A -o json | jq -e 'any(.items[]; (.metadata.name | startswith("cert-manager-operator.v1.20."))
  and .status.phase == "Succeeded")' >/dev/null || { echo "ERROR: Provider cert-manager prerequisite unavailable" >&2; exit 1; }
# Existing Applications and objects must already be ours; MachineSets are checked against their sources below.
python3 "$STAGE_APPS" preflight 020 --repo-url "$GIT_REPO_URL" --skip-kind MachineSet

# Every generated GPU MachineSet must still match the active CPU worker it was derived from.
machinesets=$(oc kustomize "$stage_gitops/020-gpu-machinesets" |
  ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' | jq -c '[.[] | select(.kind == "MachineSet")]')
[[ $(jq length <<<"$machinesets") -gt 0 ]] || { echo "ERROR: No generated GPU MachineSets" >&2; exit 1; }
infra=$(oc --request-timeout=10s get infrastructure cluster -o json)
cluster=$(jq -r '.status.infrastructureName' <<<"$infra")
region=$(jq -r '.status.platformStatus.aws.region // ""' <<<"$infra")
[[ $(jq -r '.status.platformStatus.type' <<<"$infra") == AWS ]] || { echo "ERROR: AWS environment required" >&2; exit 1; }
oc --request-timeout=10s get nodes -o json | jq -e '(.items | length) > 0 and all(.items[]; .status.nodeInfo.architecture == "amd64")' \
  >/dev/null || { echo "ERROR: Reviewed native source requires amd64 nodes" >&2; exit 1; }
for name in $(jq -r '.[].metadata.name' <<<"$machinesets"); do
  expected=$(jq -c --arg n "$name" '.[] | select(.metadata.name == $n)' <<<"$machinesets")
  jq -e --arg c "$cluster" '[.metadata.labels, .spec.selector.matchLabels, .spec.template.metadata.labels]
    | all(.[]; .["machine.openshift.io/cluster-api-cluster"] == $c)' <<<"$expected" >/dev/null ||
    { echo "ERROR: $name: generated intent belongs to another cluster" >&2; exit 1; }
  jq -e '.spec.replicas == 0' <<<"$expected" >/dev/null ||
    { echo "ERROR: $name: declare replicas 0; resume-gpu-demo.sh scales the pool" >&2; exit 1; }
  source_name=$(jq -r '.metadata.annotations["demo.rhoai.io/source-machineset"]' <<<"$expected")
  source=$(oc --request-timeout=10s get machineset "$source_name" -n openshift-machine-api -o json)
  jq -e '.spec.replicas > 0 and (.status.readyReplicas // 0) > 0' <<<"$source" >/dev/null ||
    { echo "ERROR: $name: CPU source pool $source_name is no longer active" >&2; exit 1; }
  # The generated provider is the source's, with the GPU instance type and a 200 GiB encrypted gp3 root volume.
  jq -n -e --argjson s "$source" --argjson e "$expected" --arg region "$region" '
    ($s.spec.template.spec.providerSpec.value) as $p
    | $p.placement.region == $region and ($p.capacityReservationId // "") == ""
    and ($p | .instanceType = $e.spec.template.spec.providerSpec.value.instanceType
            | .blockDevices[0].ebs += {volumeSize: 200, volumeType: "gp3", encrypted: true})
        == $e.spec.template.spec.providerSpec.value' >/dev/null ||
    { echo "ERROR: $name: provider differs from the active source (region, reservation or AMI); re-run generate-gpu-machineset.sh" >&2; exit 1; }
  live=$(oc --request-timeout=10s get machineset "$name" -n openshift-machine-api --ignore-not-found -o json)
  if [[ -n "$live" ]]; then
    jq -n -e --argjson l "$live" --argjson e "$expected" '($l.metadata.ownerReferences // [] | length) == 0
      and ($l.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("020-gpu-machinesets:"))
      and $l.spec.selector == $e.spec.selector and $l.spec.template == $e.spec.template' >/dev/null ||
      { echo "ERROR: $name: existing MachineSet is foreign, unadopted or differs from the reviewed source" >&2; exit 1; }
  fi
done
# 020-gpu-machinesets must hold a replica exception (ignoreDifferences) for every GPU MachineSet.
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$app_manifest" |
  jq -e --argjson ms "$machinesets" '([.spec.ignoreDifferences[]? | select(.kind == "MachineSet") | .name] | sort)
    == ([$ms[].metadata.name] | sort)' >/dev/null ||
  { echo "ERROR: 020-gpu-machinesets lacks a replica exception per GPU MachineSet (re-run generate-gpu-machineset.sh --write)" >&2; exit 1; }
echo "PASS $(jq length <<<"$machinesets") GPU MachineSets match their active CPU sources and carry replica exceptions"
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
# First change: the component Applications at the reviewed commit; deploy applies, syncs and waits for each.
python3 "$STAGE_APPS" deploy 020 --revision "$revision" --repo-url "$GIT_REPO_URL"
echo 'Stage 020 components reconciled; native Automatic operator reconciliation is bounded below.'
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai" --wait 900
