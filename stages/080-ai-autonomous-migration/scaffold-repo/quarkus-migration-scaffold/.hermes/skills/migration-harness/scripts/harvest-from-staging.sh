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
# O-HARVESTSTALL: also harvest src/test when main is absent (rewrite test migrations).
LEGP=${LEG//./\/}
TGTP=${TGT//./\/}
src_main="migration/staging/src/main/java/$LEGP/$rel"
src_test="migration/staging/src/test/java/$LEGP/$rel"
# O-DTOSTAGING: OpenAPI-generated DTOs often live under legacy
# target/generated-sources/openapi (not copied into migration/staging).
openapi_main="/projects/legacy/target/generated-sources/openapi/src/main/java/$LEGP/$rel"
openapi_alt="target/generated-sources/openapi/src/main/java/$LEGP/$rel"
if [ -f "$src_main" ]; then
  src="$src_main"
  dst="src/main/java/$TGTP/$rel"
elif [ -f "$src_test" ]; then
  src="$src_test"
  dst="src/test/java/$TGTP/$rel"
elif [ -f "$openapi_main" ]; then
  src="$openapi_main"
  dst="src/main/java/$TGTP/$rel"
elif [ -f "$openapi_alt" ]; then
  src="$openapi_alt"
  dst="src/main/java/$TGTP/$rel"
else
  echo "FATAL: staged source not found: $src_main (or $src_test)"
  echo "  also checked OpenAPI generated: $openapi_main"
  echo "  (path is relative to the package root; migration/staging holds the M1-transformed legacy)"
  exit 2
fi

# O-REDESIGNREVERT: do not overwrite a converted CDI/JAX-RS dest with staging
# Spring/legacy — fidelity polarity flips once converted (match staging = fail).
if [ -f "$dst" ] && [ "${HARVEST_FORCE:-}" != "1" ]; then
  if grep -qE '@(ApplicationScoped|RequestScoped|Singleton|Inject|Path|RegisterRestClient)\b' "$dst" 2>/dev/null \
    && grep -qE '@(RestController|Service|Component|Autowired|SpringBootApplication|Configuration)\b' "$src" 2>/dev/null; then
    echo "FATAL: O-REDESIGNREVERT — $dst is already converted (CDI/JAX-RS); refusing overwrite from Spring staging $src"
    echo "  Convert in place, or HARVEST_FORCE=1 only when intentional re-baseline."
    exit 4
  fi
fi

# O-HARVESTBRK: landing Spring REST/config into src/main after Spring deps are
# gone leaves an uncompilable tree. Refuse unless pom still has spring-boot.
if echo "$dst" | grep -qE '(^|/)src/main/java/' \
  && grep -qE '@(RestController|SpringBootApplication|Configuration|Component|Service)\b' "$src" 2>/dev/null; then
  if ! grep -qE 'spring-boot' pom.xml 2>/dev/null; then
    echo "FATAL: O-HARVESTBRK — staging $src still has Spring stereotypes but pom has no spring-boot"
    echo "  Convert annotations before harvest, or harvest into a convert task that lands Quarkus shape."
    exit 5
  fi
fi

mkdir -p "$(dirname "$dst")"
# O-PKGPREFIX: package-boundary rename — replace LEG only when not glued to a
# longer identifier char before the match, and only when followed by `.` / end
# of package token. Proves org.springframework.samples.petclinic → target does
# not rewrite org.springframework.boot.* (petclinic is not a prefix of boot);
# also blocks mid-token false hits (e.g. xcom.redhat.coolstore).
# O-HARVESTREPO: when pom has no spring-boot, convert Spring @Repository
# impls to CDI @ApplicationScoped (else Arc UnsatisfiedResolution / compile RED).
NO_SPRING=0
grep -qE 'spring-boot' pom.xml 2>/dev/null || NO_SPRING=1
python3 - "$LEG" "$TGT" "$src" "$dst" "$NO_SPRING" <<'PY'
import re, sys
leg, tgt, src, dst, no_spring = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1"
text = open(src, encoding="utf-8").read()
pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(leg) + r"(?=[\.;\s]|$)")
text = pat.sub(tgt, text)
# O-DTOSTAGING / jakarta harvest: OpenAPI codegen often still emits javax.*
text = text.replace("javax.validation.", "jakarta.validation.")
text = text.replace("javax.annotation.", "jakarta.annotation.")
if no_spring and re.search(r"@Repository\b", text):
    text = text.replace(
        "import org.springframework.stereotype.Repository;\n", ""
    )
    text = re.sub(
        r"import org\.springframework\.context\.annotation\.Profile;\n", "", text
    )
    text = text.replace(
        "import org.springframework.dao.DataAccessException;\n",
        "import jakarta.persistence.PersistenceException;\n",
    )
    text = re.sub(
        r"import org\.springframework\.orm\.hibernate5\.support\.OpenSessionInViewFilter;\n",
        "",
        text,
    )
    if "jakarta.enterprise.context.ApplicationScoped" not in text:
        # insert after package block's first import cluster
        text = re.sub(
            r"(package [^\n]+;\n)",
            r"\1\nimport jakarta.enterprise.context.ApplicationScoped;\n",
            text,
            count=1,
        )
    text = re.sub(r"@Repository\b", "@ApplicationScoped", text)
    text = re.sub(r"@Profile\([^)]*\)\s*\n", "", text)
    text = text.replace("DataAccessException", "PersistenceException")
    # persistence-to-quarkus: @PersistenceContext → @Inject EntityManager
    if "@PersistenceContext" in text:
        text = text.replace(
            "import jakarta.persistence.PersistenceContext;\n", ""
        )
        if "jakarta.inject.Inject" not in text:
            text = re.sub(
                r"(package [^\n]+;\n)",
                r"\1\nimport jakarta.inject.Inject;\n",
                text,
                count=1,
            )
        text = text.replace("@PersistenceContext", "@Inject")
open(dst, "w", encoding="utf-8").write(text)
PY

# Post-conditions: dest exists under the '/'-joined target package, no dotted dir.
grep -q "package[[:space:]]\+$(echo "$TGT" | sed 's/\./\\./g')" "$dst" \
  || { echo "FATAL: harvested file missing 'package $TGT' — check the staged source"; exit 3; }
echo "harvested: $src -> $dst (package $LEG -> $TGT, dest path '/'-joined)"
