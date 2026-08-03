#!/usr/bin/env bash
# O-HERMESPREFLIGHT — fail-closed pod↔worktree .hermes parity before outer start.
#
# Compares a stable digest of the golden scaffold `.hermes` tree against the
# live DevWorkspace pod (or two local trees for instruments). Mismatch → RED
# with a clear refuse message. Does NOT start outer-loop.
#
# Usage:
#   bash scripts/track-b/v10-hermes-parity.sh                 # golden vs pod
#   bash scripts/track-b/v10-hermes-parity.sh --digest DIR    # print digest
#   bash scripts/track-b/v10-hermes-parity.sh --compare A B   # local A vs B
#   bash scripts/track-b/v10-hermes-parity.sh --key-files DIR # list+hash keys
#
# Env:
#   V10_WS_NAME / V8_WS_NS / V8_WS_CONTAINER — workspace targeting
#   V9_SKIP_HERMES_PARITY=1 — skip (escape hatch only; log WARN)
#   HERMES_PARITY_ROOT — override golden scaffold root (contains .hermes/)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

SCAFFOLD_DEFAULT="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
SCAFFOLD="${HERMES_PARITY_ROOT:-$SCAFFOLD_DEFAULT}"

# Critical harness files that must exist on both sides (clear RED when missing).
HERMES_KEY_FILES=(
  .hermes/harness/plan-lint.py
  .hermes/harness/supervisor.sh
  .hermes/harness/outer-loop.sh
  .hermes/harness/sensors.sh
  .hermes/harness/plan-corpus-lint.sh
  .hermes/harness/oracle_derive.py
  .hermes/harness/m3-all-lint.sh
  .hermes/harness/tests/instruments.sh
  .hermes/harness/defaults-inventory.sh
)

_file_md5() {
  local f="$1"
  if command -v md5sum >/dev/null 2>&1; then
    md5sum "$f" | awk '{print $1}'
  else
    md5 -q "$f"
  fi
}

_stream_md5() {
  if command -v md5sum >/dev/null 2>&1; then
    md5sum | awk '{print $1}'
  else
    md5 -q
  fi
}

# Resolve DIR to the directory that contains `.hermes/`.
_hermes_parent() {
  local root="$1"
  if [ -d "${root}/.hermes" ]; then
    printf '%s\n' "$root"
  elif [ "$(basename "$root")" = ".hermes" ] && [ -d "$root" ]; then
    printf '%s\n' "$(cd "$(dirname "$root")" && pwd)"
  else
    echo "O-HERMESPREFLIGHT: no .hermes under $root" >&2
    return 1
  fi
}

# Print DIGEST=<hex> FILES=<n> for the .hermes tree under DIR (O-HERMESPARITYSEM).
hermes_digest() {
  local parent files digest
  parent="$(_hermes_parent "$1")" || return 1
  files="$(
    (cd "$parent" && qg_hermes_list_semantic_files | wc -l | tr -d ' ')
  )"
  if [ "${files:-0}" -lt 1 ]; then
    echo "O-HERMESPREFLIGHT: empty .hermes tree under $parent" >&2
    return 1
  fi
  digest="$(
    (cd "$parent" && qg_hermes_list_semantic_files \
      | while IFS= read -r f; do
          printf '%s  %s\n' "$(_file_md5 "$f")" "$f"
        done) | _stream_md5
  )"
  printf 'DIGEST=%s FILES=%s\n' "$digest" "$files"
}

# Fail if any HERMES_KEY_FILES is missing under DIR; print path=md5 lines.
hermes_key_files() {
  local parent f
  parent="$(_hermes_parent "$1")" || return 1
  for f in "${HERMES_KEY_FILES[@]}"; do
    if [ ! -f "${parent}/${f}" ]; then
      echo "O-HERMESPREFLIGHT: missing key file: ${parent}/${f}" >&2
      return 1
    fi
    printf '%s  %s\n' "$(_file_md5 "${parent}/${f}")" "$f"
  done
}

compare_local() {
  local a="$1" b="$2"
  local da db ka kb
  echo "O-HERMESPREFLIGHT: comparing local trees"
  echo "  A=$a"
  echo "  B=$b"
  ka="$(hermes_key_files "$a")" || {
    echo "O-HERMESPREFLIGHT: REFUSE — key-file check failed on A" >&2
    return 1
  }
  kb="$(hermes_key_files "$b")" || {
    echo "O-HERMESPREFLIGHT: REFUSE — key-file check failed on B" >&2
    return 1
  }
  if [ "$ka" != "$kb" ]; then
    echo "O-HERMESPREFLIGHT: REFUSE — key-file md5 mismatch" >&2
    echo "--- A keys ---" >&2
    echo "$ka" >&2
    echo "--- B keys ---" >&2
    echo "$kb" >&2
    return 1
  fi
  da="$(hermes_digest "$a")"
  db="$(hermes_digest "$b")"
  echo "  A: $da"
  echo "  B: $db"
  if [ "$da" != "$db" ]; then
    echo "O-HERMESPREFLIGHT: REFUSE — .hermes digest mismatch (pod/worktree out of sync)." >&2
    echo "  Tar-sync golden scaffold: bash scripts/track-b/v10-prep-fresh-rerun.sh" >&2
    echo "  (or: cd scaffold && tar cf - .hermes | oc exec -i … tar xf -)" >&2
    return 1
  fi
  echo "O-HERMESPREFLIGHT: GREEN — digests match ($da)"
  return 0
}

compare_pod() {
  local parent pod ns ctr local_d pod_d pod_out ws_name
  parent="$(_hermes_parent "$SCAFFOLD")" || return 1
  hermes_key_files "$parent" >/dev/null || {
    echo "O-HERMESPREFLIGHT: REFUSE — golden scaffold missing key files under $parent" >&2
    return 1
  }
  local_d="$(hermes_digest "$parent")"
  if ! command -v oc >/dev/null 2>&1; then
    echo "O-HERMESPREFLIGHT: REFUSE — oc required for pod parity (or use --compare)" >&2
    return 1
  fi
  # shellcheck source=/dev/null
  source "${ROOT}/scripts/lib.sh"
  load_env >/dev/null 2>&1 || true
  check_oc_logged_in
  # O-HERMESWSRESOLVE: resolve Running DW (or explicit V10_WS_NAME) before probe.
  ws_name="$(qg_ws_name)" || {
    echo "O-HERMESPREFLIGHT: REFUSE — workspace unresolved (set V10_WS_NAME or one Running DevWorkspace)" >&2
    return 1
  }
  pod="$(qg_ws_pod)" || {
    echo "O-HERMESPREFLIGHT: REFUSE — no Running pod for workspace ${ws_name}" >&2
    return 1
  }
  ns="$(qg_ws_ns)"
  ctr="$(qg_ws_ctr)"
  echo "O-HERMESPREFLIGHT: golden=$local_d"
  echo "O-HERMESPREFLIGHT: workspace=${ws_name}"
  echo "O-HERMESPREFLIGHT: probing ${ns}/${pod} .hermes …"
  # Same semantic digest as host (O-HERMESPARITYSEM) — portable md5sum/md5.
  pod_out="$(
    oc exec -n "$ns" "$pod" -c "$ctr" -- bash -lc '
      set -euo pipefail
      cd /projects/modernized
      if [ ! -d .hermes ]; then
        echo "MISSING_HERMES" >&2
        exit 2
      fi
      for f in \
        .hermes/harness/plan-lint.py \
        .hermes/harness/supervisor.sh \
        .hermes/harness/outer-loop.sh \
        .hermes/harness/sensors.sh \
        .hermes/harness/plan-corpus-lint.sh \
        .hermes/harness/oracle_derive.py \
        .hermes/harness/m3-all-lint.sh \
        .hermes/harness/tests/instruments.sh \
        .hermes/harness/defaults-inventory.sh
      do
        if [ ! -f "$f" ]; then
          echo "MISSING_KEY:$f" >&2
          exit 3
        fi
      done
      _fm() {
        if command -v md5sum >/dev/null 2>&1; then md5sum "$1" | awk "{print \$1}"
        else md5 -q "$1"; fi
      }
      _sm() {
        if command -v md5sum >/dev/null 2>&1; then md5sum | awk "{print \$1}"
        else md5 -q; fi
      }
      # Keep predicates identical to qg_hermes_list_semantic_files (O-HERMESPARITYSEM).
      _list() {
        find .hermes -type f ! -path "*/__pycache__/*" ! -name "*.pyc" ! -name ".DS_Store" \
          ! -name "*.bak" ! -name "._*" \
          ! -path "./.hermes/harness/.published-fp" ! -name ".published-fp" \
          ! -path "./.hermes/harness/defaults-inventory.md" ! -name "defaults-inventory.md" \
          ! -path "./.hermes/harness/guard-manifest.md" ! -name "guard-manifest.md" \
          | LC_ALL=C sort
      }
      files=$(_list | wc -l | tr -d " ")
      digest=$(_list | while IFS= read -r f; do printf "%s  %s\n" "$(_fm "$f")" "$f"; done | _sm)
      printf "DIGEST=%s FILES=%s\n" "$digest" "$files"
    ' 2>&1
  )" || {
    echo "O-HERMESPREFLIGHT: REFUSE — oc exec failed or pod .hermes incomplete" >&2
    echo "$pod_out" | qg_strip_oc_noise >&2 || echo "$pod_out" >&2
    echo "  Sync: bash scripts/track-b/v10-prep-fresh-rerun.sh (tar .hermes → workspace)" >&2
    return 1
  }
  pod_d="$(printf '%s\n' "$pod_out" | qg_strip_oc_noise | grep -E '^DIGEST=' | tail -1 || true)"
  if [ -z "$pod_d" ]; then
    echo "O-HERMESPREFLIGHT: REFUSE — could not parse pod digest" >&2
    echo "$pod_out" >&2
    return 1
  fi
  echo "O-HERMESPREFLIGHT: pod=$pod_d"
  if [ "$local_d" != "$pod_d" ]; then
    echo "O-HERMESPREFLIGHT: REFUSE — pod .hermes does not match worktree golden scaffold." >&2
    echo "  golden: $local_d" >&2
    echo "  pod:    $pod_d" >&2
    echo "  workspace: ${ws_name} (${ns}/${pod})" >&2
    echo "  Fix: tar-sync golden .hermes (v10-prep-fresh-rerun.sh) then re-run preflight." >&2
    echo "  Do not start outer-loop on a stale harness." >&2
    return 1
  fi
  echo "O-HERMESPREFLIGHT: GREEN — pod .hermes matches worktree ($local_d)"
  return 0
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/track-b/v10-hermes-parity.sh                 # golden vs pod
  bash scripts/track-b/v10-hermes-parity.sh --digest DIR
  bash scripts/track-b/v10-hermes-parity.sh --compare A B
  bash scripts/track-b/v10-hermes-parity.sh --key-files DIR
EOF
}

if [ "${V9_SKIP_HERMES_PARITY:-0}" = "1" ]; then
  echo "O-HERMESPREFLIGHT: WARN — skipped (V9_SKIP_HERMES_PARITY=1)" >&2
  exit 0
fi

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --digest)
    [ -n "${2:-}" ] || { usage >&2; exit 2; }
    hermes_digest "$2"
    ;;
  --key-files)
    [ -n "${2:-}" ] || { usage >&2; exit 2; }
    hermes_key_files "$2"
    ;;
  --compare)
    [ -n "${2:-}" ] && [ -n "${3:-}" ] || { usage >&2; exit 2; }
    compare_local "$2" "$3"
    ;;
  "")
    compare_pod
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
