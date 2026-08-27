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
# `python3 -m zipfile` discards Unix modes, so a kantra tree extracted with it
# lands 644 and analysis dies when kantra shells out to java-external-provider
# (dest-3 t_5981bf7a). /opt/kantra is chown'd away from the workspace uid, so
# the image is the only place it can be fixed. These gate the mechanism, not
# the filename: the extractor must preserve modes and the invariant must be
# asserted, so a future KANTRA_VERSION layout stays covered. Comments are
# stripped before the absence count — the Dockerfile comment names the bad
# extractor to explain why it is gone.
check "overlay Dockerfile does not extract kantra with the mode-losing extractor" \
  "grep -v '^[[:space:]]*#' \"$REPO_ROOT/workspace-images/Dockerfile\" | grep -qF 'python3 -m zipfile' && echo LOSSY_EXTRACTOR || echo MODE_PRESERVING" \
  "MODE_PRESERVING"
check "overlay Dockerfile asserts the kantra zip exec bits survived extraction" \
  "grep -qF '/opt/rhoai3/assert-zip-exec-bits.py' \"$REPO_ROOT/workspace-images/Dockerfile\" && echo ASSERT_WIRED || echo ASSERT_MISSING" \
  "ASSERT_WIRED"
check "live kantra-ensure verifies every ELF in the kantra tree is executable" \
  "test \"\$(oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -cF 'kantra-assert-exec')\" -ge 2 && echo CHECKER_WIRED || echo CHECKER_MISSING" \
  "CHECKER_WIRED"
check "init ConfigMap is DWO-mounted (volume, not kube-API curl as the primary path)" \
  "awk '/^kind: ConfigMap\$/{c=1} c && /^  name: devspace-ai-tools-init\$/{n=1} n && /controller.devfile.io\\/mount-to-devworkspace: \"true\"/ {print 1; exit} n && /^data:/{exit} /^---\$/{c=0; n=0}' \"$REPO_ROOT/gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
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
# AD-H §14 — SOUL.md is the sole judgement-doctrine carrier; init must
# abort on missing/empty/hash mismatch and smoke-test Hermes load+scan.
check "init script hash-verifies SOUL.md and aborts (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'SOUL.md hash mismatch after placement' || echo 0" \
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
check "080 golden K3 mint-verifier procedure present" \
  "test -f '${SCAFFOLD_KERNEL}/k3_schema.py' && test -f '${SCAFFOLD_KERNEL}/k3_verify.py' && echo present || echo missing" \
  "present"
check "080 golden K4 converter present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_schema.py' && test -f '${SCAFFOLD_KERNEL}/k4_convert.py' && echo present || echo missing" \
  "present"
check "080 K4 M3 payloads pin max_retries 1" \
  "grep -c 'max_retries=1' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "2"
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
check "080 bootstrap omit_park_from_staged kept" \
  "grep -c 'omit_park_from_staged' '${REPO_ROOT}/scripts/bootstrap-migration-scaffold-v2.sh' || echo 0" \
  "3"
check "080 bootstrap refuses dest chaos matrix" \
  "grep -c 'run-chaos-matrix.py present in staged dest golden' '${REPO_ROOT}/scripts/bootstrap-migration-scaffold-v2.sh' || echo 0" \
  "1"
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
check "080 GitOps no longer forbids the K2 instrumentation land" \
  "grep -c 'Do not mkdir kernel/. Do not land K2' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps hooks_auto_accept is top-level official key" \
  "grep -c 'unknown event name and never auto-approves' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 AGENTS.md assigns orchestrator/implementer not default" \
  "grep -c 'mint-verifier → \`orchestrator\`' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/AGENTS.md' || echo 0" \
  "1"
check "080 dest-init external_dirs fail-closed names unreadable path" \
  "grep -c 'missing or unreadable' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 check-external-dirs requires dest-user home literal" \
  "grep -c '/home/user/.hermes/skills' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/check-external-dirs.py' || echo 0" \
  "3"
check "080 pom platform-pins plugin coverage selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 test-toolchain assertj pin selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 emit-required-extensions harvest_referent selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/scan-with-mta/scripts/emit-required-extensions.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 plan-migration-partition selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/sdd/plan-migration-partition/scripts/plan-migration-partition.test.py' >/dev/null && echo 1 || echo 0" \
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
check "080 check-spec-readiness selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/check-spec-readiness/scripts/check-spec-readiness-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 check-external-dirs selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/check-external-dirs-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 specify-skills-root selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/assert-specify-skills-root-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 seed-speckit-skills canonical-leaf selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/seed-speckit-skills.selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 specify worker-shell run-time selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/sdd/init-spec-workspace/scripts/assert-specify-run-from-worker-home.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 dest-init installs specify PATH shim (not HERMES_HOME/bin)" \
  "grep -c 'specify-from-project.sh' '${GITOPS_INIT}' || echo 0" \
  "3"
check "080 dest-init smokes specify helper-by-path (W1)" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/sdd/init-spec-workspace/scripts/assert-dest-init-smokes-mandated-tools.py' '${GITOPS_INIT}' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 dest-init specify-smoke selftest (shim-only REFUSE)" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/sdd/init-spec-workspace/scripts/assert-dest-init-smokes-mandated-tools-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 speckit unknown-then-emit selftest (W1 paired control)" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/sdd/init-spec-workspace/scripts/assert-speckit-unknown-then-emit.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 inventory SKILL uses harvest_referent --from-manifest (W4)" \
  "awk '/inventory-entry-points.py/{getline; print}' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/inventory-legacy-surface/SKILL.md' | grep -c -- '--from-manifest' || echo 0" \
  "1"
check "080 harvest-referent pair selftest (identity cannot close W4)" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/analysis/inventory-legacy-surface/scripts/assert-harvest-referent-pair-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K4 mints STAMP_DESTINATION_TREE harvest card" \
  "grep -c 'STAMP_DESTINATION_TREE' '${SCAFFOLD_KERNEL}/k4_schema.py' || echo 0" \
  "2"
check "080 commit-destination-tree skill present" \
  "test -f '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/SKILL.md' && echo present || echo missing" \
  "present"
check "080 commit-destination-tree selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/scripts/commit-destination-tree-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"

echo ""
validation_summary
