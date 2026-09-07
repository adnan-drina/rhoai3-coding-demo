#!/usr/bin/env bash
# Bootstrap (or reset) the golden repositories that the stage 050
# golden-path templates copy from. Idempotent: re-running force-pushes the
# golden state, which is also the demo reset mechanism for the sources.
#
# Repositories managed (under github.com/${GITHUB_OWNER}):
#   agentic-quarkus-scaffold         — Stage 070, pushed verbatim from
#                                      stages/070-ai-agentic-development/scaffold-repo/
#   quarkus-migration-scaffold-v2    — live Stage 080 golden from
#                                      stages/080-ai-autonomous-migration/scaffold-repo/
#                                      Dest omit of .hermes/_park; refuse if
#                                      run-chaos-matrix.py is in the staged tree.
#
# Does not force-push historical quarkus-migration-scaffold (v1). Do not
# GitHub-rename v1. Do not add topic rhoai3-scaffolded (that marks dest
# per-run repos).
#
# Requires: gh (authenticated with repo scope), git. No cluster access.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITHUB_OWNER="${GITHUB_OWNER:-adnan-drina}"
MIGRATION_GOLDEN_REPO="${MIGRATION_GOLDEN_REPO:-quarkus-migration-scaffold-v2}"
MIGRATION_SRC="$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

log() { echo -e "\033[0;34m[scaffold-repo]\033[0m $*"; }

if [[ "$MIGRATION_GOLDEN_REPO" == "quarkus-migration-scaffold" ]]; then
  echo "REFUSE: this script must not force-push the historical v1 golden '${MIGRATION_GOLDEN_REPO}'." >&2
  exit 1
fi

command -v git >/dev/null || { echo "git is required"; exit 1; }
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

omit_park_from_staged() {
  local staged="$1"
  rm -rf "${staged}/.hermes/_park"
  if [[ -e "${staged}/.hermes/_park" ]]; then
    echo "REFUSE: .hermes/_park still present after dest omit" >&2
    exit 1
  fi
  local chaos
  chaos="$(find "${staged}" -name 'run-chaos-matrix.py' -print -quit || true)"
  if [[ -n "${chaos}" ]]; then
    echo "REFUSE: run-chaos-matrix.py present in staged dest golden (${chaos})" >&2
    exit 1
  fi
}

# --- 1. agentic-quarkus-scaffold (authored in this repo) ---
log "Staging agentic-quarkus-scaffold"
cp -R "$REPO_ROOT/stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold" "$WORKDIR/agentic-quarkus-scaffold"
ensure_repo "agentic-quarkus-scaffold" "Corporate Quarkus scaffold golden repo (agentic golden path: AGENTS.md + skills + specs)"
push_golden "$WORKDIR/agentic-quarkus-scaffold" "agentic-quarkus-scaffold" \
  "Golden state from rhoai3-coding-demo/stages/070-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold"

# --- 2. live Stage 080 golden ---
test -f "$MIGRATION_SRC/migration.yaml" || { echo "REFUSE: missing authoring tree at $MIGRATION_SRC"; exit 1; }
if [[ -e "$MIGRATION_SRC/.hermes/_park" ]]; then
  echo "REFUSE: authoring tree still has .hermes/_park" >&2
  exit 1
fi

log "Staging ${MIGRATION_GOLDEN_REPO}"
cp -R "$MIGRATION_SRC" "$WORKDIR/${MIGRATION_GOLDEN_REPO}"
omit_park_from_staged "$WORKDIR/${MIGRATION_GOLDEN_REPO}"
ensure_repo "${MIGRATION_GOLDEN_REPO}" \
  "Quarkus migration scaffold golden (stage 080). Separate from historical quarkus-migration-scaffold. Do not rename v1."
push_golden "$WORKDIR/${MIGRATION_GOLDEN_REPO}" "${MIGRATION_GOLDEN_REPO}" \
  "Golden state from rhoai3-coding-demo/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"

log "Done. Reminders:"
echo "  - The GitHub App (webhook -> EventListener route) must be installed on"
echo "    'All repositories' so template-created repos trigger the pipeline."
echo "  - Re-running this script force-pushes golden state (demo reset)."
echo "  - Stage 080 dest golden omits .hermes/_park; chaos never dest."
echo "  - Historical quarkus-migration-scaffold is not updated."
