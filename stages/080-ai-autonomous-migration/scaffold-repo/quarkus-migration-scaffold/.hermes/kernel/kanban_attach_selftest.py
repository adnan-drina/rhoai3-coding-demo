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
    attach_files,
    plan_attachments,
)


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
    print("OK: kanban attach (25 MiB cap, t_* task, OBJECT swarm absent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
