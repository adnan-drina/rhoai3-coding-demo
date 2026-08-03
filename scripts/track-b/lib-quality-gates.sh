#!/usr/bin/env bash
# Shared helpers for Track B quality gates (script-enforced, not memory).
# Library: do NOT set -e/-u here — callers own shell options (driver uses
# set -uo without -e so a tick failure cannot kill the wake loop).
# shellcheck disable=SC2034

qg_root() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$here"
}

ROOT="$(qg_root)"
# V10 bank is the operational checklist (⬜ = due before next run; 📋 = later wave).
# V9 gate doc remains archived until a V10 quality-gate file is opened.
# Active v4 wave gate log (archived V9 remains under tmp/docs-archive/).
GATE_DOC="${GATE_DOC:-${ROOT}/docs/V10-QUALITY-GATE.md}"
BANK_DOC="${BANK_DOC:-${ROOT}/docs/V10-FUTURE-IMPROVEMENTS.md}"
# Active Wave due-diligence review doc (Implementing notes). When present, O-DRV3/O-DRV5
# clear scripts refuse unless a note cites the sha — gate log alone is not enough.
REVIEW_DOC="${REVIEW_DOC:-${ROOT}/tmp/KAI-WAVE4-REVIEW.md}"
TRANSCRIPT_DIR="${V9_TRANSCRIPT_DIR:-${HOME}/.cursor/projects/Users-adrina-Sandbox-rhoai3-coding-demo/agent-transcripts}"

# DevWorkspace targeting (O-HERMESWSRESOLVE) — never default to a named workspace
# that ages out (v1→v2→v3→v4…). Resolve at call time via qg_ws_name.
QG_WS_NS_DEFAULT="wksp-ai-developer"
QG_WS_CTR_DEFAULT="development-tooling"
# O-FALSECOMPLETE — exact harness story-complete subjects only.
QG_STORY_COMPLETE_RE='^S0[0-9] story complete: (success .+|story-gate-passed)$'

qg_die() { echo "quality-gate: $*" >&2; exit 1; }

# Resolve target DevWorkspace name (O-HERMESWSRESOLVE).
# Order: explicit V10_WS_NAME → single Running DevWorkspace in ns → REFUSE.
# Instruments: set QG_WS_RUNNING_LIST (newline-separated names, may be empty)
# to exercise resolution without oc. Multi/zero Running → refuse.
qg_ws_name() {
  local ns names count
  if [[ -n "${V10_WS_NAME:-}" ]]; then
    printf '%s\n' "$V10_WS_NAME"
    return 0
  fi
  ns="$(qg_ws_ns)"
  if [[ -n "${QG_WS_RUNNING_LIST+x}" ]]; then
    names="$(printf '%s\n' "$QG_WS_RUNNING_LIST" | sed '/^$/d')"
  elif command -v oc >/dev/null 2>&1; then
    names="$(
      oc get devworkspace -n "$ns" \
        -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
        2>/dev/null || true
    )"
    names="$(printf '%s\n' "$names" | sed '/^$/d')"
  else
    echo "quality-gate: V10_WS_NAME unset and oc unavailable — refuse stale workspace default (O-HERMESWSRESOLVE)" >&2
    return 1
  fi
  count="$(printf '%s\n' "$names" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [[ "${count:-0}" -eq 1 ]]; then
    printf '%s\n' "$(printf '%s\n' "$names" | sed '/^$/d' | head -1)"
    return 0
  fi
  if [[ "${count:-0}" -eq 0 ]]; then
    echo "quality-gate: V10_WS_NAME unset and no Running DevWorkspace in ${ns} — refuse (O-HERMESWSRESOLVE)" >&2
    return 1
  fi
  echo "quality-gate: V10_WS_NAME unset and ${count} Running DevWorkspaces in ${ns} — set V10_WS_NAME explicitly:" >&2
  printf '%s\n' "$names" | sed '/^$/d' | sed 's/^/  /' >&2
  return 1
}

qg_ws_pod() {
  if [[ -n "${V8_WS_POD:-}" ]]; then
    printf '%s\n' "$V8_WS_POD"
    return 0
  fi
  local name ns pod
  name="$(qg_ws_name)" || return 1
  ns="$(qg_ws_ns)"
  if command -v oc >/dev/null 2>&1; then
    pod=$(oc get pod -n "$ns" \
      -l "controller.devfile.io/devworkspace_name=${name}" \
      --field-selector=status.phase=Running \
      -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [[ -n "${pod:-}" ]]; then
      printf '%s\n' "$pod"
      return 0
    fi
  fi
  echo "quality-gate: no Running pod for DevWorkspace ${name} in ${ns} (O-HERMESWSRESOLVE)" >&2
  return 1
}
qg_ws_ns() { printf '%s\n' "${V8_WS_NS:-$QG_WS_NS_DEFAULT}"; }
qg_ws_ctr() { printf '%s\n' "${V8_WS_CONTAINER:-$QG_WS_CTR_DEFAULT}"; }

# O-HERMESPARITYSEM — semantic .hermes digest file list (cwd = parent of .hermes).
# Excludes stamps / regenerated catalogs; generators (.sh) remain hashed.
# Keep identical predicates in v10-hermes-parity.sh / v10-golden-fresh.sh pod exec.
qg_hermes_list_semantic_files() {
  find .hermes -type f \
    ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '.DS_Store' \
    ! -name '*.bak' ! -name '._*' \
    ! -path './.hermes/harness/.published-fp' ! -name '.published-fp' \
    ! -path './.hermes/harness/defaults-inventory.md' ! -name 'defaults-inventory.md' \
    ! -path './.hermes/harness/guard-manifest.md' ! -name 'guard-manifest.md' \
    2>/dev/null | LC_ALL=C sort
}

# Same find predicates as a single line for embedding in `oc exec` digests.
qg_hermes_semantic_find_cmd() {
  printf '%s\n' \
    'find .hermes -type f ! -path "*/__pycache__/*" ! -name "*.pyc" ! -name ".DS_Store" ! -name "*.bak" ! -name "._*" ! -path "./.hermes/harness/.published-fp" ! -name ".published-fp" ! -path "./.hermes/harness/defaults-inventory.md" ! -name "defaults-inventory.md" ! -path "./.hermes/harness/guard-manifest.md" ! -name "guard-manifest.md"'
}

qg_story_complete_ok() {
  printf '%s\n' "$1" | grep -Eq "$QG_STORY_COMPLETE_RE"
}

# Remote process match that ignores the oc-exec shell argv (contains the pattern).
# Usage: qg_remote_pgrep_busy 'harness/supervisor\.sh' → 0 if busy
qg_remote_pgrep_busy() {
  local pat="$1"
  local pod ns ctr
  pod="$(qg_ws_pod)"; ns="$(qg_ws_ns)"; ctr="$(qg_ws_ctr)"
  oc exec -n "$ns" "$pod" -c "$ctr" -- bash -lc \
    "pgrep -af '${pat}' 2>/dev/null | grep -vE 'bash -lc|pgrep' | grep -q ." \
    >/dev/null 2>&1
}

# Strip OSC-633 / ANSI noise from `oc exec` output (O-HANDNOISE).
qg_strip_oc_noise() {
  sed -E \
    -e 's/\x1b\[[0-9;]*[A-Za-z]//g' \
    -e 's/\x1b\][^\x07]*\x07//g' \
    -e 's/\]633;P;HasRichCommandDetection=True//g' \
    -e 's/HasRichCommandDetection=True//g' \
    -e 's/\]633;[^[:space:]]*//g' \
    | tr -d '\000-\010\013\014\016-\037'
}

qg_require_file() {
  [ -f "$1" ] || qg_die "missing required file: $1"
}

# Extract open bank rows: lines with | ID | ⬜ |
qg_open_bank_ids() {
  qg_require_file "$BANK_DOC"
  awk -F'|' '
    /^\|/ && $3 ~ /⬜/ {
      id=$2
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", id)
      if (id != "" && id != "ID") print id
    }
  ' "$BANK_DOC"
}

# Honesty-blocking: open rows whose Notes contain [HONESTY] (case-insensitive)
# OR whose ID matches O-DRV* / O-ESCAL* / O-DEBT* / O-GATE* / O-HAND* while open.
qg_honesty_open_ids() {
  qg_require_file "$BANK_DOC"
  awk -F'|' '
    /^\|/ && $3 ~ /⬜/ {
      id=$2; notes=$4
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", id)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", notes)
      if (id == "" || id == "ID") next
      low=tolower(notes)
      if (low ~ /\[honesty\]/ || id ~ /^O-(DRV|ESCAL|DEBT|GATE|HAND|ADV)/) print id
    }
  ' "$BANK_DOC"
}

# Find ## sections in the gate doc that mention a short or full SHA.
# Prints section bodies separated by \0 for python, or lists matching headers.
qg_gate_sections_for_sha() {
  local sha="$1"
  local short="${sha:0:7}"
  qg_require_file "$GATE_DOC"
  python3 - "$GATE_DOC" "$sha" "$short" <<'PY'
import sys, re
path, full, short = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8", errors="replace").read()
parts = re.split(r"(?m)^(## .+)$", text)
# parts: [pre, h1, body1, h2, body2, ...]
hits = []
for i in range(1, len(parts), 2):
    header, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
    blob = header + "\n" + body
    if full in blob or short in blob:
        hits.append((header.strip(), body))
if not hits:
    sys.exit(2)
for h, b in hits:
    print("HEADER\t" + h)
    print(b.rstrip())
    print("ENDSECTION")
PY
}

# Validate a task-gate section has real review substance (not a one-liner).
qg_validate_task_section() {
  local body="$1"
  python3 -c '
import sys, re
body = sys.argv[1]
low = body.lower()
errors = []
if len([ln for ln in body.splitlines() if ln.strip()]) < 8:
    errors.append("section too thin (<8 non-empty lines)")
# Must judge code + actions (flexible headings)
code_ok = bool(re.search(r"(ai[- ]?generated )?code quality|what shipped|substance|git show|diff", low))
act_ok = bool(re.search(r"(ai )?action quality|actor path|worker|minimax|escalat|mechan|o-escw|style-autofix", low))
if not code_ok:
    errors.append("missing AI code-quality / substance judgment")
if not act_ok:
    errors.append("missing AI action-quality / actor-path judgment")
if not re.search(r"\b(hold|advance|abort|next action|banked)\b", low):
    errors.append("missing verdict / next action / banked signal")
# Reject pure table-only catch-up blocks without prose
prose = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("|") and not ln.strip().startswith("#")]
if len(prose) < 4:
    errors.append("insufficient prose (table-only or checklist-only)")
if errors:
    print("FAIL: " + "; ".join(errors), file=sys.stderr)
    sys.exit(1)
print("ok")
' "$body"
}

qg_validate_m_section() {
  local body="$1"
  python3 -c '
import sys, re
body = sys.argv[1]
low = body.lower()
errors = []
if len([ln for ln in body.splitlines() if ln.strip()]) < 10:
    errors.append("milestone section too thin (<10 non-empty lines)")
if not re.search(r"\*\*verdict:\*\*\s*(advance|hold|abort)", low):
    errors.append("missing **Verdict:** ADVANCE|HOLD|ABORT")
if not re.search(r"(ai[- ]?generated )?code quality|what shipped|substance", low):
    errors.append("missing AI code-quality / substance")
if not re.search(r"(ai )?action|escalat|actor|worker|minimax|process", low):
    errors.append("missing AI action / process notes")
if not re.search(r"banked|next action", low):
    errors.append("missing Banked / Next action")
if errors:
    print("FAIL: " + "; ".join(errors), file=sys.stderr)
    sys.exit(1)
print("ok")
' "$body"
}

qg_section_has_verdict() {
  local body="$1" want="$2"
  echo "$body" | grep -qiE '\*\*Verdict:\*\*[[:space:]]*'"$want"
}

# Diff evidence: require tmp/V9-DIFF-EVIDENCE/<sha>.stat OR ≥2 paths from
# provided stat text appear in the gate section body.
qg_validate_diff_evidence() {
  local sha="$1" body="$2" stat_file="${3:-}"
  local short="${sha:0:7}"
  local evid="${ROOT}/tmp/V9-DIFF-EVIDENCE/${sha}.stat"
  [ -f "$evid" ] || evid="${ROOT}/tmp/V9-DIFF-EVIDENCE/${short}.stat"
  if [ -f "$evid" ]; then
    local n
    # Count citable path lines (include specs/ — M3 plan commits are specs-only).
    n=$(grep -cE '^\s|bin/|src/|pom\.xml|migration/|specs/' "$evid" 2>/dev/null || echo 0)
    n=$(printf '%s' "$n" | tr -dc '0-9')
    [ "${n:-0}" -ge 1 ] || qg_die "diff evidence file empty: $evid"
    # At least one path from evidence must appear in gate body
    # O-DRV3EV: path citation is mandatory — evidence file size alone is not enough.
    if ! python3 - "$evid" "$body" <<'PY'
import sys, re
evid = open(sys.argv[1], encoding="utf-8", errors="replace").read()
body = sys.argv[2]
paths = re.findall(r"(?:^|\s)((?:src|migration|specs|pom\.xml)[\w./-]*)", evid, re.M)
# de-dupe preserve order
seen, uniq = set(), []
for p in paths:
    if len(p) <= 6 or p in seen:
        continue
    seen.add(p)
    uniq.append(p)
uniq = uniq[:40]
if not uniq:
    print("FAIL: evidence file has no citable paths", file=sys.stderr)
    sys.exit(1)
need = 2 if len(uniq) >= 2 else 1
hits = sum(1 for p in uniq if p in body)
if hits < need:
    print(f"FAIL: gate cites {hits}/{need} evidence paths (need ≥{need})", file=sys.stderr)
    sys.exit(1)
sys.exit(0)
PY
    then
      qg_die "gate section does not cite paths from diff evidence $evid"
    fi
    return 0
  fi
  if [ -n "$stat_file" ] && [ -f "$stat_file" ]; then
    qg_validate_diff_evidence "$sha" "$body" # recursive with copied? skip
  fi
  # Fallback: body must mention git show / --stat / concrete src path
  echo "$body" | grep -qiE 'git show|`--stat`|--stat|src/(main|test)/' \
    || qg_die "no tmp/V9-DIFF-EVIDENCE/${sha}.stat and gate lacks diff/path citations — run v9-capture-diff.sh first"
}

# Require an ### Implementing note in REVIEW_DOC that cites this sha.
# Skips only when REVIEW_DOC is absent (non-Wave-4 runs). Hard-fail when present.
qg_require_wave1_review_note() {
  local sha="$1"
  local short="${sha:0:7}"
  [ -f "$REVIEW_DOC" ] || return 0
  python3 - "$REVIEW_DOC" "$sha" "$short" <<'PY' || qg_die "no Implementing note in ${REVIEW_DOC#$ROOT/} cites sha $short — append findings there before clearing (handshake rules 4–5; gate log alone is insufficient)"
import sys, re
path, full, short = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8", errors="replace").read()
parts = re.split(r"(?m)^(### Implementing note[^\n]*)$", text)
hits = []
for i in range(1, len(parts), 2):
    header = parts[i]
    rest = parts[i + 1] if i + 1 < len(parts) else ""
    # Body ends at next ## / ### heading
    body = re.split(r"(?m)^#{2,3} ", rest, maxsplit=1)[0]
    blob = header + "\n" + body
    if full in blob or short in blob:
        hits.append(header.strip())
if not hits:
    sys.exit(2)
print("review-note-ok:", hits[-1])
PY
}

qg_write_validated_sha() {
  local out="$1" sha="$2"
  {
    printf '%s\n' "$sha"
    printf '# validated: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '# clearer: %s\n' "$(basename "$0")"
  } >"$out"
}

qg_sha_is_validated() {
  local f="$1"
  [ -f "$f" ] || return 1
  grep -qE '^# validated:' "$f"
}

# O-SESSIONREG-PREFLIGHT / O-HERMES-CLI-PREFLIGHT — remote harness before outer start.
qg_remote_orchestrator_preflight() {
  local pod ns ctr
  pod="$(qg_ws_pod)"; ns="$(qg_ws_ns)"; ctr="$(qg_ws_ctr)"
  if ! command -v oc >/dev/null 2>&1; then
    qg_die "oc required for orchestrator preflight (session-registry + hermes CLI)"
  fi
  oc exec -n "$ns" "$pod" -c "$ctr" -- bash -lc '
    set -euo pipefail
    cd /projects/modernized
    reg=.hermes/harness/session-registry.sh
    if [ ! -f "$reg" ]; then
      echo "quality-gate: missing $reg — tar-sync golden scaffold .hermes/ (v10-prep-fresh-rerun.sh)" >&2
      exit 1
    fi
    bash -n "$reg"
    bash -n .hermes/harness/outer-loop.sh
    # shellcheck source=/dev/null
    . "$reg"
    if ! declare -F session_register >/dev/null 2>&1; then
      echo "quality-gate: session_register not defined after sourcing $reg" >&2
      exit 1
    fi
    export PATH="${HOME}/.local/bin:${HOME}/.opencode/bin:${PATH}"
    if ! command -v hermes >/dev/null 2>&1; then
      echo "quality-gate: hermes not on PATH — run workspace init (ensure_hermes) or fix xz shim" >&2
      exit 1
    fi
    if ! hermes --help >/dev/null 2>&1 && ! hermes --version >/dev/null 2>&1; then
      echo "quality-gate: hermes CLI not executable (hermes --help/--version failed)" >&2
      exit 1
    fi
    echo "orchestrator-preflight: session-registry + hermes OK"
  '
}
