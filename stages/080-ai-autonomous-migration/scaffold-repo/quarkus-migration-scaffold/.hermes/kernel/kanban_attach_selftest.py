#!/usr/bin/env python3
"""kanban attach selftest. Not dest. Not live kanban."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from kanban_attach import (  # noqa: E402
    DEFAULT_REL,
    MAX_BYTES,
    argv_for_attach,
    attach_and_prove,
    attach_files,
    plan_attachments,
)

STEPS_M1 = KERNEL.parent / "skills" / "paved-road" / "paved-road-m1" / "steps.json"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    src = (KERNEL / "kanban_attach.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and "create_task" in stripped:
            return _fail("imports create_task")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        keep = root / "evidence"
        keep.mkdir()
        handoff = keep / "findings-handoff.json"
        handoff.write_text('{"schema":"rhoai3.findings-handoff/v1"}', encoding="utf-8")
        (keep / "type-inventory.json").write_text(
            '{"schema":"rhoai3.type-inventory/v1"}', encoding="utf-8"
        )
        derived = keep / "derived"
        derived.mkdir()
        (derived / "legacy-at-3.json").write_text(
            '{"schema":"legacy-at-3/v2"}', encoding="utf-8"
        )
        huge = keep / "mta-findings.json"
        huge.write_bytes(b"x" * (MAX_BYTES + 1))
        plan = plan_attachments(root)
        paths = {Path(f["path"]).name for f in plan["files"]}
        if "findings-handoff.json" not in paths:
            return _fail("handoff not planned: %s" % plan)
        if "type-inventory.json" not in paths:
            return _fail("type-inventory not planned (dest-13): %s" % plan)
        if "legacy-at-3.json" in paths:
            return _fail("derivation manifest must not attach: %s" % plan)
        if any("legacy-at-3" in rel for rel in DEFAULT_REL):
            return _fail("DEFAULT_REL still names derived/legacy-at-3.json")
        if "evidence/type-inventory.json" not in DEFAULT_REL:
            return _fail("DEFAULT_REL must name type-inventory.json")
        if any(Path(f["path"]).name == "mta-findings.json" for f in plan["files"]):
            return _fail("oversize findings must not attach")
        if not any(s["reason"] == "exceeds 25 MiB cap" for s in plan["skipped"]):
            return _fail("oversize skip missing")
        argv = argv_for_attach("t_m1abcd", handoff, hermes="/bin/hermes")
        if argv != ["/bin/hermes", "kanban", "attach", "t_m1abcd", str(handoff)]:
            return _fail("argv %s" % argv)
        try:
            argv_for_attach("not-a-task", handoff)
            return _fail("bad task id did not refuse")
        except ValueError:
            pass
        calls: list[list[str]] = []

        def runner(a: list[str]) -> tuple[int, str, str]:
            calls.append(list(a))
            return 0, '{"ok":true}', ""

        minted = attach_files("t_m1abcd", plan, runner=runner, hermes="/bin/hermes")
        if minted.get("claimed_control") is not False:
            return _fail("claimed_control")
        if not calls or "swarm" in calls[0]:
            return _fail("calls %s" % calls)
    rc = _native_proof_cases()
    if rc:
        return rc
    print("OK: kanban attach (25 MiB cap, t_* task, OBJECT swarm absent; --exec proven by native records: "
          "missing/incomplete refuse, valid passes, a proven file is not re-attached; set == M1 KEEP)")
    return 0


def _native_proof_cases() -> int:
    """v23 M1: the attach step's OK is proven by the native records read back."""
    step = next(x for x in json.loads(STEPS_M1.read_text(encoding="utf-8"))["steps"] if x["id"] == "kanban-attach")
    if list(step["keep"]) != list(DEFAULT_REL) or step.get("native_attachments") is not True:
        return _fail("DEFAULT_REL must be the kanban-attach KEEP set with native_attachments: %s vs %s" % (DEFAULT_REL, step["keep"]))
    with tempfile.TemporaryDirectory() as tmp:
        root, store = Path(tmp) / "ws", Path(tmp) / "store"
        store.mkdir()
        for i, rel in enumerate(DEFAULT_REL):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text('{"n": %d}' % i, encoding="utf-8")
        records: list[dict] = []

        def read(task: str) -> list[dict]:
            return [dict(r) for r in records]

        def storing(mangle: str = "", drop: str = ""):
            def runner(argv: list[str]) -> tuple[int, str, str]:
                src = Path(argv[-1])
                if src.name == drop:
                    return 0, "", ""  # the CLI said nothing went wrong and recorded nothing
                data = src.read_bytes()[:-1] if src.name == mangle else src.read_bytes()
                dst = store / ("%d-%s" % (len(records), src.name))
                dst.write_bytes(data)
                records.append({"id": len(records) + 1, "filename": src.name, "size": len(data), "stored_path": str(dst)})
                return 0, "", ""
            return runner

        plan = plan_attachments(root)
        got = attach_and_prove(root, "t_m1abcd", plan, runner=storing(drop="type-inventory.json"), read=read)
        if not any("type-inventory.json: missing" in g for g in got["gaps"]):
            return _fail("an attach the store never recorded must be a gap: %s" % got["gaps"])
        records.clear()
        got = attach_and_prove(root, "t_m1abcd", plan, runner=storing(mangle="mta-findings.json"), read=read)
        if not any("mta-findings.json: incomplete" in g for g in got["gaps"]) or len(got["gaps"]) != 1:
            return _fail("a stored copy that differs must be a gap: %s" % got["gaps"])
        # the retry re-attaches only the unproven file; the newest record supersedes
        calls: list[str] = []
        base = storing()

        def counting(argv: list[str]) -> tuple[int, str, str]:
            calls.append(Path(argv[-1]).name)
            return base(argv)

        got = attach_and_prove(root, "t_m1abcd", plan, runner=counting, read=read)
        if got["gaps"] or calls != ["mta-findings.json"] or len(got["already_attached"]) != 5:
            return _fail("valid set after retry: gaps=%s calls=%s already=%s" % (got["gaps"], calls, got["already_attached"]))
        calls.clear()
        got = attach_and_prove(root, "t_m1abcd", plan, runner=counting, read=read)
        if got["gaps"] or calls:
            return _fail("a proven set is not re-attached: %s %s" % (calls, got["gaps"]))
        # evidence absent from the workspace is a gap, never a silent skip
        (root / DEFAULT_REL[2]).unlink()
        got = attach_and_prove(root, "t_m1abcd", plan_attachments(root), runner=counting, read=read)
        if not any(DEFAULT_REL[2] in g for g in got["gaps"]):
            return _fail("absent evidence must be a gap: %s" % got["gaps"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
