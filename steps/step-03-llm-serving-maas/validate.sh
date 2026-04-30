#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS — Validation Script
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

log_step "Models"
check "gpt-oss-20b ready" \
  "oc get llminferenceservice gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check "nemotron-3-nano-30b-a3b ready" \
  "oc get llminferenceservice nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check_pods_ready "maas" "app.kubernetes.io/name=gpt-oss-20b" 1
check_pods_ready "maas" "app.kubernetes.io/name=nemotron-3-nano-30b-a3b" 1

log_step "MaaS API (upstream)"
check "Tenant-managed maas-api deployment ready" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "maas-api owned by upstream tenant reconciler" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.metadata.labels.maas\\.opendatahub\\.io/tenant-name}'" \
  "default-tenant"
check "maas-api uses models-as-a-service policy namespace" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name==\"MAAS_SUBSCRIPTION_NAMESPACE\")].value}'" \
  "models-as-a-service"
check "maas-api uses upstream image with ExternalModel discovery" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].image}'" \
  "quay.io/opendatahub/maas-api:latest"
check_pods_ready "redhat-ods-applications" "control-plane=maas-controller" 1
check_pods_ready "redhat-ods-applications" "app=postgres" 1

log_step "MaaS Gateway API"
GATEWAY_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[?(@.name=="https")].hostname}' 2>/dev/null || echo "")
if [ -n "$GATEWAY_HOST" ]; then
  echo -e "${GREEN}[PASS]${NC} Gateway hostname: $GATEWAY_HOST"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  echo -e "${YELLOW}[WARN]${NC} No HTTPS listener found on gateway"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "ExternalModels"
check "ExternalModel gpt-4o exists" \
  "oc get externalmodel gpt-4o -n maas -o jsonpath='{.spec.provider}'" \
  "openai"
check "ExternalModel gpt-4o-mini exists" \
  "oc get externalmodel gpt-4o-mini -n maas -o jsonpath='{.spec.provider}'" \
  "openai"
check "MaaSModelRef gpt-4o ready" \
  "oc get maasmodelref gpt-4o -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef gpt-4o-mini ready" \
  "oc get maasmodelref gpt-4o-mini -n maas -o jsonpath='{.status.phase}'" \
  "Ready"

log_step "MaaS CRDs (upstream)"
check "MaaSAuthPolicy all-models-access active" \
  "oc get maasauthpolicy all-models-access -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "MaaSSubscription all-models-subscription active" \
  "oc get maassubscription all-models-subscription -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"

log_step "Governance"
check "Per-route AuthPolicy for gpt-oss-20b" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-gpt-oss-20b"
check "Per-route AuthPolicy for gpt-4o" \
  "oc get authpolicy maas-auth-gpt-4o -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-gpt-4o"

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
    MODELS_JSON=$(curl -sk -H "Authorization: Bearer $TOKEN" "https://${GATEWAY_HOST}/maas-api/v1/models" 2>/dev/null || echo "{}")
    MODEL_NAMES=$(printf '%s' "$MODELS_JSON" | python3 -c 'import json,sys; print("\n".join(sorted(m.get("id","") for m in (json.load(sys.stdin).get("data") or []))))' 2>/dev/null || true)
    if printf '%s\n' "$MODEL_NAMES" | grep -qx "gpt-oss-20b" && \
       printf '%s\n' "$MODEL_NAMES" | grep -qx "nemotron-3-nano-30b-a3b" && \
       printf '%s\n' "$MODEL_NAMES" | grep -qx "gpt-4o" && \
       printf '%s\n' "$MODEL_NAMES" | grep -qx "gpt-4o-mini"; then
      echo -e "${GREEN}[PASS]${NC} MaaS API lists 4 models (2 local + 2 external)"
      VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
      echo -e "${YELLOW}[WARN]${NC} MaaS API model list missing expected entries: ${MODEL_NAMES:-none}"
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
