#!/usr/bin/env bash
# Stage 120: Agentic Development - Validation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

echo "Stage 120: Agentic Development — Validation"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_stage_applications 070

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

log_step "Private GitLab golden readiness"
check "Published agentic golden matches the reviewed staging tree" \
  "python3 '${REPO_ROOT}/scripts/demo/check-gitlab-golden.py' agentic-quarkus-scaffold" \
  "PASS: agentic-quarkus-scaffold"
# Factory destfile is the GitOps skeleton (template replace:true), not the
# GitLab golden destfile. per-workspace avoids RWO FailedMount when the
# Stage 070 agentic-coolstore seat is still Running.
SKELETON_070="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/agentic-quarkus-scaffold/skeleton/devfile.yaml"
STAGING_070="$SCRIPT_DIR/scaffold-repo/agentic-quarkus-scaffold/devfile.yaml"
check "GitOps 070 factory destfile uses per-workspace storage" \
  "grep -q 'controller.devfile.io/storage-type: per-workspace' '$SKELETON_070' && echo present || echo missing" \
  "present"
check "staging 070 destfile uses per-workspace storage" \
  "grep -q 'controller.devfile.io/storage-type: per-workspace' '$STAGING_070' && echo present || echo missing" \
  "present"

log_step "OpenCode gateway trust (Bun system-CA fix)"
# OpenCode embeds Bun, and Bun 1.3+ dropped default system-CA trust
# (oven-sh/bun#23735) — without NODE_USE_SYSTEM_CA it rejects the MaaS gateway's
# ingress cert and reaches zero models. Validate both surfaces carry it.
check "init script exports NODE_USE_SYSTEM_CA" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | contains NODE_USE_SYSTEM_CA && echo present || echo missing" \
  "present"
check "scaffold devfile sets NODE_USE_SYSTEM_CA container env" \
  "cat '${STAGING_070}' | contains NODE_USE_SYSTEM_CA && echo present || echo missing" \
  "present"

log_step "MaaS prerequisites from earlier stages"
check "workspace MaaS key Secret exists (Stage 070)" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "maas-devspace-api-keys"
check "MaaS model key provisioned (MAAS_API_KEY_QWEN27B serves Qwen 3.8)" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_KEY_QWEN27B}' | wc -c | tr -d ' ' | awk '{print (\$1>10)?\"yes\":\"no\"}'" \
  "yes"
check "ai-admin has its own MaaS key (per-persona attribution)" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-admin -o jsonpath='{.data.MAAS_API_KEY_QWEN27B}' | wc -c | tr -d ' ' | awk '{print (\$1>10)?\"yes\":\"no\"}'" \
  "yes"

log_step "Migration golden drift"
check "Published migration golden matches the reviewed staging tree" \
  "python3 '${REPO_ROOT}/scripts/demo/check-gitlab-golden.py' quarkus-migration-scaffold-v2" \
  "PASS: quarkus-migration-scaffold-v2"

echo ""
validation_summary
