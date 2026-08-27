#!/usr/bin/env bash
# spec-kit 0.16.1 Hermes integration resolves skills via Path.home()/.hermes/skills
# (spec-kit#3334 unmerged). Point that lookup at the project skills root so a
# worker shell `specify workflow run speckit` finds speckit-specify where
# init-spec-workspace seeded it — without the worker prefixing HOME=.
# HOME is set only for this child. Do not collapse profile HOME.
# Do not add user-root external_dirs. Do not widen K2_ALLOW_ROOT.
set -euo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_has_speckit() {
  [[ -f "${1}/.hermes/skills/speckit-specify/SKILL.md" ]]
}

ROOT=""
if [[ "${1:-}" == "--root" ]]; then
  ROOT="$(cd "${2:?--root needs a directory}" && pwd)"
  shift 2
fi
SPECIFY_ARGS=("$@")

if [[ -z "${ROOT}" ]]; then
  if [[ -n "${SPECIFY_PROJECT_ROOT:-}" ]]; then
    ROOT="$(cd "${SPECIFY_PROJECT_ROOT}" && pwd)"
  elif _has_speckit "$(pwd)"; then
    ROOT="$(pwd)"
  elif _has_speckit "/projects/modernized"; then
    ROOT="/projects/modernized"
  else
    d="$(pwd)"
    while [[ "${d}" != "/" ]]; do
      if _has_speckit "${d}"; then
        ROOT="${d}"
        break
      fi
      d="$(dirname "${d}")"
    done
  fi
fi

if [[ -z "${ROOT}" ]]; then
  echo "specify-from-project: no project skills root (missing .hermes/skills/speckit-specify)" >&2
  exit 1
fi
# dest-init PATH shim is `exec bash …/specify-from-project.sh` (Architect
# 131720ZA: 1744 concurrent helpers). A PATH search for `specify` can
# rediscover that shim. SPECIFY_REAL is the intended seam
# (Architect 153721ZA): dest-init / install-specify-shim bake the uv
# specify-cli path into the wrapper. Do not PATH-search. Do not prefer a
# wrapper. Do not widen K2_ALLOW_ROOT.
_is_wrapper() {
  local cand="$1"
  [[ -f "${cand}" ]] || return 1
  grep -qF "specify-from-project.sh" "${cand}" 2>/dev/null
}

if [[ -z "${SPECIFY_REAL:-}" ]]; then
  echo "specify-from-project: SPECIFY_REAL unset (dest-init must export the uv specify path)" >&2
  exit 1
fi
REAL="${SPECIFY_REAL}"
if [[ ! -x "${REAL}" ]]; then
  echo "specify-from-project: SPECIFY_REAL not executable: ${REAL}" >&2
  exit 1
fi
if _is_wrapper "${REAL}"; then
  echo "specify-from-project: refusing wrapper ${REAL} (re-enters this script)" >&2
  exit 1
fi

export HOME="${ROOT}"
set +e
"${REAL}" "${SPECIFY_ARGS[@]}"
_rc=$?
set -e
python3 "${_here}/stamp-speckit-workflow-receipt.py" "${ROOT}" "${_rc}" \
  "${SPECIFY_ARGS[@]}"
exit "${_rc}"
