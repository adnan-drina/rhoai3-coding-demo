#!/usr/bin/env bash
# Stage 030: Private Model Serving — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 030: Private Model Serving — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "030-private-model-serving"

log_step "LeaderWorkerSet"
check_crd_exists "leaderworkersets.leaderworkerset.x-k8s.io"

log_step "Local model resources"
check "gpt-oss-20b resource exists" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "gpt-oss-20b"
check "nemotron-3-nano-30b-a3b resource exists" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.name}'" \
  "nemotron-3-nano-30b-a3b"
check_warn "gpt-oss-20b ready" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check_warn "nemotron-3-nano-30b-a3b ready" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "Model Registry"
check_warn "Local models registered" \
  "oc exec deployment/demo-registry -n rhoai-model-registries -- curl -sf http://localhost:8080/api/model_registry/v1alpha3/registered_models 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"size\"])'" \
  "2"

echo ""
validation_summary
