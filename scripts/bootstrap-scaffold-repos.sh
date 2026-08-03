#!/usr/bin/env bash
# Bootstrap (or reset) the golden repositories that the stage 050
# golden-path templates copy from. Idempotent: re-running force-pushes the
# golden state, which is also the demo reset mechanism for the sources.
#
# Repositories managed (under github.com/${GITHUB_OWNER}):
#   agentic-quarkus-scaffold   — pushed verbatim from stages/070-ai-agentic-development/scaffold-repo/
#   quarkus-migration-scaffold — pushed verbatim from stages/080-ai-autonomous-migration/scaffold-repo/
#
# Requires: gh (authenticated with repo scope), git. No cluster access.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITHUB_OWNER="${GITHUB_OWNER:-adnan-drina}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

log() { echo -e "\033[0;34m[scaffold-repo]\033[0m $*"; }
warn() { echo -e "\033[1;33m[scaffold-repo][WARN]\033[0m $*"; }

command -v gh >/dev/null || { echo "gh CLI is required"; exit 1; }
gh auth status >/dev/null || { echo "gh is not authenticated"; exit 1; }

ensure_repo() {
  local repo="$1" description="$2"
  if ! gh repo view "${GITHUB_OWNER}/${repo}" >/dev/null 2>&1; then
    log "Creating github.com/${GITHUB_OWNER}/${repo}"
    gh repo create "${GITHUB_OWNER}/${repo}" --public --description "${description}"
  fi
  gh repo edit "${GITHUB_OWNER}/${repo}" --add-topic rhoai3-golden-path >/dev/null
}

push_golden() {
  local dir="$1" repo="$2" message="$3"
  (
    cd "$dir"
    git init -q -b main
    git add -A
    git commit -q -m "$message"
    git remote add origin "https://github.com/${GITHUB_OWNER}/${repo}.git"
    gh auth setup-git >/dev/null 2>&1 || true
    git push -q --force origin main
  )
  log "Pushed golden state to ${GITHUB_OWNER}/${repo}"
}

# --- 1. agentic-quarkus-scaffold (authored in this repo) ---
log "Staging agentic-quarkus-scaffold"
cp -R "$REPO_ROOT/stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold" "$WORKDIR/agentic-quarkus-scaffold"
ensure_repo "agentic-quarkus-scaffold" "Corporate Quarkus scaffold golden repo (agentic golden path: AGENTS.md + skills + specs)"
push_golden "$WORKDIR/agentic-quarkus-scaffold" "agentic-quarkus-scaffold" \
  "Golden state from rhoai3-coding-demo/stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold"

# --- 2. quarkus-migration-scaffold (authored in this repo) ---
log "Staging quarkus-migration-scaffold"
cp -R "$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold" "$WORKDIR/quarkus-migration-scaffold"
# O-GOLDENFRESH: stamp publish fingerprint into staged + SoT trees before push
# so preflight can three-way compare repo == published == pod.
bash "$REPO_ROOT/scripts/track-b/v10-golden-fresh.sh" --stamp \
  "$WORKDIR/quarkus-migration-scaffold"
bash "$REPO_ROOT/scripts/track-b/v10-golden-fresh.sh" --stamp \
  "$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
ensure_repo "quarkus-migration-scaffold" "Corporate Quarkus migration scaffold golden repo (stage 080: legacy + modernized dual-project workspace)"
push_golden "$WORKDIR/quarkus-migration-scaffold" "quarkus-migration-scaffold" \
  "Golden state from rhoai3-coding-demo/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"

log "Done. Reminders:"
echo "  - The GitHub App (webhook -> EventListener route) must be installed on"
echo "    'All repositories' so template-created repos trigger the pipeline."
echo "  - Re-running this script force-pushes golden state (demo reset)."
echo "  - O-GOLDENFRESH: .hermes/harness/.published-fp stamped; preflight refuses"
echo "    outer start when repo/published/pod digests diverge."
