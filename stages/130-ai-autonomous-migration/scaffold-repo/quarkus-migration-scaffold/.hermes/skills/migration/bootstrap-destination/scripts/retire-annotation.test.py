#!/usr/bin/env python3
"""java_retire_annotation selftest (recipe retire-adapter-owned-annotation/v1).

Real JDK parse tree (JavaStructure), real files, the decided-repairs engine:

  applicable       class- and method-level sites of the qualified annotation
                   and its single-type import are removed; an on-demand import
                   stays; another package's annotation of the same simple name
                   is untouched; the row never claims the adapter behaviour
  idempotent       a second run is already-applied and byte-identical
  inapplicable     a decision made for another source structure refuses and
                   changes nothing
  partial          a destination carrying only some of the sites refuses and
                   changes nothing
  ambiguous        a simple name the parse tree and imports cannot resolve
                   refuses and changes nothing
  wrong edit       an edit that also removes another annotation still parses
                   and compiles, and the independent structural postcondition
                   refuses it and restores every file
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_decided_repairs", HERE / "_decided_repairs.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

ANN = "org.springframework.web.bind.annotation.CrossOrigin"
SOURCES = {
    "src/main/java/org/acme/web/OwnerController.java": (
        "package org.acme.web;\n\n"
        "import org.springframework.web.bind.annotation.CrossOrigin;\n"
        "import org.springframework.web.bind.annotation.RestController;\n\n"
        "@RestController\n"
        "@CrossOrigin(exposedHeaders = \"errors, content-type\")\n"
        "public class OwnerController {\n"
        "    @CrossOrigin\n"
        "    public String list() { return \"\"; }\n\n"
        "    public String keep() { return \"\"; }\n"
        "}\n"),
    "src/main/java/org/acme/web/Star.java": (
        "package org.acme.web;\n\n"
        "import org.springframework.web.bind.annotation.*;\n\n"
        "@RestController @CrossOrigin(origins = \"*\") public class Star { }\n"),
    "src/main/java/org/acme/other/Other.java": (
        "package org.acme.other;\n\n"
        "import com.acme.cors.CrossOrigin;\n\n"
        "@CrossOrigin\n"
        "public class Other { }\n"),
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def tree(td: Path, *, extra: dict | None = None, drop_dest_site: bool = False) -> tuple[Path, Path]:
    root, copy = td / "dest", td / "frozen"
    for base in (root, copy):
        for rel, text in {**SOURCES, **(extra or {})}.items():
            p = base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    if drop_dest_site:
        p = root / "src/main/java/org/acme/web/OwnerController.java"
        p.write_text(p.read_text(encoding="utf-8").replace("    @CrossOrigin\n", ""), encoding="utf-8")
    return root, copy


def digest_tree(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.java")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def run(root: Path, copy: Path, t: dict) -> dict:
    manifest = {"transformations": [t]}
    eng = dr.Engine(root, copy, Path("-"), manifest, {"ADR-9"}, {"adr": "ADR-9", "applies": ["ADR-9"]})
    try:
        rows, _blocks = eng.run()
    finally:
        eng.java.close()
    return rows[0]


def authored(root: Path, copy: Path) -> dict:
    t = {"id": "t-cors", "adr": "ADR-9", "kind": "java_retire_annotation", "annotation": ANN, "roots": ["src/main/java"]}
    d = dr.describe_source(root, copy, {"transformations": [t]})[0]
    t["applicability"] = {"sites": d["sites"], "structure_sha256": d["structure_sha256"]}
    return t


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP: retire-annotation (no javac on PATH)")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="retire-"))
    try:
        # applicable, then idempotent
        root, copy = tree(tmp / "a")
        t = authored(root, copy)
        if t["applicability"]["sites"] != 3:
            return _fail("three qualified sites expected (class, method, on-demand), got %s" % t["applicability"])
        row = run(root, copy, t)
        if row["status"] != "applied":
            return _fail("the retirement must apply: %s" % row.get("refusal"))
        ctrl = (root / "src/main/java/org/acme/web/OwnerController.java").read_text()
        star = (root / "src/main/java/org/acme/web/Star.java").read_text()
        other = (root / "src/main/java/org/acme/other/Other.java").read_text()
        if "CrossOrigin" in ctrl or "@RestController" not in ctrl or "keep()" not in ctrl:
            return _fail("the controller must lose exactly the annotation and its import:\n" + ctrl)
        if "@CrossOrigin" in star or "import org.springframework.web.bind.annotation.*;" not in star or "@RestController" not in star:
            return _fail("an on-demand import stays; only the site goes:\n" + star)
        if other != SOURCES["src/main/java/org/acme/other/Other.java"]:
            return _fail("another package's CrossOrigin was touched")
        if row["details"]["discharges_adapter_obligation"] is not False:
            return _fail("the retirement must say it discharges no adapter behaviour")
        before = digest_tree(root)
        again = run(root, copy, t)
        if again["status"] != "already-applied" or digest_tree(root) != before:
            return _fail("a second run must be already-applied and change nothing: %s" % again["status"])

        # inapplicable: another source structure
        root, copy = tree(tmp / "b")
        bad = dict(authored(root, copy), applicability={"sites": 3, "structure_sha256": "0" * 64})
        before = digest_tree(root)
        row = run(root, copy, bad)
        if row["status"] != "refused" or row["refusal"]["class"] != "REPAIR_NOT_APPLICABLE" or digest_tree(root) != before:
            return _fail("a decision for another structure must refuse without edits: %s" % row.get("refusal"))

        # partial: the destination lost one site already
        root, copy = tree(tmp / "c", drop_dest_site=True)
        t = authored(root, copy)
        before = digest_tree(root)
        row = run(root, copy, t)
        if row["status"] != "refused" or row["refusal"]["class"] != "REPAIR_SITE_MISMATCH" or digest_tree(root) != before:
            return _fail("a partial destination must refuse without edits: %s" % row.get("refusal"))

        # ambiguous: an unimported simple name nothing declares
        root, copy = tree(tmp / "d", extra={"src/main/java/org/acme/web/Loose.java": "package org.acme.web;\n\n@CrossOrigin public class Loose { }\n"})
        t = {"id": "t-cors", "adr": "ADR-9", "kind": "java_retire_annotation", "annotation": ANN, "roots": ["src/main/java"],
             "applicability": {"sites": 3, "structure_sha256": "0" * 64}}
        before = digest_tree(root)
        row = run(root, copy, t)
        if row["status"] != "refused" or row["refusal"]["class"] != "REPAIR_ANNOTATION_UNRESOLVED" or digest_tree(root) != before:
            return _fail("an unresolvable name must refuse without edits: %s" % row.get("refusal"))

        # a wrong edit that still parses: the structural postcondition refuses it
        root, copy = tree(tmp / "e")
        t = authored(root, copy)
        real_write = dr.Engine._write_java

        def overreach(self, edits):
            real_write(self, edits)
            for rel in edits:
                p = self.root / rel
                p.write_text(p.read_text(encoding="utf-8").replace("@RestController\n", ""), encoding="utf-8")

        dr.Engine._write_java = overreach
        try:
            before = digest_tree(root)
            row = run(root, copy, t)
        finally:
            dr.Engine._write_java = real_write
        if row["status"] != "refused" or row["refusal"]["class"] != "REPAIR_POSTCONDITION" or digest_tree(root) != before:
            return _fail("an edit that also removed @RestController must be refused and restored: %s" % row.get("refusal"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: retire-annotation (class, method and on-demand sites of the qualified annotation retired with the single-type "
          "import; another package's name untouched; idempotent; inapplicable, partial and unresolvable refuse with no edit; "
          "a wrong edit that still parses is refused by the structural postcondition and restored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
