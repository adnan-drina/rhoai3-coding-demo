#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Phase A / M1 ANALYZE (script-owned ground truth) — extracted from the
# supervisor so the outer loop can run it before M2 sequencing. Runs the
# harness-owned kantra analysis with the migration.yaml analysis contract,
# computes the spec input bundle (dependency order, findings inventory,
# recipe-executed rewrites), and commits it all in ONE 'Phase A:' commit.
# Exit 0 = bundle committed (or already present); exit 1 = ground truth
# unavailable. All output to stdout/stderr — callers redirect.
# ---------------------------------------------------------------------------
set -u
export PATH=$HOME/.opencode/bin:$HOME/.local/bin:$PATH
cd /projects/modernized

if [ -f migration/mta-findings.json ]; then
  echo "analyze: ground truth already present — nothing to do"
  exit 0
fi

echo "analyze: running the harness-owned kantra analysis"
kantra-ensure || true
# Rule selection is label filtering (MTA 8.2 rules guide): the analysis
# contract lives in migration.yaml analysis: targets. NEVER a --source
# filter — validated 2026-07-27: it excludes source-labelless rules
# (including the custom contract rules) and narrows the set.
A_TARGETS=$(grep -A12 "^analysis:" migration.yaml 2>/dev/null | grep -m1 "targets:" | sed 's/.*\[\(.*\)\].*/\1/; s/,/ /g')
[ -n "$A_TARGETS" ] || A_TARGETS="quarkus jakarta-ee9 cloud-readiness"
K_ARGS=""
for t in $A_TARGETS; do K_ARGS="$K_ARGS --target $t"; done
[ -d .hermes/rules ] && K_ARGS="$K_ARGS --rules /projects/modernized/.hermes/rules"
echo "analyze: kantra args: $K_ARGS (source-only mode)"
# Neutral cwd: the JDTLS-based java provider dumps Equinox state into CWD.
# Java 21 REQUIRED: kantra's analyzer bundles declare osgi.ee=JavaSE-21 —
# under the pod default (17) JDTLS never starts and the provider waits
# forever (the root cause of every observed kantra wedge). source-only:
# our rule set needs no dependency analysis and keeps the run minutes-scale.
(cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
  /tmp/kantra/kantra analyze -i /projects/legacy -o /tmp/kantra-baseline \
  $K_ARGS --mode source-only --json-output --overwrite) || true
mkdir -p migration
cp /tmp/kantra-baseline/output.json migration/mta-findings.json 2>/dev/null \
  || { echo "FATAL: Phase A ground truth unavailable"; exit 1; }
# Spec input bundle (docs/MTA-TO-SPEC-MAPPING.md): the mechanical
# projections of the findings are computed here, not re-derived by the
# sequencing model — dependency order, the findings inventory with the
# MAPPINGS join, and recipe-executed rewrites.
python3 .hermes/harness/dependency-order.py /projects/legacy > migration/dependency-order.md 2>/dev/null \
  || echo "WARN: dependency analysis failed — plan orders without it"
python3 .hermes/harness/findings-inventory.py migration/mta-findings.json \
    .hermes/skills/migration-harness/MAPPINGS.md > migration/findings-inventory.md 2>/dev/null \
  || echo "WARN: findings inventory failed — sequencing derives the join itself"
.hermes/harness/recipe-transform.sh /projects/legacy migration/findings-inventory.md \
  || echo "WARN: recipe transform failed — recipe-class rules fall back to plan tasks"
SUMMARY=$(python3 .hermes/skills/migration-harness/scripts/extract_findings.py migration/mta-findings.json | head -3)
git add migration/mta-findings.json migration/dependency-order.md \
        migration/findings-inventory.md migration/recipe-log.md migration/staging 2>/dev/null
git commit -q -m "Phase A: ground truth + spec input bundle (supervisor script step)

${SUMMARY}"
echo "analyze: committed — ${SUMMARY}"
