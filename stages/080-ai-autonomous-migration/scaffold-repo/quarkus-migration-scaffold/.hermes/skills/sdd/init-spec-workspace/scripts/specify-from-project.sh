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

# Skip dest helper wrappers so exec does not recurse into this script.
# dest-init writes the same wrapper to ${ROOT}/.hermes/bin AND
# /projects/.platform/hermes/bin. Architect 131720ZA: preferring the
# platform copy is a fork bomb (1744 helpers). Restore the skip of
# `.platform/hermes/bin` and `/etc/hermes/bin` (revert 104855ZL
# narrowing). v10 M2 uv Unknown skill stays OPEN; do not prefer a
# wrapper to paper over it. Do not widen K2_ALLOW_ROOT.
_skip_dirs="${_here}:${ROOT}/.hermes/bin"
_skip_dirs="${_skip_dirs}:/projects/.platform/hermes/bin:/etc/hermes/bin"
if [[ -n "${HERMES_MANAGED_DIR:-}" ]]; then
  _skip_dirs="${_skip_dirs}:${HERMES_MANAGED_DIR}/bin"
fi

_abs_dir() {
  local p="$1"
  if [[ -d "${p}" ]]; then
    (cd "${p}" && pwd)
  else
    printf '%s\n' "${p}"
  fi
}

# dest-init PATH shim is `exec bash …/specify-from-project.sh` (Architect
# 131720ZA: 1744 concurrent helpers). Prefer/exec of that file is a loop.
_is_wrapper() {
  local cand="$1"
  [[ -f "${cand}" ]] || return 1
  grep -qF "specify-from-project.sh" "${cand}" 2>/dev/null
}

_is_skip() {
  local abs="$1"
  local s sabs
  local IFS=':'
  local -a skips
  # dest-init copies this helper to any */.platform/hermes/bin/specify
  # (dest-11 postStart: preferring that copy recursed to shell-level 1000).
  case "${abs}" in
    */.platform/hermes/bin|/etc/hermes/bin)
      return 0
      ;;
  esac
  read -r -a skips <<< "${_skip_dirs}"
  for s in "${skips[@]}"; do
    [[ -z "${s}" ]] && continue
    sabs="$(_abs_dir "${s}")"
    if [[ "${abs}" == "${sabs}" ]]; then
      return 0
    fi
  done
  return 1
}

_filtered_path=""
IFS=':' read -r -a _path_parts <<< "${PATH}"
for _p in "${_path_parts[@]}"; do
  [[ -z "${_p}" ]] && continue
  _abs="$(_abs_dir "${_p}")"
  if _is_skip "${_abs}"; then
    continue
  fi
  if _is_wrapper "${_p}/specify"; then
    continue
  fi
  if [[ -z "${_filtered_path}" ]]; then
    _filtered_path="${_p}"
  else
    _filtered_path="${_filtered_path}:${_p}"
  fi
done

REAL=""
if [[ -n "${SPECIFY_REAL:-}" ]]; then
  REAL="${SPECIFY_REAL}"
else
  REAL="$(PATH="${_filtered_path}" command -v specify || true)"
fi

if [[ -z "${REAL}" || ! -x "${REAL}" ]]; then
  echo "specify-from-project: specify not on PATH (after skipping shims)" >&2
  exit 1
fi
if [[ -z "${SPECIFY_REAL:-}" ]] && _is_wrapper "${REAL}"; then
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
