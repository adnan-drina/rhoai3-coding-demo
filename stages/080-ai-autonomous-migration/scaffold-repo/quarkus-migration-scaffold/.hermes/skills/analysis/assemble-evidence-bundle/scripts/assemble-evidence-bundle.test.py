#!/usr/bin/env python3
"""assemble-evidence-bundle selftest: determinism, shuffle invariance, refusals."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
SCRIPT = HERE / "assemble-evidence-bundle.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bundle-") as tmp:
        t = Path(tmp).resolve()
        spec = specimens.specimen("http")
        a = specimens.build_dest(t / "a", spec, decisions=specimens.full_decisions(), seed=1)
        b = specimens.build_dest(t / "b", spec, decisions=specimens.full_decisions(), seed=99)
        for root in (a, b):
            p = _run(root)
            if p.returncode != 0:
                return _fail("assemble %s: %s%s" % (root.name, p.stdout, p.stderr))
        ba = (a / "evidence" / "planning" / "evidence-bundle.json").read_bytes()
        bb = (b / "evidence" / "planning" / "evidence-bundle.json").read_bytes()
        from planner.canonical import digest

        da, db = digest(load_json(a / "evidence" / "planning" / "evidence-bundle.json")), digest(load_json(b / "evidence" / "planning" / "evidence-bundle.json"))
        if da != db:
            return _fail("shuffled producer order must yield the same sealed digest (%s != %s)" % (da[:12], db[:12]))
        sa = {k: v for k, v in load_json(a / "evidence" / "planning" / "evidence-bundle.json").items() if k != "observations"}
        sb = {k: v for k, v in load_json(b / "evidence" / "planning" / "evidence-bundle.json").items() if k != "observations"}
        if sa != sb:
            return _fail("shuffled producer order must yield identical sealed content")
        _run(a)
        if (a / "evidence" / "planning" / "evidence-bundle.json").read_bytes() != ba:
            return _fail("rerun must be byte-identical")
        doc = load_json(a / "evidence" / "planning" / "evidence-bundle.json")
        if doc["schema"] != "rhoai3.evidence-bundle/v1" or len(doc["entry_points"]) != 4 or doc["mta"]["canary"]["fired"] is not True:
            return _fail("bundle content %s %s" % (len(doc["entry_points"]), doc["mta"]))
        if any(k in ba.decode("utf-8") for k in ("observed_at", "hostname")):
            return _fail("observations must be stripped")
        bare = t / "bare"
        bare.mkdir()
        (bare / ".hermes").mkdir()
        import shutil

        shutil.copytree(GOLDEN / ".hermes" / "planning", bare / ".hermes" / "planning")
        p = _run(bare)
        if p.returncode != 1 or "EVIDENCE_BUNDLE" not in p.stderr:
            return _fail("missing freeze must refuse: %s" % p.stderr)
    print("OK: assemble-evidence-bundle (identical rerun; shuffle-invariant; missing freeze refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
