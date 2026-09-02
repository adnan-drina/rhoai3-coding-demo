#!/usr/bin/env bash
# O-GOLDENFRESH — publish-fp stamp + three-way repo/published/pod parity.
#
# Catches commit-lag / stale-scaffold class (R-88 / F-6): harness work landed
# in the demo-repo golden tree but never published, or pod still on an older
# published fingerprint. Distinct from O-HERMESPREFLIGHT (worktree↔pod only).
#
# Stamp path: .hermes/harness/.published-fp
# Digest intentionally EXCLUDES the stamp file so stamping is stable.
#
# Usage:
#   bash scripts/track-b/v10-golden-fresh.sh                 # three-way (repo/stamp/pod)
#   bash scripts/track-b/v10-golden-fresh.sh --stamp [DIR]   # write stamp for DIR
#   bash scripts/track-b/v10-golden-fresh.sh --digest DIR    # print DIGEST=… FILES=…
#   bash scripts/track-b/v10-golden-fresh.sh --check-local DIR
#       # repo digest vs stamp only (no oc; instruments)
#   bash scripts/track-b/v10-golden-fresh.sh --check-local-mismatch DIR
#       # instrument helper: force RED when stamp disagrees with tree
#
# Env:
#   HERMES_PARITY_ROOT — override golden scaffold root (contains .hermes/)
#   V9_SKIP_GOLDEN_FRESH=1 — skip (escape hatch only; log WARN)
#   V10_WS_NAME / V8_WS_NS / V8_WS_CONTAINER — workspace targeting
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
qg_refuse_retired_wave5_harness

SCAFFOLD_DEFAULT="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
SCAFFOLD="${HERMES_PARITY_ROOT:-$SCAFFOLD_DEFAULT}"
STAMP_REL=".hermes/harness/.published-fp"

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

_hermes_parent() {
  local root="$1"
  if [ -d "${root}/.hermes" ]; then
    printf '%s\n' "$root"
  elif [ "$(basename "$root")" = ".hermes" ] && [ -d "$root" ]; then
    printf '%s\n' "$(cd "$(dirname "$root")" && pwd)"
  else
    echo "O-GOLDENFRESH: no .hermes under $root" >&2
    return 1
  fi
}

# Digest of .hermes under DIR (O-HERMESPARITYSEM — shared with v10-hermes-parity.sh).
publish_digest() {
  local parent files digest
  parent="$(_hermes_parent "$1")" || return 1
  files="$(
    (cd "$parent" && qg_hermes_list_semantic_files | wc -l | tr -d ' ')
  )"
  if [ "${files:-0}" -lt 1 ]; then
    echo "O-GOLDENFRESH: empty .hermes tree under $parent" >&2
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

write_stamp() {
  local parent line
  parent="$(_hermes_parent "${1:-$SCAFFOLD}")" || return 1
  mkdir -p "${parent}/.hermes/harness"
  line="$(publish_digest "$parent")" || return 1
  {
    echo "# O-GOLDENFRESH publish fingerprint — written by v10-golden-fresh.sh / bootstrap-scaffold-repos.sh"
    echo "# Compare with live tree digest (stamp file excluded from hash)."
    echo "$line"
    echo "STAMPED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "${parent}/${STAMP_REL}"
  echo "O-GOLDENFRESH: wrote ${parent}/${STAMP_REL}"
  echo "O-GOLDENFRESH: $line"
}

read_stamp() {
  local parent stamp dig
  parent="$(_hermes_parent "$1")" || return 1
  stamp="${parent}/${STAMP_REL}"
  if [ ! -f "$stamp" ]; then
    echo "O-GOLDENFRESH: REFUSE — missing publish stamp ${stamp}" >&2
    echo "  Fix: bash scripts/track-b/v10-golden-fresh.sh --stamp" >&2
    echo "       then re-run bootstrap-scaffold-repos.sh before next provision." >&2
    return 1
  fi
  dig="$(grep -E '^DIGEST=' "$stamp" | tail -1 || true)"
  if [ -z "$dig" ]; then
    echo "O-GOLDENFRESH: REFUSE — stamp missing DIGEST= line: $stamp" >&2
    return 1
  fi
  printf '%s\n' "$dig"
}

check_local() {
  local parent repo_d pub_d
  parent="$(_hermes_parent "${1:-$SCAFFOLD}")" || return 1
  repo_d="$(publish_digest "$parent")" || return 1
  pub_d="$(read_stamp "$parent")" || return 1
  echo "O-GOLDENFRESH: repo=$repo_d"
  echo "O-GOLDENFRESH: published=$pub_d"
  if [ "$repo_d" != "$pub_d" ]; then
    echo "O-GOLDENFRESH: REFUSE — repo golden digest ≠ publish stamp (commit/publish lag)." >&2
    echo "  repo:      $repo_d" >&2
    echo "  published: $pub_d" >&2
    echo "  Fix: stamp+publish: bash scripts/track-b/v10-golden-fresh.sh --stamp && bash scripts/bootstrap-scaffold-repos.sh" >&2
    echo "       then tar-sync / refresh workspace before outer start." >&2
    return 1
  fi
  echo "O-GOLDENFRESH: GREEN — repo matches publish stamp ($repo_d)"
  return 0
}

pod_publish_digest() {
  local pod ns ctr pod_out
  if ! command -v oc >/dev/null 2>&1; then
    echo "O-GOLDENFRESH: REFUSE — oc required for pod leg (or use --check-local)" >&2
    return 1
  fi
  # shellcheck source=/dev/null
  source "${ROOT}/scripts/lib.sh"
  load_env >/dev/null 2>&1 || true
  # stdout of this function is only the DIGEST= line (captured by callers) —
  # keep check_oc / resolve chatter on stderr.
  check_oc_logged_in >&2
  local ws_name
  ws_name="$(qg_ws_name)" || {
    echo "O-GOLDENFRESH: REFUSE — workspace unresolved (set V10_WS_NAME or one Running DevWorkspace)" >&2
    return 1
  }
  pod="$(qg_ws_pod)" || {
    echo "O-GOLDENFRESH: REFUSE — no Running pod for workspace ${ws_name}" >&2
    return 1
  }
  ns="$(qg_ws_ns)"
  ctr="$(qg_ws_ctr)"
  echo "O-GOLDENFRESH: workspace=${ws_name} pod=${ns}/${pod}" >&2
  pod_out="$(
    oc exec -n "$ns" "$pod" -c "$ctr" -- bash -lc '
      set -euo pipefail
      cd /projects/modernized
      if [ ! -d .hermes ]; then
        echo "MISSING_HERMES" >&2
        exit 2
      fi
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
    echo "O-GOLDENFRESH: REFUSE — oc exec failed or pod .hermes incomplete" >&2
    echo "$pod_out" | qg_strip_oc_noise >&2 || echo "$pod_out" >&2
    return 1
  }
  printf '%s\n' "$pod_out" | qg_strip_oc_noise | grep -E '^DIGEST=' | tail -1
}

check_three_way() {
  local parent repo_d pub_d pod_d
  parent="$(_hermes_parent "$SCAFFOLD")" || return 1
  repo_d="$(publish_digest "$parent")" || return 1
  pub_d="$(read_stamp "$parent")" || return 1
  echo "O-GOLDENFRESH: repo=$repo_d"
  echo "O-GOLDENFRESH: published=$pub_d"
  if [ "$repo_d" != "$pub_d" ]; then
    echo "O-GOLDENFRESH: REFUSE — repo golden digest ≠ publish stamp (commit/publish lag)." >&2
    echo "  repo:      $repo_d" >&2
    echo "  published: $pub_d" >&2
    echo "  Fix: bash scripts/track-b/v10-golden-fresh.sh --stamp && bash scripts/bootstrap-scaffold-repos.sh" >&2
    return 1
  fi
  pod_d="$(pod_publish_digest)" || return 1
  if [ -z "$pod_d" ]; then
    echo "O-GOLDENFRESH: REFUSE — could not parse pod digest" >&2
    return 1
  fi
  echo "O-GOLDENFRESH: pod=$pod_d"
  if [ "$pod_d" != "$pub_d" ]; then
    echo "O-GOLDENFRESH: REFUSE — pod .hermes ≠ publish stamp (stale workspace / partial sync)." >&2
    echo "  published: $pub_d" >&2
    echo "  pod:       $pod_d" >&2
    echo "  Fix: full golden .hermes tar-sync (v10-prep-fresh-rerun.sh) then re-run preflight." >&2
    echo "  Do not start outer-loop on a stale or partially synced harness." >&2
    return 1
  fi
  echo "O-GOLDENFRESH: GREEN — repo == published == pod ($repo_d)"
  return 0
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/track-b/v10-golden-fresh.sh                 # three-way repo/published/pod
  bash scripts/track-b/v10-golden-fresh.sh --stamp [DIR]
  bash scripts/track-b/v10-golden-fresh.sh --digest DIR
  bash scripts/track-b/v10-golden-fresh.sh --check-local [DIR]
EOF
}

if [ "${V9_SKIP_GOLDEN_FRESH:-0}" = "1" ]; then
  echo "O-GOLDENFRESH: WARN — skipped (V9_SKIP_GOLDEN_FRESH=1)" >&2
  exit 0
fi

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --digest)
    [ -n "${2:-}" ] || { usage >&2; exit 2; }
    publish_digest "$2"
    ;;
  --stamp)
    write_stamp "${2:-$SCAFFOLD}"
    ;;
  --check-local)
    check_local "${2:-$SCAFFOLD}"
    ;;
  "")
    check_three_way
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
