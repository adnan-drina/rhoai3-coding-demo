#!/usr/bin/env bash
# Native Gen AI Studio API through its own backend (BFF), which owns playground, agent-profile and guardrail
# provisioning; this never edits its generated deployments or database. Tokens stay in memory; output carries no
# payloads. Contract: deployed odh-dashboard f4a81e89bf8a1fb0bbe3dfdc7b10eaa39b3d7439 (the BFF image is pinned below).
#   (default)                     read-only status GET
#   --install-model MODEL_ID      create a new retained playground for one MaaS model (never replaces one)
#   --qualify-agents MODEL_ID     save/load two disposable owned agent profiles, check foreign denial, clean them up
#   --initialize-guardrails       native guardrail initialization (no model calls)
# Usage: stages/040-governed-models-as-a-service/studio-api.sh --expected-revision SHA [ACTION] [--persona-kubeconfig FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"

NS=demo-sandbox
UI_NS=redhat-ods-applications
UI_HOST=odh-dashboard-gen-ai-ui.redhat-ods-applications.svc
SOURCE_IMAGE=registry.redhat.io/rhoai/odh-mod-arch-gen-ai-rhel9@sha256:9fccbc4215f2c3c792eeaa5a4081826fe4e6cbeb69d5f9aa4572ad06c4b2aecc
REVISION="" ACTION=status MODEL="" PERSONA=""
fail() { echo "[FAIL] $*"; exit 1; }
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
while [[ $# -gt 0 ]]; do
    case "$1" in
        --expected-revision) REVISION=${2:-}; shift 2 ;;
        --install-model) [[ "$ACTION" == status ]] || usage; ACTION=install; MODEL=${2:-}; shift 2 ;;
        --qualify-agents) [[ "$ACTION" == status ]] || usage; ACTION=qualify; MODEL=${2:-}; shift 2 ;;
        --initialize-guardrails) [[ "$ACTION" == status ]] || usage; ACTION=guardrails; shift ;;
        --persona-kubeconfig) PERSONA=${2:-}; shift 2 ;;
        *) usage ;;
    esac
done
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || fail "Supply the reviewed published 40-character stage revision"
load_env >/dev/null
check_oc_logged_in >/dev/null || fail "OpenShift login/expected-server guard failed; renew approved access before continuing"
if [[ -n "$PERSONA" ]]; then
    KUBECONFIG="$PERSONA" bash -c 'source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in' guard "$REPO_ROOT" >/dev/null 2>&1 ||
        fail "Persona login/expected-server guard failed"
fi
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" status 040 --revision "$REVISION" --repo-url "$GIT_REPO_URL" >/dev/null 2>&1 ||
    fail "Exact native stage Application source/readiness guard failed"
[[ $(oc --request-timeout=15s get deployment gen-ai-ui -n "$UI_NS" -o jsonpath='{.spec.template.spec.containers[0].image}') == "$SOURCE_IMAGE" ]] ||
    fail "GenAI BFF image differs from the reviewed API source contract"

# BFF over a port-forward, TLS verified with the service CA for its service name; the caller token is the persona's
# (or the bootstrap session's) and reaches curl only through --config on stdin.
TOKEN=$(oc --request-timeout=15s ${PERSONA:+--kubeconfig "$PERSONA"} whoami --show-token)
WORK=$(mktemp -d)
oc --request-timeout=15s get configmap mlflow-service-ca -n "$UI_NS" -o jsonpath='{.data.service-ca\.crt}' >"$WORK/ca.crt"
oc port-forward -n "$UI_NS" service/odh-dashboard-gen-ai-ui :8143 --address=127.0.0.1 >"$WORK/forward.log" 2>&1 &
FORWARD=$!
trap 'kill "$FORWARD" 2>/dev/null && wait "$FORWARD" 2>/dev/null; rm -rf "$WORK"' EXIT
for _ in $(seq 1 75); do
    PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward.log" | head -1)
    [[ -n "$PORT" ]] && break
    sleep 0.2
done
[[ -n "${PORT:-}" ]] || fail "Native BFF port-forward unavailable"
# METHOD PATH [JSON]: prints the HTTP status; the body goes to $WORK/body. Error bodies are never printed.
bff() {
    local status
    status=$(printf 'header = "x-forwarded-access-token: %s"\n' "$TOKEN" |
        curl --config - -s --max-time 70 --max-filesize 2097152 --cacert "$WORK/ca.crt" --resolve "$UI_HOST:$PORT:127.0.0.1" \
            -X "$1" -H 'Content-Type: application/json' ${3:+--data "$3"} -D "$WORK/headers" -o "$WORK/body" -w '%{http_code}' \
            "https://$UI_HOST:$PORT/api/v1/$2" || echo 000)
    grep -qi '^X-MLflow-BFF-Unavailable: *true' "$WORK/headers" 2>/dev/null &&
        fail "Native MLflow BFF unavailable; an empty-list fallback is not success"
    echo "$status"
}
# Like bff but requires a 2xx status; prints the JSON body.
bff_ok() { local s; s=$(bff "$@"); [[ "$s" =~ ^20[014]$ ]] || { echo "HTTP $s" >&2; return 1; }; cat "$WORK/body"; }
q() { jq -rn --arg ns "${2:-$NS}" --arg p "$1" '"\($p)?namespace=\($ns | @uri)"'; }

case "$ACTION" in
status)
    bff_ok GET "$(q lsd/status)" | jq -c '{scope: "native Studio status GET", response_present: (.data != null)}' ;;
install)
    [[ -z "$(oc --request-timeout=15s get ogxservers.ogx.io -n "$NS" -o name)" ]] ||
        fail "Playground already exists; preserve its state and use read-only validation"
    created=$(bff_ok POST "$(q lsd/install)" "$(jq -n -c --arg m "$MODEL" '{models: [{model_name: $m, model_source_type: "maas",
        model_type: "llm", max_tokens: 128}], enable_tracing: true}')") || fail "Native playground install request failed"
    name=$(jq -r '.data.name' <<<"$created")
    # Attach the stage-owned retained PVC before the new playground is used.
    oc --request-timeout=15s get pvc genai-playground-state -n "$NS" -o json | jq -e '.metadata.deletionTimestamp == null
        and .metadata.annotations["argocd.argoproj.io/tracking-id"] == "040-genai-studio:/PersistentVolumeClaim:demo-sandbox/genai-playground-state"' \
        >/dev/null || fail "Native playground persistence requires the stage-owned retained PVC"
    for attempt in $(seq 1 30); do
        instances=$(oc --request-timeout=15s get ogxservers.ogx.io -n "$NS" -o json)
        [[ $(jq '.items | length' <<<"$instances") -gt 0 ]] && break
        (( attempt < 30 )) || fail "Native playground creation did not produce its customer CR"
        sleep 1
    done
    jq -e --arg n "$name" '(.items | length) == 1 and .items[0].metadata.deletionTimestamp == null and .items[0].metadata.name == $n
        and ((.items[0].spec.workload.overrides // {}) | (.volumes // []) == [] and (.volumeMounts // []) == [])' <<<"$instances" >/dev/null ||
        fail "New playground identity is ambiguous or it already has customer mounts; no persistence change applied"
    current=$(jq -c '.items[0]' <<<"$instances")
    spec=$(jq -c '.spec | .workload.overrides.volumes = [{name: "retained-sqlite", persistentVolumeClaim: {claimName: "genai-playground-state"}}]
        | .workload.overrides.volumeMounts = [{name: "retained-sqlite", mountPath: "/opt/app-root/src/.llama/distributions/rh"}]' <<<"$current")
    saved=$(jq -c --argjson s "$spec" '[{op: "test", path: "/metadata/uid", value: .metadata.uid},
        {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
        {op: "test", path: "/spec", value: .spec}, {op: "replace", path: "/spec", value: $s}]' <<<"$current" |
        oc --request-timeout=15s patch ogxserver "$name" -n "$NS" --type=json --patch-file=/dev/stdin -o json) ||
        fail "Native persistence attachment failed; the playground must not be used until corrected"
    jq -e --argjson c "$current" --argjson s "$spec" '.metadata.uid == $c.metadata.uid and .spec == $s' <<<"$saved" >/dev/null ||
        fail "Native playground persistence readback differs"
    echo "[PASS] Native retained playground creation requested with opt-in tracing; readiness and spans still require qualification." ;;
guardrails)
    [[ $(oc --request-timeout=15s get odhdashboardconfig odh-dashboard-config -n "$UI_NS" -o jsonpath='{.spec.dashboardConfig.guardrails}') == true ]] ||
        fail "Native Studio guardrails flag must be enabled by its stage owner first"
    existing=$(oc --request-timeout=15s get nemoguardrails.trustyai.opendatahub.io -n "$NS" -o json | jq -c '[.items[].metadata.name]')
    if [[ "$existing" == '[]' ]]; then
        bff_ok POST "$(q nemo-guardrails/init)" '{}' >/dev/null || fail "Native guardrail initialization failed"
    elif [[ "$existing" != '["nemoguardrails"]' ]]; then
        fail "Unexpected guardrail resources; refusing competing provisioning"
    fi
    echo "[PASS] Native Studio guardrail initialization retained; model-backed input/output qualification remains separate." ;;
qualify)
    [[ -n "$PERSONA" ]] || fail "Agent qualification requires an explicit developer persona kubeconfig"
    # GenAI flattens the inter-BFF MaaS envelope into {object, data: [...]}.
    url=$(bff_ok GET "$(q maas/models)" | jq -r --arg m "$MODEL" '[.data[] | select(.id == $m and .ready)] | if length == 1 then .[0].url else "" end')
    [[ -n "$url" ]] || fail "Selected governed model is not uniquely available to this persona"
    preexisting=$(bff_ok GET "$(q agent-profiles)" | jq -c '[.data.profiles[].profileId]')
    RUN=$(openssl rand -hex 6)
    # Private identity/content snapshot of a fixture's ConfigMap (uid, resourceVersion, data digest); no payload.
    record() {
        local cm
        cm=$(oc --request-timeout=15s get configmap "agent-profile-$1" -n "$NS" -o json) || return 1
        jq -e --arg n "agent-profile-$1" --arg ns "$NS" '.metadata as $m | $m.name == $n and $m.namespace == $ns
            and ($m.ownerReferences // [] | length) == 0 and ($m.finalizers // [] | length) == 0 and $m.deletionTimestamp == null
            and $m.labels["opendatahub.io/agent-profile"] == "true"' <<<"$cm" >/dev/null || return 1
        printf '%s %s %s' "$(jq -r '.metadata.uid' <<<"$cm")" "$(jq -r '.metadata.resourceVersion' <<<"$cm")" \
            "$(jq -cS '.data // {}' <<<"$cm" | shasum -a 256 | cut -d' ' -f1)"
    }
    : >"$WORK/owned"
    receipts='[]'
    FAILURE=""
    for variant in false true; do
        spec=$(jq -n -c --arg run "$RUN" --argjson v "$variant" --arg m "$MODEL" --arg u "$url" --arg ns "$NS" '{
            displayName: ("Qualification code review " + $run + (if $v then " variant" else "" end)),
            description: "Disposable owned qualification fixture", model: {id: $m, uri: $u, sourceType: "maas"},
            prompt: {name: "governed-code-review", source: "mlflow", namespace: $ns, version: "2"},
            maxOutputTokens: 128, temperature: (if $v then 0.1 else 0 end), stream: true}')
        id=$(bff_ok POST "$(q agent-profiles)" "$(jq -c '{spec: .}' <<<"$spec")" | jq -r '.data.profileId') || { FAILURE="create failed"; break; }
        [[ "$id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] && ! jq -e --arg i "$id" 'index($i)' <<<"$preexisting" >/dev/null &&
            ! grep -q "^$id " "$WORK/owned" || { FAILURE="Native create returned a foreign or duplicate fixture ID; adoption refused"; break; }
        echo "$id $(jq -c . <<<"$spec" | base64 | tr -d '\n') -" >>"$WORK/owned"  # journal the returned ID before further reads
        snapshot=$(record "$id") || { FAILURE="Foreign agent fixture record"; break; }
        sed -i '' "s|^$id \(.*\) -\$|$id \1 $(base64 <<<"$snapshot" | tr -d '\n')|" "$WORK/owned"
        bff_ok GET "$(q "agent-profiles/$id")" | jq -e --arg i "$id" --argjson s "$spec" '.data.metadata.name == $i and .data.spec == $s' >/dev/null ||
            { FAILURE="Persisted owned agent configuration differs; refusing overwrite"; break; }
        receipts=$(jq -c --arg i "$id" --argjson v "$variant" '. + [{profile_id: $i, variant: $v, persisted: true}]' <<<"$receipts")
    done
    # MLflow global read access must not confer access to another project's agent configuration.
    if [[ -z "$FAILURE" ]]; then
        status=$(bff GET "$(q agent-profiles ai-curated-prompts)")
        [[ "$status" == 403 ]] || FAILURE="Persona can access a foreign agent configuration namespace (HTTP $status)"
    fi
    # Cleanup: recheck identity and content immediately before DELETE (it has no precondition), then prove absence.
    deleted='[]' retained='[]'
    while read -r id spec_b64 snapshot_b64; do
        [[ -n "$id" ]] || continue
        status=$(bff GET "$(q "agent-profiles/$id")")
        if [[ "$status" == 404 ]]; then deleted=$(jq -c --arg i "$id" '. + [$i]' <<<"$deleted"); continue; fi
        spec=$(base64 -d <<<"$spec_b64")
        if [[ "$status" != 200 || "$snapshot_b64" == - ]] || ! jq -e --arg i "$id" --argjson s "$spec" '.data.metadata.name == $i and .data.spec == $s' \
            "$WORK/body" >/dev/null || [[ "$(record "$id" 2>/dev/null)" != "$(base64 -d <<<"$snapshot_b64")" ]]; then
            retained=$(jq -c --arg i "$id" '. + [{profile_id: $i, reason: "Identity/content guard failed; review this retained fixture."}]' <<<"$retained")
            continue
        fi
        bff DELETE "$(q "agent-profiles/$id")" >/dev/null
        if [[ $(bff GET "$(q "agent-profiles/$id")") == 404 ]]; then
            deleted=$(jq -c --arg i "$id" '. + [$i]' <<<"$deleted")
        else
            retained=$(jq -c --arg i "$id" '. + [{profile_id: $i, reason: "Native cleanup or absence verification failed."}]' <<<"$retained")
        fi
    done <"$WORK/owned"
    jq -n -c --arg run "$RUN" --argjson p "$receipts" --argjson d "$deleted" --argjson r "$retained" '{
        scope: "disposable agent persistence and foreign-namespace denial; no inference", run_id: $run, profiles: $p,
        cleanup: {deleted_ids: $d, retained: $r},
        cleanup_boundary: "Immediate identity/content recheck; native DELETE has no atomic precondition."}'
    [[ "$retained" == '[]' ]] || fail "Qualification left guarded fixtures for review; exact IDs are in the cleanup receipt"
    [[ -z "$FAILURE" ]] || fail "$FAILURE" ;;
esac
