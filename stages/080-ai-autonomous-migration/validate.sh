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
    GOLDEN_V2_SHA=$(gh api repos/adnan-drina/quarkus-migration-scaffold-v2/git/refs/heads/main --jq '.object.sha' 2>/dev/null || echo "")
    if [[ -n "$GOLDEN_V2_SHA" ]]; then
        echo -e "${GREEN}[PASS]${NC} quarkus-migration-scaffold-v2 golden repo exists (${GOLDEN_V2_SHA:0:12})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} quarkus-migration-scaffold-v2 golden repo missing (run scripts/bootstrap-migration-scaffold-v2.sh)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} gh not available — skipping golden repo check"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Harness Tooling (Session 0 — init script contract)"
# The migration golden path's workspaces (PROFILE=modernized) get the
# harness orchestrator + sensor tooling from the shared init ConfigMap:
# overlay-baked Hermes CLI (no curl install.sh) and the lazy kantra
# sensor helper (~690MB zip — deliberately NOT downloaded at postStart).
check "live init ConfigMap uses overlay-baked Hermes CLI" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes_bin=\"/usr/local/bin/hermes\"' || echo 0" \
  "1"
check "live init ConfigMap does not curl-install Hermes" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes-agent.nousresearch.com/install.sh' || echo 0" \
  "0"
check "init script pins Hermes main model to qwen3-6-27b" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"default\": \"qwen3-6-27b\"' || echo 0" \
  "1"
check "init script names the Hermes Qwen provider qwen27b" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"provider\": \"qwen27b\"' || echo 0" \
  "2"
check "init script sets Hermes api_mode chat_completions" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"api_mode\": \"chat_completions\"' || echo 0" \
  "1"
check "init script disables Hermes /models discovery on named providers" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"discover_models\": False' || echo 0" \
  "2"
check "GitOps init script does not use legacy custom:maas-m2 default" \
  "grep -c 'custom:maas-m2' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo NONE" \
  "NONE"
check "GitOps init script forbids Hermes fallback_providers" \
  "grep -c 'forbids fallback_providers' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "init script ships the kantra-ensure lazy sensor helper (pinned)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'KANTRA_VERSION=\"v0.10.0-beta.1\"' || echo 0" \
  "1"
check "kantra-ensure download message is on stderr (ensure_cli captures stdout as the CLI path)" \
  "grep -c 'Downloading kantra.*>&2' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "init ConfigMap is DWO-mounted (volume, not kube-API curl as the primary path)" \
  "grep -c 'controller.devfile.io/mount-to-devworkspace' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
SCAFFOLD_080="$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
check "v2 scaffold has no dispatch-phase package" \
  "test ! -e \"$SCAFFOLD_080/.hermes/skills/harness/dispatch-phase\" && echo 1 || echo 0" \
  "1"
check "v2 scaffold has no .hermes/home/scripts" \
  "test ! -e \"$SCAFFOLD_080/.hermes/home/scripts\" && echo 1 || echo 0" \
  "1"
check "v2 scaffold has no handover-mint.py" \
  "test -d \"$SCAFFOLD_080\" && test -z \"$(find \"$SCAFFOLD_080\" -name handover-mint.py -print -quit 2>/dev/null)\" && echo 1 || echo 0" \
  "1"
check "v2 Hermes config template is present" \
  "test -f \"$SCAFFOLD_080/.hermes/config/config.yaml.template\" && echo 1 || echo 0" \
  "1"
check "v2 config template forbids fallback_providers" \
  "grep -c 'OBJECT: fallback_providers' \"$SCAFFOLD_080/.hermes/config/config.yaml.template\" || echo 0" \
  "1"
check "inventory-type-graph imports type_graph as a module (no tree walk)" \
  "grep -c '_find_type_graph' \"$SCAFFOLD_080/.hermes/skills/analysis/inventory-entry-points/scripts/inventory-type-graph.py\" || echo NONE" \
  "NONE"
check "check-phase-matrix.py is not in the golden scaffold" \
  "test ! -f \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/check-phase-matrix.py\" && echo 1 || echo 0" \
  "1"
check "harness tooling is gated on the modernized profile" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'PROFILE}\" = \"modernized\"' || echo 0" \
  "2"
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

# Stage 080 dest is Hermes Kanban. OpenCode skill diffs against stage 070
# were the dual-tool destfile lie (ST-7). Static destfile contract:
SCAFFOLD_DEVFILE="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/devfile.yaml"
SCAFFOLD_DASH="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/dashboard"
check "080 destfile is not OpenCode-only" \
  "grep -c 'OpenCode-only by design' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 destfile has no opencode-managed volume" \
  "grep -c 'opencode-managed' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 destfile keeps hermes-dash endpoint" \
  "grep -c 'name: hermes-dash' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "1"
check "080 destfile has no start-hermes-dashboard launcher" \
  "grep -c 'start-hermes-dashboard' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 ships pin-stamped dashboard index.html" \
  "test -f '${SCAFFOLD_DASH}/web_dist/index.html' && echo present || echo missing" \
  "present"
check "080 dashboard PIN matches pins.json" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks/assert-web-dist-pin.py' --pins '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/pins.json' --stamp '${SCAFFOLD_DASH}/PIN' --bundle '${SCAFFOLD_DASH}/web_dist/index.html' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 agent-pin assert MATCH on on-pin hermes_cli constants" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks/assert-agent-pin.py' --pins '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/pins.json' --agent-src '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks/fixtures/hermes-agent-on-pin' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 agent-pin assert refuses off-pin hermes_cli constants" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks/assert-agent-pin.py' --pins '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/pins.json' --agent-src '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks/fixtures/hermes-agent-off-pin' >/dev/null && echo 0 || echo 1" \
  "1"

SCAFFOLD_PROFILES="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/config/profiles"
GITOPS_INIT="${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml"
check "080 GitOps invokes golden assert-agent-pin.py" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -c '.hermes/checks/assert-agent-pin.py' | grep -qx 1 && grep -qF 'python3 \"\${agent_assert}\" --pins' '${GITOPS_INIT}' && echo 1 || echo 0" \
  "1"
check "080 GitOps pin oracle uses --agent-src" \
  "grep -c -- '--agent-src' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps has no agent-pin heredoc" \
  "grep -c 'AGENTPINEOF' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps does not curl-install Hermes" \
  "grep -c 'hermes-install.sh' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps uses overlay-baked /usr/local/bin/hermes" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -qF 'hermes_bin=\"/usr/local/bin/hermes\"' && echo 1 || echo 0" \
  "1"
check "080 GitOps pin oracle ast-reads overlay /opt/hermes-agent" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -qF 'agent_src=\"/opt/hermes-agent\"' && echo 1 || echo 0" \
  "1"
check "080 golden orchestrator profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/orchestrator.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden implementer profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/implementer.yaml.template' && echo present || echo missing" \
  "present"
check "080 GitOps seats dest worker profiles (C-2 skip retired)" \
  "grep -c 'ensure_dest_worker_profiles' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 GitOps does not skip single-persona profile create" \
  "grep -c 'skip hermes profile create (single-persona)' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps creates profiles with --no-alias" \
  "grep -c 'profile create \"\${name}\" --no-alias' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps does not invoke profile create --clone" \
  "grep -cE 'profile create [^\"]*--clone|profile create --clone' '${GITOPS_INIT}' || echo 0" \
  "0"
SCAFFOLD_KERNEL="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/kernel"
SCAFFOLD_LAYOUT="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/LAYOUT.md"
check "080 golden K2 REHOST pre_tool_call.sh present" \
  "test -f '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo present || echo missing" \
  "present"
check "080 golden pre_tool_call.sh is executable" \
  "test -x '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 LAYOUT classifies K2 as REHOST" \
  "grep -q 'K2 REHOST' '${SCAFFOLD_LAYOUT}' && echo present || echo missing" \
  "present"
check "080 golden K1 schema loader validator present" \
  "test -f '${SCAFFOLD_KERNEL}/k1_schema.py' && test -f '${SCAFFOLD_KERNEL}/k1_load.py' && test -f '${SCAFFOLD_KERNEL}/k1_validate.py' && test -f '${SCAFFOLD_KERNEL}/.hermes-kernel' && echo present || echo missing" \
  "present"
check "080 golden K3 mint-verifier procedure present" \
  "test -f '${SCAFFOLD_KERNEL}/k3_schema.py' && test -f '${SCAFFOLD_KERNEL}/k3_verify.py' && echo present || echo missing" \
  "present"
check "080 golden K4 converter present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_schema.py' && test -f '${SCAFFOLD_KERNEL}/k4_convert.py' && echo present || echo missing" \
  "present"
check "080 golden K4 selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
SCAFFOLD_PARK="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/_park"
check "080 golden _park retired" \
  "test ! -e '${SCAFFOLD_PARK}' && echo absent || echo present" \
  "absent"
check "080 bootstrap omit_park_from_staged kept" \
  "grep -c 'omit_park_from_staged' '${REPO_ROOT}/scripts/bootstrap-migration-scaffold-v2.sh' || echo 0" \
  "3"
check "080 bootstrap refuses dest chaos matrix" \
  "grep -c 'run-chaos-matrix.py present in staged dest golden' '${REPO_ROOT}/scripts/bootstrap-migration-scaffold-v2.sh' || echo 0" \
  "1"
check "080 GitOps copies kernel pre_tool_call when k2_present" \
  "grep -c 'elif k2_present' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps K2 matcher includes execute_code" \
  "grep -c 'execute_code|delegate_task' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps no longer forbids the K2 instrumentation land" \
  "grep -c 'Do not mkdir kernel/. Do not land K2' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps hooks_auto_accept is top-level official key" \
  "grep -c 'unknown event name and never auto-approves' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 AGENTS.md assigns orchestrator/implementer not default" \
  "grep -c 'M2 / mint-verifier' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/AGENTS.md' || echo 0" \
  "1"

echo ""
validation_summary
