#!/usr/bin/env python3
"""The errors header's objectName translation (compat-mapping validation_helpers
getObjectName), checked against Spring itself.

Spring binds a validated @RequestBody under Conventions.getVariableNameForParameter,
which for a non-collection, non-array type is ClassUtils.getShortNameAsProperty:
java.beans.Introspector.decapitalize of the short name. The catalog's
translation must give the same name for ordinary, two-capital, single-letter
and nested type names, and the old getRootBeanClass().getSimpleName() mapping
(M-3 2026-09-30: OwnerDto where the source sent ownerDto) must not.

The oracle compiles and runs a small program against spring-core 5.3.31 from
the local Maven repository; SKIP with the reason when it is absent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
CATALOG = GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
SPRING_CORE = Path.home() / ".m2" / "repository" / "org" / "springframework" / "spring-core" / "5.3.31" / "spring-core-5.3.31.jar"
EXPR = "java.beans.Introspector.decapitalize(violation.getRootBeanClass().getSimpleName())"
NAMES = ["OwnerDto", "PetTypeDto", "URLDto", "A", "Outer.InnerDto", "X1Dto"]


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    for key in ("org.springframework.validation.BindingResult", "org.springframework.validation.FieldError",
                "org.springframework.validation.Errors"):
        row = cat["validation_helpers"][key]
        if row["mapping"]["getObjectName()"] != EXPR or EXPR not in row["action"]:
            print("FAIL: %s maps getObjectName() to Spring's binding name: %s" % (key, row["mapping"]["getObjectName()"]), file=sys.stderr)
            return 1
        if "getRootBeanClass().getSimpleName()" in row["action"].replace(EXPR, ""):
            print("FAIL: %s still offers the bare simple name" % key, file=sys.stderr)
            return 1
    if not (shutil.which("javac") and shutil.which("java")):
        print("SKIP: validation-object-name: javac/java not on PATH (catalog rows checked)")
        return 0
    if not SPRING_CORE.is_file():
        print("SKIP: validation-object-name: %s is not in the local Maven repository (catalog rows checked)" % SPRING_CORE)
        return 0
    with tempfile.TemporaryDirectory(prefix="objname-") as td:
        src = Path(td) / "Oracle.java"
        decls = "".join("static class %s {}\n" % n for n in NAMES if "." not in n)
        decls += "static class Outer { static class InnerDto {} }\n"
        rows = "".join('  show(Oracle.%s.class);\n' % n for n in NAMES)
        src.write_text("public class Oracle {\n%s"
                       "static void show(Class<?> c) {\n"
                       "  System.out.println(org.springframework.util.ClassUtils.getShortNameAsProperty(c) + \" \" + "
                       "java.beans.Introspector.decapitalize(c.getSimpleName()) + \" \" + c.getSimpleName());\n}\n"
                       "public static void main(String[] a) {\n%s}\n}\n" % (decls, rows), encoding="utf-8")
        c = subprocess.run(["javac", "-cp", str(SPRING_CORE), "-d", td, str(src)], capture_output=True, text=True)
        if c.returncode != 0:
            print("FAIL: the oracle does not compile: %s" % c.stderr[-400:], file=sys.stderr)
            return 1
        r = subprocess.run(["java", "-cp", "%s:%s" % (SPRING_CORE, td), "Oracle"], capture_output=True, text=True)
        if r.returncode != 0:
            print("FAIL: the oracle does not run: %s" % r.stderr[-400:], file=sys.stderr)
            return 1
    lines = [ln.split() for ln in r.stdout.strip().splitlines()]
    bad = [ln for ln in lines if ln[0] != ln[1]]
    if bad or len(lines) != len(NAMES):
        print("FAIL: Spring's binding name differs from the translation: %s" % bad, file=sys.stderr)
        return 1
    if not any(ln[0] != ln[2] for ln in lines) or dict((ln[2], ln[0]) for ln in lines).get("OwnerDto") != "ownerDto":
        print("FAIL: the negative control: the bare simple name must differ (OwnerDto vs ownerDto): %s" % lines, file=sys.stderr)
        return 1
    print("OK: validation-object-name (spring-core 5.3.31 ClassUtils.getShortNameAsProperty == %s for %s; the bare "
          "getSimpleName() differs, e.g. OwnerDto vs ownerDto)" % (EXPR, ", ".join("%s->%s" % (ln[2], ln[0]) for ln in lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
