#!/usr/bin/env bash
# Stage 080: MTA — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 080: Autonomous Application Migration (MTA 8.2)     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_argocd_app "050-advanced-app-platform"

log_step "MTA Operator"
check_csv_succeeded "openshift-mta" "mta-operator"

log_step "MTA Instance"
check "Tackle CR exists" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta"
check "Tackle LLM proxy enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_proxy_enabled}'" \
  "true"
check "Tackle Solution Server enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_solution_server_enabled}'" \
  "true"
check "Tackle hub auth enabled (built-in OIDC provider)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.feature_auth_required}'" \
  "true"
check "Tackle idp_primary auto-redirect enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.idp_primary}'" \
  "true"
check "Tackle LLM provider is OpenAI-compatible" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_provider}'" \
  "openai"
check "Tackle LLM model is private MaaS model" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_model}'" \
  "nemotron-3-nano-30b-a3b"
check "Tackle LLM base URL uses MaaS route" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_baseurl}'" \
  "/models-as-a-service/nemotron-3-nano-30b-a3b/v1"

log_step "MTA Core Deployments"
check "mta-ui deployment ready" \
  "oc get deployment mta-ui -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "mta-hub deployment ready" \
  "oc get deployment mta-hub -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "Red Hat Developer Lightspeed (AI)"
check "kai-api deployment ready" \
  "oc get deployment kai-api -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "llm-proxy deployment ready" \
  "oc get deployment llm-proxy -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "Tackle AI Conditions"
check_tackle_condition() {
    local condition="$1"
    local status=""
    for _ in $(seq 1 30); do
        status=$(oc get tackle mta -n openshift-mta \
          -o jsonpath="{.status.conditions[?(@.type==\"${condition}\")].status}" 2>/dev/null || echo "")
        if [[ "$status" == "True" ]]; then
            echo -e "${GREEN}[PASS]${NC} Tackle ${condition}"
            VALIDATE_PASS=$((VALIDATE_PASS + 1))
            return
        fi
        sleep 5
    done
    echo -e "${RED}[FAIL]${NC} Tackle ${condition} (expected: True, got: ${status:-empty})"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
}

check_tackle_condition "KaiAPIKeysConfigured"
check_tackle_condition "LLMProxyReady"
check_tackle_condition "KaiSolutionServerReady"

log_step "MaaS Credentials (non-placeholder)"
check_secret_value "OPENAI_API_BASE" "openshift-mta" "kai-api-keys" "OPENAI_API_BASE"
check_secret_value "OPENAI_API_KEY" "openshift-mta" "kai-api-keys" "OPENAI_API_KEY"

log_step "Platform SSO Federation (built-in Hub OIDC)"
check "IdentityProvider platform-sso exists" \
  "oc get identityprovider platform-sso -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "platform-sso"
check "IdentityProvider issuer targets the platform realm" \
  "oc get identityprovider platform-sso -n openshift-mta -o jsonpath='{.spec.issuer}' | grep -c '/realms/platform' || echo 0" \
  "1"
check "IdP client Secret exists" \
  "oc get secret mta-idp-client-secret -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta-idp-client-secret"
MTA_ROUTE_HOST=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE_HOST" ]]; then
    check_http_code "Hub OIDC discovery" \
      "https://${MTA_ROUTE_HOST}/oidc/.well-known/openid-configuration" "200"
    HUB_ANON=$(curl -sk -H "Accept: application/json" -o /dev/null -w '%{http_code}' "https://${MTA_ROUTE_HOST}/hub/applications" 2>/dev/null || echo "000")
    if [[ "$HUB_ANON" == "401" ]]; then
        echo -e "${GREEN}[PASS]${NC} Hub API enforces authentication (HTTP 401 unauthenticated)"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} Hub API does not enforce authentication (HTTP ${HUB_ANON}, expected 401)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
fi

log_step "MTA UI Route"
MTA_ROUTE=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE" ]]; then
    check_http_code "MTA UI: https://${MTA_ROUTE}" "https://${MTA_ROUTE}" "200,302"
else
    echo -e "${YELLOW}[WARN]${NC} MTA UI route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "ConsoleLink"
MTA_CL_HREF=$(oc get consolelink mta -o jsonpath='{.spec.href}' 2>/dev/null || echo "")
if [[ -n "$MTA_CL_HREF" ]] && [[ "$MTA_CL_HREF" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} MTA ConsoleLink: ${MTA_CL_HREF}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} MTA ConsoleLink href is placeholder or missing"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Modernization Workspaces (mta component)"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "mca-coolstore workspace exists: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o jsonpath='{.metadata.name}'" \
        "mca-coolstore"
    check "mca-coolstore workspace declares Kilo Code and MTA default extensions: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q '/tmp/kilo.vsix;/tmp/mta.vsix;/tmp/mta-core.vsix;/tmp/mta-java.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA VS Code extension 8.2.0: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-vscode-extension-8.2.0.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA core extension 8.2.0: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-core-8.2.0.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA Java extension 8.2.0: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-java-8.2.0.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace sets HUB_URL to the internal hub service: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'mta-ui.openshift-mta.svc.cluster.local:8080' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace sets FORCE_HUB_ENABLED: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'FORCE_HUB_ENABLED' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace sets HUB_INSECURE: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'HUB_INSECURE' && echo present || echo missing" \
        "present"
    check "mta-hub-config ConfigMap exists with MTA hub URL: $ns" \
        "oc get configmap mta-hub-config -n $ns -o jsonpath='{.data.MTA_HUB_URL}' 2>/dev/null | grep -c 'https://' || echo 0" \
        "1"
done

log_step "Pre-Demo Readiness"
MAAS_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress \
  -o jsonpath='{.spec.listeners[0].hostname}' 2>/dev/null || echo "")
MAAS_KEY_VAL=$(oc get secret kai-api-keys -n openshift-mta \
  -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
if [[ -n "$MAAS_HOST" ]] && [[ "$MAAS_KEY_VAL" == sk-oai-* ]]; then
    MAAS_HTTP=$(curl -sk -H "Authorization: Bearer ${MAAS_KEY_VAL}" \
      "https://${MAAS_HOST}/models-as-a-service/nemotron-3-nano-30b-a3b/v1/models" \
      -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    if [[ "$MAAS_HTTP" == "200" ]]; then
        echo -e "${GREEN}[PASS]${NC} MaaS auth works with kai-api-keys key (HTTP ${MAAS_HTTP})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} MaaS auth failed with kai-api-keys key (HTTP ${MAAS_HTTP})"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
else
    echo -e "${RED}[FAIL]${NC} Cannot test MaaS auth (host=${MAAS_HOST:-missing}, key starts with ${MAAS_KEY_VAL:0:7}...)"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

check_warn "llm-proxy has real OPENAI_API_KEY" \
  "oc exec deployment/llm-proxy -n openshift-mta -- printenv OPENAI_API_KEY 2>/dev/null | grep -c '^sk-oai-'" \
  "1"

check "MTA Hub deployment ready" \
  "oc get deployment mta-hub -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

echo ""
validation_summary
