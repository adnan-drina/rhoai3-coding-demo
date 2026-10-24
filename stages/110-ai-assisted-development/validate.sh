#!/usr/bin/env bash
# Stage 110: AI-Assisted Development — Validation (the Stage 070 Dev Spaces and AI-tools resources it consumes)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in

# The Kilo provider SHAPE the Dev Spaces AI-tools init script generates (architect review B3, 2026-10-01: an endpoint
# string somewhere in the script is weaker than proof that the intended provider is configured and selectable).
# Reads the script on stdin; prints "provider-ok" or the first failed property.
kilo_provider() {
    local provider=$1 model=$2
    # awk reads its whole input (an early exit would kill the producer with SIGPIPE under pipefail).
    awk '/cat > "\$\{HOME\}\/\.config\/kilo\/kilo\.jsonc" <<KILOEOF/ && !done { f = 1; next }
        f && /^[[:space:]]*KILOEOF[[:space:]]*$/ { f = 0; done = 1; next } f' |
        sed -e 's/\\\$/$/g' -e 's/\${[A-Z0-9_]*}/PLACEHOLDER/g' |
        jq -r --arg p "$provider" --arg m "publishers/internal-models/models/$model" '(.provider[$p] // null) as $b
            | if (.enabled_providers // [] | index($p)) == null then "provider \($p) is not in enabled_providers"
              elif (.disabled_providers // [] | index($p)) != null then "provider \($p) is disabled"
              elif ($b | type) != "object" then "no provider.\($p) block"
              elif $b.npm != "@ai-sdk/openai-compatible" then "provider.\($p).npm is not the OpenAI-compatible adapter"
              elif ($b.options.baseURL // "") != "PLACEHOLDER/v1" then "provider.\($p).options.baseURL is not the common MaaS base"
              elif ($b.options.apiKey // "") == "" then "provider.\($p).options.apiKey is empty"
              elif ($b.models // {} | has($m)) | not then "provider.\($p).models has no \($m)"
              elif . as $c | ($c.model // "" | index("/")) as $i | $i == null or (($c.provider[$c.model[:$i]].models // {}) | has($c.model[$i + 1:]) | not)
                then "default model selector does not preserve a configured canonical model ID"
              else "provider-ok" end' 2>/dev/null || echo "no kilo.jsonc heredoc in the init script"
}

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 110: AI-Assisted Development — Validation                 ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_stage_applications 070

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
    check "Che Code editor configuration defaults Kilo to qwen3-8-27b: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'kilo-code.new.model.modelID.: .publishers/internal-models/models/qwen3-8-27b.' && echo present || echo missing" \
        "present"
    check "Che Code editor configuration disables Workspace Trust so Kilo activates: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.settings\\.json}' | contains 'security.workspace.trust.enabled.: false' && echo present || echo missing" \
        "present"
    check "Che Code product defaults disable Workspace Trust before first UI: $ns" \
        "oc get configmap vscode-editor-configurations -n $ns -o jsonpath='{.data.product\\.json}' | contains 'security.workspace.trust.enabled.: false' && echo present || echo missing" \
        "present"
    for retired in getting-started-ai-coding agentic-coolstore mca-coolstore; do
        check "Retired standing DevWorkspace is absent: $ns/$retired" \
            "oc get devworkspace $retired -n $ns >/dev/null 2>&1 && echo present || echo absent" \
            "absent"
    done
done

log_step "Agentic Coolstore Workspace (stage 070 golden path)"
for ns in wksp-ai-developer wksp-ai-admin; do
    check "coolstore-inventory-service DevWorkspace exists: $ns" \
        "oc get devworkspace coolstore-inventory-service -n $ns -o jsonpath='{.metadata.name}'" \
        "coolstore-inventory-service"
    check "coolstore-inventory-service tooling image is digest-pinned: $ns" \
        "case \"\$(oc get devworkspace coolstore-inventory-service -n $ns -o jsonpath='{.spec.template.components[0].container.image}')\" in *@sha256:*) echo pinned ;; *) echo unpinned ;; esac" \
        "pinned"
    check "coolstore-inventory-service declares Java 21 JAVA_HOME: $ns" \
        "oc get devworkspace coolstore-inventory-service -n $ns -o yaml | contains '/home/tooling/.sdkman/candidates/java/21.0.5-tem' && echo present || echo missing" \
        "present"
    check "coolstore-inventory-service startup configures Java 21 shell default: $ns" \
        "oc get devworkspace coolstore-inventory-service -n $ns -o yaml | contains 'rhoai3-coding-demo: java 21 default' && echo present || echo missing" \
        "present"
    check "coolstore-inventory-service declares Kilo Code default extension: $ns" \
        "oc get devworkspace coolstore-inventory-service -n $ns -o yaml | contains '/tmp/kilo.vsix' && echo present || echo missing" \
        "present"
    check "coolstore-inventory-service downloads Kilo Code extension 7.4.8: $ns" \
        "oc get devworkspace coolstore-inventory-service -n $ns -o yaml | contains 'kilo-code-7.4.8' && echo present || echo missing" \
        "present"
    phase=$(oc get devworkspace coolstore-inventory-service -n "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "ERROR")
    if [[ "$phase" == "Failed" || "$phase" == "Failing" || "$phase" == "ERROR" ]]; then
        echo -e "${RED}[FAIL]${NC} coolstore-inventory-service is not failed: $ns (got: $phase)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    else
        echo -e "${GREEN}[PASS]${NC} coolstore-inventory-service is not failed: $ns (phase: ${phase:-NotStarted})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    fi
done
check "coolstore-inventory-service tracks main branch" \
    "oc get devworkspace coolstore-inventory-service -n wksp-ai-developer -o yaml | grep -A2 'checkoutFrom' | contains 'revision: main' && echo main || echo other" \
    "main"
check "coolstore-inventory-service exposes quarkus-dev endpoint" \
    "oc get devworkspace coolstore-inventory-service -n wksp-ai-developer -o yaml | contains 'name: quarkus-dev' && echo present || echo missing" \
    "present"
check "coolstore-inventory-service has package command" \
    "oc get devworkspace coolstore-inventory-service -n wksp-ai-developer -o yaml | contains 'id: package' && echo present || echo missing" \
    "present"
check "coolstore-inventory-service has start-dev command" \
    "oc get devworkspace coolstore-inventory-service -n wksp-ai-developer -o yaml | contains 'id: start-dev' && echo present || echo missing" \
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
check "Init script defaults Kilo to qwen3-8-27b" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'qwen38/publishers/internal-models/models/qwen3-8-27b' && echo present || echo missing" \
    "present"
# the generated provider's SHAPE (enabled, OpenAI-compatible, MaaS route, key, model), not a string anywhere
check "Init script configures Kilo provider qwen38 (qwen3-8-27b)" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | kilo_provider qwen38 qwen3-8-27b" \
    "provider-ok"
check "Init script allow-lists only the MaaS Qwen 3.8 provider for Kilo" \
    "oc get configmap devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\\.sh}' | contains 'enabled_providers.: \\[\"qwen38\"\\]' && echo present || echo missing" \
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
