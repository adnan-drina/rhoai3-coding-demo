#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS — Validation Script
# Validates RHOAI 3.4 operator-native MaaS deployment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Step 03: LLM Serving + MaaS — Validation"
echo ""

log_step "ArgoCD Application"
check_argocd_app "step-03-llm-serving-maas"

log_step "Operators"
check_csv_succeeded "rhcl-operator" "Connectivity Link"
check_csv_succeeded "openshift-operators" "cloudnative-pg"

log_step "Gateway"
check "MaaS Gateway exists" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"

log_step "Kuadrant"
check "Kuadrant ready" \
  "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "MaaS API (operator-managed)"
check_pods_ready "redhat-ods-applications" "app.kubernetes.io/name=maas-api" 1
check "tier-to-group-mapping ConfigMap exists" \
  "oc get configmap tier-to-group-mapping -n redhat-ods-applications -o jsonpath='{.metadata.name}'" \
  "tier-to-group-mapping"

log_step "Models"
check "gpt-oss-20b ready" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check "nemotron-3-nano-30b-a3b ready" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check_pods_ready "maas" "serving.kserve.io/llminferenceservice=gpt-oss-20b" 1
check_pods_ready "maas" "serving.kserve.io/llminferenceservice=nemotron-3-nano-30b-a3b" 1

log_step "Tier RBAC (auto-created by tiers annotation)"
check "gpt-oss-20b RoleBindings exist" \
  "oc get rolebindings -n maas --no-headers 2>/dev/null | grep -c gpt-oss-20b" \
  "1"
check_warn "nemotron-3-nano-30b-a3b RoleBindings exist" \
  "oc get rolebindings -n maas --no-headers 2>/dev/null | grep -c nemotron-3-nano-30b-a3b" \
  "1"

log_step "MaaS Gateway API"
GATEWAY_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[?(@.name=="https")].hostname}' 2>/dev/null || echo "")
if [ -n "$GATEWAY_HOST" ]; then
  echo -e "${GREEN}[PASS]${NC} Gateway hostname: $GATEWAY_HOST"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  echo -e "${YELLOW}[WARN]${NC} No HTTPS listener found on gateway"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "MCP Servers"
check_warn "OpenShift MCP running" \
  "oc get pods -n coding-assistant -l app=openshift-mcp --no-headers 2>/dev/null | grep -c Running" \
  "1"
check_warn "Slack MCP running" \
  "oc get pods -n coding-assistant -l app=slack-mcp --no-headers 2>/dev/null | grep -c Running" \
  "1"
check_warn "BrightData MCP running" \
  "oc get pods -n coding-assistant -l app=brightdata-mcp --no-headers 2>/dev/null | grep -c Running" \
  "1"
check "MCP ConfigMap exists" \
  "oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.metadata.name}'" \
  "gen-ai-aa-mcp-servers"

log_step "MaaS API Models"
GATEWAY_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[?(@.name=="https")].hostname}' 2>/dev/null || echo "")
if [ -n "$GATEWAY_HOST" ]; then
  TOKEN=$(oc whoami -t 2>/dev/null || echo "")
  if [ -n "$TOKEN" ]; then
    MODEL_COUNT=$(curl -sk -H "Authorization: Bearer $TOKEN" "https://${GATEWAY_HOST}/v1/models" 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("data") or []))' 2>/dev/null || echo "0")
    if [ "$MODEL_COUNT" = "2" ]; then
      echo -e "${GREEN}[PASS]${NC} MaaS API lists 2 models"
      VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
      echo -e "${YELLOW}[WARN]${NC} MaaS API lists ${MODEL_COUNT} models (expected 2)"
      VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
  else
    echo -e "${YELLOW}[WARN]${NC} No auth token available for MaaS API test"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
  fi
else
  echo -e "${YELLOW}[WARN]${NC} Gateway hostname not found, skipping MaaS API model count"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Model Registry"
check "Models registered" \
  "oc exec deployment/demo-registry -n rhoai-model-registries -- curl -sf http://localhost:8080/api/model_registry/v1alpha3/registered_models 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"size\"])'" \
  "2"

log_step "Grafana"
check_pods_ready "grafana" "app=grafana" 1

echo ""
validation_summary
