#!/usr/bin/env bash
# Capture git show --stat (+ optional name-only) for O-DRV3 diff proof.
# Usage:
#   bash scripts/track-b/v9-capture-diff.sh <sha>          # local git in CWD or V9_APP_GIT
#   bash scripts/track-b/v9-capture-diff.sh --oc <sha>     # via oc exec workspace
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

USE_OC=0
if [ "${1:-}" = "--oc" ]; then USE_OC=1; shift; fi
SHA="${1:-}"
[ -n "$SHA" ] || qg_die "usage: $0 [--oc] <sha>"

OUT_DIR="${ROOT}/tmp/V9-DIFF-EVIDENCE"
mkdir -p "$OUT_DIR"
OUT="${OUT_DIR}/${SHA}.stat"
SHORT_OUT="${OUT_DIR}/${SHA:0:7}.stat"

if [ "$USE_OC" = "1" ]; then
  # shellcheck source=/dev/null
  source "${ROOT}/scripts/lib.sh"
  load_env >/dev/null
  check_oc_logged_in || {
    # best-effort re-login from .env
    set -a; [ -f "${ROOT}/.env" ] && source "${ROOT}/.env"; set +a
    if [ -n "${OPENSHIFT_API_URL:-}" ] && [ -n "${OPENSHIFT_USER:-}" ] && [ -n "${OPENSHIFT_PASSWORD:-}" ]; then
      oc login "$OPENSHIFT_API_URL" -u "$OPENSHIFT_USER" -p "$OPENSHIFT_PASSWORD" --insecure-skip-tls-verify=true >/dev/null
    fi
    check_oc_logged_in || qg_die "oc not logged in"
  }
  POD="$(qg_ws_pod)"
  NS="$(qg_ws_ns)"
  CTR="$(qg_ws_ctr)"
  {
    oc exec -n "$NS" "$POD" -c "$CTR" -- \
      git -C /projects/modernized show --stat --format=fuller "$SHA"
    echo "---"
    oc exec -n "$NS" "$POD" -c "$CTR" -- \
      git -C /projects/modernized show --name-only --format= "$SHA"
  } 2>/dev/null | qg_strip_oc_noise >"$OUT"
else
  GIT_DIR="${V9_APP_GIT:-.}"
  {
    git -C "$GIT_DIR" show --stat --format=fuller "$SHA"
    echo "---"
    git -C "$GIT_DIR" show --name-only --format= "$SHA"
  } >"$OUT"
fi

[ -s "$OUT" ] || qg_die "empty diff evidence for $SHA"
cp -f "$OUT" "$SHORT_OUT"
echo "diff evidence: $OUT ($(wc -l <"$OUT" | tr -d ' ') lines)"
