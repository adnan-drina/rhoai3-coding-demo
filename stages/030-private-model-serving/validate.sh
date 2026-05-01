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

log_step "Model Serving Project"
check "maas namespace exists" \
  "oc get namespace maas -o jsonpath='{.metadata.name}'" \
  "maas"
check "ai-admin has admin access to maas namespace" \
  "oc get rolebinding ai-admin-maas -n maas -o jsonpath='{.roleRef.name}{\" \"}{.subjects[0].name}'" \
  "admin ai-admin"
check "tier-to-group mapping includes premium tier" \
  "oc get configmap tier-to-group-mapping -n redhat-ods-applications -o jsonpath='{.data.tiers}'" \
  "premium"

log_step "Local model resources"
check "gpt-oss-20b resource exists" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "gpt-oss-20b"
check "nemotron-3-nano-30b-a3b resource exists" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.name}'" \
  "nemotron-3-nano-30b-a3b"
check "gpt-oss-20b exposes dashboard GenAI asset metadata" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.metadata.labels.opendatahub\\.io/genai-asset}{\" \"}{.metadata.annotations.security\\.opendatahub\\.io/enable-auth}'" \
  "true true"
check "nemotron-3-nano-30b-a3b exposes dashboard GenAI asset metadata" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.labels.opendatahub\\.io/genai-asset}{\" \"}{.metadata.annotations.security\\.opendatahub\\.io/enable-auth}'" \
  "true true"
check "gpt-oss-20b requests GPU resources" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.spec.template.containers[0].resources.requests.nvidia\\.com/gpu}'" \
  "1"
check "nemotron-3-nano-30b-a3b requests GPU resources" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.spec.template.containers[0].resources.requests.nvidia\\.com/gpu}'" \
  "1"
check "gpt-oss-20b targets MaaS Gateway" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.spec.router.gateway.refs[0].namespace}/{.spec.router.gateway.refs[0].name}'" \
  "openshift-ingress/maas-default-gateway"
check "nemotron-3-nano-30b-a3b targets MaaS Gateway" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.spec.router.gateway.refs[0].namespace}/{.spec.router.gateway.refs[0].name}'" \
  "openshift-ingress/maas-default-gateway"
check_warn "gpt-oss-20b ready" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check_warn "nemotron-3-nano-30b-a3b ready" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "Model Registry"
SEED_JOB_STATUS=$(oc get job model-registry-seed -n rhoai-model-registries -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "")
if [[ "$SEED_JOB_STATUS" == "1" ]]; then
  echo -e "${GREEN}[PASS]${NC} model-registry-seed job succeeded"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
elif [[ -z "$SEED_JOB_STATUS" ]]; then
  echo -e "${YELLOW}[INFO]${NC} model-registry-seed hook job is no longer present; validating durable registry contents instead"
else
  echo -e "${YELLOW}[WARN]${NC} model-registry-seed job status: ${SEED_JOB_STATUS}"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi
check "Model registry contains gpt-oss-20b" \
  "oc exec deployment/demo-registry -n rhoai-model-registries -- curl -sf http://localhost:8080/api/model_registry/v1alpha3/registered_models 2>/dev/null | python3 -c 'import json,sys; print(\"\\n\".join(item.get(\"name\", \"\") for item in json.load(sys.stdin).get(\"items\", [])))'" \
  "gpt-oss-20b"
check "Model registry contains nemotron-3-nano-30b-a3b" \
  "oc exec deployment/demo-registry -n rhoai-model-registries -- curl -sf http://localhost:8080/api/model_registry/v1alpha3/registered_models 2>/dev/null | python3 -c 'import json,sys; print(\"\\n\".join(item.get(\"name\", \"\") for item in json.load(sys.stdin).get(\"items\", [])))'" \
  "nemotron-3-nano-30b-a3b"
check_warn "Local model registry has at least two models" \
  "oc exec deployment/demo-registry -n rhoai-model-registries -- curl -sf http://localhost:8080/api/model_registry/v1alpha3/registered_models 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"size\"])'" \
  "2"

echo ""
validation_summary
