#!/usr/bin/env bash
# Summarize GuideLLM result ConfigMaps created by Stage 040 load tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

usage() {
    cat <<'EOF'
Usage:
  stages/040-governed-models-as-a-service/summarize-guidellm-results.sh [model-name]

Lists the latest GuideLLM result ConfigMaps and their normalized run metadata.
The detailed console summary remains in each ConfigMap as summary.log.
EOF
}

case "${1:-}" in
    -h|--help|help)
        usage
        exit 0
        ;;
esac

load_env
check_oc_logged_in

GUIDELLM_NAMESPACE="${GUIDELLM_NAMESPACE:-maas}"
MODEL_FILTER="${1:-}"

selector="app.kubernetes.io/name=guidellm-load-test"
if [[ -n "$MODEL_FILTER" ]]; then
    model_safe="$(echo "$MODEL_FILTER" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/--*/-/g; s/^-//; s/-$//')"
    selector="${selector},demo.rhoai.io/model=${model_safe}"
fi

if ! oc get namespace "$GUIDELLM_NAMESPACE" >/dev/null 2>&1; then
    log_error "Namespace ${GUIDELLM_NAMESPACE} does not exist"
    exit 1
fi

results_json="$(oc get configmap -n "$GUIDELLM_NAMESPACE" -l "$selector" -o json 2>/dev/null || true)"
count="$(jq '.items | length' <<<"$results_json" 2>/dev/null || echo 0)"
if [[ "$count" -eq 0 ]]; then
    log_warn "No GuideLLM result ConfigMaps found in ${GUIDELLM_NAMESPACE}"
    exit 2
fi

jq -r '
  (["CREATED", "CONFIGMAP", "MODEL", "PROFILE", "RATE", "REQUESTS", "OUTPUT_TOKENS"] | @tsv),
  (.items
    | sort_by(.metadata.creationTimestamp)
    | reverse
    | .[:10][]
    | [
        .metadata.creationTimestamp,
        .metadata.name,
        (.data.model // ""),
        (.data.profile // ""),
        (.data.rate // ""),
        (.data.requests // ""),
        (.data["output-tokens"] // "")
      ] | @tsv)' <<<"$results_json" | column -t

echo ""
echo "Detailed summaries:"
jq -r '
  .items
  | sort_by(.metadata.creationTimestamp)
  | reverse
  | .[:3][]
  | "- " + .metadata.namespace + "/" + .metadata.name + " contains summary.log"
' <<<"$results_json"
