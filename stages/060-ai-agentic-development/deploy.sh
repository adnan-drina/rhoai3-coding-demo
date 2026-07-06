#!/usr/bin/env bash
# Stage 060: Agentic Development - Deploy
# Provisions the agentic workspace (coolstore + skills branch, agent-scale
# resources). Consumes Stage 050 Dev Spaces and Stage 040 MaaS keys.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="060-ai-agentic-development"

load_env
check_oc_logged_in

log_step "Stage 060: Agentic Development"
apply_stage_app "$STAGE_NAME"

log_info "The agentic-coolstore workspace clones the demo/agentic-skills branch"
log_info "(AGENTS.md + .opencode/skills). Flip to main after the branch merges."
echo "  oc get devworkspace agentic-coolstore -n wksp-ai-developer"
