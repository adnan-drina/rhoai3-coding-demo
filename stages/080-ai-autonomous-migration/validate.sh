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
check "Tackle LLM proxy disabled (Lightspeed off until needed)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_proxy_enabled}'" \
  "false"
check "Tackle Solution Server disabled (Lightspeed off until needed)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_solution_server_enabled}'" \
  "false"
check "Tackle hub auth enabled (built-in OIDC provider)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.feature_auth_required}'" \
  "true"
check "Tackle idp_primary auto-redirect enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.idp_primary}'" \
  "true"

log_step "MTA Core Deployments"
check "mta-ui deployment ready" \
  "oc get deployment mta-ui -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "mta-hub deployment ready" \
  "oc get deployment mta-hub -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

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

log_step "Migration Golden Path (app-migration template)"
check "app-migration template Location in the runtime catalog" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -c 'templates/app-migration/template.yaml' || echo 0" \
  "1"
check "runtime catalog Location revision is not the placeholder" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -c '__RHOAI3_DEMO_REVISION__' || echo 0" \
  "0"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GOLDEN_SHA=$(gh api repos/adnan-drina/quarkus-migration-scaffold/git/refs/heads/main --jq '.object.sha' 2>/dev/null || echo "")
    if [[ -n "$GOLDEN_SHA" ]]; then
        echo -e "${GREEN}[PASS]${NC} quarkus-migration-scaffold golden repo exists (${GOLDEN_SHA:0:12})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} quarkus-migration-scaffold golden repo missing (run scripts/bootstrap-scaffold-repos.sh)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} gh not available — skipping golden repo check"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Harness Tooling (Session 0 — init script contract)"
# The migration golden path's workspaces (PROFILE=modernized) get the
# harness orchestrator + sensor tooling from the shared init ConfigMap:
# Hermes CLI (idempotent PVC install, MaaS-wired) and the lazy kantra
# sensor helper (~690MB zip — deliberately NOT downloaded at postStart).
check "init script installs the Hermes Agent CLI" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes-agent.nousresearch.com/install.sh' || echo 0" \
  "1"
check "init script seats the M2 orchestrator default" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'custom:maas-m2' || echo 0" \
  "1"
check "init script keeps the local 27B fallback orchestrator" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'custom:maas-qwen27b' || echo 0" \
  "1"
check "init script ships the kantra-ensure lazy sensor helper (pinned)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'KANTRA_VERSION=\"v0.10.0-beta.1\"' || echo 0" \
  "1"
check "kantra-ensure download message is on stderr (ensure_cli captures stdout as the CLI path)" \
  "grep -c 'Downloading kantra.*>&2' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "harness tooling is gated on the modernized profile" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'PROFILE}\" = \"modernized\"' || echo 0" \
  "1"
# AD-H §14 — SOUL.md is the sole judgement-doctrine carrier; init must
# abort on missing/empty/hash mismatch and smoke-test Hermes load+scan.
check "init script hash-verifies SOUL.md and aborts (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'SOUL.md hash mismatch after placement' || echo 0" \
  "1"
check "init script load-time SOUL smoke via load_soul_md (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'from agent.prompt_builder import load_soul_md' || echo 0" \
  "1"

log_step "Modernization Workspaces (mta component)"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "mca-coolstore workspace exists: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o jsonpath='{.metadata.name}'" \
        "mca-coolstore"
    # Manifest presence only — does not assert Che-Code activation (Operator E-20260817T104424Z).
    check "mca-coolstore workspace declares Kilo Code and MTA default extensions: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q '/tmp/kilo.vsix;/tmp/mta.vsix;/tmp/mta-core.vsix;/tmp/redhat-java.vsix;/tmp/mta-java.vsix' && echo present || echo missing" \
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
    check "mca-coolstore workspace downloads redhat.java 1.47.0 (mta-java dependency): $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.java-1.47.0.vsix' && echo present || echo missing" \
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

echo ""
validation_summary

# Shared worker skills must not drift between the 070 and 080 scaffolds —
# they are one contract expressed in two repos.
for f in spec-driven-workflow project-test-standards quarkus-rest-conventions llm-integration; do
  check "shared skill in sync across scaffolds: ${f}" \
    "diff -q '${SCRIPT_DIR}/../070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold/.opencode/skills/${f}.md' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.opencode/skills/${f}.md' >/dev/null 2>&1 && echo 1 || echo 0" \
    "1" "warn"
done
