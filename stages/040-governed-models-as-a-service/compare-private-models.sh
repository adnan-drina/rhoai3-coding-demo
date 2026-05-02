#!/usr/bin/env bash
# Run the same short GuideLLM profile against the private MaaS-published models.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

usage() {
    cat <<'EOF'
Usage:
  stages/040-governed-models-as-a-service/compare-private-models.sh

Runs the Stage 040 GuideLLM load-test wrapper against each private model
listed in GUIDELLM_COMPARE_MODELS.

Defaults:
  GUIDELLM_COMPARE_MODELS   gpt-oss-20b nemotron-3-nano-30b-a3b
  GUIDELLM_PROFILE          constant
  GUIDELLM_RATE             1
  GUIDELLM_MAX_SECONDS      20
  GUIDELLM_REQUESTS         5
  GUIDELLM_OUTPUT_TOKENS    64

The wrapper stores each run as a labeled ConfigMap in the maas namespace.
Use summarize-guidellm-results.sh to list the latest comparison evidence.
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

GUIDELLM_COMPARE_MODELS="${GUIDELLM_COMPARE_MODELS:-gpt-oss-20b nemotron-3-nano-30b-a3b}"

log_step "Stage 040 private model comparison"
for model in $GUIDELLM_COMPARE_MODELS; do
    log_info "Running GuideLLM comparison profile for ${model}"
    "$SCRIPT_DIR/run-guidellm-load-test.sh" "$model"
done

log_step "Latest GuideLLM results"
"$SCRIPT_DIR/summarize-guidellm-results.sh"
