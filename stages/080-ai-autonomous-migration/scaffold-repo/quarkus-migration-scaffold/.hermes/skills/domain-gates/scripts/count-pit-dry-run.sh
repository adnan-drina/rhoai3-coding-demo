#!/usr/bin/env bash
# G-1 volume floor — PIT dry-run mutant count (Research R1 / Architect E-20260808T075704Z).
# Pin: pitest-maven 1.25.5, -Dpit.dryRun=true. Fail closed if no mutations.xml.
# Do NOT use -DskipTests. Do NOT invent a static-metric floor.
set -euo pipefail

PIT_VERSION="${PIT_VERSION:-1.25.5}"
PIT_JUNIT5_VERSION="${PIT_JUNIT5_VERSION:-1.2.3}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODULE_DIR="${1:-}"
OUT_JSON="${2:-}"

die() { echo "FAIL: $*" >&2; exit 1; }

[ -n "${MODULE_DIR}" ] || die "usage: count-pit-dry-run.sh <maven-module-dir> [evidence.json]"
[ -f "${MODULE_DIR}/pom.xml" ] || die "no pom.xml under ${MODULE_DIR}"

# Refuse skipTests in the environment / args
case "${MAVEN_OPTS:-}${MAVEN_ARGS:-}" in
  *skipTests*|*maven.test.skip*) die "refuse -DskipTests / maven.test.skip for PIT dry-run floor" ;;
esac

cd "${MODULE_DIR}"
rm -rf target/pit-reports
# Prefer JAVA_HOME_21 when set (scaffold convention)
if [ -n "${JAVA_HOME_21:-}" ]; then
  export JAVA_HOME="${JAVA_HOME_21}"
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

# Prefer project-declared pitest-maven (carries pitest-junit5-plugin ≥1.2.3 —
# required for Quarkus/JUnit 5; bare GAV CLI omits it and fails closed).
PIT_GOAL="org.pitest:pitest-maven:${PIT_VERSION}:mutationCoverage"
if grep -q '<artifactId>pitest-maven</artifactId>' pom.xml; then
  PIT_GOAL="org.pitest:pitest-maven:mutationCoverage"
fi

# Optional scope (default: specimen-free harness probe — green unit for volume).
# Override for slice kill-ratio (#8) once the suite is green under PIT.
PIT_TARGET_CLASSES="${PIT_TARGET_CLASSES:-com.demo.harness.*}"
PIT_TARGET_TESTS="${PIT_TARGET_TESTS:-com.demo.harness.*}"

# PIT 1.25.x defaults HTML-only in some setups; parser needs mutations.xml.
PIT_OUTPUT_FORMATS="${PIT_OUTPUT_FORMATS:-XML,HTML}"

set +e
mvn -q test-compile \
  "${PIT_GOAL}" \
  -Dpit.dryRun=true \
  -Ddetail=true \
  -DtargetClasses="${PIT_TARGET_CLASSES}" \
  -DtargetTests="${PIT_TARGET_TESTS}" \
  -DoutputFormats="${PIT_OUTPUT_FORMATS}" \
  2>&1 | tee /tmp/pit-dry-run.log
mvn_rc=${PIPESTATUS[0]}
set -e

if grep -Eqi 'pitest junit 5 plugin is not installed|could not run any tests' /tmp/pit-dry-run.log; then
  die "PIT JUnit 5 plugin missing/unusable (need pitest-junit5-plugin ≥${PIT_JUNIT5_VERSION} inside pitest-maven) — refuse as floor evidence"
fi

if grep -Eqi 'Skipping project because:.*no tests|Test execution should be skipped' /tmp/pit-dry-run.log; then
  die "PIT skipped (zero tests or skipTests) — cannot use as G-1 volume floor; add ≥1 compilable test"
fi

REPORT=""
if [ -f target/pit-reports/mutations.xml ]; then
  REPORT="target/pit-reports/mutations.xml"
else
  # PIT may nest timestamp dirs
  REPORT="$(find target/pit-reports -name mutations.xml 2>/dev/null | head -1 || true)"
fi
[ -n "${REPORT}" ] || die "no mutations.xml after dry-run (mvn_rc=${mvn_rc}) — refuse as floor evidence"

OUT_ARGS=()
if [ -n "${OUT_JSON}" ]; then
  OUT_ARGS=(-o "${OUT_JSON}")
fi
python3 "${SKILL_DIR}/scripts/parse-pit-mutations.py" "${REPORT}" "${OUT_ARGS[@]+"${OUT_ARGS[@]}"}"
