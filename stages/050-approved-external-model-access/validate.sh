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
check "ExternalModel gpt-4o-mini exists" \
  "oc get externalmodel gpt-4o-mini -n maas -o jsonpath='{.spec.provider}'" \
  "openai"
check "MaaSModelRef gpt-4o ready" \
  "oc get maasmodelref gpt-4o -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef gpt-4o-mini ready" \
  "oc get maasmodelref gpt-4o-mini -n maas -o jsonpath='{.status.phase}'" \
  "Ready"

log_step "External model subscriptions"
check "MaaSAuthPolicy external-models-access active" \
  "oc get maasauthpolicy external-models-access -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "MaaSSubscription external-models-subscription active" \
  "oc get maassubscription external-models-subscription -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"

log_step "Credential placeholder check"
OPENAI_SECRET=$(oc get secret openai-api-key -n maas -o jsonpath='{.data.api-key}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
if [[ -n "$OPENAI_SECRET" ]] && [[ "$OPENAI_SECRET" != "REPLACE_WITH_OPENAI_API_KEY" ]]; then
    echo -e "${GREEN}[PASS]${NC} openai-api-key contains a non-placeholder value"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} openai-api-key is placeholder or missing; external inference is not validated"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

echo ""
validation_summary
