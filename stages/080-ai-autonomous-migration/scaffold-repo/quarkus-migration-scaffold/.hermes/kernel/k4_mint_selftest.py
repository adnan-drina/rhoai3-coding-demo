#!/usr/bin/env python3
"""K4 mint-writer selftest. Not pytest. Not dest. Not live kanban."""
from __future__ import annotations

import json
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k4_convert import convert_file  # noqa: E402
from k4_mint import argv_for_payload, mint_payloads, parse_created_id  # noqa: E402
from k4_schema import IMPL, ORCH  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    for label in ("k4_mint.py", "k4_schema.py"):
        blob = (KERNEL / label).read_text(encoding="utf-8")
        for line in blob.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and "create_task" in stripped:
                return _fail("%s imports create_task: %s" % (label, stripped))

    result, issues = convert_file(KERNEL / "fixtures" / "k4-valid-partition.json")
    if issues or result is None:
        return _fail("convert: %s" % issues)
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> tuple[int, str, str]:
        calls.append(list(argv))
        tid = "t_mint%04d" % len(calls)
        return 0, json.dumps({"task_id": tid}), ""

    minted = mint_payloads(result["payloads"], runner=runner, hermes="/bin/hermes")
    expect = ["mint-writer", "mint-verifier", "setup", "US1", "US2"]
    got = [row["logical_id"] for row in minted["created"]]
    if got != expect:
        return _fail("create order %s != %s" % (got, expect))
    if minted.get("claimed_control") is not False:
        return _fail("claimed_control must stay false")
    by = minted["by_logical_id"]
    us1 = next(c for c in minted["created"] if c["logical_id"] == "US1")
    argv = us1["argv"]
    if argv[0:4] != ["/bin/hermes", "kanban", "create", "M3 US1"]:
        return _fail("US1 argv head %s" % argv[:4])
    if argv[argv.index("--assignee") + 1] != IMPL:
        return _fail("US1 assignee")
    if argv[argv.index("--max-retries") + 1] != "1":
        return _fail("US1 max-retries")
    parents = [argv[i + 1] for i, a in enumerate(argv) if a == "--parent"]
    if parents != [by["mint-verifier"], by["setup"]]:
        return _fail("US1 parents %s vs %s" % (parents, [by["mint-verifier"], by["setup"]]))
    if "swarm" in argv or "decompose" in argv or "daemon" in argv:
        return _fail("US1 argv used OBJECT verb")
    writer = next(c for c in minted["created"] if c["logical_id"] == "mint-writer")
    if "--max-retries" in writer["argv"]:
        return _fail("factory card pinned max-retries")
    if writer["argv"][writer["argv"].index("--assignee") + 1] != ORCH:
        return _fail("writer assignee")
    if parse_created_id('{"id":"t_abc123"}') != "t_abc123":
        return _fail("parse id fallback")

    bad = dict(result["payloads"][3])
    bad["title"] = "hand-mint US1"
    try:
        argv_for_payload(bad, {"mint-verifier": "t_mint0002", "setup": "t_mint0003"})
        return _fail("wrong title did not refuse")
    except ValueError as exc:
        if "K4_MINT_TITLE" not in str(exc):
            return _fail("wrong title: %s" % exc)

    swarm = ["/bin/hermes", "kanban", "swarm", "nope"]
    try:
        from k4_mint import assert_native_create

        assert_native_create(swarm)
        return _fail("swarm argv did not refuse")
    except ValueError as exc:
        if "K4_MINT_CREATE" not in str(exc):
            return _fail("swarm: %s" % exc)

    print("OK: K4 mint-writer (serial create, max-retries 1, OBJECT swarm/decompose)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
