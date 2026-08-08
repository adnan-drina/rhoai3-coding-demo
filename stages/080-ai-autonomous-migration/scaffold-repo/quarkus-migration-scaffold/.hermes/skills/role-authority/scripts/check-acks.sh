#!/usr/bin/env bash
# AD-H §16.3 — require acknowledged ack artifacts before phase advance.
# Usage: check-acks.sh <M2|M3|M4|M5> [project_root]
# Idle exit 0 when phase has no requires_acks.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "${2:-${SKILL_DIR}/../../..}" && pwd)"
PHASE="${1:-}"
DISPATCH="${ROOT}/.hermes/phase-dispatch.yaml"
ACK_DIR="${ROOT}/migration/acks"

die() { echo "FAIL: $*" >&2; exit 1; }
[ -n "${PHASE}" ] || die "usage: check-acks.sh <phase> [root]"
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
    "${ACK_DIR}/${ack_type}.ack.json"; do
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
    echo "FAIL: phase ${PHASE} requires ack '${ack_type}' under migration/acks/ (status: acknowledged)" >&2
    bad=1
  fi
done <<EOF
${REQUIRED_TXT}
EOF

[ "${bad}" -eq 0 ] || exit 1
echo "OK: all required acks present for ${PHASE}"
