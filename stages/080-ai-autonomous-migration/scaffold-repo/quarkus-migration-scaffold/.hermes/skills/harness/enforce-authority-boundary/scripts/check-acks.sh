#!/usr/bin/env bash
# AD-H §16.3 — require acknowledged ack artifacts before phase advance.
# Usage: check-acks.sh <M2|M3|M4|M5> [project_root]
# Idle exit 0 when phase has no requires_acks.
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
check-acks.sh — require acknowledged ack artifacts before phase advance (AD-H §16.3).

Usage:
  check-acks.sh <M1|M2|M2a|M2b|M3|M4|M5|factory> [project_root]
  check-acks.sh -h|--help

Exit codes:
  0  all required acks present, or phase has no requires_acks (idle)
  1  BLOCK — missing or non-authoritative ack
  2  usage error
USAGE
    exit 0
    ;;
esac

if [ -n "${2:-}" ]; then
  ROOT="$(cd "$2" && pwd)"
else
  d="$(cd "$(dirname "$0")" && pwd)"
  ROOT=""
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      ROOT="$d"
      break
    fi
    d="$(dirname "$d")"
  done
  if [ -z "${ROOT}" ]; then
    echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
    exit 1
  fi
fi
PHASE="${1:-}"
DISPATCH="${ROOT}/.hermes/phase-dispatch.yaml"
ACK_DIR="${ROOT}/evidence/acks"

die() { echo "FAIL: $*" >&2; exit 1; }
[ -n "${PHASE}" ] || { echo "usage: check-acks.sh <phase> [root]" >&2; exit 2; }
[ -f "${DISPATCH}" ] || die "missing ${DISPATCH}"

REQUIRED_TXT="$(python3 - "${DISPATCH}" "${PHASE}" <<'PY'
import sys
path, phase = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read().splitlines()
in_phase = False
in_acks = False
for ln in text:
    if ln.startswith("  ") and not ln.startswith("    ") and ln.strip().endswith(":"):
        name = ln.strip().rstrip(":")
        in_phase = name == phase
        in_acks = False
        continue
    if not in_phase:
        continue
    if ln.strip().startswith("requires_acks:"):
        rest = ln.split(":", 1)[1].strip()
        if rest == "[]":
            break
        # empty rest ⇒ block list on following lines
        in_acks = True
        if rest.startswith("- "):
            print(rest[2:].strip().strip("\"'"))
        continue
    if in_acks:
        if ln.strip().startswith("- "):
            print(ln.strip()[2:].strip().strip("\"'"))
        elif ln.strip() and not ln.startswith("      ") and not ln.strip().startswith("-"):
            break
PY
)"

if [ -z "${REQUIRED_TXT}" ]; then
  echo "OK: phase ${PHASE} has no required acks"
  exit 0
fi

bad=0
while IFS= read -r ack_type; do
  [ -n "${ack_type}" ] || continue
  found=0
  for f in \
    "${ACK_DIR}/${ack_type}.ack.yaml" \
    "${ACK_DIR}/${ack_type}.ack.yml" \
    "${ACK_DIR}/${ack_type}.ack.json" \
    "${ACK_DIR}/m3-${ack_type}.ack.yaml"; do
    if [ -f "${f}" ]; then
      if python3 - "${f}" "${ack_type}" <<'PY'
import json, re, sys
path, want = sys.argv[1], sys.argv[2]
raw = open(path, encoding="utf-8").read()
if path.endswith(".json"):
    doc = json.loads(raw)
else:
    def field(name):
        m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
        return m.group(1).strip().strip("\"'") if m else ""
    doc = {"kind": field("kind"), "ack_type": field("ack_type"), "status": field("status")}
if doc.get("kind") != "migration-ack":
    sys.exit(1)
if doc.get("ack_type") != want:
    sys.exit(1)
if str(doc.get("status", "")).lower() != "acknowledged":
    sys.exit(1)
sys.exit(0)
PY
      then
        found=1
        echo "OK: ack ${ack_type} ← ${f#"${ROOT}"/}"
        break
      fi
    fi
  done
  # 5.1 — auto-issue m1-findings / brief-identity as gate records when the
  # named verifier is green. Missing yaml is not a human GO. rc≠0 still
  # typed-blocks.
  if [ "${found}" -eq 0 ] && [ "${ack_type}" = "m1-findings" ]; then
    ISSUER="${ROOT}/.hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py"
    if [ -f "${ISSUER}" ]; then
      if python3 "${ISSUER}" "${ROOT}"; then
        if [ -f "${ACK_DIR}/m1-findings.ack.yaml" ]; then
          found=1
          echo "OK: ack ${ack_type} ← evidence/acks/m1-findings.ack.yaml (5.1 gate-record)"
        fi
      fi
    fi
  fi
  if [ "${found}" -eq 0 ] && [ "${ack_type}" = "brief-identity" ]; then
    ISSUER="${ROOT}/.hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py"
    if [ -f "${ISSUER}" ]; then
      if python3 "${ISSUER}" "${ROOT}"; then
        if [ -f "${ACK_DIR}/m3-brief-identity.ack.yaml" ] || [ -f "${ACK_DIR}/brief-identity.ack.yaml" ]; then
          found=1
          echo "OK: ack ${ack_type} ← evidence/acks/m3-brief-identity.ack.yaml (gate-record)"
        fi
      fi
    fi
  fi
  # story-scoped brief-identity-*.ack.yaml
  if [ "${found}" -eq 0 ]; then
    for f in "${ACK_DIR}/${ack_type}"-*.ack.yaml "${ACK_DIR}/${ack_type}"-*.ack.yml; do
      [ -f "${f}" ] || continue
      if python3 - "${f}" "${ack_type}" <<'PY'
import re, sys
path, want = sys.argv[1], sys.argv[2]
raw = open(path, encoding="utf-8").read()
def field(name):
    m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
    return m.group(1).strip().strip("\"'") if m else ""
if field("kind") != "migration-ack" or field("ack_type") != want:
    sys.exit(1)
if field("status").lower() != "acknowledged":
    sys.exit(1)
sys.exit(0)
PY
      then
        found=1
        echo "OK: ack ${ack_type} ← ${f#"${ROOT}"/}"
        break
      fi
    done
  fi
  if [ "${found}" -eq 0 ]; then
    hint=""
    bare="${ACK_DIR}/${ack_type}.json"
    if [ -f "${bare}" ]; then
      bare_status="$(python3 - "${bare}" <<'PY'
import json, sys
try:
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    print(str(doc.get("status", "")).strip() or "?")
except Exception as e:
    print(f"unreadable:{e.__class__.__name__}")
PY
)"
      hint="; found non-authoritative ${bare#"${ROOT}"/} status=${bare_status} — want ${ack_type}.ack.yaml|.ack.json kind=migration-ack status=acknowledged (AR-1.1; bare *.json worker grants refused)"
    else
      hint="; want evidence/acks/${ack_type}.ack.yaml|.ack.json kind=migration-ack status=acknowledged (no matching .ack.* file)"
    fi
    echo "FAIL: phase ${PHASE} missing authoritative ack '${ack_type}'${hint}" >&2
    bad=1
  fi
done <<EOF
${REQUIRED_TXT}
EOF

[ "${bad}" -eq 0 ] || exit 1
echo "OK: all required acks present for ${PHASE}"
