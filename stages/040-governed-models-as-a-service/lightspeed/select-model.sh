#!/usr/bin/env bash
# Select OpenShift Lightspeed's default model: qwen (the private primary, Git's default) or nemotron (the approved
# external fallback, for while Qwen is parked). Lightspeed has one default provider and no automatic failover, and
# Argo CD self-heals the OLSConfig, so the selection is a Kustomize patch on the 040-openshift-lightspeed Application,
# next to the provider URLs deploy.sh sets there: nemotron adds one patch replacing spec.ols.defaultProvider and
# defaultModel, qwen removes it. Changes only that Application's spec.source.kustomize.patches; the operator restarts
# the Lightspeed app server, and the script waits until the API is Ready. Safe to rerun; a Stage 040 deploy.sh run
# also returns to qwen. Selecting qwen while Qwen has no replicas is refused.
# Usage: stages/040-governed-models-as-a-service/lightspeed/select-model.sh qwen|nemotron [--timeout SECONDS]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

USAGE="Usage: stages/040-governed-models-as-a-service/lightspeed/select-model.sh qwen|nemotron [--timeout SECONDS]"
APP=040-openshift-lightspeed
GITOPS_NS=openshift-gitops
TIMEOUT=600
MODEL=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        qwen|nemotron) MODEL=$1; shift ;;
        --timeout) TIMEOUT=${2:-}; shift 2 ;;
        *) echo "$USAGE" >&2; exit 2 ;;
    esac
done
[[ -n "$MODEL" && "$TIMEOUT" =~ ^[0-9]+$ ]] || { echo "$USAGE" >&2; exit 2; }
case "$MODEL" in
    qwen) PROVIDER=qwen-maas; DEFAULT_MODEL=publishers/internal-models/models/qwen3-8-27b ;;
    nemotron) PROVIDER=nemotron-maas; DEFAULT_MODEL=nemotron-3-ultra-550b-a55b ;;
esac

load_env
check_oc_logged_in

# ── Preflight (read-only) ───────────────────────────────────────────────────────────────────────────────────────
app=$(oc --request-timeout=15s get applications.argoproj.io "$APP" -n "$GITOPS_NS" -o json) ||
    { log_error "Application $APP not found; deploy Stage 040 first"; exit 1; }
jq -e '[.spec.source.kustomize.patches[]? | select(.target.kind == "OLSConfig")] | length > 0' <<<"$app" >/dev/null ||
    { log_error "$APP has no deploy-time OLSConfig patch; run stages/040-governed-models-as-a-service/deploy.sh first"; exit 1; }
if [[ "$MODEL" == qwen ]]; then
    replicas=$(oc --request-timeout=15s get llminferenceservice qwen3-8-27b -n internal-models -o jsonpath='{.spec.replicas}')
    [[ "${replicas:-0}" -gt 0 ]] ||
        { log_error "Qwen is parked (replicas ${replicas:-0}); resume it before selecting it for Lightspeed"; exit 1; }
fi

# ── Selection: the deploy-time patches, minus any earlier default selection, plus the new one for the fallback ──
patches=$(jq -c --arg p "$PROVIDER" --arg m "$DEFAULT_MODEL" '
    def selection: .target.kind == "OLSConfig" and (.patch | contains("/spec/ols/defaultProvider"));
    [.spec.source.kustomize.patches[] | select(selection | not)]
    + (if $p == "qwen-maas" then [] else [{target: {group: "ols.openshift.io", version: "v1alpha1", kind: "OLSConfig",
        name: "cluster"}, patch: ([{op: "replace", path: "/spec/ols/defaultProvider", value: $p},
        {op: "replace", path: "/spec/ols/defaultModel", value: $m}] | tojson)}] end)' <<<"$app")
if [[ "$patches" == "$(jq -c '.spec.source.kustomize.patches' <<<"$app")" ]]; then
    log_info "$APP already selects $MODEL"
else
    jq -n -c --argjson p "$patches" '{spec: {source: {kustomize: {patches: $p}}}}' |
        oc --request-timeout=15s patch applications.argoproj.io "$APP" -n "$GITOPS_NS" --type merge --patch-file=/dev/stdin >/dev/null
    oc --request-timeout=15s annotate applications.argoproj.io "$APP" -n "$GITOPS_NS" argocd.argoproj.io/refresh=normal --overwrite >/dev/null
    log_success "$APP now selects $MODEL ($PROVIDER); Argo CD syncs it automatically"
fi

# ── Wait for Argo CD to apply the default, the app server to roll out and the API to report Ready ─────────────
log_step "Waiting up to ${TIMEOUT}s for Lightspeed to answer on $PROVIDER"
deadline=$((SECONDS + TIMEOUT))
olsconfig() { oc --request-timeout=15s get olsconfig cluster -o json 2>/dev/null || echo '{}'; }
until jq -e --arg p "$PROVIDER" --arg m "$DEFAULT_MODEL" '.spec.ols.defaultProvider == $p and .spec.ols.defaultModel == $m' \
    <<<"$(olsconfig)" >/dev/null; do
    [[ $SECONDS -lt $deadline ]] || { log_error "Argo CD did not apply the selection within ${TIMEOUT}s; check $APP"; exit 1; }
    sleep 10
done
oc rollout status deployment/lightspeed-app-server -n openshift-lightspeed --timeout="$((deadline > SECONDS ? deadline - SECONDS : 1))s" ||
    { log_error "lightspeed-app-server did not become ready; see docs/TROUBLESHOOTING.md (Lightspeed API unready)"; exit 1; }
until olsconfig | jq -e '. as $ols | any(.status.conditions[]?; .type == "ApiReady" and .status == "True"
    and .observedGeneration == $ols.metadata.generation)' >/dev/null; do
    [[ $SECONDS -lt $deadline ]] || { log_error "OLSConfig ApiReady is not True after ${TIMEOUT}s"; exit 1; }
    sleep 10
done
log_success "OpenShift Lightspeed default is $PROVIDER / $DEFAULT_MODEL and its API is Ready"
