#!/usr/bin/env bash
# LG9a — run the harness suite against a materialised git index.
#
# SR-14's in-tree check is `git ls-files` (index membership). The rest of
# validate.sh reads the work tree, so a dirty tree can pass while the index
# (what ships) would fail. This script:
#   1. runs tip-sync on the live scaffold (SR-14 membership)
#   2. `git checkout-index -a --prefix=<tmp>/`
#   3. runs validate.sh on that snapshot
#
# Install as .git/hooks/pre-commit (dest provision does this when .git exists).
# Do not recurse: VALIDATE_INDEX_SNAPSHOT=1 skips a nested snapshot.
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
pre-commit-index-suite.sh — materialise the git index and run validate-contracts.

Usage:
  pre-commit-index-suite.sh
  pre-commit-index-suite.sh --help

Must run inside a git work tree. Exit 0 if tip-sync + snapshot suite pass.
USAGE
    exit 0
    ;;
esac

if [[ "${VALIDATE_INDEX_SNAPSHOT:-}" == "1" ]]; then
  echo "pre-commit-index-suite: refusing nested snapshot (VALIDATE_INDEX_SNAPSHOT=1)" >&2
  exit 2
fi

command -v git >/dev/null 2>&1 || { echo "pre-commit-index-suite: git required" >&2; exit 2; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "pre-commit-index-suite: not a git work tree" >&2; exit 2; }

TOPLEVEL="$(git rev-parse --show-toplevel)"
if [[ -f "${TOPLEVEL}/migration.yaml" ]]; then
  LIVE="${TOPLEVEL}"
elif [[ -f "${TOPLEVEL}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/migration.yaml" ]]; then
  LIVE="${TOPLEVEL}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
else
  echo "pre-commit-index-suite: no migration.yaml under ${TOPLEVEL} (not a dest/platform scaffold tree)" >&2
  exit 2
fi

TIP_SYNC="${LIVE}/.hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py"
VALIDATE="${LIVE}/.hermes/skills/harness/validate-contracts/scripts/validate.sh"
[[ -f "${TIP_SYNC}" ]] || { echo "pre-commit-index-suite: missing ${TIP_SYNC}" >&2; exit 1; }
[[ -f "${VALIDATE}" ]] || { echo "pre-commit-index-suite: missing ${VALIDATE}" >&2; exit 1; }

echo "pre-commit-index-suite: tip-sync on live work tree ${LIVE}"
python3 "${TIP_SYNC}" "${LIVE}"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/sr14-index.XXXXXX")"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

echo "pre-commit-index-suite: git checkout-index -a --prefix=${TMP}/"
git -C "${TOPLEVEL}" checkout-index -a --prefix="${TMP}/"

if [[ -f "${TMP}/migration.yaml" ]]; then
  SNAP="${TMP}"
else
  SNAP="${TMP}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
fi
[[ -f "${SNAP}/migration.yaml" ]] || {
  echo "pre-commit-index-suite: snapshot missing migration.yaml at ${SNAP}" >&2
  exit 1
}

echo "pre-commit-index-suite: validate.sh on index snapshot ${SNAP}"
export VALIDATE_INDEX_SNAPSHOT=1
bash "${SNAP}/.hermes/skills/harness/validate-contracts/scripts/validate.sh"
echo "pre-commit-index-suite: index snapshot suite passed"
