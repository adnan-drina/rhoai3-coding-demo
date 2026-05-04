#!/usr/bin/env bash
# Stage 060: MCP Context Integrations — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 060: MCP Context Integrations — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "060-mcp-context-integrations"

log_step "OpenShift MCP"
check "coding-assistant namespace exists" \
  "oc get namespace coding-assistant -o jsonpath='{.metadata.name}'" \
  "coding-assistant"
check "coding-assistant visible in OpenShift AI dashboard" \
  "oc get namespace coding-assistant -o jsonpath='{.metadata.labels.opendatahub\\.io/dashboard}'" \
  "true"
check "coding-assistant has display name" \
  "oc get namespace coding-assistant -o jsonpath='{.metadata.annotations.openshift\\.io/display-name}'" \
  "Coding Assistant"
check "ai-developer can edit coding-assistant" \
  "oc get rolebinding ai-developer-edit -n coding-assistant -o jsonpath='{.roleRef.name}{\" \"}{.subjects[0].kind}/{.subjects[0].name}'" \
  "edit User/ai-developer"
check "ai-admin can administer coding-assistant" \
  "oc get rolebinding ai-admin-admin -n coding-assistant -o jsonpath='{.roleRef.name}{\" \"}{.subjects[0].kind}/{.subjects[0].name}'" \
  "admin User/ai-admin"
check "OpenShift MCP ServiceAccount exists" \
  "oc get serviceaccount openshift-mcp -n coding-assistant -o jsonpath='{.metadata.name}'" \
  "openshift-mcp"
check "OpenShift MCP has read-only ClusterRoleBinding" \
  "oc get clusterrolebinding openshift-mcp-view -o jsonpath='{.roleRef.name}{\" \"}{.subjects[0].namespace}/{.subjects[0].name}'" \
  "view coding-assistant/openshift-mcp"
check "OpenShift MCP running" \
  "oc get pods -n coding-assistant -l app=openshift-mcp --no-headers 2>/dev/null | grep -c Running" \
  "1"
check "OpenShift MCP Service exists" \
  "oc get service openshift-mcp -n coding-assistant -o jsonpath='{.metadata.name}'" \
  "openshift-mcp"
check "OpenShift MCP registered in Playground ConfigMap" \
  "oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.data.OpenShift-MCP}'" \
  "openshift-mcp"

log_step "Slack MCP"
if oc get secret slack-mcp-credentials -n coding-assistant &>/dev/null; then
  check "Slack MCP running" \
    "oc get pods -n coding-assistant -l app=slack-mcp --no-headers 2>/dev/null | grep -c Running" \
    "1"
else
  echo -e "${YELLOW}[WARN]${NC} Slack MCP credentials not present; Slack MCP runtime is not validated"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
  check "Slack MCP deployment is credential-gated" \
    "oc get deployment slack-mcp -n coding-assistant -o jsonpath='{.spec.replicas}'" \
    "0"
fi
check "Slack MCP Service exists" \
  "oc get service slack-mcp -n coding-assistant -o jsonpath='{.metadata.name}'" \
  "slack-mcp"
check_warn "Slack MCP registered in Playground ConfigMap" \
  "oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.data.Slack-MCP}'" \
  "slack-mcp"

log_step "BrightData MCP"
if oc get secret brightdata-mcp-credentials -n coding-assistant &>/dev/null; then
  check "BrightData MCP running" \
    "oc get pods -n coding-assistant -l app=brightdata-mcp --no-headers 2>/dev/null | grep -c Running" \
    "1"
else
  echo -e "${YELLOW}[WARN]${NC} BrightData MCP credentials not present; BrightData MCP runtime is not validated"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
  check "BrightData MCP deployment is credential-gated" \
    "oc get deployment brightdata-mcp -n coding-assistant -o jsonpath='{.spec.replicas}'" \
    "0"
fi
check "BrightData MCP Service exists" \
  "oc get service brightdata-mcp -n coding-assistant -o jsonpath='{.metadata.name}'" \
  "brightdata-mcp"
check_warn "BrightData MCP registered in Playground ConfigMap" \
  "oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.data.BrightData-Web}'" \
  "brightdata-mcp"

echo ""
validation_summary
