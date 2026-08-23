#!/usr/bin/env bash
# Publish the Stage 080 authoring tree to the v2 golden GitHub repo.
# Idempotent: re-running force-pushes the golden (v2 reset).
#
# Authoring: stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold
# Golden:    github.com/${GITHUB_OWNER}/quarkus-migration-scaffold-v2
#
# Dest clones omit .hermes/_park/ (ST-10 / Architect E-20260822T135403Z).
# Platform git keeps that tree (requeue residue; mint drawer deleted after
# K4). Chaos matrix never dest. Do not mkdir empty .hermes/kernel/ here;
# empty .hermes/kernel/ here; golden ships K2 REHOST pre_tool_call.sh plus
# K1/K3/K4 Python. GitOps copies only the hook into Managed Scope. Do not
# dest-apply a REHOST or K4 as a new fence. Do not run this script this
# sitting unless Operator names it.
#
# This script does not touch:
#   - quarkus-migration-scaffold (v1 live golden)
#   - agentic-quarkus-scaffold (stage 070)
#
# Do not run scripts/bootstrap-scaffold-repos.sh from branch harness-v2
# (that force-pushes v1). Do not GitHub-rename the v1 golden.
#
# DRY_RUN=1 stages a temp tree, omits _park, asserts chaos absent, and
# exits without gh / force-push (Operator publish GO still required).
#
# Topics: default is none. rhoai3-scaffolded would treat this golden as a
# dest (Argo namespace + pipeline). rhoai3-golden-path is the v1 golden
# reset topic — add it only when you intend that wiring for -v2.
#
# Requires: gh (authenticated with repo scope), git — unless DRY_RUN=1.
# No cluster access.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITHUB_OWNER="${GITHUB_OWNER:-adnan-drina}"
GOLDEN_REPO="${MIGRATION_GOLDEN_REPO:-quarkus-migration-scaffold-v2}"
SRC="$REPO_ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
DRY_RUN="${DRY_RUN:-0}"

log() { echo -e "\033[0;34m[scaffold-v2]\033[0m $*"; }
warn() { echo -e "\033[1;33m[scaffold-v2][WARN]\033[0m $*"; }

if [[ "$GOLDEN_REPO" == "quarkus-migration-scaffold" ]]; then
  echo "REFUSE: this script must not force-push the v1 golden '${GOLDEN_REPO}'." >&2
  echo "Use scripts/bootstrap-scaffold-repos.sh from overlay-a8-publish for v1." >&2
  exit 1
fi

command -v git >/dev/null || { echo "git is required"; exit 1; }
test -f "$SRC/migration.yaml" || { echo "REFUSE: missing authoring tree at $SRC"; exit 1; }
test -d "$SRC/.hermes/_park" || {
  echo "REFUSE: authoring tree missing .hermes/_park (platform git must keep it)" >&2
  exit 1
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

log "Staging ${GOLDEN_REPO} from scaffold-repo/quarkus-migration-scaffold"
cp -R "$SRC" "$WORKDIR/${GOLDEN_REPO}"
omit_park_from_staged "$WORKDIR/${GOLDEN_REPO}"
log "Omitted .hermes/_park from dest golden (authoring-only; chaos never dest)"
log "Authoring _park tracked=$(git -C "$REPO_ROOT" ls-files -- "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/_park" | wc -l | tr -d ' '); dest staged _park=absent"

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: no gh, no force-push. Staged ${WORKDIR}/${GOLDEN_REPO}"
  test ! -e "$WORKDIR/${GOLDEN_REPO}/.hermes/_park"
  test -d "$SRC/.hermes/_park"
  exit 0
fi

command -v gh >/dev/null || { echo "gh CLI is required"; exit 1; }
gh auth status >/dev/null || { echo "gh is not authenticated"; exit 1; }

ensure_repo() {
  local repo="$1" description="$2"
  if ! gh repo view "${GITHUB_OWNER}/${repo}" >/dev/null 2>&1; then
    log "Creating github.com/${GITHUB_OWNER}/${repo}"
    gh repo create "${GITHUB_OWNER}/${repo}" --public --description "${description}"
  fi
  # Do not add rhoai3-golden-path / rhoai3-scaffolded here. See header.
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

ensure_repo "${GOLDEN_REPO}" \
  "Harness-v2 Quarkus migration scaffold golden (stage 080). Separate from v1 quarkus-migration-scaffold. Do not rename v1."
push_golden "$WORKDIR/${GOLDEN_REPO}" "${GOLDEN_REPO}" \
  "Golden state from rhoai3-coding-demo/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold (harness-v2)"

log "Done. Reminders:"
echo "  - Live overlay GitOps still fetches v1 until this branch's template.yaml is the Argo source."
echo "  - Dest comes from Developer Hub Application migration after that GitOps GO."
echo "  - Re-running this script force-pushes ${GOLDEN_REPO} only."
echo "  - Dest golden omits .hermes/_park (authoring-only; chaos never dest)."
echo "  - Leftover adnan-drina/greeting-v2 is not a dest. Do not provision it."
