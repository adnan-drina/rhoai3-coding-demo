#!/usr/bin/env bash
# Stage 070: Dev Spaces — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 070: Dev Spaces & AI Code Assistant — Validation          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_argocd_app "070-advanced-app-platform"

log_step "Dev Spaces Operator"
check_csv_succeeded "openshift-devspaces" "devspaces"

log_step "CheCluster"
check "CheCluster phase Active" \
    "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}'" \
    "Active"

log_step "Dev Spaces URL"
DEVSPACES_URL=$(oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.cheURL}' 2>/dev/null || echo "")
if [[ -n "$DEVSPACES_URL" ]]; then
    echo -e "${GREEN}[PASS]${NC} Dev Spaces URL: $DEVSPACES_URL"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} Dev Spaces URL not available"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

log_step "Persona Workspace Namespaces"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "Workspace namespace exists: $ns" \
        "oc get namespace $ns -o jsonpath='{.metadata.name}'" \
        "$ns"
    check "Che Code editor configuration exists: $ns/vscode-editor-configurations" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.metadata.name}'" \
        "vscode-editor-configurations"
    check "Che Code editor configuration does not force Kilo into factory workspaces: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.extensions\\.json}' | contains 'kilocode.kilo-code' && echo present || echo absent" \
        "absent"
    check "Che Code editor configuration recommends OpenShift Toolkit: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.extensions\\.json}' | contains 'redhat.vscode-openshift-connector' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration defaults to bash: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'terminal.integrated.defaultProfile.linux' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration sets Kilo Code default model: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'kilo-code.new.model.providerID.: .qwen38' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration defaults Kilo to qwen3-8-27b-int4: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'kilo-code.new.model.modelID.: .qwen3-8-27b-int4' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration disables Workspace Trust so Kilo activates: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'security.workspace.trust.enabled.: false' && echo present || echo missing" \
        "present"
    check "Che Code product defaults disable Workspace Trust before first UI: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.product\\.json}' | contains 'security.workspace.trust.enabled.: false' && echo present || echo missing" \
        "present"
    for retired in getting-started-ai-coding coolstore-inventory-service mca-coolstore; do
        check "Retired standing DevWorkspace is absent: $ns/$retired" \
            "oc get devworkspace $retired -n $ns >/dev/null 2>&1 && echo present || echo absent" \
            "absent"
    done
done

log_step "Agentic Coolstore Workspace (stage 070 golden path)"
for ns in wksp-ai-developer wksp-ai-admin; do
    check "agentic-coolstore DevWorkspace exists: $ns" \
        "oc get devworkspace agentic-coolstore -n $ns -o jsonpath='{.metadata.name}'" \
        "agentic-coolstore"
    check "agentic-coolstore tooling image is digest-pinned: $ns" \
        "case \"\$(oc get devworkspace agentic-coolstore -n $ns -o jsonpath='{.spec.template.components[0].container.image}')\" in *@sha256:*) echo pinned ;; *) echo unpinned ;; esac" \
        "pinned"
    check "agentic-coolstore declares Java 21 JAVA_HOME: $ns" \
        "oc get devworkspace agentic-coolstore -n $ns -o yaml | contains '/home/tooling/.sdkman/candidates/java/21.0.5-tem' && echo present || echo missing" \
        "present"
    check "agentic-coolstore startup configures Java 21 shell default: $ns" \
        "oc get devworkspace agentic-coolstore -n $ns -o yaml | contains 'rhoai3-coding-demo: java 21 default' && echo present || echo missing" \
        "present"
    check "agentic-coolstore declares Kilo Code default extension: $ns" \
        "oc get devworkspace agentic-coolstore -n $ns -o yaml | contains '/tmp/kilo.vsix' && echo present || echo missing" \
        "present"
    check "agentic-coolstore downloads Kilo Code extension 7.4.8: $ns" \
        "oc get devworkspace agentic-coolstore -n $ns -o yaml | contains 'kilo-code-7.4.8' && echo present || echo missing" \
        "present"
    phase=$(oc get devworkspace agentic-coolstore -n "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "ERROR")
    if [[ "$phase" == "Failed" || "$phase" == "Failing" || "$phase" == "ERROR" ]]; then
        echo -e "${RED}[FAIL]${NC} agentic-coolstore is not failed: $ns (got: $phase)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    else
        echo -e "${GREEN}[PASS]${NC} agentic-coolstore is not failed: $ns (phase: ${phase:-NotStarted})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    fi
done
check "agentic-coolstore tracks main branch" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | grep -A2 'checkoutFrom' | contains 'revision: main' && echo main || echo other" \
    "main"
check "agentic-coolstore exposes quarkus-dev endpoint" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | contains 'name: quarkus-dev' && echo present || echo missing" \
    "present"
check "agentic-coolstore has package command" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | contains 'id: package' && echo present || echo missing" \
    "present"
check "agentic-coolstore has start-dev command" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | contains 'id: start-dev' && echo present || echo missing" \
    "present"

log_step "RHDH Platform Integration"
check "Runtime catalog contains SonarQube URL" \
    "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | contains 'sonarqube-sonarqube' && echo present || echo missing" \
    "present"
check "rhdh-secrets contains SONARQUBE_URL key" \
    "[ -n \"\$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.SONARQUBE_URL}' 2>/dev/null)\" ] && echo present || echo missing" \
    "present"
check "rhdh-secrets contains DEVSPACES_URL key" \
    "[ -n \"\$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.DEVSPACES_URL}' 2>/dev/null)\" ] && echo present || echo missing" \
    "present"

check "ai-admin workspace edit RoleBinding exists" \
    "oc get rolebinding wksp-edit-ai-admin -n wksp-ai-admin -o jsonpath='{.subjects[0].name}'" \
    "ai-admin"
check "ai-admin workspace RoleBinding grants edit" \
    "oc get rolebinding wksp-edit-ai-admin -n wksp-ai-admin -o jsonpath='{.roleRef.name}'" \
    "edit"
check "ai-developer workspace edit RoleBinding exists" \
    "oc get rolebinding wksp-edit-ai-developer -n wksp-ai-developer -o jsonpath='{.subjects[0].name}'" \
    "ai-developer"
check "ai-developer workspace RoleBinding grants edit" \
    "oc get rolebinding wksp-edit-ai-developer -n wksp-ai-developer -o jsonpath='{.roleRef.name}'" \
    "edit"

log_step "MaaS AI Tool Auto-Configuration"
check "DevWorkspace MaaS key provisioner Job completed" \
    "oc get job provision-devspace-maas-api-keys -n wksp-ai-developer -o jsonpath='{.status.succeeded}'" \
    "1"
check "DevWorkspace AI tools init ConfigMap exists" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
    "devspace-ai-tools-init"
check "Init script defaults Kilo to qwen3-8-27b-int4" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'qwen38/qwen3-8-27b-int4' && echo present || echo missing" \
    "present"
# the generated provider's SHAPE (enabled, OpenAI-compatible, MaaS route, key, model), not a string anywhere
check "Init script configures Kilo provider qwen38 (qwen3-8-27b-int4)" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | python3 \"$REPO_ROOT/scripts/demo/check-kilo-provider.py\" qwen38 qwen3-8-27b-int4 qwen3-8-27b-int4" \
    "provider-ok"
check "Init script keeps Kilo provider qwen27b (qwen3-6-27b) selectable" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | python3 \"$REPO_ROOT/scripts/demo/check-kilo-provider.py\" qwen27b qwen3-6-27b qwen3-6-27b" \
    "provider-ok"
check "Init script allow-lists the MaaS Qwen providers for Kilo" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'enabled_providers.: \\[\"qwen38\", \"qwen27b\"\\]' && echo present || echo missing" \
    "present"
check "Init script writes kilo.jsonc (Kilo 7.4 primary config)" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'kilo.jsonc' && echo present || echo missing" \
    "present"
check "Init script disables ungoverned Kilo providers (kilo gateway, z.ai)" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'disabled_providers' && echo present || echo missing" \
    "present"
check "Init script configures git identity on fresh volumes" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'ensure_git_identity' && echo present || echo missing" \
    "present"
check "DevWorkspace MaaS API key Secret exists" \
    "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
    "maas-devspace-api-keys"
# Local-model keys are required. External-model keys are not provisioned into
# workspaces: the per-model keys were removed on 2026-07-20 and the
# REDHAT_MODELS_* direct-endpoint (MiniMax escalation) path on 2026-10-09.
for key_name in \
    MAAS_BASE_URL \
    MAAS_API_KEY_QWEN27B; do
    check "DevWorkspace MaaS Secret contains $key_name" \
        "[ -n \"\$(oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.data.$key_name}' 2>/dev/null)\" ] && echo present || echo missing" \
        "present"
done

log_step "Demo Reset Readiness"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GOLDEN_EXISTS=$(gh api repos/adnan-drina/coolstore-inventory-service/git/refs/heads/golden --jq '.object.sha' 2>/dev/null || echo "")
    if [[ -n "$GOLDEN_EXISTS" ]]; then
        echo -e "${GREEN}[PASS]${NC} coolstore-inventory-service golden branch exists (${GOLDEN_EXISTS:0:12})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} coolstore-inventory-service golden branch not found"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} gh CLI not available or not authenticated — skipping golden branch check"
fi

echo ""
validation_summary
