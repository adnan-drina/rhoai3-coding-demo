#!/usr/bin/env bash
# Stage 060: Dev Spaces — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 060: Dev Spaces & AI Code Assistant — Validation          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_argocd_app "050-advanced-app-platform"

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

log_step "Pre-Provisioned Workspace Namespaces"
WORKSPACES=(
    getting-started-ai-coding
    coolstore-inventory-service
    mca-coolstore
)
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "Workspace namespace exists: $ns" \
        "oc get namespace $ns -o jsonpath='{.metadata.name}'" \
        "$ns"
    check "Che Code editor configuration exists: $ns/vscode-editor-configurations" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.metadata.name}'" \
        "vscode-editor-configurations"
    check "Che Code editor configuration recommends Kilo Code: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.extensions\\.json}' | grep -q 'kilocode.kilo-code' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration recommends OpenShift Toolkit: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.extensions\\.json}' | grep -q 'redhat.vscode-openshift-connector' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration defaults to bash: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | grep -q 'terminal.integrated.defaultProfile.linux' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration sets Kilo Code default model: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | grep -q 'kilo-code.new.model.providerID' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace declares Kilo Code and MTA default extensions: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q '/tmp/kilo.vsix;/tmp/mta.vsix;/tmp/mta-core.vsix;/tmp/mta-java.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads Kilo Code extension 7.4.7: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'kilo-code-7.4.7' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA VS Code extension 8.1.2: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-vscode-extension-8.1.2.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA core extension 8.1.2: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-core-8.1.2.vsix' && echo present || echo missing" \
        "present"
    check "mca-coolstore workspace downloads MTA Java extension 8.1.2: $ns" \
        "oc get devworkspace mca-coolstore -n $ns -o yaml | grep -q 'redhat.mta-java-8.1.2.vsix' && echo present || echo missing" \
        "present"
    for workspace in "${WORKSPACES[@]}"; do
        check "Workspace DevWorkspace exists: $ns/$workspace" \
            "oc get devworkspace $workspace -n $ns -o jsonpath='{.metadata.name}'" \
            "$workspace"
        check "Workspace tooling image is digest-pinned: $ns/$workspace" \
            "case \"\$(oc get devworkspace $workspace -n $ns -o jsonpath='{.spec.template.components[0].container.image}')\" in *@sha256:*) echo pinned ;; *) echo unpinned ;; esac" \
            "pinned"
        check "Workspace declares Java 21 JAVA_HOME: $ns/$workspace" \
            "oc get devworkspace $workspace -n $ns -o yaml | grep -q '/home/tooling/.sdkman/candidates/java/21.0.5-tem' && echo present || echo missing" \
            "present"
        check "Workspace startup configures Java 21 shell default: $ns/$workspace" \
            "oc get devworkspace $workspace -n $ns -o yaml | grep -q 'rhoai3-coding-demo: java 21 default' && echo present || echo missing" \
            "present"
        check "Workspace declares Kilo Code default extension: $ns/$workspace" \
            "oc get devworkspace $workspace -n $ns -o yaml | grep -q '/tmp/kilo.vsix' && echo present || echo missing" \
            "present"
        check "Workspace downloads Kilo Code extension 7.4.7: $ns/$workspace" \
            "oc get devworkspace $workspace -n $ns -o yaml | grep -q 'kilo-code-7.4.7' && echo present || echo missing" \
            "present"
        phase=$(oc get devworkspace "$workspace" -n "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "ERROR")
        if [[ "$phase" == "Failed" || "$phase" == "Failing" || "$phase" == "ERROR" ]]; then
            echo -e "${RED}[FAIL]${NC} Workspace DevWorkspace is not failed: $ns/$workspace (got: $phase)"
            VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
        else
            echo -e "${GREEN}[PASS]${NC} Workspace DevWorkspace is not failed: $ns/$workspace (phase: ${phase:-NotStarted})"
            VALIDATE_PASS=$((VALIDATE_PASS + 1))
        fi
    done
done

log_step "Agentic Coolstore Workspace (stage 060 golden path)"
check "agentic-coolstore tracks main branch" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | grep -A2 'checkoutFrom' | grep -q 'revision: main' && echo main || echo other" \
    "main"
check "agentic-coolstore exposes quarkus-dev endpoint" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | grep -q 'name: quarkus-dev' && echo present || echo missing" \
    "present"
check "agentic-coolstore has package command" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | grep -q 'id: package' && echo present || echo missing" \
    "present"
check "agentic-coolstore has start-dev command" \
    "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o yaml | grep -q 'id: start-dev' && echo present || echo missing" \
    "present"

log_step "RHDH Platform Integration"
check "Runtime catalog contains SonarQube URL" \
    "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -q 'sonarqube-sonarqube' && echo present || echo missing" \
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
check "DevWorkspace MaaS API key Secret exists" \
    "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
    "maas-devspace-api-keys"
for key_name in \
    MAAS_BASE_URL \
    MAAS_API_KEY_NEMOTRON \
    MAAS_API_KEY_QWEN \
    MAAS_API_KEY_QWEN3_235B \
    MAAS_API_KEY_MINIMAX_M2; do
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
