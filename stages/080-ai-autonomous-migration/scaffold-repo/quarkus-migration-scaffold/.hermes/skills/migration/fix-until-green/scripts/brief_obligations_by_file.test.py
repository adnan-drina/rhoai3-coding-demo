#!/usr/bin/env python3
"""An objective's obligations are listed per file with every line, mechanical removals apart from decision
sites, from the compiler's own tree position (v30 H-3, t_bdc6bab8; architect decision 2026-10-01).

Run 26/27/3 of the DAO-exceptions objective grepped `--section items` 60+ times to rebuild a file -> line map
of 97 obligations (two loop-guard halts, I-2/I-2b); the constituent counter showed a structural-rule zero beside
open compiler obligations. The real JdkDiagnostics runs on a DAO-shaped file; the work list carries its
``site``; the brief groups by file; the digest prints every line; the site is audit-only (not identity)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brief as B  # noqa: E402
from _loop_common import ensure_hermes_lib  # noqa: E402,F401
from planner.worklist import compile_items as diagnostic_items  # noqa: E402
from planner.plan_semantics import ITEM_AUDIT  # noqa: E402

SRC = """package p;

import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;

public class ClinicServiceImpl {
    public int find(int id) throws DataAccessException {
        try {
            return id;
        } catch (EmptyResultDataAccessException e) {
            return 0;
        }
    }

    public void save(int id) throws DataAccessException, java.io.IOException { }

    public Object fail() { return new DataAccessException("x"); }
}
"""


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    root = Path(tempfile.mkdtemp())
    f = root / "src/main/java/p/ClinicServiceImpl.java"
    f.parent.mkdir(parents=True)
    f.write_text(SRC)
    out = root / "d.json"
    subprocess.run(["java", str(HERE / "jdk-diagnostics" / "JdkDiagnostics.java"), "--source", str(root), "--out", str(out)],
                   check=True, capture_output=True)
    diags = json.loads(out.read_text())
    sites = {(d["line"], d.get("site")) for d in diags["diagnostics"] if d["kind"] == "ERROR"}
    check({(3, "import"), (4, "import"), (7, "throws"), (10, "catch"), (15, "throws"), (17, "other")} <= sites,
          "the compiler's tree position names import / throws / catch / other", sorted(sites))
    items = diagnostic_items(diags)
    check(all(i.get("site") for i in items if i.get("path", "").endswith(".java")), "the work list carries each item's site", items[:2])
    check("site" in ITEM_AUDIT, "site is audit evidence, not part of the plan's content")
    by = B.obligations_by_file(items)
    row = by["src/main/java/p/ClinicServiceImpl.java"]
    check(row["mechanical"] == {"import": [3, 4], "throws": [7, 15]}, "mechanical: imports and throws clauses with lines", row)
    check(row["decision"] == {"catch": [10], "other": [17]}, "decision sites: the catch and the other use", row)
    check(sorted(row["ids"]) == sorted(i["id"] for i in items), "every obligation identity is conserved", row["ids"])
    lines = B.obligations_by_file_lines(by)
    text = "\n".join(lines)
    check("mechanical: import L3,4; throws L7,15" in text and "DECISION: catch L10; other L17" in text,
          "the digest prints every line per file", lines)
    legacy = [{"id": "err:a", "path": "x/A.java", "line": 5}]
    check(B.obligations_by_file(legacy)["x/A.java"]["unclassified"] == [5], "an item without a site is listed, unclassified")
    check(B.obligations_by_file_lines({}) == [], "no objective, no table")
    print("OK: brief obligations by file" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
