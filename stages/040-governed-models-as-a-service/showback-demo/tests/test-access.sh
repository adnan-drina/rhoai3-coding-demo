#!/usr/bin/env bash
# Offline access-contract tests; no network or cluster calls.
set -euo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$TEST_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
bash "$DEMO_DIR/render-access.sh" > "$work/preview.json"
bash "$DEMO_DIR/render-access.sh" --write "$work/manifests"
for file in "$work/manifests"/*.yaml; do
    yaml_json < "$file" | jq -ce 'if length==1 then .[0] else error("multiple resources in one file") end'
done | jq -s . > "$work/resources.json"
jq -e --slurpfile preview "$work/preview.json" 'sort_by(.kind,.metadata.name)==($preview[0]|sort_by(.kind,.metadata.name))' \
    "$work/resources.json" >/dev/null
jq -e '
 length==6 and ([.[]|select(.kind=="MaaSSubscription")]|length)==3 and
 ([.[]|select(.kind=="MaaSAuthPolicy")|.spec.modelRefs[]]|length)==4 and
 all(.[];.apiVersion=="maas.opendatahub.io/v1alpha1" and .metadata.namespace=="models-as-a-service") and
 ([.[]|select(.kind=="MaaSSubscription" and .metadata.name=="team-engineering")|
   .spec.owner.users[0],.spec.modelRefs[0].name,.spec.modelRefs[0].tokenRateLimits[0].limit] ==
   ["showback-engineering","qwen3-8-27b",700000]) and
 ([.[]|select(.kind=="MaaSAuthPolicy" and .metadata.name=="team-marketing")|.spec.modelRefs[].name] ==
   ["mistral-small4-119b"]) and
 ([.[]|select(.kind=="MaaSSubscription" and .metadata.name=="team-support")|
   .spec.modelRefs[].tokenRateLimits[0].limit] == [300000,300000]) and
 all(.[]; (.spec.tokenMetadata.costCenter // .spec.meteringMetadata.costCenter)==.metadata.labels["demo.rhoai.io/team"] and
   .metadata.labels["app.kubernetes.io/part-of"]=="maas" and .metadata.labels["app.kubernetes.io/managed-by"]=="argocd")
' "$work/resources.json" >/dev/null
bash "$DEMO_DIR/render-access.sh" --check "$DEMO_DIR/manifests"
bash "$DEMO_DIR/render-access.sh" --check "$work/manifests"
printf '\n' >> "$work/manifests/team-support-auth-policy.yaml"
if bash "$DEMO_DIR/render-access.sh" --check "$work/manifests" >/dev/null 2>&1; then
    printf '%s\n' 'FAIL: generated drift accepted' >&2
    exit 1
fi
for mutation in \
    '.teams.engineering.models["qwen3-8-27b"].token_limit=-1' \
    '.teams.engineering.models["unknown-model"]={token_limit:10,window:"1h"}' \
    '.teams.marketing.models["qwen3-8-27b"]={token_limit:10,window:"1h"}' \
    '.teams.support.user=.teams.engineering.user' \
    '.models["qwen3-8-27b"].namespace=null'; do
    jq "$mutation" "$DEMO_DIR/scenario.json" > "$work/invalid.json"
    if bash "$DEMO_DIR/render-access.sh" --scenario "$work/invalid.json" > "$work/invalid.json.out" 2>/dev/null; then
        printf 'FAIL: invalid access scenario accepted: %s\n' "$mutation" >&2
        exit 1
    fi
    [[ ! -s "$work/invalid.json.out" ]]
    if bash "$DEMO_DIR/render-access.sh" --scenario "$work/invalid.json" --write "$work/invalid" >/dev/null 2>&1; then
        printf '%s\n' 'FAIL: invalid access scenario written' >&2
        exit 1
    fi
    [[ ! -e "$work/invalid" ]]
done
printf '%s\n' 'Access tests passed: one resource per file, four allowed/two denied pairs, quotas, labels, reproducibility and invalid input.'
