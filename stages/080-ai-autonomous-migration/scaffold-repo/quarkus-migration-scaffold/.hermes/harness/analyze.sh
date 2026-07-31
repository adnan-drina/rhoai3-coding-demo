#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# M1 / M1 ANALYZE (script-owned ground truth) — extracted from the
# supervisor so the outer loop can run it before M2 sequencing. Runs the
# harness-owned kantra analysis with the migration.yaml analysis contract,
# computes the spec input bundle (dependency order, findings inventory,
# recipe-executed rewrites), and commits it all in ONE 'M1 analyze:' commit.
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
# K4: materialize preserve/forbidden/acceptance as custom analyzer rules
# from migration.yaml (sensors stay defense-in-depth).
python3 .hermes/harness/gen-contract-rules.py \
  --yaml migration.yaml \
  --out .hermes/rules/generated-contract-rules.yaml \
  || echo "WARN: K4 gen-contract-rules failed — static demo-contract-rules only"
# Rule selection is label filtering (MTA 8.2 rules guide): the analysis
# contract lives in migration.yaml analysis: targets. NEVER a --source
# filter — validated 2026-07-27: it excludes source-labelless rules
# (including the custom contract rules) and narrows the set.
A_TARGETS=$(grep -A12 "^analysis:" migration.yaml 2>/dev/null | grep -m1 "targets:" | sed 's/.*\[\(.*\)\].*/\1/; s/,/ /g')
[ -n "$A_TARGETS" ] || A_TARGETS="quarkus jakarta-ee9 cloud-readiness"
# Poll 81 E2: analysis.mode from migration.yaml (default source-only).
A_MODE=$(grep -A12 "^analysis:" migration.yaml 2>/dev/null | grep -m1 -E "^[[:space:]]*mode:" | awk '{print $2}' | tr -d '"' || true)
A_MODE="${A_MODE:-source-only}"
case "$A_MODE" in
  source-only|full) ;;
  *) echo "WARN: analysis.mode '$A_MODE' unsupported — using source-only"; A_MODE=source-only ;;
esac
K_ARGS=""
for t in $A_TARGETS; do K_ARGS="$K_ARGS --target $t"; done
[ -d .hermes/rules ] && K_ARGS="$K_ARGS --rules /projects/modernized/.hermes/rules"
echo "analyze: kantra args: $K_ARGS (mode=$A_MODE)"
# Neutral cwd: the JDTLS-based java provider dumps Equinox state into CWD.
# Java 21 REQUIRED: kantra's analyzer bundles declare osgi.ee=JavaSE-21 —
# under the pod default (17) JDTLS never starts and the provider waits
# forever (the root cause of every observed kantra wedge). source-only:
# our rule set needs no dependency analysis and keeps the run minutes-scale.
(cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
  /tmp/kantra/kantra analyze -i /projects/legacy -o /tmp/kantra-baseline \
  $K_ARGS --mode "$A_MODE" --json-output --overwrite) || true
mkdir -p migration
cp /tmp/kantra-baseline/output.json migration/mta-findings.json 2>/dev/null \
  || { echo "FATAL: M1 ground truth unavailable"; exit 1; }
# K6: kantra on pristine destination (exclude staging/.hermes) → dest-baseline
# for scaffold-presatisfied.generated.txt (pom/config pre-satisfied only).
DEST_SRC=/tmp/kantra-dest-src
rm -rf "$DEST_SRC" /tmp/kantra-dest
mkdir -p "$DEST_SRC"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude 'migration/staging/' --exclude '.hermes/' --exclude 'target/' \
    --exclude '.git/' \
    /projects/modernized/ "$DEST_SRC/" 2>/dev/null || true
else
  cp -a /projects/modernized/. "$DEST_SRC/" 2>/dev/null || true
  rm -rf "$DEST_SRC/migration/staging" "$DEST_SRC/.hermes" "$DEST_SRC/target" \
    "$DEST_SRC/.git" 2>/dev/null || true
fi
(cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
  /tmp/kantra/kantra analyze -i "$DEST_SRC" -o /tmp/kantra-dest \
  $K_ARGS --mode "$A_MODE" --json-output --overwrite) 2>/dev/null || true
if [ -f /tmp/kantra-dest/output.json ]; then
  cp /tmp/kantra-dest/output.json migration/mta-findings-dest-baseline.json
  ORACLE_ROOT=/projects/modernized python3 .hermes/harness/dest-presatisfied.py \
    || echo "WARN: dest-presatisfied generation failed"
  echo "analyze: K6 dest-baseline + scaffold-presatisfied.generated.txt"
else
  echo "WARN: K6 dest-baseline kantra failed — static scaffold-presatisfied.txt only"
fi
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
git add migration/mta-findings.json migration/mta-findings-dest-baseline.json \
        migration/scaffold-presatisfied.generated.txt \
        migration/dependency-order.md \
        migration/findings-inventory.md migration/recipe-log.md migration/staging 2>/dev/null
git commit -q -m "M1 analyze: ground truth + spec input bundle (supervisor script step)

${SUMMARY}"
echo "analyze: committed — ${SUMMARY}"
