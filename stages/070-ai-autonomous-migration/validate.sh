#!/usr/bin/env bash
# Stage 070: MTA — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 070: Autonomous Application Migration (MTA 8.1)     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "070-ai-autonomous-migration"

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

log_step "OpenShift OAuth Federation"
check "OAuthClient mta-keycloak exists" \
  "oc get oauthclient mta-keycloak -o jsonpath='{.metadata.name}'" \
  "mta-keycloak"
check "OAuthClient mta-keycloak grant method is auto" \
  "oc get oauthclient mta-keycloak -o jsonpath='{.grantMethod}'" \
  "auto"

OAUTH_REDIRECT=$(oc get oauthclient mta-keycloak -o jsonpath='{.redirectURIs[0]}' 2>/dev/null || echo "")
if [[ -n "$OAUTH_REDIRECT" ]] && [[ "$OAUTH_REDIRECT" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} OAuthClient redirect URI: ${OAUTH_REDIRECT}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} OAuthClient redirect URI is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

MTA_ROUTE_HOST=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE_HOST" ]]; then
    IDP_CHECK=$(curl -sk "https://${MTA_ROUTE_HOST}/auth/realms/mta/protocol/openid-connect/auth?client_id=mta-ui&response_type=code&redirect_uri=https://${MTA_ROUTE_HOST}" 2>/dev/null \
      | grep -c 'social-openshift' || echo "0")
    if [[ "$IDP_CHECK" -ge 1 ]]; then
        echo -e "${GREEN}[PASS]${NC} MTA login page shows 'Log in with OpenShift'"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} OpenShift IdP not visible on MTA login page"
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

log_step "Agentic migration workspace (Wave 2)"
check "agentic-migration DevWorkspace exists" \
  "oc get devworkspace agentic-migration -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "agentic-migration"
check "workspace clones the migiq sample" \
  "oc get devworkspace agentic-migration -n wksp-ai-developer -o jsonpath='{.spec.template.projects[0].git.remotes.origin}'" \
  "migiq-spring-boot-sample"
# The provisioning hook deletes itself on success (HookSucceeded policy);
# the durable evidence is the Secret and a live authorization check.
check "elevated key authenticates against the governed gateway" \
  "KEY=\$(oc get secret maas-agentic-migration-key -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_KEY}' | base64 -d); HOST=\$(oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[0].hostname}'); curl -sk -o /dev/null -w '%{http_code}' -H \"Authorization: Bearer \$KEY\" \"https://\$HOST/models-as-a-service/qwen3-6-35b-a3b/v1/models\"" \
  "200"
check "elevated MaaS key Secret exists" \
  "oc get secret maas-agentic-migration-key -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "maas-agentic-migration-key"

echo ""
validation_summary
