#!/usr/bin/env bash
# Recipe-executed rewrites (docs/MTA-TO-SPEC-MAPPING.md R3): rules the
# MAPPINGS join classifies `recipe:` are transformed deterministically by
# OpenRewrite against a COPY of the legacy tree; transformed sources land
# in migration/staging/ for harvest tasks to pull from (already-jakarta),
# and migration/recipe-log.md records which rule ids are thereby resolved
# (plan-lint accepts those as covered without a task).
#
# Usage: recipe-transform.sh <legacy-root> <inventory.md>
# Exit 0 with recipe-log written, or 0 with "no recipe-class rules" noted
# (never blocks M1); real transform failures exit 1.
set -uo pipefail
LEGACY="${1:-/projects/legacy}"
INVENTORY="${2:-migration/findings-inventory.md}"
WORK=/tmp/recipe-work

# Rule ids classified recipe: in the inventory summary, and the recipe
# spec from the matching MAPPINGS join line embedded in each rule section
# header line "## <rid> [recipe]".
RIDS=$(grep -E "^- recipe: " "$INVENTORY" 2>/dev/null | sed 's/.*— //' | tr -d ',')
if [ -z "$RIDS" ]; then
  echo "no recipe-class rules in the inventory — nothing to transform"
  exit 0
fi

# Recipe specs come from the MAPPINGS join table (single source):
# class cell format recipe:<plugin-ver>:<artifact-coords>:<recipe-name>
MAPPINGS=".hermes/skills/migration-harness/MAPPINGS.md"
SPECS=$(grep -oE "recipe:[0-9][^ |]*" "$MAPPINGS" | sort -u)
[ -n "$SPECS" ] || { echo "no recipe specs in MAPPINGS join table"; exit 1; }

rm -rf "$WORK"
cp -r "$LEGACY" "$WORK"
rm -rf "$WORK/.git" "$WORK/target"

for spec in $SPECS; do
  # recipe:5.46.1:group:artifact:version:recipe.Name
  body="${spec#recipe:}"
  plugin_ver="${body%%:*}"; rest="${body#*:}"
  recipe_name="${rest##*:}"; coords="${rest%:*}"
  echo "running $recipe_name (plugin $plugin_ver, deps $coords)"
  (cd "$WORK" && mvn -q "org.openrewrite.maven:rewrite-maven-plugin:${plugin_ver}:run" \
      -Drewrite.recipeArtifactCoordinates="$coords" \
      -Drewrite.activeRecipes="$recipe_name") > /tmp/recipe-run.log 2>&1 \
    || { echo "RECIPE FAILED: $recipe_name — /tmp/recipe-run.log"; exit 1; }
done

mkdir -p migration/staging
rm -rf migration/staging/src
cp -r "$WORK/src" migration/staging/src
CHANGED=$(diff -rq "$LEGACY/src" "$WORK/src" 2>/dev/null | grep -c "^Files" || true)

{
  echo "# Recipe execution log (supervisor script step)"
  echo ""
  echo "Transformed legacy sources staged in migration/staging/src —"
  echo "harvest tasks MUST pull from the staging tree, not /projects/legacy."
  echo ""
  echo "Resolved rule ids (plan-lint accepts these as covered):"
  for rid in $RIDS; do echo "- $rid"; done
  echo ""
  echo "Recipes run: $SPECS"
  echo "Files changed: $CHANGED"
} > migration/recipe-log.md
echo "recipe transform complete: $CHANGED files changed, log in migration/recipe-log.md"
