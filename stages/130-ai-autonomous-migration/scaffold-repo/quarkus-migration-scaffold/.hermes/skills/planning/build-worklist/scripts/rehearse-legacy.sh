#!/usr/bin/env bash
# rehearse-legacy: the isolated PetClinic rehearsal (SAD v3 §9 exit 5) without
# agent dispatch. Runs the M1 producers, the deterministic bootstrap, and the
# first real verification on a legacy checkout, and prints the work-list head.
# Nothing is minted; no Hermes is involved. Every step is the same script a
# card would run.
#
#   rehearse-legacy.sh --legacy <dir> --root <fresh destination dir>
#
# Requires: JDK 21 (javac), Maven (network for the one-time warm-up), git.
# MTA CLI optional: without it the rescan does not run and the measure stays
# UNKNOWN for incidents (the rehearsal still proves freeze → build → JDK
# model → bootstrap → diagnostics on real code).
set -euo pipefail
LEGACY=""; ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --legacy) LEGACY="${2:-}"; shift 2 ;;
    --root) ROOT="${2:-}"; shift 2 ;;
    *) echo "usage: rehearse-legacy.sh --legacy <dir> --root <dir>" >&2; exit 2 ;;
  esac
done
[[ -n "${LEGACY}" && -d "${LEGACY}" && -n "${ROOT}" ]] || { echo "usage: rehearse-legacy.sh --legacy <dir> --root <dir>" >&2; exit 2; }
GOLDEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
mkdir -p "${ROOT}"; ROOT="$(cd "${ROOT}" && pwd)"
S="${GOLDEN}/.hermes/skills"
step() { echo; echo "=== $*"; }

step "0 scaffold copy → ${ROOT}"
for sub in .hermes .mvn decisions.yaml migration.yaml .gitignore; do
  [[ -e "${GOLDEN}/${sub}" ]] && { rm -rf "${ROOT}/${sub}"; cp -R "${GOLDEN}/${sub}" "${ROOT}/${sub}"; }
done
find "${ROOT}/.hermes" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
[[ -d "${ROOT}/.git" ]] || ( cd "${ROOT}" && git init -q && git -c user.email=r@r -c user.name=rehearsal add -A && git -c user.email=r@r -c user.name=rehearsal commit -q -m "scaffold" )

step "1 freeze-migration-input"
python3 "${S}/analysis/freeze-migration-input/scripts/freeze-migration-input.py" --source "${LEGACY}" --root "${ROOT}" --copy-to "${ROOT}/.derived/frozen-input"
step "2 capture-build-evidence (warm-up needs network once)"
bash "${S}/analysis/capture-build-evidence/scripts/capture-build-evidence.sh" --root "${ROOT}" || echo "WARN: build evidence recorded a failure (planning-only)"
step "3 inventory-legacy-surface (JDK model)"
bash "${S}/analysis/inventory-legacy-surface/scripts/run-jdk-model-extract.sh" --root "${ROOT}"
step "4 scan-with-mta"
if command -v mta-cli >/dev/null 2>&1 || command -v kantra >/dev/null 2>&1; then
  bash "${S}/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh" --root "${ROOT}" || echo "WARN: MTA analysis failed"
else
  echo "SKIP: no MTA CLI on PATH — the bundle will carry no MTA obligations and admission will block MTA_MISSING (expected in a toolchain rehearsal)"
fi
step "5 assemble-evidence-bundle"
python3 "${S}/analysis/assemble-evidence-bundle/scripts/assemble-evidence-bundle.py" --root "${ROOT}" || echo "WARN: bundle assembly reported a gap"
step "6a probe-bom-managed (network once: the pinned BOM)"
python3 "${S}/migration/bootstrap-destination/scripts/probe-bom-managed.py" --root "${ROOT}" || echo "WARN: BOM probe failed (bootstrap will block BOM_PROBE_MISSING)"
step "6 bootstrap-destination"
python3 "${S}/migration/bootstrap-destination/scripts/bootstrap-destination.py" --root "${ROOT}" || echo "WARN: bootstrap BLOCKED (see evidence/producers/bootstrap.json blocks)"
step "7 run-verify (JDK diagnostics, tests, rescan) → work list"
bash "${S}/migration/fix-until-green/scripts/run-verify.sh" --root "${ROOT}" || echo "WARN: verify reported a tool failure"
step "8 result"
python3 - "${ROOT}" <<'PYEOF'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
wl = json.load(open(root / "evidence/planning/worklist.json"))
m = wl["measure"]
print("measure:", m["tuple"], "known:", m["known"], "blocked:", m.get("blocked"))
print("clusters:", len(wl["clusters"]), "head:", wl["head"])
for c in wl["clusters"][:12]:
    print("  %-6s %-70s items=%d" % (c["kind"], c["path"], len(c["items"])))
b = root / "evidence/producers/bootstrap.json"
if b.is_file():
    d = json.load(open(b)); print("bootstrap:", d["status"], "changes:", len(d["changes"]), "blocks:", [x["class"] + ":" + x["subject"] for x in d.get("blocks", [])])
PYEOF
echo; echo "Rehearsal artefacts: ${ROOT}/evidence/planning/worklist.json, ${ROOT}/verification/build/run.json, ${ROOT}/evidence/producers/*.json"
