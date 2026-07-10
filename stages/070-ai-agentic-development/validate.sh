#!/usr/bin/env bash
# Stage 070: Agentic Development - Validation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 070: Agentic Development — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "070-ai-agentic-development"

log_step "Agentic workspace"
check "agentic-coolstore DevWorkspace exists" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "agentic-coolstore"
check "workspace clones the skills-bearing revision" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.spec.template.projects[0].git.checkoutFrom.revision}'" \
  "agentic-skills"
check "workspace has agent-scale memory" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.spec.template.components[0].container.memoryLimit}'" \
  "6Gi"
check "workspace DevWorkspace is not failed" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.status.phase}' | grep -vq Failed && echo ok" \
  "ok"

log_step "Skills exist on the workspace revision (remote check)"
check "demo/agentic-skills branch exists upstream" \
  "git ls-remote --heads https://github.com/adnan-drina/coolstore-inventory-service.git demo/agentic-skills | wc -l | tr -d ' '" \
  "1"

log_step "MaaS prerequisites from earlier stages"
check "workspace MaaS key Secret exists (Stage 060)" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "maas-devspace-api-keys"
check "qwen executor key provisioned" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_KEY_QWEN}' | wc -c | tr -d ' ' | awk '{print (\$1>10)?\"yes\":\"no\"}'" \
  "yes"

echo ""
validation_summary
