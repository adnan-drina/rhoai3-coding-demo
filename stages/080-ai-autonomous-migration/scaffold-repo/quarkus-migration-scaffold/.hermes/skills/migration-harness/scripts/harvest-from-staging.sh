#!/usr/bin/env bash
# Harvest one M1-transformed class from migration/staging into the scaffold,
# applying ONLY the package rename (legacyPackage -> targetPackage, read from
# migration.yaml). The destination PATH is computed deterministically so a
# rewrite task NEVER hand-builds it.
#
# Why this exists (V5 run-4): a rewrite session substituted the target
# package as a DOTTED directory — `src/main/java/com.demo/model/...` instead
# of `src/main/java/com/demo/model/...`. That compiles (javac reads the
# package declaration, not the path), so no build/sonar gate catches it; and
# the session could not clean it up because the headless command policy
# denies `rm`/`git clean` (a 35-minute stall). Computing the path with '/'
# joins here makes a dotted directory impossible — the model supplies only
# the package-relative path, never the package directories.
#
# Usage:  harvest-from-staging.sh <package-relative-path>
#   e.g.  harvest-from-staging.sh model/Product.java
#         harvest-from-staging.sh service/CatalogService.java
# The path is RELATIVE TO THE PACKAGE ROOT (below com/redhat/coolstore or
# com/demo). Do not include the package directories, and never pass an
# absolute or dotted path. Run from the modernized repo root.
set -euo pipefail

rel="${1:?usage: harvest-from-staging.sh <package-relative-path, e.g. model/Product.java>}"
rel="${rel#/}"

[ -f migration.yaml ] || { echo "FATAL: run from the modernized repo root (migration.yaml not found)"; exit 2; }
LEG=$(grep -m1 -E "^[[:space:]]*legacyPackage:" migration.yaml | awk '{print $2}')
TGT=$(grep -m1 -E "^[[:space:]]*targetPackage:" migration.yaml | awk '{print $2}')
[ -n "$LEG" ] && [ -n "$TGT" ] || { echo "FATAL: legacyPackage/targetPackage missing from migration.yaml"; exit 2; }

# '/'-joined package paths — the whole point: a dotted directory cannot arise.
LEGP=${LEG//./\/}
TGTP=${TGT//./\/}
src="migration/staging/src/main/java/$LEGP/$rel"
dst="src/main/java/$TGTP/$rel"

[ -f "$src" ] || { echo "FATAL: staged source not found: $src"; echo "  (path is relative to the package root; migration/staging holds the M1-transformed legacy)"; exit 2; }

mkdir -p "$(dirname "$dst")"
sed "s/${LEG//./\\.}/$TGT/g" "$src" > "$dst"

# Post-conditions: dest exists under the '/'-joined target package, no dotted dir.
grep -q "package[[:space:]]\+$(echo "$TGT" | sed 's/\./\\./g')" "$dst" \
  || { echo "FATAL: harvested file missing 'package $TGT' — check the staged source"; exit 3; }
echo "harvested: $src -> $dst (package $LEG -> $TGT, dest path '/'-joined)"
