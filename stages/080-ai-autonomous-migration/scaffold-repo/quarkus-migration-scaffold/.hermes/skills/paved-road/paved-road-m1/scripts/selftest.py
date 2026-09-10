#!/usr/bin/env python3
"""paved-road-m1 selftest: audit.json sync; green PASS; silence REFUSE; steps order contract."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = HERE / "assert-paved-road-audit.py"
GREEN = SKILL / "fixtures" / "green-m1"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from paved_road import GOLDEN_ROOT, coverage, load_steps, sync_audit, validate_steps_doc  # noqa: E402


def _run(log: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--log", str(log), "--root", str(root)], text=True, capture_output=True)


def main() -> int:
    rc, msg = sync_audit(SKILL)
    if rc != 0:
        return _fail(msg)
    doc = load_steps(SKILL / "steps.json")
    skills = [s["skill"] for s in doc["steps"] if s["backing"] == "skill"]
    if skills[0] != "freeze-migration-input" or "derive-legacy-boot3" in skills:
        return _fail("M1 must start with the freeze and never list derive-legacy-boot3: %s" % skills)
    if skills.index("inventory-legacy-surface") > skills.index("scan-with-mta"):
        return _fail("M1 order %s" % skills)
    # the bundle is assembled, and only then is the source recorded: the
    # capture reads the bundle's entry points and binds to its digest
    if skills[-1] != "capture-source-oracles" or skills.index("assemble-evidence-bundle") != len(skills) - 2:
        return _fail("M1 must end with the bundle and then the source capture: %s" % skills)
    producer = [s for s in doc["steps"] if s.get("producer")][0]
    if producer["skill"] != "assemble-evidence-bundle" or "evidence/planning/evidence-bundle.json" not in producer["keep"]:
        return _fail("M1 producer must be assemble-evidence-bundle owning evidence-bundle.json")
    swapped = json.loads(json.dumps(doc))
    steps = swapped["steps"]
    i = next(k for k, s in enumerate(steps) if s.get("skill") == "inventory-legacy-surface")
    j = next(k for k, s in enumerate(steps) if s.get("skill") == "scan-with-mta")
    steps[i], steps[j] = steps[j], steps[i]
    if not any("order" in e for e in validate_steps_doc(swapped)):
        return _fail("scan before inventory must be refused")
    derived = json.loads(json.dumps(doc))
    derived["steps"].insert(0, {"id": "derive-legacy-boot3", "backing": "skill", "skill": "derive-legacy-boot3"})
    if not any("derive-legacy-boot3" in e for e in validate_steps_doc(derived)):
        return _fail("derive-legacy-boot3 as an M1 step must be refused")

    green_txt = (GREEN / "official.log").read_text(encoding="utf-8")
    if "[exit 0]" in green_txt:
        return _fail("green fixture must omit [exit 0] (dispatcher success format)")
    proc = _run(GREEN / "official.log", GREEN)
    if proc.returncode != 0:
        return _fail("green-m1 must PASS: %s%s" % (proc.stdout, proc.stderr))

    with tempfile.TemporaryDirectory(prefix="paved-m1-") as tmp:
        official = Path(tmp) / "kanban" / "logs" / "t_silence.log"
        official.parent.mkdir(parents=True)
        official.write_text("reasoning: skip MTA\n", encoding="utf-8")
        proc = _run(official, GREEN)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or ("silence" not in blob and "absent" not in blob):
            return _fail("silence must REFUSE: %s" % blob)
        cache = Path(tmp) / "profiles" / "implementer" / "cache" / "terminal-output" / "out-1.log"
        cache.parent.mkdir(parents=True)
        cache.write_text("  ┊ 📚 skill  freeze-migration-input\n", encoding="utf-8")
        proc = _run(cache, GREEN)
        if proc.returncode != 1 or "not an official kanban log" not in proc.stdout + proc.stderr:
            return _fail("implementer cache --log must REFUSE")
        # missing KEEP refuses even with a green log
        partial = Path(tmp) / "partial"
        partial.mkdir()
        proc = _run(GREEN / "official.log", partial)
        if proc.returncode != 1 or "missing KEEP" not in proc.stdout + proc.stderr:
            return _fail("missing KEEP must REFUSE")

    if coverage(GOLDEN_ROOT) != 0:
        return _fail("coverage lint failed")
    print("OK: paved-road-m1 selftest (sync; order contract; green PASS; silence/cache/KEEP REFUSE; coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
