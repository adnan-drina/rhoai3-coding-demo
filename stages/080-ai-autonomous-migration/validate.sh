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
check "runtime catalog placeholders are resolved" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -cE '__RHOAI3_DEMO_(REVISION|LOCATION_REF)__' || echo 0" \
  "0"
check "runtime catalog app-migration Location is not SHA-pinned" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep 'templates/app-migration/template.yaml' | grep -cE '/blob/[0-9a-f]{40}/' || echo 0" \
  "0"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GOLDEN_SHA=$(gh api repos/adnan-drina/quarkus-migration-scaffold-v2/git/refs/heads/main --jq '.object.sha' 2>/dev/null || echo "")
    if [[ -n "$GOLDEN_SHA" ]]; then
        echo -e "${GREEN}[PASS]${NC} quarkus-migration-scaffold-v2 golden repo exists (${GOLDEN_SHA:0:12})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} quarkus-migration-scaffold-v2 golden repo missing (run scripts/bootstrap-scaffold-repos.sh)"
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
check "live kantra-ensure verifies every ELF in the kantra tree is executable" \
  "test \"\$(oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -cF 'kantra-assert-exec')\" -ge 2 && echo CHECKER_WIRED || echo CHECKER_MISSING" \
  "CHECKER_WIRED"
check "init ConfigMap is DWO-mounted (volume, not kube-API curl as the primary path)" \
  "awk '/^kind: ConfigMap\$/{c=1} c && /^  name: devspace-ai-tools-init\$/{n=1} n && /controller.devfile.io\\/mount-to-devworkspace: \"true\"/ {print 1; exit} n && /^data:/{exit} /^---\$/{c=0; n=0}' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
SCAFFOLD_080="$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
check "v2 scaffold ships dispatch-phase/autostart-migration.sh (the dest-init consumer the devfile postStart calls)" \
  "test -f \"$SCAFFOLD_080/.hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh\" && grep -c 'dispatch-phase/scripts/autostart-migration.sh' '$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' | awk '{print (\$1>=1)?1:0}'" \
  "1"
check "v2 scaffold has no .hermes/home/scripts" \
  "test ! -e \"$SCAFFOLD_080/.hermes/home/scripts\" && echo 1 || echo 0" \
  "1"
check "v2 scaffold has no handover-mint.py" \
  "test -d \"$SCAFFOLD_080\" && test -z \"$(find \"$SCAFFOLD_080\" -name handover-mint.py -print -quit 2>/dev/null)\" && echo 1 || echo 0" \
  "1"
check "ensure_cli invokes kantra-assert-exec (capability, not presence)" \
  "grep -c 'kantra-assert-exec' \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh\" || echo 0" \
  "3"
check "ensure_cli does not add a kantra version handshake" \
  "grep -E 'kantra[[:space:]]+version|--list-providers' \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh\" && echo HANDSHAKE || echo NONE" \
  "NONE"
check "assert-ensure-cli-path rejects a present-but-unusable sibling" \
  "bash \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/assert-ensure-cli-path.sh\" >/dev/null && echo PASS || echo FAIL" \
  "PASS"
check "run-m4-pre-verdict invokes assert-no-fence-evasion (not a card pin)" \
  "grep -c 'assert-no-fence-evasion' \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh\" || echo 0" \
  "5"
check "run-m4-pre-verdict resolves work logs not M4 self" \
  "test -f \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/resolve-m4-work-logs.py\" && grep -c 'resolve-m4-work-logs' \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh\" || echo 0" \
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
# AD-H §14 — dest-user + per-profile SOUL.md; init must abort on
# missing/empty/hash mismatch and smoke-test Hermes load+scan.
check "init script hash-verifies SOUL.md and aborts (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'SOUL.md hash mismatch after placement' || echo 0" \
  "1"
check "init script places per-profile SOUL.md (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'profiles/\${name}/SOUL.md' || echo 0" \
  "1"
check "init script load-time SOUL smoke via load_soul_md (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'from agent.prompt_builder import load_soul_md' || echo 0" \
  "1"
check "live dest-init SOUL smoke uses overlay /opt/hermes-agent" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes_agent_root=\"/opt/hermes-agent\"' || echo 0" \
  "1"
check "live dest-init does not copy dest kanban-stuck-watchdog" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'home/scripts/kanban-stuck-watchdog' || echo 0" \
  "0"
check "live dest-init does not invoke golden assert-agent-pin.py" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -v '^[[:space:]]*#' | grep -c 'assert-agent-pin.py' || echo 0" \
  "0"
check "live workspace-maas-model-endpoint is the MaaS gateway path (not KServe)" \
  "oc get cm workspace-maas-model-endpoint -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_PATH}'" \
  "/models-as-a-service/qwen3-6-27b/v1"
check "live workspace-maas-credentials Secret exists" \
  "oc get secret workspace-maas-credentials -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "workspace-maas-credentials"

log_step "Factory Migration Workspace (app-migration destfile)"
# Stage 080 seats are created at demo time from the RHDH template. Do not
# require a standing mca-coolstore DevWorkspace. Assert the factory contract
# and that the retired GitOps seats are gone.
SKELETON_080="$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml"
GOLDEN_DEVFILE="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/devfile.yaml"
check_factory_mta_destfile() {
    local label="$1"
    local destfile="$2"
    check "factory destfile declares MTA default extensions: $label" \
        "grep -q '/tmp/mta.vsix;/tmp/mta-core.vsix;/tmp/redhat-java.vsix;/tmp/mta-java.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile downloads MTA VS Code extension 8.2.0: $label" \
        "grep -q 'redhat.mta-vscode-extension-8.2.0.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile downloads MTA core extension 8.2.0: $label" \
        "grep -q 'redhat.mta-core-8.2.0.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile downloads MTA Java extension 8.2.0: $label" \
        "grep -q 'redhat.mta-java-8.2.0.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile downloads redhat.java 1.47.0 (mta-java dependency): $label" \
        "grep -q 'redhat.java-1.47.0.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile sets HUB_URL to the internal hub service: $label" \
        "grep -q 'mta-ui.openshift-mta.svc.cluster.local:8080' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile sets FORCE_HUB_ENABLED: $label" \
        "grep -q 'FORCE_HUB_ENABLED' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile sets HUB_INSECURE: $label" \
        "grep -q 'HUB_INSECURE' '$destfile' && echo present || echo missing" \
        "present"
}
check_factory_mta_destfile "RHDH app-migration skeleton" "$SKELETON_080"
check_factory_mta_destfile "080 golden destfile" "$GOLDEN_DEVFILE"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "retired mca-coolstore standing workspace is absent: $ns" \
        "oc get devworkspace mca-coolstore -n $ns >/dev/null 2>&1 && echo present || echo absent" \
        "absent"
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
check "080 dashboard launcher defaults HERMES_WEB_DIST to overlay bake" \
  "grep -qF ': \"\${HERMES_WEB_DIST:=/usr/local/share/hermes/web_dist}\"' '${SCAFFOLD_DASH}/start-dashboard.sh' && echo 1 || echo 0" \
  "1"
check "080 dashboard launcher does not override HERMES_WEB_DIST to dest hermes_cli" \
  "grep -c 'hermes-agent/hermes_cli/web_dist' '${SCAFFOLD_DASH}/start-dashboard.sh' || echo 0" \
  "0"
check "080 dashboard launcher does not call dest-side install-web-dist" \
  "grep -c 'install-web-dist.sh' '${SCAFFOLD_DASH}/start-dashboard.sh' || echo 0" \
  "0"
check "080 golden has no dest dashboard web_dist bundle" \
  "test ! -e '${SCAFFOLD_DASH}/web_dist' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest install-web-dist.sh" \
  "test ! -e '${SCAFFOLD_DASH}/install-web-dist.sh' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest dashboard PIN" \
  "test ! -e '${SCAFFOLD_DASH}/PIN' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest .hermes/checks tree" \
  "test ! -e '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks' && echo 1 || echo 0" \
  "1"

SCAFFOLD_PROFILES="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/config/profiles"
GITOPS_INIT="${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml"
check "080 GitOps does not invoke golden assert-agent-pin.py" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -c 'assert-agent-pin.py' || echo 0" \
  "0"
check "080 GitOps pin oracle does not use --agent-src" \
  "grep -c -- '--agent-src' '${GITOPS_INIT}' || echo 0" \
  "0"
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
check "080 GitOps SOUL smoke uses overlay /opt/hermes-agent (no dest fallback)" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -qF 'hermes_agent_root=\"/opt/hermes-agent\"' && echo 1 || echo 0" \
  "1"
check "080 GitOps dest-init prefers env MAAS_API_BASE_URL then gateway MAAS_BASE_URL" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -qF 'os.environ.get(\"MAAS_API_BASE_URL\")' && grep -qF 'os.environ.get(\"MAAS_BASE_URL\")' '${GITOPS_INIT}' && grep -qF '/models-as-a-service/qwen3-6-27b/v1' '${GITOPS_INIT}' && echo 1 || echo 0" \
  "1"
check "080 GitOps ConfigMap is the MaaS gateway path (not KServe host)" \
  "grep -qF 'MAAS_API_PATH: /models-as-a-service/qwen3-6-27b/v1' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/workspace-maas-model-endpoint.yaml' && grep -q 'name: workspace-maas-model-endpoint' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/workspace-maas-model-endpoint.yaml' && ! grep -q 'kserve-workload-svc' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/devspaces/workspace-maas-model-endpoint.yaml' && echo 1 || echo 0" \
  "1"
check "080 GitOps derives workspace-maas-credentials from QWEN27B key + ConfigMap URL" \
  "grep -qF '\"name\": \"workspace-maas-credentials\"' '${GITOPS_INIT}' && grep -q 'workspace-maas-model-endpoint' '${GITOPS_INIT}' && grep -q 'field-manager=devspace-maas-key-provisioner' '${GITOPS_INIT}' && echo 1 || echo 0" \
  "1"
check "080 GitOps MaaS env derive does not bounce Running dest pods" \
  "awk '/workspace-maas-credentials derived/,0' '${GITOPS_INIT}' | grep -c 'oc delete pod' || echo 0" \
  "0"
check "080 GitOps dest-init derives worker base from gateway MAAS_BASE_URL" \
  "grep -c 'MaaS gateway base from MAAS_BASE_URL' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps dest-init pin files do not label the gateway as KServe" \
  "grep -c 'in-cluster-kserve' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps dest-init does not pin ssl_ca_cert on the qwen provider" \
  "grep -c '\"ssl_ca_cert\": service_ca,' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps dest-init pairs ssl_ca_cert with resolved .svc vs route" \
  "grep -c 'route endpoint must NOT pin ssl_ca_cert' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps dest-init ssl_ca_cert gate uses resolved model_base" \
  "grep -c 'Use the RESOLVED url (model_base)' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps does not copy dest kanban-stuck-watchdog" \
  "grep -c 'home/scripts/kanban-stuck-watchdog' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 RHDH skeleton destfile does not invoke dest supervise-gateway" \
  "grep -c '.hermes/home/scripts/supervise-gateway.sh' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "0"
check "080 golden destfile does not invoke dest supervise-gateway" \
  "grep -c '.hermes/home/scripts/supervise-gateway.sh' '${SCAFFOLD_080}/devfile.yaml' || echo 0" \
  "0"
check "080 golden destfile enables DWO debug-start" \
  "grep -c 'controller.devfile.io/debug-start' '${SCAFFOLD_080}/devfile.yaml' || echo 0" \
  "1"
check "080 golden destfile does not tee postStart to PVC" \
  "grep -c 'poststart.log' '${SCAFFOLD_080}/devfile.yaml' || echo 0" \
  "0"
check "080 RHDH skeleton destfile enables DWO debug-start" \
  "grep -c 'controller.devfile.io/debug-start' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "1"
check "080 RHDH skeleton destfile does not tee postStart to PVC" \
  "grep -c 'poststart.log' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "0"
check "080 golden orchestrator profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/orchestrator.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden implementer profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/implementer.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden reviewer profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/reviewer.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden orchestrator SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' && echo present || echo missing" \
  "present"
check "080 golden implementer SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/implementer.SOUL.md' && echo present || echo missing" \
  "present"
check "080 golden reviewer SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' && echo present || echo missing" \
  "present"
check "080 every SOUL.md survives the Hermes injection scanner" \
  "python3 '${SCRIPT_DIR}/assert-soul-scanner-clean.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 golden worker SOUL.md files are git-tracked" \
  "git -C '${REPO_ROOT}' ls-files --error-unmatch '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' >/dev/null && echo tracked || echo missing" \
  "tracked"
check "080 four SOUL.md files have distinct sha256" \
  "sha256sum '${SCAFFOLD_080}/.hermes/SOUL.md' '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' | awk '{print \$1}' | sort -u | wc -l | tr -d ' '" \
  "4"
check "080 dest-user SOUL.md names dest-user identity" \
  "grep -c 'You are the dest-user' '${SCAFFOLD_080}/.hermes/SOUL.md' || echo 0" \
  "1"
# kanban_block is a phrasing lint, not the identity gate. Distinct sha256
# (above) is what proves dest-user is not a copy of a worker SOUL.
check "080 dest-user SOUL.md is not the implementer identity" \
  "grep -c 'kanban_block' '${SCAFFOLD_080}/.hermes/SOUL.md' || echo 0" \
  "0"
check "080 implementer SOUL.md names kanban_block" \
  "grep -c 'kanban_block' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' || echo 0" \
  "1"
check "080 orchestrator SOUL.md refuses to implement" \
  "grep -c 'You do not implement' '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' || echo 0" \
  "1"
check "080 reviewer SOUL.md refuses to write the product tree" \
  "grep -c 'You do not write the product tree' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' || echo 0" \
  "1"
check "080 GitOps places per-profile SOUL.md" \
  "grep -c 'profiles/\${name}/SOUL.md' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps asserts four SOUL.md sha256 are distinct" \
  "grep -c 'four SOUL.md files have distinct sha256' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps resolves worker home via hermes -p profile show" \
  "grep -c -- '-p \"\${_soul_profile}\" profile show' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps SOUL smoke does not couple identity phrasing" \
  "grep -c 'doctrine marker missing after load' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps seats dest worker profiles (C-2 skip retired)" \
  "grep -c 'ensure_dest_worker_profiles' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 GitOps seats reviewer profile" \
  "grep -c '_ensure_one_dest_profile reviewer' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps pins kanban.review_dispatch true" \
  "grep -c '\"review_dispatch\": True' '${GITOPS_INIT}' || echo 0" \
  "1"
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
check "080 K2 hook splits allow-root on pathsep" \
  "grep -q 'allow.split(os.pathsep)' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 hook uses hook_cwd for transparent pathless" \
  "grep -q 'hook_cwd' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 hook denies opaque construction" \
  "grep -q '_OPAQUE' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 opacity is not gated on not-proven" \
  "awk '/for _rx in _OPAQUE/{found=1; exit} /if cmd.strip()/{ok=1} END{print (found && ok)?1:0}' '${SCAFFOLD_KERNEL}/pre_tool_call.sh'" \
  "1"
check "080 K2 hook strips env assignments as values not access" \
  "grep -q 'strip_env_assignments' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 toolchain reads are not an allow-root widen" \
  "grep -q 'def toolchain_read' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 names orchestrator disabled toolset" \
  "grep -q 'disabled for profile orchestrator' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 enforces files_writable" \
  "grep -q 'files_writable' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 refuses complete after a red bound gate" \
  "grep -q 'kanban_complete refused' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 inventory-legacy-surface scan root is fence-legal" \
  "awk '/inventory-entry-points.py/{getline; print}' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/inventory-legacy-surface/SKILL.md' | grep -c '/projects/.derived/legacy-at-3' || echo 0" \
  "0"
check "080 catalog Locations use a stable Argo ref not a SHA blob" \
  "python3 '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/jobs/catalog-location-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K2 env-assignment selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k2_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K2 implementer complete is request_review" \
  "grep -c 'implementer terminator is kanban_request_review' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' || echo 0" \
  "1"
check "080 K2 complete hook writes breadcrumb" \
  "grep -c 'complete-invocations.jsonl' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' || echo 0" \
  "1"
SCAFFOLD_LIB="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib"
SCAFFOLD_PAVED="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/paved-road"
SCAFFOLD_AUTOSTART="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/harness/dispatch-phase/scripts"
check "080 paved-road lib selftest passes" \
  "python3 '${SCAFFOLD_LIB}/paved_road.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m1 selftest passes" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m1/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m2 selftest passes (activation gate first; not-activated REFUSE)" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m2/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road coverage lint passes" \
  "python3 '${SCAFFOLD_LIB}/paved_road.py' coverage >/dev/null && echo 1 || echo 0" \
  "1"
check "080 autostart pins paved-road-m1 only on M1" \
  "grep -c -- '--skill paved-road-m1' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart mints M2 only behind pins.planner.activation" \
  "grep -c 'PLANNER_ACTIVATION}\" == \"activated\"' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart M2 card pins paved-road-m2 (child of M1, key m2-plan)" \
  "grep -c -- '--idempotency-key m2-plan' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart never mints M3/M4" \
  "grep -c -E '\"M3 |\"M4 ' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "0"
check "080 autostart does not pin scan-with-mta on the card" \
  "grep -c -- '--skill scan-with-mta' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "0"
check "080 autostart-migration selftest passes" \
  "python3 '${SCAFFOLD_AUTOSTART}/autostart-migration.selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 derive default DERIVED_ROOT is inside dest tree" \
  "grep -c '\${MODERNIZED_ROOT}/.derived/legacy-at-3' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/migration/derive-legacy-boot3/scripts/derive-legacy-boot3.sh' || echo 0" \
  "1"
check "080 derive-legacy-boot3 identity omits derived_root" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/migration/derive-legacy-boot3/scripts/derive-legacy-boot3.selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 GitOps dest-init K2_ALLOW_ROOT includes /projects/legacy" \
  "awk '/K2_ALLOW_ROOT/ && /\\/projects\\/legacy/ {print 1; exit}' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps write sandbox stays PROJECT_DIR (legacy not in HERMES_WRITE_SAFE_ROOT)" \
  "grep -E '^[[:space:]]*(export )?HERMES_WRITE_SAFE_ROOT=' '${GITOPS_INIT}' | grep -c '/projects/legacy' || echo 0" \
  "0"
check "080 LAYOUT classifies K2 as REHOST" \
  "grep -q 'K2 REHOST' '${SCAFFOLD_LAYOUT}' && echo present || echo missing" \
  "present"
check "080 golden K1 schema loader validator present" \
  "test -f '${SCAFFOLD_KERNEL}/k1_schema.py' && test -f '${SCAFFOLD_KERNEL}/k1_load.py' && test -f '${SCAFFOLD_KERNEL}/k1_validate.py' && test -f '${SCAFFOLD_KERNEL}/.hermes-kernel' && echo present || echo missing" \
  "present"
check "080 golden K3 snapshot + live comparator present" \
  "test -f '${SCAFFOLD_KERNEL}/k3_schema.py' && test -f '${SCAFFOLD_KERNEL}/k3_verify.py' && test -f '${SCAFFOLD_KERNEL}/k3_live.py' && echo present || echo missing" \
  "present"
check "080 K1 selftest passes (receipt/write-set/artifact body codes)" \
  "python3 '${SCAFFOLD_KERNEL}/k1_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden K4 converter present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_schema.py' && test -f '${SCAFFOLD_KERNEL}/k4_convert.py' && echo present || echo missing" \
  "present"
check "080 K4 payloads pin max_retries 1" \
  "grep -c '\"max_retries\": 1' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "1"
check "080 K4 converter emits no fixed m4-verify idempotency key (receipt-bound for M4 too)" \
  "grep -c 'm4-verify' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "0"
check "080 K4 mint refuses a fixed m4-verify key" \
  "grep -c 'key == \"m4-verify\"' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 RHDH autoStartMigration parameter defaults true" \
  "grep -A6 'autoStartMigration:' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/template.yaml' | grep -c 'default: true' || echo 0" \
  "1"
check "080 destfile stamps AUTO_START_MIGRATION" \
  "grep -c 'AUTO_START_MIGRATION' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "1"
check "080 RHDH template has no needsDatabase parameter" \
  "grep -c 'needsDatabase' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/template.yaml' || echo 0" \
  "0"
check "080 skeleton ships postgres as k8s-templates not cut-time k8s/" \
  "test -f '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/k8s-templates/postgres.yaml' && test ! -f '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/k8s/postgres.yaml' && echo 1 || echo 0" \
  "1"
check "080 skeleton app.yaml is not Jinja-gated on needsDatabase" \
  "grep -c 'needsDatabase' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/k8s/app.yaml' || echo 0" \
  "0"
check "080 golden migration.yaml has no needsDatabase field" \
  "grep -c 'needsDatabase' '${SCAFFOLD_080}/migration.yaml' || echo 0" \
  "0"
check "080 golden K4 selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden K4 mint-writer present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_mint.py' && echo present || echo missing" \
  "present"
check "080 K4 mint-writer selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_mint_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 kanban attach selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/kanban_attach_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 G-4 claim consistency selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/gates/check-release-readiness/scripts/assert-g4-claim-consistency.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
SCAFFOLD_PARK="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/_park"
check "080 golden _park retired" \
  "test ! -e '${SCAFFOLD_PARK}' && echo absent || echo present" \
  "absent"
check "080 dest-init pins security.tirith_enabled false" \
  "grep -c 'tirith_enabled.: False' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 dest-init does not prepend HERMES_HOME/bin (braced; Operator 123436ZO)" \
  "grep -c 'HERMES_HOME}/bin' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 tirith-declared-absent rule retired" \
  "test ! -f '${REPO_ROOT}/.agents/rules/tirith-declared-absent.md' && echo absent || echo present" \
  "absent"
check "080 python human_home is in .hermes/lib" \
  "test -f '${SCAFFOLD_080}/.hermes/lib/human_home.py' && grep -c 'Path.home() in a KEEP' '${SCAFFOLD_080}/.hermes/lib/human_home.py' || echo 0" \
  "1"
check "080 assert-extension-tooling uses human_home" \
  "grep -c 'human_home()' '${SCAFFOLD_080}/.hermes/skills/migration/manage-quarkus-extensions/scripts/assert-extension-tooling.py' || echo 0" \
  "1"
check "080 GitOps copies kernel pre_tool_call when k2_present" \
  "grep -c 'elif k2_present' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps K2 matcher includes execute_code" \
  "grep -c 'execute_code|delegate_task' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps K2 matcher includes skill_manage" \
  "grep -c 'delegate_task|skill_manage' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps pre_tool_call matcher includes native complete" \
  "python3 -c \"
import pathlib, re
t = pathlib.Path('${GITOPS_INIT}').read_text(encoding='utf-8')
ms = re.findall(r'\\\"matcher\\\": \\\"([^\\\"]+)\\\"', t)
print(sum(1 for m in ms if 'kanban_complete' in m and 'complete_task' in m))
\"" \
  "2"
check "080 GitOps no longer forbids the K2 instrumentation land" \
  "grep -c 'Do not mkdir kernel/. Do not land K2' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps hooks_auto_accept is top-level official key" \
  "grep -c 'unknown event name and never auto-approves' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 AGENTS.md states the AI is not the planner of record" \
  "grep -c 'the AI is not the planner of record' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/AGENTS.md' || echo 0" \
  "1"
check "080 dest-init external_dirs fail-closed names unreadable path" \
  "grep -c 'missing or unreadable' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 check-external-dirs requires dest-user home literal" \
  "grep -c '/home/user/.hermes/skills' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib/check-external-dirs.py' || echo 0" \
  "3"
check "080 pom platform-pins plugin coverage selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 test-toolchain assertj pin selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 emit-required-extensions (freeze analysis copy) selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/scan-with-mta/scripts/emit-required-extensions.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
SCAFFOLD_SKILLS="${SCAFFOLD_080}/.hermes/skills"
check "080 Spec Kit skills are removed (no compatibility path)" \
  "test ! -d '${SCAFFOLD_SKILLS}/sdd/plan-migration-partition' && test ! -d '${SCAFFOLD_SKILLS}/sdd/check-spec-readiness' && test ! -f '${SCAFFOLD_KERNEL}/speckit_feature.py' && echo absent || echo present" \
  "absent"
check "080 Spec Kit residue scan is clean (skills, kernel, lib, planning)" \
  "{ grep -rIl -E 'speckit|/speckit\\.|specify init|\\.specify/|spec\\.md|tasks\\.md|check-spec-readiness|plan-migration-partition|partition\\.json' '${SCAFFOLD_SKILLS}' '${SCAFFOLD_KERNEL}' '${SCAFFOLD_LIB}' '${SCAFFOLD_080}/.hermes/planning' --exclude-dir=__pycache__ || true; } | { grep -v -E 'paved_road(\\.test)?\\.py$|k4_(convert|schema|selftest|mint|mint_selftest)\\.py$|paved-road-m2/(SKILL\\.md|scripts/selftest\\.py)$|derive-story-oracles/|k2_selftest\\.py$|dispatch-phase/scripts/autostart-migration\\.(sh|selftest\\.py)$' || true; } | wc -l | tr -d ' '" \
  "0"
check "080 pins.json planner activation is not-activated on golden" \
  "python3 -c \"import json,pathlib; p=json.loads(pathlib.Path('${SCAFFOLD_080}/.hermes/pins.json').read_text())['pins']; print(p.get('planner',{}).get('activation'))\"" \
  "not-activated"
check "080 pins.json: structure_extractor pinned to the toolchain JDK, mta_cli pinned 8.2, no retired optional producers" \
  "python3 -c \"import json,pathlib; p=json.loads(pathlib.Path('${SCAFFOLD_080}/.hermes/pins.json').read_text())['pins']; print('ok' if p.get('structure_extractor',{}).get('version')=='jdk-21' and p.get('mta_cli',{}).get('version')=='8.2' and not p['mta_cli'].get('artifact_sha256') and 'spoon' not in p and 'jqassistant' not in p and 'context_probe' not in p else 'bad')\"" \
  "ok"
check "080 K2 hook vetoes worker graph mutation (kanban_create/link/swarm/decompose)" \
  "grep -c 'GRAPH_MUTATION_TOOLS' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' || echo 0" \
  "2"
check "080 K4 mint records task-id provenance for K3 (mint receipt)" \
  "grep -c 'def write_mint_receipt' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 K3 never infers card provenance from title or body" \
  "grep -c -E 'title\\[len\\(prefix\\)|startswith\\(prefix\\)' '${SCAFFOLD_LIB}/planner/live_board.py' || echo 0" \
  "0"
check "080 K4 re-derives the activation/pilot verdict from pins.json" \
  "grep -c 'activation_gaps(' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "1"
check "080 golden pins.json carries no pilot seal" \
  "python3 -c \"import json,pathlib; p=json.loads(pathlib.Path('${SCAFFOLD_080}/.hermes/pins.json').read_text())['pins']['planner']; print('none' if not p.get('pilot') else 'present')\"" \
  "none"
check "080 planning contracts present (schemas, catalogs, canary, decisions example)" \
  "test -f '${SCAFFOLD_080}/.hermes/planning/schemas/admission-receipt.schema.json' && test -f '${SCAFFOLD_080}/.hermes/planning/catalogs/destination-platforms.json' && test -f '${SCAFFOLD_080}/.hermes/planning/mta-rules/rhoai3-canary.yaml' && test -f '${SCAFFOLD_080}/.hermes/planning/decisions.example.yaml' && echo present || echo missing" \
  "present"
check "080 freeze-migration-input selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/freeze-migration-input/scripts/freeze-migration-input.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 capture-build-evidence selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/capture-build-evidence/scripts/emit-build-receipt.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 inventory-legacy-surface (JDK-model extractor) selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/inventory-legacy-surface/scripts/inventory-legacy-surface.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 assemble-evidence-bundle selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/assemble-evidence-bundle/scripts/assemble-evidence-bundle.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 scan-with-mta selftest passes (provenance, canary, never --source)" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/scan-with-mta/scripts/scan-with-mta.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 worklist selftest passes (order, measure, progress rule)" \
  "python3 '${SCAFFOLD_LIB}/planner/worklist.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 fix-until-green loop selftest passes (bootstrap → baseline → accept/revert/defer → M4)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/fix-until-green.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K4 mint + K3 live selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_mint_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden decisions.yaml is schema-valid with no missing decision (platform quarkus-rhbq-3.27, max_attempts 3)" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions, missing_decisions, max_attempts; d=load_decisions(Path('.')); print('ok' if d['destination_platform']['id']=='quarkus-rhbq-3.27' and max_attempts(d)==3 and not missing_decisions(d, Path('.')) else 'bad')\"" \
  "ok"
check "080 bootstrap-destination selftest passes (launcher with behavior kept; unmapped starter blocks; Maven settings wiring required; second run preserves the tree)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 advance.py binds acceptance to the issued card and the verified candidate tree" \
  "grep -c -E 'LOOP_NOT_ISSUED|LOOP_CANDIDATE_CHANGED|LOOP_WRONG_CARD' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/advance.py' | awk '{print (\$1>=3)?1:0}'" \
  "1"
check "080 revert restores the index as well as the working tree" \
  "grep -c 'git(root, \"reset\", \"-q\", \"HEAD\"' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/_loop_common.py' || echo 0" \
  "1"
check "080 run-verify.sh records the mvn test exit status and deletes stale surefire reports" \
  "grep -c -E 'surefire-reports\"\$|--test-rc' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.sh' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 bootstrap retires only ADR-listed sources (decisions.yaml retired_sources) and blocks on a stale path" \
  "grep -c -E 'RETIRED_SOURCE_MISSING|retired_sources' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 bootstrap carries legacy-resolved versions for dependencies the pinned BOM does not manage (measured, never guessed)" \
  "grep -c -E 'VERSION_UNMANAGED|BOM_PROBE_MISSING|pom.pin-legacy-version' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' | awk '{print (\$1>=3)?1:0}'" \
  "1"
check "080 run-verify.sh warms the destination up online once, then measures offline, and records the warm-up outcome" \
  "grep -c -E 'dependency:go-offline|\"warmup\": \{\"ran\"' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.sh' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 work list marks source obligations unknown unless the MTA producer status is ok (an absent scan is not zero incidents)" \
  "grep -c 'incidents_known = mta_status == \"ok\"' '${SCAFFOLD_LIB}/planner/worklist.py' || echo 0" \
  "1"
check "080 obligation identity is line-free (rule, file, variables, message)" \
  "grep -c 'line-free identity' '${SCAFFOLD_LIB}/planner/worklist.py' || echo 0" \
  "1"
check "080 K4 mint registers control cards instead of treating every HERMES_KANBAN_TASK as M2" \
  "grep -c 'def register_control_cards' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 AGENTS.md follows the Spring-compatibility path (no native-only rule)" \
  "grep -c 'Native Quarkus only' '${SCAFFOLD_080}/AGENTS.md' || echo 0" \
  "0"
check "080 compat mapping catalog present (bootstrap contract)" \
  "test -f '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json' && echo present || echo missing" \
  "present"
check "080 no ownership map / DAG / probe / bytecode machinery remains" \
  "{ grep -rIl -E 'planner\\.dag|planner\\.ownership|planner\\.ledger|increment-dag\\.json|probe-spring-bindings|enrich-legacy-bytecode' '${SCAFFOLD_080}/.hermes/lib' '${SCAFFOLD_080}/.hermes/kernel' '${SCAFFOLD_080}/.hermes/skills' --exclude-dir=__pycache__ --exclude-dir=fixtures || true; } | wc -l | tr -d ' '" \
  "0"
check "080 admit-migration-plan selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/planning/admit-migration-plan/scripts/admit-migration-plan.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 capture-source-oracles selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K4 producer-skill bar selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_producers.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 compose-m4-verdict selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/gates/compose-m4-verdict/scripts/compose-m4-verdict.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 assert-pinned-gates-ran receipts selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/gates/assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 run-m4-pre-verdict selftest passes" \
  "bash '${SCAFFOLD_080}/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.test.sh' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 cold-cache maven-settings skill text selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/reference-rh-quarkus-pom/scripts/reference-rh-quarkus-pom.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 JAX-RS DefaultValue mapping selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/spring-to-quarkus-patterns/scripts/rest-annotations-defaultvalue.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 check-external-dirs selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib/check-external-dirs.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 init-spec-workspace skill is removed" \
  "test ! -d '${SCAFFOLD_080}/.hermes/skills/sdd/init-spec-workspace' && echo absent || echo present" \
  "absent"
check "080 destfile does not call Spec Kit init-workspace.sh" \
  "grep -E 'init-workspace.sh|init-spec-workspace' '${REPO_ROOT}/gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml' '${SCAFFOLD_080}/devfile.yaml' >/dev/null && echo present || echo absent" \
  "absent"
check "080 dest-init does not install specify PATH shim" \
  "grep -c 'specify-from-project.sh' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 dest-init does not run specify init" \
  "grep -c 'dest-init specify init' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 pins.json has no spec_kit pin" \
  "python3 -c \"import json,pathlib; p=json.loads(pathlib.Path('${SCAFFOLD_080}/.hermes/pins.json').read_text()); print('present' if 'spec_kit' in (p.get('pins') or {}) else 'absent')\"" \
  "absent"
check "080 inventory SKILL runs the JDK compiler-API extractor (no third-party dependency, no regex)" \
  "grep -c 'run-jdk-model-extract.sh' '${SCAFFOLD_SKILLS}/analysis/inventory-legacy-surface/SKILL.md' || echo 0" \
  "2"
check "080 no Spoon, JavaParser, JDT, or regex extractor in the scaffold" \
  "{ grep -rIl -E 'import spoon|spoon-core|com.github.javaparser|org.eclipse.jdt|oracle-regex' '${SCAFFOLD_080}/.hermes' --exclude-dir=__pycache__ || true; } | wc -l | tr -d ' '" \
  "0"
check "080 M1 paved road freezes the original source first (derive-legacy-boot3 never first)" \
  "python3 -c \"import json,pathlib; d=json.load(open('${SCAFFOLD_SKILLS}/paved-road/paved-road-m1/steps.json')); s=d['steps'][0]; print(s.get('skill') or s.get('native') or s.get('kernel'))\"" \
  "freeze-migration-input"
check "080 K4 mints one card per step and M4 VERIFY only on an empty list" \
  "grep -c 'CLOSE_ID = \"M4_VERIFY\"' '${SCAFFOLD_LIB}/planner/cards.py' || echo 0" \
  "1"
check "080 commit-destination-tree skill present" \
  "test -f '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/SKILL.md' && echo present || echo missing" \
  "present"
check "080 commit-destination-tree selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/scripts/commit-destination-tree-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"

echo ""
validation_summary
