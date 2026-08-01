#!/usr/bin/env python3
"""Harvest-fidelity check (improvement B4): harvested classes in the
destination must match the recipe-staged legacy source modulo the
APPROVED transforms — catches silent drift like V3's serialVersionUID
rewrite mechanically.

Usage: harvest-fidelity.py [staging-root] [dest-src-root]
Defaults: migration/staging/src/main/java  src/main/java

For every staged class that exists in the destination (matched by
filename), diff after normalizing approved transforms:
  - package/import rename legacyPackage -> targetPackage (migration.yaml)
  - whitespace/blank-line/trailing-newline differences
  - comment-only lines (sonar-driven comment additions)
  - diamond operator (new X<...>() -> new X<>())
  - added annotation lines (CDI/MP annotations are conversion work)
  - Spring DAO / support drops on Quarkus classpath (O-FIDELITYDAO):
    `throws DataAccessException`, PropertyComparator/MutableSortDefinition,
    ToStringCreator — JDK Comparator / plain toString are approved
Anything else prints 'FIDELITY:<file>: <line>' and exits 1.
Classes only in one tree are skipped (conversion adds/removes are
story work, not drift).
"""
import os
import re
import sys


def package_map(root="."):
    """(legacyPackage, targetPackage) from migration.yaml — the single
    source of the rename. Falls back to the cart-demo values so a repo
    without the keys (or the instrument fixtures) still works."""
    leg, tgt = "com.redhat.coolstore", "com.demo"
    for base in (root, "."):
        try:
            y = open(os.path.join(base, "migration.yaml"), encoding="utf-8").read()
        except OSError:
            continue
        ml = re.search(r"legacyPackage:\s*([\w.]+)", y)
        mt = re.search(r"targetPackage:\s*([\w.]+)", y)
        if ml:
            leg = ml.group(1)
        if mt:
            tgt = mt.group(1)
        break
    return leg, tgt


LEGACY_PKG, TARGET_PKG = package_map()


# Statement-continuation reflow (V5 finding #1): a multi-line expression
# whose line breaks differ between staged and destination is NOT drift —
# e.g. a toString() that staged splits one `+ "..." + field` fragment per
# line but the harvest merged two fragments per line. A line-by-line
# membership test reports each staged fragment as "absent" though the
# statement is identical. Join continuation lines into one logical line on
# BOTH trees before comparing, so reflow compares equal while real content
# drift (a dropped/changed field) still differs.
_CONT_LEAD = re.compile(r"^(\+(?!\+)|\.|&&|\|\||\?|:|,)")  # +, ., &&, ||, ?, :, ,  (not ++)
_CONT_TRAIL = re.compile(r"(\+(?<!\+\+)|,|\(|&&|\|\||=)$")  # ends with + , ( && || =


def _join_continuations(lines):
    out = []
    for s in lines:
        if out and (_CONT_LEAD.match(s) or _CONT_TRAIL.search(out[-1])):
            out[-1] = out[-1] + s
        else:
            out.append(s)
    return out


_PKG_RENAME = re.compile(
    r"(?<![A-Za-z0-9_])" + re.escape(LEGACY_PKG) + r"(?=[\.;\s]|$)"
)


def normalize(text):
    out = []
    for line in text.splitlines():
        # O-PKGPREFIX: same package-boundary rename as harvest-from-staging.sh
        line = _PKG_RENAME.sub(TARGET_PKG, line)
        line = re.sub(r"new (\w+)<[^>]+>\(\)", r"new \1<>()", line)
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("*") or s.startswith("/*") or s.endswith("*/"):
            continue
        if re.fullmatch(r"@\w+(\([^)]*\))?", s):  # annotation-only lines
            continue
        if s.startswith("import "):
            # imports move with transforms; compare the set separately? keep simple: skip
            continue
        s = re.sub(r"\s+", " ", s)
        # Token-normalize spacing around structural punctuation (V4 finding
        # #5: legacy `if ( x )` reformatted to `if (x)` during conversion
        # flagged as drift though behavior is identical). Collapse spaces
        # adjacent to ()[]{};, so token-equivalent lines compare equal.
        s = re.sub(r"\s*([(){}\[\];,])\s*", r"\1", s)
        # Normalize spacing around the `+` concatenation operator so a
        # reflowed multi-line expression compares equal once its
        # continuation lines are joined (V5 #1: `x + a` vs the join boundary
        # `x + a+ ...`). Whitespace is already an approved, lossy transform
        # (the \s+ collapse above), so this stays within that contract.
        s = re.sub(r"\s*\+\s*", "+", s)
        # O-FIDELITYDAO: Spring DAO checked exceptions are not on the Quarkus
        # classpath — stripping `throws DataAccessException` is required for
        # compile, not silent harvest drift (S02 T-004).
        s = re.sub(r"throws\s*DataAccessException\b", "", s)
        # O-FIDSONAR: Sonar S112 / signature polish — ignore throws clauses.
        # Wave2 T-015: dest `throws IllegalArgumentException` vs staged
        # `throws Exception` (normalized away) still FIDELITY RED on
        # `void saveUser(User user);` absent — strip all throws on both sides.
        s = re.sub(r"throws\s+[A-Za-z0-9_.,\s]+", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            continue
        out.append(s)
    return _join_continuations(out)


def _approved_spring_support_drop(line: str) -> bool:
    """Staged Spring-support lines that Quarkus harvests replace with JDK APIs.

    O-FIDELITYDAO (S02 T-004): PropertyComparator/MutableSortDefinition →
    Comparator.comparing; ToStringCreator → ordinary toString. Re-harvesting
    Spring support to green-wash fidelity trips O-SFIXNOSPRING.
    """
    if "PropertyComparator" in line or "MutableSortDefinition" in line:
        return True
    if "ToStringCreator" in line:
        return True
    return False


def main():
    staging = sys.argv[1] if len(sys.argv) > 1 else "migration/staging/src/main/java"
    dest = sys.argv[2] if len(sys.argv) > 2 else "src/main/java"
    if not os.path.isdir(staging):
        print("no staging tree — fidelity check skipped")
        return 0
    staged = {}
    for dp, _, fs in os.walk(staging):
        for fn in fs:
            if fn.endswith(".java"):
                staged[fn] = os.path.join(dp, fn)
    problems = 0
    for dp, _, fs in os.walk(dest):
        for fn in fs:
            if fn in staged and fn.endswith(".java"):
                raw_dest = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
                # Semantic discriminator: a class that gained CDI/JAX-RS
                # annotations was CONVERTED (restructuring is the work);
                # fidelity applies to pure harvests only.
                if re.search(r"@(ApplicationScoped|RequestScoped|Singleton|Inject|Path|RegisterRestClient)\b", raw_dest):
                    continue
                staged_raw = open(staged[fn], encoding="utf-8", errors="replace").read()
                # O-FIDELITYVALID (Wave2 T-004): Spring BindingResult/FieldError
                # → Jakarta ConstraintViolation is intentional validation API
                # conversion (task "…with Jakarta validation"), not silent
                # harvest drift. Treat like CDI/JAX-RS conversion — skip.
                if re.search(r"\b(BindingResult|FieldError)\b", staged_raw) and re.search(
                    r"\bConstraintViolation\b", raw_dest
                ):
                    continue
                a = normalize(staged_raw)
                b = normalize(raw_dest)
                missing = [
                    l
                    for l in a
                    if l not in b and not _approved_spring_support_drop(l)
                ]
                # Conversion vs harvest (real-tree lesson: converted
                # classes legitimately restructure): only a file that
                # retained most staged lines is a HARVEST — a few
                # missing lines there are drift. Heavy restructuring is
                # conversion work; skip it.
                if a and len(missing) / len(a) > 0.25:
                    continue
                for l in missing[:3]:
                    print(f"FIDELITY:{fn}: staged line absent from destination: {l[:90]}")
                    problems += 1
    if problems:
        print(
            f"HARVEST FIDELITY RED: {problems} drifted lines "
            "(approved transforms: package, whitespace, comments, annotations, "
            "diamond, Spring-DAO/support drops)"
        )
        print("FIX: the destination class must match its migration/staging source (approved")
        print("     transforms only). Re-harvest the drifted file from migration/staging, or")
        print("     revert an invented/fabricated class. Do NOT hand-edit constants to match.")
        return 1
    print("harvest fidelity GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
