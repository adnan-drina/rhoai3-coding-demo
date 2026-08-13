#!/usr/bin/env bash
# AD-H §16.4 / ER#2 F2 — OS-level deny-list for proving-min write fence.
# lock (default role=implementer): make ACK/gate/skill/SOUL/kanban.db non-writable
# unlock: restore u+w for Lead/human ack grants
set -euo pipefail

ROLE="${WRITE_FENCE_ROLE:-implementer}"
ROOT="."
ACTION="lock"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    lock|unlock|status)
      ACTION="$1"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -*)
      echo "usage: $0 [--dry-run] [ROOT] {lock|unlock|status}" >&2
      exit 2
      ;;
    *)
      ROOT="$1"
      shift
      ;;
  esac
done

ROOT="$(cd "${ROOT}" && pwd)"

DENY_DIRS=(
  "evidence/acks"
  "evidence/verdicts"
  ".hermes/skills"
)
# Note: do NOT chmod .hermes/home/kanban.db — Hermes kanban tools must write it.
# Ballot/DB tampering via write_file is refused by check-write-fence.py deny-list.
DENY_FILES=(
  "SOUL.md"
  ".hermes/SOUL.md"
)

# Validator may write verdicts; keep other deny paths locked.
if [[ "${ROLE}" == "validator" ]]; then
  DENY_DIRS=(
    "evidence/acks"
    ".hermes/skills"
  )
fi

lock_path() {
  local p="$1"
  if [[ -d "${p}" ]]; then
    find "${p}" -type f -exec chmod a-w {} + 2>/dev/null || true
    find "${p}" -type d -exec chmod a-w {} + 2>/dev/null || true
    find "${p}" -type d -exec chmod u+x,g+x,o+x {} + 2>/dev/null || true
  elif [[ -f "${p}" ]]; then
    chmod a-w "${p}" 2>/dev/null || true
  fi
}

unlock_path() {
  local p="$1"
  if [[ -d "${p}" ]]; then
    find "${p}" -type d -exec chmod u+wx {} + 2>/dev/null || true
    find "${p}" -type f -exec chmod u+w {} + 2>/dev/null || true
  elif [[ -f "${p}" ]]; then
    chmod u+w "${p}" 2>/dev/null || true
  fi
}

case "${ACTION}" in
  lock)
    if [[ "${DRY_RUN}" == "1" ]]; then
      echo "DRY-RUN: write-fence LOCK role=${ROLE} root=${ROOT}"
      for rel in "${DENY_DIRS[@]}"; do
        echo "DRY-RUN: would lock ${ROOT}/${rel}"
      done
      for rel in "${DENY_FILES[@]}"; do
        [[ -e "${ROOT}/${rel}" ]] || continue
        echo "DRY-RUN: would lock ${ROOT}/${rel}"
      done
      exit 0
    fi
    for rel in "${DENY_DIRS[@]}"; do
      mkdir -p "${ROOT}/${rel}"
      lock_path "${ROOT}/${rel}"
    done
    for rel in "${DENY_FILES[@]}"; do
      [[ -e "${ROOT}/${rel}" ]] || continue
      lock_path "${ROOT}/${rel}"
    done
    echo "OK: write-fence LOCKED role=${ROLE} root=${ROOT}"
    ;;
  unlock)
    if [[ "${DRY_RUN}" == "1" ]]; then
      echo "DRY-RUN: write-fence UNLOCK role=${ROLE} root=${ROOT}"
      for rel in "${DENY_DIRS[@]}"; do
        [[ -e "${ROOT}/${rel}" ]] || continue
        echo "DRY-RUN: would unlock ${ROOT}/${rel}"
      done
      for rel in "${DENY_FILES[@]}"; do
        [[ -e "${ROOT}/${rel}" ]] || continue
        echo "DRY-RUN: would unlock ${ROOT}/${rel}"
      done
      exit 0
    fi
    for rel in "${DENY_DIRS[@]}"; do
      [[ -e "${ROOT}/${rel}" ]] || continue
      unlock_path "${ROOT}/${rel}"
    done
    for rel in "${DENY_FILES[@]}"; do
      [[ -e "${ROOT}/${rel}" ]] || continue
      unlock_path "${ROOT}/${rel}"
    done
    echo "OK: write-fence UNLOCKED root=${ROOT}"
    ;;
  status)
    echo "role=${ROLE} root=${ROOT}"
    for rel in "${DENY_DIRS[@]}" "${DENY_FILES[@]}"; do
      p="${ROOT}/${rel}"
      if [[ -e "${p}" ]]; then
        ls -ld "${p}" | awk -v r="${rel}" '{print r, $1}'
      else
        echo "${rel} MISSING"
      fi
    done
    ;;
  *)
    echo "usage: $0 [ROOT] {lock|unlock|status}" >&2
    exit 2
    ;;
esac
