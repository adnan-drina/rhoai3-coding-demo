#!/usr/bin/env bash
# Verifies, or with --seed creates, the reviewed sample prompt governed-code-review (two versions) in the curated
# global MLflow workspace and in demo-sandbox, through the shipped MLflow dashboard backend. No inference. Existing
# versions must match the reviewed text; another owner's prompt is refused. --persona-kubeconfig (read-only) also proves
# that a developer sees the curated prompt as global and read-only in Gen AI Studio and cannot curate it.
# Usage: stages/050-model-evaluation/prompts.sh --expected-revision SHA [--seed | --persona-kubeconfig FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"

GLOBAL=ai-curated-prompts
LOCAL=demo-sandbox
NAME=governed-code-review
OWNER=rhoai3-coding-demo
TEMPLATE_1='Review the supplied {{language}} code. Explain correctness and security issues without inventing test results.'
TEMPLATE_2='Review the supplied {{language}} code. Explain correctness and security issues without inventing test results. Separate observed evidence from assumptions.'
REVISION="" SEED=false PERSONA=""
fail() { echo "[FAIL] $*" >&2; exit 1; }
while [[ $# -gt 0 ]]; do
    case "$1" in
        --expected-revision) REVISION=${2:-}; shift 2 ;;
        --seed) SEED=true; shift ;;
        --persona-kubeconfig) PERSONA=${2:-}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || fail "Supply the reviewed published 40-character Stage 050 revision"
[[ -z "$PERSONA" || "$SEED" == false ]] || fail "Curated seed uses an administrator; persona mode is read-only"
load_env >/dev/null
check_oc_logged_in >/dev/null || fail "OpenShift login/expected-server guard failed"
if [[ -n "$PERSONA" ]]; then
    KUBECONFIG="$PERSONA" bash -c 'source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in' guard "$REPO_ROOT" >/dev/null 2>&1 ||
        fail "Persona login/expected-server guard failed"
fi
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" status 050 --revision "$REVISION" --repo-url "$GIT_REPO_URL" >/dev/null 2>&1 ||
    fail "Exact native stage Application source/readiness guard failed"
[[ $(oc --request-timeout=15s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.globalMLflowNamespaces}') == "[\"$GLOBAL\"]" ]] ||
    fail "Native global prompt namespace differs from the dedicated curated workspace"
[[ $(oc --request-timeout=15s get namespace "$GLOBAL" -o jsonpath='{.metadata.labels.opendatahub\.io/global-mlflow-workspace}') == mlflow ]] ||
    fail "Native global workspace reconciliation label is missing"

WORK=$(mktemp -d)
oc --request-timeout=15s get configmap mlflow-service-ca -n redhat-ods-applications -o jsonpath='{.data.service-ca\.crt}' >"$WORK/ca.crt"
trap 'while read -r p; do kill "$p" 2>/dev/null && wait "$p" 2>/dev/null; done <"$WORK/pids"; rm -rf "$WORK"' EXIT
: >"$WORK/pids"
# Port-forward a dashboard backend Service; sets HOST and PORT for api().
backend() {
    HOST="$1.redhat-ods-applications.svc"
    oc port-forward -n redhat-ods-applications "service/$1" ":$2" --address=127.0.0.1 >"$WORK/forward-$1.log" 2>&1 &
    echo "$!" >>"$WORK/pids"
    PORT=""
    for _ in $(seq 1 75); do
        PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward-$1.log" | head -1)
        [[ -n "$PORT" ]] && return 0
        sleep 0.2
    done
    fail "Native backend port-forward unavailable ($1)"
}
# METHOD PATH [JSON]: the response .data on success; the caller's token reaches curl only through --config on stdin.
api() {
    local status token
    token=$(oc --request-timeout=15s ${PERSONA:+--kubeconfig "$PERSONA"} whoami --show-token)
    status=$(printf 'header = "x-forwarded-access-token: %s"\n' "$token" |
        curl --config - -s --max-time 70 --max-filesize 2097152 --cacert "$WORK/ca.crt" --resolve "$HOST:$PORT:127.0.0.1" \
            -X "$1" -H 'Content-Type: application/json' ${3:+--data "$3"} -D "$WORK/headers" -o "$WORK/body" -w '%{http_code}' \
            "https://$HOST:$PORT$2" || echo 000)
    [[ "$status" =~ ^20[014]$ ]] || fail "Native API returned HTTP $status"
    ! grep -qi '^X-MLflow-BFF-Unavailable: *true' "$WORK/headers" || fail "Native MLflow BFF unavailable; an empty-list fallback is not success"
    jq -c '.data' "$WORK/body"
}
prompts_path() { jq -rn --arg w "$1" --arg s "${2:-}" --arg q "${3:-}" '"/mlflow/api/v1/prompts\($s)?workspace=\($w | @uri)\($q)"'; }

receipts='[]'
backend odh-dashboard-mlflow-ui 8343
for workspace in "$GLOBAL" "$LOCAL"; do
    listing=$(api GET "$(prompts_path "$workspace" "" "&filter_name=$NAME")")
    jq -e '((.failed_namespaces // []) | length) == 0 and ((.next_page_token // "") == "")' <<<"$listing" >/dev/null ||
        fail "Prompt discovery is incomplete or a configured namespace is unauthorized"
    existing=$(jq -r --arg n "$NAME" --arg w "$workspace" '[.prompts[]? | select(.name == $n and .scope.namespace == $w and .scope.type == "project")]
        | if length > 1 then "duplicate" elif length == 1 then .[0].latest_version else "0" end' <<<"$listing")
    [[ "$existing" != duplicate ]] || fail "Duplicate scoped sample prompt discovery"
    if (( existing > 0 )); then
        # Registration tags live on the PromptVersion; the list's registered-model tags can legitimately be empty.
        [[ $(api GET "$(prompts_path "$workspace" "/$NAME" "&version=1")" | jq -r '.tags["demo.owner"] // ""') == "$OWNER" ]] ||
            fail "Existing sample version belongs to another owner; refusing append"
    fi
    for version in 1 2; do
        template=$TEMPLATE_1; [[ $version == 2 ]] && template=$TEMPLATE_2
        if (( version > existing )); then
            [[ "$SEED" == true ]] || fail "Reviewed prompt versions are not registered; run the explicit --seed after deployment"
            created=$(api POST "$(prompts_path "$workspace")" "$(jq -n -c --arg n "$NAME" --arg t "$template" --arg o "$OWNER" --argjson v "$version" \
                '{name: $n, template: $t, commit_message: "Reviewed public demo instructions version \($v)", tags: {"demo.owner": $o}, create_only: ($v == 1)}')")
            [[ $(jq -r '.version | tonumber' <<<"$created") == "$version" ]] || fail "Concurrent prompt registration changed the expected version sequence"
        fi
        api GET "$(prompts_path "$workspace" "/$NAME" "&version=$version")" | jq -e --arg t "$template" --arg o "$OWNER" --argjson v "$version" \
            '.template == $t and (.version | tonumber) == $v and .tags["demo.owner"] == $o' >/dev/null ||
            fail "Persisted prompt version differs from the reviewed public instructions"
        receipts=$(jq -c --arg w "$workspace" --arg n "$NAME" --argjson v "$version" --arg sha "$(printf '%s' "$template" | shasum -a 256 | cut -d' ' -f1)" \
            '. + [{workspace: $w, name: $n, version: $v, template_sha256: $sha}]' <<<"$receipts")
    done
done
if [[ -n "$PERSONA" ]]; then
    backend odh-dashboard-gen-ai-ui 8143
    api GET "/api/v1/mlflow/prompts?namespace=$LOCAL" | jq -e --arg n "$NAME" --arg g "$GLOBAL" '[.prompts[]?
        | select(.name == $n and .scope.namespace == $g and .scope.type == "global")] | length == 1 and .[0].scope.read_only == true' >/dev/null ||
        fail "Studio did not expose the curated prompt as globally read-only"
    for version in 1 2; do
        template=$TEMPLATE_1; [[ $version == 2 ]] && template=$TEMPLATE_2
        api GET "/api/v1/mlflow/prompts/$NAME?namespace=$LOCAL&workspace=$GLOBAL&version=$version" | jq -e --arg t "$template" '.template == $t' >/dev/null ||
            fail "Studio global prompt load differs from the retained version"
    done
    [[ $(oc --kubeconfig "$PERSONA" auth can-i create registeredmodels.mlflow.kubeflow.org -n "$GLOBAL" 2>/dev/null || true) == no ]] ||
        fail "Developer global curation denial was not verified"
fi
jq -n -c --argjson p "$receipts" '{scope: "native prompt registration/load/version persistence", prompts: $p}'
