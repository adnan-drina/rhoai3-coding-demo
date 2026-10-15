#!/usr/bin/env bash
# Read-only: refuse foreign agent catalog content before the Stage 030 Application write. The desired ConfigMap must
# hold exactly the reviewed source and the two metadata-only agent cards; an existing one must be ours, or the
# installer's empty customer source (the only shape that may be adopted).
# Usage: stages/030-private-model-serving/preflight-agent-catalog.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

NAME=agent-catalog-sources
NS=rhoai-model-registries
DESIRED="$REPO_ROOT/gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/agent-catalog-sources.yaml"
fail() { echo "[FAIL] $*"; exit 1; }
# A ConfigMap as JSON with each data value parsed from YAML.
parse_data() { ruby -ryaml -rjson -e 'cm = JSON.parse(STDIN.read)
    cm["parsed"] = (cm["data"] || {}).transform_values { |v| YAML.safe_load(v) }
    puts JSON.generate(cm)'; }

desired=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$DESIRED" | parse_data)
jq -e '.data | keys == ["governed-coding-agents.yaml", "sources.yaml"]' <<<"$desired" >/dev/null ||
    fail "Desired catalog file inventory differs"
jq -e '.parsed["sources.yaml"] == {agent_catalogs: [{id: "governed-coding-agents", name: "Governed Coding Agents",
    type: "yaml", enabled: true, properties: {yamlCatalogPath: "governed-coding-agents.yaml"}, labels: ["coding"]}]}' \
    <<<"$desired" >/dev/null || fail "Desired source ID/path/schema differs"
jq -e '.parsed["governed-coding-agents.yaml"].agents // [] | length == 2
    and (map({key: .name, value: .displayName}) | from_entries) == {opencode: "OpenCode", hermes: "Hermes"}
    and all(.[]; (.readme // "") != "" and (.templates | not) and (.artifacts | not))' <<<"$desired" >/dev/null ||
    fail "Desired agent cards must be the two reviewed metadata-only entries"

if [[ -z "$(oc --request-timeout=10s get namespace "$NS" --ignore-not-found -o name)" ]]; then
    echo "[PASS] Agent catalog namespace absent; clean installation"
    exit 0
fi
existing=$(oc --request-timeout=10s get configmap "$NAME" -n "$NS" --ignore-not-found -o json)
if [[ -n "$existing" ]]; then
    jq -e '(.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null and (.immutable | not)' \
        <<<"$existing" >/dev/null || fail "Catalog configuration is native-owned, terminating, or immutable"
    tracking=$(jq -r '.metadata.annotations["argocd.argoproj.io/tracking-id"] // ""' <<<"$existing")
    if [[ "$tracking" != "030-private-model-serving:/ConfigMap:$NS/$NAME" ]]; then
        [[ -z "$tracking" ]] && jq -e '(.binaryData | not) and (.data | keys) == ["sources.yaml"]' <<<"$existing" >/dev/null ||
            fail "Foreign catalog configuration requires reviewed merge"
        parse_data <<<"$existing" | jq -e '.parsed["sources.yaml"] == {agent_catalogs: []}' >/dev/null ||
            fail "Existing custom agent sources cannot be overwritten"
    fi
fi
echo "[PASS] Agent catalog source ownership/content preflight"
