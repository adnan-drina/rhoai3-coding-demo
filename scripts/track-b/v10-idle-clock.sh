#!/usr/bin/env bash
# O-IDLEWSFP — dual idle clock for Track B review/wake.
# O-HARNESSFP-POD — agent harness_fp includes a pod-side digest so hot-sync /
# tar-sync / instrument drops on the DevWorkspace are not invisible "idle".
#
# Usage:
#   bash scripts/track-b/v10-idle-clock.sh [--json]
#   bash scripts/track-b/v10-idle-clock.sh --self-test
#       # no oc; proves pod digest moves harness_fp / agent_idle / last_activity
#
# Prints:
#   workspace_fp=<head>-<outer>-<sup>   # run clock (stall detection)
#   host_fp=<12hex>                     # host golden harness digest
#   pod_fp=<12hex|none>                 # live pod harness digest (O-HARNESSFP-POD)
#   harness_fp=<12hex>                  # hash(host_fp|pod_fp) — agent-implementing
#   run_idle_s=<seconds since workspace_fp changed>
#   agent_idle_s=<seconds since harness_fp changed>
#   idle_note_basis=workspace_fp        # mandatory: run idle uses workspace only
#
# Env:
#   V10_WS_NAME / V8_WS_NS / V8_WS_CONTAINER — workspace targeting (O-HERMESWSRESOLVE)
#   V10_IDLE_POD_DIGEST — override pod_fp (instruments / --self-test; no oc)
#   V10_IDLE_HOST_DIGEST — override host_fp (instruments / --self-test)
#   V10_IDLE_STATE / V10_IDLE_POLL — override state + poll paths (self-test)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

JSON=0
SELFTEST=0
case "${1:-}" in
  --json) JSON=1 ;;
  --self-test) SELFTEST=1 ;;
  "") ;;
  *)
    echo "usage: $0 [--json|--self-test]" >&2
    exit 2
    ;;
esac

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

_short_fp() {
  printf '%s' "$1" | cut -c1-12
}

# Digest of harness *.sh/*.py under DIR (host or local fixture).
_host_harness_digest() {
  local dir="$1"
  local digest
  if [ -n "${V10_IDLE_HOST_DIGEST:-}" ]; then
    _short_fp "$V10_IDLE_HOST_DIGEST"
    return 0
  fi
  if [ ! -d "$dir" ]; then
    echo none
    return 0
  fi
  digest="$(
    (cd "$dir" && find . -type f \( -name '*.sh' -o -name '*.py' \) \
      ! -path './__pycache__/*' ! -name '*.pyc' \
      -print0 2>/dev/null \
      | sort -z \
      | while IFS= read -r -d '' f; do
          printf '%s  %s\n' "$(_file_md5 "$f")" "$f"
        done) | _stream_md5
  )"
  _short_fp "${digest:-none}"
}

# Digest of harness *.sh/*.py on the live pod (O-HARNESSFP-POD).
_pod_harness_digest() {
  local pod="$1" ns="$2" ctr="$3"
  local digest
  if [ -n "${V10_IDLE_POD_DIGEST:-}" ]; then
    _short_fp "$V10_IDLE_POD_DIGEST"
    return 0
  fi
  if [ -z "$pod" ]; then
    echo none
    return 0
  fi
  digest="$(
    oc exec -n "$ns" "$pod" -c "$ctr" -- bash -lc '
      set -e
      d=/projects/modernized/.hermes/harness
      if [ ! -d "$d" ]; then echo none; exit 0; fi
      cd "$d"
      if command -v md5sum >/dev/null 2>&1; then
        find . -type f \( -name "*.sh" -o -name "*.py" \) \
          ! -path "./__pycache__/*" ! -name "*.pyc" 2>/dev/null \
          | LC_ALL=C sort \
          | while IFS= read -r f; do md5sum "$f"; done \
          | md5sum | awk "{print \$1}"
      else
        find . -type f \( -name "*.sh" -o -name "*.py" \) \
          ! -path "./__pycache__/*" ! -name "*.pyc" 2>/dev/null \
          | LC_ALL=C sort \
          | while IFS= read -r f; do md5 -q "$f"; done \
          | md5 -q
      fi
    ' 2>/dev/null | tr -d '\r' | qg_strip_oc_noise | tail -1 | tr -d '[:space:]'
  )"
  if [ -z "$digest" ] || [ "$digest" = "none" ]; then
    echo none
  else
    _short_fp "$digest"
  fi
}

_combine_harness_fp() {
  local host="$1" pod="$2"
  _short_fp "$(printf '%s|%s' "$host" "$pod" | _stream_md5)"
}

# Update poll-state last_activity + harness_fp when agent fingerprint moves.
# Does NOT touch idle_note_level (review agent owns the ladder).
_update_poll_activity() {
  local poll="$1" harness="$2" host="$3" pod="$4" iso="$5"
  [ -f "$poll" ] || return 0
  local tmp
  tmp="$(mktemp)"
  # Rewrite known keys; append missing ones.
  awk -v hf="$harness" -v host="$host" -v pod="$pod" -v la="$iso" '
    BEGIN { seen_la=0; seen_hf=0; seen_host=0; seen_pod=0 }
    /^last_activity=/ { print "last_activity=" la; seen_la=1; next }
    /^harness_fp=/ { print "harness_fp=" hf; seen_hf=1; next }
    /^host_fp=/ { print "host_fp=" host; seen_host=1; next }
    /^pod_fp=/ { print "pod_fp=" pod; seen_pod=1; next }
    { print }
    END {
      if (!seen_la) print "last_activity=" la
      if (!seen_hf) print "harness_fp=" hf
      if (!seen_host) print "host_fp=" host
      if (!seen_pod) print "pod_fp=" pod
    }
  ' "$poll" >"$tmp"
  mv "$tmp" "$poll"
}

_run_self_test() {
  local tmp state poll out1 out2 fp1 fp2 idle2 la
  tmp=$(mktemp -d)
  state="$tmp/state"
  poll="$tmp/poll"
  cat >"$poll" <<'EOF'
last_poll=2026-01-01T00:00:00Z
last_activity=2026-01-01T00:00:00Z
harness_fp=oldvalue
idle_note_level=2
EOF
  # Tick 1: pod digest A
  V10_IDLE_HOST_DIGEST=hostaaaaaaaa \
  V10_IDLE_POD_DIGEST=podaaaaaaaaaa \
  V10_IDLE_STATE="$state" \
  V10_IDLE_POLL="$poll" \
  V10_WS_NAME=self-test-ws \
  V8_WS_POD= \
  QG_WS_RUNNING_LIST=self-test-ws \
    bash "$0" >"$tmp/out1" 2>"$tmp/err1" || {
      echo "self-test tick1 failed"; cat "$tmp/err1"; rm -rf "$tmp"; return 1
    }
  fp1=$(grep '^harness_fp=' "$tmp/out1" | cut -d= -f2)
  grep -q '^pod_fp=podaaaaaaaa' "$tmp/out1" || {
    echo "self-test: pod_fp missing on tick1"; cat "$tmp/out1"; rm -rf "$tmp"; return 1
  }
  # Tick 2: pod digest B (host unchanged) — must move harness_fp + reset agent_idle
  sleep 1
  V10_IDLE_HOST_DIGEST=hostaaaaaaaa \
  V10_IDLE_POD_DIGEST=podbbbbbbbbb \
  V10_IDLE_STATE="$state" \
  V10_IDLE_POLL="$poll" \
  V10_WS_NAME=self-test-ws \
  V8_WS_POD= \
  QG_WS_RUNNING_LIST=self-test-ws \
    bash "$0" >"$tmp/out2" 2>"$tmp/err2" || {
      echo "self-test tick2 failed"; cat "$tmp/err2"; rm -rf "$tmp"; return 1
    }
  fp2=$(grep '^harness_fp=' "$tmp/out2" | cut -d= -f2)
  idle2=$(grep '^agent_idle_s=' "$tmp/out2" | cut -d= -f2)
  la=$(grep '^last_activity=' "$poll" | cut -d= -f2)
  if [ "$fp1" = "$fp2" ]; then
    echo "self-test: harness_fp did not move on pod digest change ($fp1)"
    rm -rf "$tmp"
    return 1
  fi
  if [ "${idle2:-99}" -ne 0 ]; then
    echo "self-test: agent_idle_s=$idle2 expected 0 after pod move"
    rm -rf "$tmp"
    return 1
  fi
  if [ "$la" = "2026-01-01T00:00:00Z" ]; then
    echo "self-test: last_activity not refreshed from pod evidence"
    rm -rf "$tmp"
    return 1
  fi
  if grep -q '^idle_note_level=2$' "$poll"; then
    :
  else
    echo "self-test: idle_note_level must remain review-owned"
    cat "$poll"
    rm -rf "$tmp"
    return 1
  fi
  # Tick 3: same digests — agent_idle should advance (>0)
  sleep 1
  V10_IDLE_HOST_DIGEST=hostaaaaaaaa \
  V10_IDLE_POD_DIGEST=podbbbbbbbbb \
  V10_IDLE_STATE="$state" \
  V10_IDLE_POLL="$poll" \
  V10_WS_NAME=self-test-ws \
  V8_WS_POD= \
  QG_WS_RUNNING_LIST=self-test-ws \
    bash "$0" >"$tmp/out3" 2>"$tmp/err3" || {
      echo "self-test tick3 failed"; cat "$tmp/err3"; rm -rf "$tmp"; return 1
    }
  idle3=$(grep '^agent_idle_s=' "$tmp/out3" | cut -d= -f2)
  if [ "${idle3:-0}" -lt 1 ]; then
    echo "self-test: agent_idle_s=$idle3 expected >=1 when pod/host static"
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
  echo "O-HARNESSFP-POD: self-test GREEN"
  return 0
}

if [ "$SELFTEST" = "1" ]; then
  _run_self_test
  exit $?
fi

# Fixture / self-test path: allow digest overrides without a live pod.
# Detect BEFORE load_env/check_oc — instruments run from mktemp cwd where
# .env is absent and check_oc_logged_in exits 43 (unguarded), aborting
# --self-test tick1 (O-HARNESSFP-POD flake).
FIXTURE=0
if [ -n "${V10_IDLE_HOST_DIGEST:-}" ] || [ -n "${V10_IDLE_POD_DIGEST:-}" ]; then
  if [ -n "${V10_IDLE_STATE:-}" ] || [ -n "${V10_IDLE_POLL:-}" ]; then
    FIXTURE=1
  fi
fi

# Preserve caller-explicit V10_WS_NAME across load_env (.env may pin a Stopped
# workspace — W4-120a). Empty explicit value still means "unset after load".
_explicit_ws_set=0
_explicit_ws=""
if [ "${V10_WS_NAME+x}" = "x" ]; then
  _explicit_ws_set=1
  _explicit_ws="${V10_WS_NAME}"
fi
if [ "$FIXTURE" != "1" ]; then
  # load_env reads cwd .env — enter ROOT so instruments/mktemp cwd still works.
  _idle_cwd=$(pwd)
  cd "$ROOT" || true
  load_env >/dev/null 2>&1 || true
  cd "$_idle_cwd" || true
  if [ "$_explicit_ws_set" = "1" ]; then
    export V10_WS_NAME="${_explicit_ws}"
  fi
  # check_oc_logged_in uses exit (not return) on guard miss — fixture mode
  # must never reach it (see FIXTURE detect above).
  check_oc_logged_in >/dev/null 2>&1 || true
elif [ "$_explicit_ws_set" = "1" ]; then
  export V10_WS_NAME="${_explicit_ws}"
fi

STATE="${V10_IDLE_STATE:-${ROOT}/tmp/V10-IDLE-CLOCK.state}"
POLL="${V10_IDLE_POLL:-${ROOT}/tmp/KAI-POLL-STATE.txt}"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"
CTR="$(qg_ws_ctr)"
NS="${V10_NS:-$(qg_ws_ns)}"

head="unknown"; outer=0; sup=0; pod=""
if [ "$FIXTURE" = "1" ]; then
  # Instruments / --self-test: no oc; synthetic workspace fp.
  workspace_fp="fixture-0-0"
  host_fp="$(_host_harness_digest "$HARNESS")"
  pod_fp="$(_pod_harness_digest "" "$NS" "$CTR")"
else
  # O-HERMESWSRESOLVE: resolve via lib (explicit V10_WS_NAME or single Running DW).
  WS="$(qg_ws_name)" || {
    echo "v10-idle-clock: REFUSE — set V10_WS_NAME or ensure one Running DevWorkspace" >&2
    exit 1
  }
  pod="$(qg_ws_pod 2>/dev/null || true)"
  if [ -n "$pod" ]; then
    read -r head outer sup < <(oc exec -n "$NS" "$pod" -c "$CTR" -- bash -lc '
      h=$(git -C /projects/modernized rev-parse --short HEAD 2>/dev/null || echo none)
      o=0; pgrep -f "[.]hermes/harness/outer-loop[.]sh" >/dev/null && o=1
      s=0; pgrep -f "[.]hermes/harness/supervisor[.]sh" >/dev/null && s=1
      echo "$h $o $s"
    ' 2>/dev/null | tr -d '\r' | qg_strip_oc_noise | tail -1)
  fi
  workspace_fp="${head}-${outer}-${sup}"
  host_fp="$(_host_harness_digest "$HARNESS")"
  pod_fp="$(_pod_harness_digest "$pod" "$NS" "$CTR")"
fi

# Combined agent fingerprint — host OR pod churn resets agent_idle (O-HARNESSFP-POD).
harness_fp="$(_combine_harness_fp "$host_fp" "$pod_fp")"

now=$(date +%s)
iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
prev_ws=""; prev_ws_ts=0; prev_ag=""; prev_ag_ts=0
if [ -f "$STATE" ]; then
  # shellcheck disable=SC1090
  source "$STATE" || true
  prev_ws="${workspace_fp_prev:-}"
  prev_ws_ts="${workspace_fp_ts:-0}"
  prev_ag="${agent_fp_prev:-}"
  prev_ag_ts="${agent_fp_ts:-0}"
fi

agent_moved=0
if [ "$workspace_fp" != "$prev_ws" ]; then
  prev_ws_ts=$now
  prev_ws=$workspace_fp
fi
if [ "$harness_fp" != "$prev_ag" ]; then
  prev_ag_ts=$now
  prev_ag=$harness_fp
  agent_moved=1
fi

run_idle_s=$((now - prev_ws_ts))
agent_idle_s=$((now - prev_ag_ts))

cat >"$STATE" <<EOF
workspace_fp_prev=$prev_ws
workspace_fp_ts=$prev_ws_ts
agent_fp_prev=$prev_ag
agent_fp_ts=$prev_ag_ts
host_fp_prev=$host_fp
pod_fp_prev=$pod_fp
EOF

# O-HARNESSFP-POD: when pod/host harness digest moves, refresh last_activity so
# "all three unchanged" cannot imply idle while pod sync just landed.
if [ "$agent_moved" = "1" ]; then
  _update_poll_activity "$POLL" "$harness_fp" "$host_fp" "$pod_fp" "$iso"
fi

if [ "$JSON" = "1" ]; then
  printf '{"workspace_fp":"%s","host_fp":"%s","pod_fp":"%s","harness_fp":"%s","run_idle_s":%s,"agent_idle_s":%s,"idle_note_basis":"workspace_fp"}\n' \
    "$workspace_fp" "$host_fp" "$pod_fp" "$harness_fp" "$run_idle_s" "$agent_idle_s"
else
  echo "workspace_fp=$workspace_fp"
  echo "host_fp=$host_fp"
  echo "pod_fp=$pod_fp"
  echo "harness_fp=$harness_fp"
  echo "run_idle_s=$run_idle_s"
  echo "agent_idle_s=$agent_idle_s"
  echo "idle_note_basis=workspace_fp"
fi
