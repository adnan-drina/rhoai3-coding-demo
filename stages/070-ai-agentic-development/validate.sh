#!/usr/bin/env bash
# Stage 070: Agentic Development - Validation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 070: Agentic Development — Validation"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_argocd_app "050-advanced-app-platform"

log_step "Agentic workspace"
check "agentic-coolstore DevWorkspace exists" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "agentic-coolstore"
check "workspace clones the main revision" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.spec.template.projects[0].git.checkoutFrom.revision}'" \
  "main"
check "workspace has agent-scale memory" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.spec.template.components[0].container.memoryLimit}'" \
  "6Gi"
check "workspace DevWorkspace is not failed" \
  "oc get devworkspace agentic-coolstore -n wksp-ai-developer -o jsonpath='{.status.phase}' | grep -vq Failed && echo ok" \
  "ok"

log_step "Golden-path template readiness (remote check)"
check "golden branch exists upstream for scaffold template" \
  "git ls-remote --heads https://github.com/adnan-drina/agentic-quarkus-scaffold.git golden | wc -l | tr -d ' '" \
  "1"
check "scaffold devfile uses the OpenCode tooling image (cli-ai-tools)" \
  "curl -fsSL https://raw.githubusercontent.com/adnan-drina/agentic-quarkus-scaffold/main/devfile.yaml | grep -q 'che-incubator/cli-ai-tools' && echo present || echo missing" \
  "present"
check "scaffold devfile runs the platform init script on postStart" \
  "curl -fsSL https://raw.githubusercontent.com/adnan-drina/agentic-quarkus-scaffold/main/devfile.yaml | grep -q 'devspace-ai-tools-init' && echo present || echo missing" \
  "present"
check "scaffold carries the OpenCode selector signal (.opencode/skills)" \
  "curl -fsSL 'https://api.github.com/repos/adnan-drina/agentic-quarkus-scaffold/contents/.opencode/skills?ref=main' | grep -cq 'quarkus-rest-conventions' && echo present || echo missing" \
  "present"

log_step "OpenCode gateway trust (Bun system-CA fix)"
# OpenCode embeds Bun, and Bun 1.3+ dropped default system-CA trust
# (oven-sh/bun#23735) — without NODE_USE_SYSTEM_CA it rejects the MaaS gateway's
# ingress cert and reaches zero models. Validate both surfaces carry it.
check "init script exports NODE_USE_SYSTEM_CA" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -q NODE_USE_SYSTEM_CA && echo present || echo missing" \
  "present"
check "scaffold devfile sets NODE_USE_SYSTEM_CA container env" \
  "curl -fsSL https://raw.githubusercontent.com/adnan-drina/agentic-quarkus-scaffold/main/devfile.yaml | grep -q NODE_USE_SYSTEM_CA && echo present || echo missing" \
  "present"

log_step "MaaS prerequisites from earlier stages"
check "workspace MaaS key Secret exists (Stage 060)" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "maas-devspace-api-keys"
check "qwen executor key provisioned" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_KEY_QWEN}' | wc -c | tr -d ' ' | awk '{print (\$1>10)?\"yes\":\"no\"}'" \
  "yes"

echo ""
validation_summary
