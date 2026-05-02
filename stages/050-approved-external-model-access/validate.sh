#!/usr/bin/env bash
# Stage 050: Approved External Model Access — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 050: Approved External Model Access — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "050-approved-external-model-access"

log_step "ExternalModels"
check "ExternalModel gpt-4o exists" \
  "oc get externalmodel gpt-4o -n maas -o jsonpath='{.spec.provider}'" \
  "openai"
check "ExternalModel gpt-4o points at OpenAI endpoint" \
  "oc get externalmodel gpt-4o -n maas -o jsonpath='{.spec.endpoint}{\" \"}{.spec.credentialRef.name}{\" \"}{.spec.targetModel}'" \
  "api.openai.com openai-api-key gpt-4o"
check "ExternalModel gpt-4o-mini exists" \
  "oc get externalmodel gpt-4o-mini -n maas -o jsonpath='{.spec.provider}'" \
  "openai"
check "ExternalModel gpt-4o-mini points at OpenAI endpoint" \
  "oc get externalmodel gpt-4o-mini -n maas -o jsonpath='{.spec.endpoint}{\" \"}{.spec.credentialRef.name}{\" \"}{.spec.targetModel}'" \
  "api.openai.com openai-api-key gpt-4o-mini"
check "MaaSModelRef gpt-4o ready" \
  "oc get maasmodelref gpt-4o -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef gpt-4o targets ExternalModel" \
  "oc get maasmodelref gpt-4o -n maas -o jsonpath='{.spec.modelRef.kind}/{.spec.modelRef.name}'" \
  "ExternalModel/gpt-4o"
check "MaaSModelRef gpt-4o-mini ready" \
  "oc get maasmodelref gpt-4o-mini -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef gpt-4o-mini targets ExternalModel" \
  "oc get maasmodelref gpt-4o-mini -n maas -o jsonpath='{.spec.modelRef.kind}/{.spec.modelRef.name}'" \
  "ExternalModel/gpt-4o-mini"

log_step "External model subscriptions"
check "MaaSAuthPolicy external-models-access active" \
  "oc get maasauthpolicy external-models-access -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "External AuthPolicy generated for gpt-4o" \
  "oc get authpolicy maas-auth-gpt-4o -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "External AuthPolicy generated for gpt-4o-mini" \
  "oc get authpolicy maas-auth-gpt-4o-mini -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "MaaSSubscription external-models-subscription active" \
  "oc get maassubscription external-models-subscription -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "External subscription token limits ready" \
  "oc get maassubscription external-models-subscription -n models-as-a-service -o jsonpath='{.status.tokenRateLimitStatuses[*].ready}'" \
  "true"
check "External TokenRateLimitPolicy for gpt-4o accepted" \
  "oc get tokenratelimitpolicy maas-trlp-gpt-4o -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "External TokenRateLimitPolicy for gpt-4o-mini accepted" \
  "oc get tokenratelimitpolicy maas-trlp-gpt-4o-mini -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"

log_step "Credential placeholder check"
OPENAI_SECRET=$(oc get secret openai-api-key -n maas -o jsonpath='{.data.api-key}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
OPENAI_SECRET_LC=$(printf '%s' "$OPENAI_SECRET" | tr '[:upper:]' '[:lower:]')
if [[ -n "$OPENAI_SECRET" ]] && [[ "$OPENAI_SECRET_LC" != *"replace"* ]] && [[ "$OPENAI_SECRET_LC" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} openai-api-key contains a non-placeholder value"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} openai-api-key is placeholder or missing; external inference is not validated"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "External inference boundary"
if [[ "${GUIDELLM_EXTERNAL_SMOKE_TEST:-false}" == "true" ]]; then
    if [[ -n "$OPENAI_SECRET" ]] && [[ "$OPENAI_SECRET_LC" != *"replace"* ]] && [[ "$OPENAI_SECRET_LC" != *"placeholder"* ]]; then
        echo -e "${YELLOW}[INFO]${NC} Running opt-in GuideLLM smoke test against gpt-4o-mini through MaaS"
        MAAS_HOST="$(oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[0].hostname}' 2>/dev/null || true)"
        USER_TOKEN="$(oc whoami -t 2>/dev/null || true)"
        EXTERNAL_MAAS_API_KEY=""
        if [[ -n "$MAAS_HOST" && -n "$USER_TOKEN" && "$MAAS_HOST" != *placeholder* ]]; then
            EXTERNAL_MAAS_API_KEY="$(curl -sk -X POST \
                -H "Authorization: Bearer ${USER_TOKEN}" \
                -H "Content-Type: application/json" \
                -d "{\"name\":\"stage050-external-smoke-$(date -u +%Y%m%d%H%M%S)\",\"subscription\":\"external-models-subscription\"}" \
                "https://${MAAS_HOST}/maas-api/v1/api-keys" 2>/dev/null \
                | python3 -c 'import json,sys; print(json.load(sys.stdin).get("key",""))' 2>/dev/null || true)"
        fi
        if [[ "$EXTERNAL_MAAS_API_KEY" != sk-oai-* ]]; then
            echo -e "${RED}[FAIL]${NC} Could not create MaaS API key for external-models-subscription"
            VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
            echo ""
            validation_summary
            exit 1
        fi
        GUIDELLM_REQUESTS="${GUIDELLM_REQUESTS:-1}" \
        GUIDELLM_MAX_SECONDS="${GUIDELLM_MAX_SECONDS:-20}" \
        GUIDELLM_OUTPUT_TOKENS="${GUIDELLM_OUTPUT_TOKENS:-32}" \
        GUIDELLM_PROMPT="${GUIDELLM_PROMPT:-Explain one operational difference between private and external AI models.}" \
        GUIDELLM_API_KEY="$EXTERNAL_MAAS_API_KEY" \
        GUIDELLM_VALIDATE_BACKEND=false \
        "$REPO_ROOT/stages/040-governed-models-as-a-service/run-guidellm-load-test.sh" gpt-4o-mini
        echo -e "${GREEN}[PASS]${NC} Opt-in external MaaS inference smoke test completed"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} External inference smoke test requested, but openai-api-key is placeholder or missing"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
else
    echo -e "${YELLOW}[INFO]${NC} External inference smoke test skipped; set GUIDELLM_EXTERNAL_SMOKE_TEST=true to run it"
fi

echo ""
validation_summary
