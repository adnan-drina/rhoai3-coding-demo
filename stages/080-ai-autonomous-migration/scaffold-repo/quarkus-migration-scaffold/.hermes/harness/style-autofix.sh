#!/usr/bin/env bash
# Deterministic style-autofix (improvement E13): on a sonar red, run the
# OpenRewrite cleanup recipes BEFORE spending a model session — V3
# measured 152 min of model time on mechanically-fixable violations
# (unused imports, public test modifiers, diamond operators, isEmpty).
# Exit 0 = recipes ran (caller re-checks the sensor); non-zero = recipes
# unavailable/failed (caller falls through to the model session).
set -uo pipefail
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
export PATH="${JAVA_HOME}/bin:${PATH}"
cd "${SENSOR_ROOT:-/projects/modernized}"

M2_RUN="${M2_RUN:-/tmp/m2-run}"
# The recipe set mirrors the recurring sonar rules of runs 1–3:
#   RemoveUnusedImports            (unused imports)
#   TestsShouldNotBePublic         (java:S5786)
#   UseDiamondOperator             (java:S2293)
#   IsEmptyCallOnCollections       (java:S1155)
#   RemoveUnusedLocalVariables     (java:S1481)
#   SimplifyChainedAssertJAssertions (java:S5838 — S03: 24 of 26
#   preflight violations were this one rule, burning two 900s fix
#   sessions; the recipe collapses assertThat(x.size()).isEqualTo(n)
#   chains deterministically)
mvn -q -Dmaven.repo.local="$M2_RUN" \
  org.openrewrite.maven:rewrite-maven-plugin:5.46.1:run \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-static-analysis:1.21.1,org.openrewrite.recipe:rewrite-testing-frameworks:2.23.1 \
  -Drewrite.activeRecipes=org.openrewrite.java.RemoveUnusedImports,org.openrewrite.java.testing.cleanup.TestsShouldNotBePublic,org.openrewrite.staticanalysis.UseDiamondOperator,org.openrewrite.staticanalysis.IsEmptyCallOnCollections,org.openrewrite.staticanalysis.RemoveUnusedLocalVariables,org.openrewrite.java.testing.assertj.SimplifyChainedAssertJAssertions \
  > /tmp/style-autofix.log 2>&1 || { echo "style-autofix: recipes failed — /tmp/style-autofix.log"; exit 1; }
CHANGED=$(git diff --name-only -- src/ | wc -l | tr -d ' ')
echo "style-autofix: recipes complete, $CHANGED files changed"
