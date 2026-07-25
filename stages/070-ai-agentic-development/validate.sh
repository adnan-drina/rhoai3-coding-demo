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
check "scaffold devfile uses the shared UDI base image (udi-rhel9)" \
  "curl -fsSL https://raw.githubusercontent.com/adnan-drina/agentic-quarkus-scaffold/main/devfile.yaml | grep -q 'devspaces/udi-rhel9' && echo present || echo missing" \
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
check "qwen27b model key provisioned" \
  "oc get secret maas-devspace-api-keys -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_KEY_QWEN27B}' | wc -c | tr -d ' ' | awk '{print (\$1>10)?\"yes\":\"no\"}'" \
  "yes"

log_step "Scaffold repo drift (checked-in staging vs live repos)"
# The checked-in scaffold-repo staging folders are the bootstrap force-push
# sources; drift against the live repos means bootstrap would clobber live
# changes (BACKLOG "Scaffold dual source of truth"). Warn-level: drift is a
# known condition to reconcile, not a broken deployment.
check_golden_drift() {
    local local_dir="$1" repo="$2"
    if ! command -v git >/dev/null 2>&1 || ! git ls-remote "https://github.com/adnan-drina/${repo}.git" >/dev/null 2>&1; then
        echo -e "${YELLOW}[WARN]${NC} cannot reach github.com/adnan-drina/${repo} — skipping drift check"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
        return
    fi
    local tmp
    tmp=$(mktemp -d)
    if git clone -q --depth 1 "https://github.com/adnan-drina/${repo}.git" "$tmp/live" 2>/dev/null \
       && diff -r -q -x .git "$REPO_ROOT/$local_dir" "$tmp/live" >/dev/null 2>&1; then
        echo -e "${GREEN}[PASS]${NC} ${repo}: checked-in staging matches the live scaffold repo"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} ${repo}: checked-in staging DIFFERS from the live scaffold repo (reconcile before running bootstrap-scaffold-repos.sh)"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
    rm -rf "$tmp"
}
check_golden_drift "stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold" "agentic-quarkus-scaffold"
check_golden_drift "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold" "quarkus-migration-scaffold"

echo ""
validation_summary
