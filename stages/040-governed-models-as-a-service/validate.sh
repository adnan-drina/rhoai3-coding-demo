#!/usr/bin/env bash
# Stage 040: Governed Models-as-a-Service — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"
load_env

echo "Stage 040: Governed Models-as-a-Service — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "040-governed-models-as-a-service"

log_step "Operators"
check_csv_succeeded "rhcl-operator" "Connectivity Link"
check_csv_succeeded "openshift-operators" "cloudnative-pg"

log_step "MaaS CRDs"
check_crd_exists "maasmodelrefs.maas.opendatahub.io"
check_crd_exists "maasauthpolicies.maas.opendatahub.io"
check_crd_exists "maassubscriptions.maas.opendatahub.io"
check_crd_exists "externalmodels.maas.opendatahub.io"
check_crd_exists "configs.maas.opendatahub.io"
check_crd_exists "tenants.maas.opendatahub.io"

log_step "MaaS database"
check "MaaS Config anchor exists" \
  "oc get config.maas.opendatahub.io default -o jsonpath='{.metadata.name}'" \
  "default"
check "MaaS PostgreSQL cluster exists" \
  "oc get cluster maas-db -n redhat-ods-applications -o jsonpath='{.metadata.name}'" \
  "maas-db"
check "MaaS PostgreSQL write endpoint exists" \
  "oc get endpoints maas-db-rw -n redhat-ods-applications -o jsonpath='{.subsets[*].addresses[*].ip}'" \
  "."
check "MaaS database connection secret exists" \
  "oc get secret maas-db-config -n redhat-ods-applications -o jsonpath='{.metadata.name}'" \
  "maas-db-config"

log_step "Gateway and policy"
check "MaaS GatewayClass accepted" \
  "oc get gatewayclass openshift-default -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "MaaS Gateway exists" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "MaaS Gateway programmed" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Programmed\")].status}'" \
  "True"
check "MaaS Gateway hostname assigned" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[0].hostname}'" \
  "maas."
check "Kuadrant ready" \
  "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check "Authorino deployment ready" \
  "oc get deployment authorino -n kuadrant-system -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "Limitador deployment ready" \
  "oc get deployment limitador-limitador -n kuadrant-system -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "MaaS API"
check "Dashboard MaaS user and admin flags enabled" \
  "oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.modelAsService}{\" \"}{.spec.dashboardConfig.genAiStudio}{\" \"}{.spec.dashboardConfig.maasAuthPolicies}{\" \"}{.spec.dashboardConfig.vLLMDeploymentOnMaaS}'" \
  "true true true true"
check "Tenant-managed maas-api deployment ready" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "Tenant-managed maas-api endpoint ready" \
  "oc get endpoints maas-api -n redhat-ods-applications -o jsonpath='{.subsets[*].addresses[*].ip}'" \
  "."
check "RHOAI MaaS controller deployment ready" \
  "oc get deployment maas-controller -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "MaaS tenant active" \
  "oc get tenant default-tenant -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "MaaS tenant telemetry enabled" \
  "oc get tenant default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry.enabled}{\" \"}{.spec.telemetry.metrics.captureOrganization}{\" \"}{.spec.telemetry.metrics.captureModelUsage}'" \
  "true true true"
check "DataScienceCluster MaaS component ready" \
  "oc get dsc default-dsc -o jsonpath='{.status.conditions[?(@.type==\"ModelsAsServiceReady\")].status}'" \
  "True"
check "MaaS API route accepted" \
  "oc get httproute maas-api-route -n redhat-ods-applications -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "maas-api uses RHOAI 3.4 image" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].image}'" \
  "registry.redhat.io/rhoai/odh-maas-api-rhel9"

log_step "Local MaaS resources"
check "MaaSModelRef gpt-oss-20b ready" \
  "oc get maasmodelref gpt-oss-20b -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef nemotron-3-nano-30b-a3b ready" \
  "oc get maasmodelref nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSAuthPolicy local-models-access active" \
  "oc get maasauthpolicy local-models-access -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "MaaSSubscription demo-models-subscription active" \
  "oc get maassubscription demo-models-subscription -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "demo-models-subscription uses RHOAI demo groups" \
  "oc get maassubscription demo-models-subscription -n models-as-a-service -o jsonpath='{.spec.owner.groups[*].name}'" \
  "rhoai-users"
SUBSCRIPTION_GROUPS="$(oc get maassubscription demo-models-subscription -n models-as-a-service -o jsonpath='{.spec.owner.groups[*].name}' 2>/dev/null || true)"
if [[ "$SUBSCRIPTION_GROUPS" != *"tier-"* ]]; then
  echo -e "${GREEN}[PASS]${NC} demo-models-subscription no longer uses 3.3 tier groups"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  echo -e "${RED}[FAIL]${NC} demo-models-subscription no longer uses 3.3 tier groups"
  VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi
check "demo-models-subscription token limits ready" \
  "oc get maassubscription demo-models-subscription -n models-as-a-service -o jsonpath='{.status.tokenRateLimitStatuses[*].ready}'" \
  "true"
check "Playground token bridge uses demo subscription" \
  "oc get deployment tokens-bridge -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name==\"PLAYGROUND_MAAS_SUBSCRIPTION\")].value}'" \
  "demo-models-subscription"

USER_TOKEN="$(oc whoami -t 2>/dev/null || true)"
if [[ -n "$USER_TOKEN" ]]; then
  BRIDGE_RESPONSE=$(oc run "maas-bridge-key-smoke-$(date +%s)" \
    -n redhat-ods-applications \
    --restart=Never \
    --rm \
    -i \
    --quiet \
    --image=registry.access.redhat.com/ubi9/ubi-minimal \
    -- curl -s -X POST \
      -H "X-Forwarded-Access-Token: ${USER_TOKEN}" \
      -H "X-Forwarded-User: ai-developer" \
      -H 'X-Forwarded-Groups: rhoai-users,system:authenticated:oauth,system:authenticated' \
      -H "Content-Type: application/json" \
      --data '{"model":"nemotron-3-nano-30b-a3b","subscription":"demo-models-subscription"}' \
      http://tokens-bridge.redhat-ods-applications.svc:8080/v1/tokens 2>/dev/null || true)
  BRIDGE_KEY_LENGTH=$(printf '%s' "$BRIDGE_RESPONSE" | jq -r '((.key // "") | length)' 2>/dev/null || echo 0)
  BRIDGE_TOKEN_LENGTH=$(printf '%s' "$BRIDGE_RESPONSE" | jq -r '((.token // "") | length)' 2>/dev/null || echo 0)
  BRIDGE_DATA_KEY_LENGTH=$(printf '%s' "$BRIDGE_RESPONSE" | jq -r '((.data.key // "") | length)' 2>/dev/null || echo 0)
  BRIDGE_DATA_TOKEN_LENGTH=$(printf '%s' "$BRIDGE_RESPONSE" | jq -r '((.data.token // "") | length)' 2>/dev/null || echo 0)
  BRIDGE_KEY_ID=$(printf '%s' "$BRIDGE_RESPONSE" | jq -r '.id // .data.id // empty' 2>/dev/null || true)
  if (( BRIDGE_KEY_LENGTH > 0 && BRIDGE_TOKEN_LENGTH > 0 && BRIDGE_DATA_KEY_LENGTH > 0 && BRIDGE_DATA_TOKEN_LENGTH > 0 )); then
    echo -e "${GREEN}[PASS]${NC} Gen AI token bridge returns top-level and nested key/token fields"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} Gen AI token bridge returns top-level and nested key/token fields"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi
  if [[ -n "$BRIDGE_KEY_ID" ]]; then
    oc run "maas-bridge-key-cleanup-$(date +%s)" \
      -n redhat-ods-applications \
      --restart=Never \
      --rm \
      -i \
      --quiet \
      --image=registry.access.redhat.com/ubi9/ubi-minimal \
      -- curl -s -X DELETE \
        -H "Authorization: Bearer ${USER_TOKEN}" \
        -H "X-MaaS-Username: ai-developer" \
        -H 'X-MaaS-Group: ["rhoai-users","system:authenticated:oauth","system:authenticated"]' \
        "https://maas-api.redhat-ods-applications.svc:8443/v1/api-keys/${BRIDGE_KEY_ID}" \
        -k >/dev/null 2>&1 || true
  fi
else
  echo -e "${YELLOW}[WARN]${NC} Skipping token bridge key smoke test because no OpenShift user token is available"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Local model routing"
check "Per-route AuthPolicy for gpt-oss-20b" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-gpt-oss-20b"
check "AuthPolicy for gpt-oss-20b enforced" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "Per-route AuthPolicy for nemotron-3-nano-30b-a3b" \
  "oc get authpolicy maas-auth-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-nemotron-3-nano-30b-a3b"
check "AuthPolicy for nemotron-3-nano-30b-a3b enforced" \
  "oc get authpolicy maas-auth-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "HTTPRoute for gpt-oss-20b accepted" \
  "oc get httproute gpt-oss-20b-kserve-route -n maas -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "HTTPRoute for nemotron-3-nano-30b-a3b accepted" \
  "oc get httproute nemotron-3-nano-30b-a3b-kserve-route -n maas -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "TokenRateLimitPolicy for gpt-oss-20b accepted" \
  "oc get tokenratelimitpolicy maas-trlp-gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "TokenRateLimitPolicy for nemotron-3-nano-30b-a3b accepted" \
  "oc get tokenratelimitpolicy maas-trlp-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"

log_step "MaaS Observability Configuration"
check "Kuadrant ready for MaaS policy enforcement" \
  "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "GuideLLM load test"
if [[ "${GUIDELLM_SKIP_LOAD_TEST:-false}" == "true" ]]; then
  echo -e "${YELLOW}[WARN]${NC} GuideLLM load test skipped by GUIDELLM_SKIP_LOAD_TEST=true"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
elif "$SCRIPT_DIR/run-guidellm-load-test.sh"; then
  echo -e "${GREEN}[PASS]${NC} GuideLLM short MaaS load test completed"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  GUIDELLM_RC=$?
  if [[ "$GUIDELLM_RC" -eq 2 ]]; then
    echo -e "${YELLOW}[WARN]${NC} GuideLLM load test skipped because prerequisites are unavailable"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
  else
    echo -e "${RED}[FAIL]${NC} GuideLLM short MaaS load test failed"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi
fi

echo ""
validation_summary
