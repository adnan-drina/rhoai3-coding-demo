#!/usr/bin/env python3
"""K4 mint selftest. Not pytest. Not dest. Not live kanban."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k4_convert import convert_file  # noqa: E402
from k4_mint import (  # noqa: E402
    M4_ID,
    M4_IDEMPOTENCY_KEY,
    M4_SKILLS,
    M4_TITLE,
    argv_for_m4_terminator,
    argv_for_payload,
    mint_payloads,
    parse_created_id,
)
from k4_schema import IMPL, STAMP_ID, STAMP_SKILL, WRITER_ID  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    os.environ.pop("HERMES_KANBAN_TASK", None)
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
    expect = ["setup", "US1", "US2", STAMP_ID, M4_ID]
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
    if parents != [by["setup"]]:
        return _fail("US1 parents %s vs %s" % (parents, [by["setup"]]))
    if argv[argv.index("--workspace") + 1] != "dir:/projects/modernized":
        return _fail("US1 workspace %s" % argv)
    if argv[argv.index("--max-runtime") + 1] != "2h":
        return _fail("US1 max-runtime")
    skills = [argv[i + 1] for i, a in enumerate(argv) if a == "--skill"]
    if "spring-to-quarkus-patterns" not in skills:
        return _fail("US1 --skill %s" % skills)
    if minted.get("created_cards") != [row["task_id"] for row in minted["created"]]:
        return _fail("created_cards %s" % minted.get("created_cards"))
    if minted["created_cards"] != [
        "t_mint0001",
        "t_mint0002",
        "t_mint0003",
        "t_mint0004",
        "t_mint0005",
    ]:
        return _fail("native created_cards %s" % minted["created_cards"])
    stamp_row = next(c for c in minted["created"] if c["logical_id"] == STAMP_ID)
    stamp_argv = stamp_row["argv"]
    if stamp_argv[0:4] != ["/bin/hermes", "kanban", "create", "M3 %s" % STAMP_ID]:
        return _fail("stamp argv head %s" % stamp_argv[:4])
    stamp_parents = [
        stamp_argv[i + 1] for i, a in enumerate(stamp_argv) if a == "--parent"
    ]
    if stamp_parents != [by["setup"], by["US1"], by["US2"]]:
        return _fail("stamp parents %s" % stamp_parents)
    stamp_skills = [
        stamp_argv[i + 1] for i, a in enumerate(stamp_argv) if a == "--skill"
    ]
    if stamp_skills != [STAMP_SKILL]:
        return _fail("stamp --skill %s" % stamp_skills)
    if stamp_argv[stamp_argv.index("--max-retries") + 1] != "1":
        return _fail("stamp max-retries")
    if stamp_row["task_id"] != "t_mint0004":
        return _fail("stamp native id %s" % stamp_row["task_id"])
    m4_row = next(c for c in minted["created"] if c["logical_id"] == M4_ID)
    m4_argv = m4_row["argv"]
    if m4_argv[0:4] != ["/bin/hermes", "kanban", "create", M4_TITLE]:
        return _fail("M4 argv head %s" % m4_argv[:4])
    m4_parents = [m4_argv[i + 1] for i, a in enumerate(m4_argv) if a == "--parent"]
    m3_ids = [by["setup"], by["US1"], by["US2"], by[STAMP_ID]]
    if m4_parents != m3_ids:
        return _fail("M4 parents %s vs %s" % (m4_parents, m3_ids))
    if by["US1"] not in m4_parents or by["US2"] not in m4_parents:
        return _fail("M4 not parented to both stories")
    m4_skills = [m4_argv[i + 1] for i, a in enumerate(m4_argv) if a == "--skill"]
    if m4_skills != list(M4_SKILLS):
        return _fail("M4 --skill %s" % m4_skills)
    if m4_argv[m4_argv.index("--idempotency-key") + 1] != M4_IDEMPOTENCY_KEY:
        return _fail("M4 idempotency")
    if m4_argv[m4_argv.index("--max-retries") + 1] != "1":
        return _fail("M4 max-retries")
    if m4_argv[m4_argv.index("--assignee") + 1] != IMPL:
        return _fail("M4 assignee")
    if m4_row["task_id"] != "t_mint0005":
        return _fail("M4 native id %s" % m4_row["task_id"])
    if any(tok in m4_argv for tok in ("PASS", "REFUSE", "PROVISIONAL_ACCEPT")):
        return _fail("M4 argv carries a verdict token")
    if "empty created_cards" not in str(minted.get("attribution") or ""):
        return _fail("mint attribution missing Architect 144916ZA note")
    if "swarm" in argv or "decompose" in argv or "daemon" in argv:
        return _fail("US1 argv used OBJECT verb")
    dest5 = dict(result["payloads"][1])
    dest5["skills"] = []
    try:
        argv_for_payload(dest5, {"setup": "t_mint0001"})
        return _fail("dest-5 empty skills did not refuse")
    except ValueError as exc:
        if "K4_MINT_SKILLS" not in str(exc):
            return _fail("empty skills: %s" % exc)

    scratch = dict(result["payloads"][1])
    os.environ["K4_WORKSPACE"] = "/tmp/k4-scratch"
    try:
        argv_for_payload(scratch, {"setup": "t_mint0001"})
        return _fail("scratch K4_WORKSPACE did not refuse")
    except ValueError as exc:
        if "K4_MINT_WORKSPACE" not in str(exc):
            return _fail("scratch workspace: %s" % exc)
    finally:
        os.environ.pop("K4_WORKSPACE", None)

    os.environ["MODERNIZED_ROOT"] = "/projects/legacy"
    try:
        argv_for_payload(scratch, {"setup": "t_mint0001"})
        return _fail("legacy MODERNIZED_ROOT did not refuse")
    except ValueError as exc:
        if "K4_MINT_WORKSPACE" not in str(exc):
            return _fail("legacy workspace: %s" % exc)
    finally:
        os.environ.pop("MODERNIZED_ROOT", None)

    os.environ["K4_WORKSPACE"] = ""
    try:
        argv_for_payload(scratch, {"setup": "t_mint0001"})
        return _fail("empty K4_WORKSPACE did not refuse")
    except ValueError as exc:
        if "K4_MINT_WORKSPACE" not in str(exc):
            return _fail("empty workspace: %s" % exc)
    finally:
        os.environ.pop("K4_WORKSPACE", None)

    os.environ["K4_WORKSPACE"] = "relative/ws"
    try:
        argv_for_payload(scratch, {"setup": "t_mint0001"})
        return _fail("relative K4_WORKSPACE did not refuse")
    except ValueError as exc:
        if "K4_MINT_WORKSPACE" not in str(exc):
            return _fail("relative workspace: %s" % exc)
    finally:
        os.environ.pop("K4_WORKSPACE", None)

    os.environ["K4_WORKSPACE"] = "/projects/modernized/ws"
    try:
        under = argv_for_payload(scratch, {"setup": "t_mint0001"})
    finally:
        os.environ.pop("K4_WORKSPACE", None)
    if under[under.index("--workspace") + 1] != "dir:/projects/modernized/ws":
        return _fail("under-tree workspace %s" % under)

    no_prod = dict(result["payloads"][1])
    no_prod["skills"] = ["check-spec-readiness"]
    try:
        argv_for_payload(no_prod, {"setup": "t_mint0001"})
        return _fail("checker-only skills did not refuse")
    except ValueError as exc:
        if "K4_NO_PRODUCER" not in str(exc):
            return _fail("checker-only skills: %s" % exc)
    if parse_created_id('{"id":"t_abc123"}') != "t_abc123":
        return _fail("parse id fallback")

    bad = dict(result["payloads"][1])
    bad["title"] = "hand-mint US1"
    try:
        argv_for_payload(bad, {"setup": "t_mint0001"})
        return _fail("wrong title did not refuse")
    except ValueError as exc:
        if "K4_MINT_TITLE" not in str(exc):
            return _fail("wrong title: %s" % exc)

    try:
        argv_for_payload(
            {
                "logical_id": WRITER_ID,
                "title": "Mint writer",
                "assignee": "orchestrator",
                "parents": [],
                "body": "{}",
                "idempotency_key": "k4:mint-writer:dead",
            },
            {},
        )
        return _fail("factory payload did not refuse")
    except ValueError as exc:
        if "K4_FACTORY" not in str(exc):
            return _fail("factory: %s" % exc)

    os.environ["HERMES_KANBAN_TASK"] = "t_m2plan01"
    try:
        argv_m2 = argv_for_payload(dict(result["payloads"][1]), {"setup": "t_mint0001"})
    finally:
        os.environ.pop("HERMES_KANBAN_TASK", None)
    m2_parents = [argv_m2[i + 1] for i, a in enumerate(argv_m2) if a == "--parent"]
    if m2_parents != ["t_m2plan01", "t_mint0001"]:
        return _fail("M2 parent stamp %s" % m2_parents)

    swarm = ["/bin/hermes", "kanban", "swarm", "nope"]
    try:
        from k4_mint import assert_native_create

        assert_native_create(swarm)
        return _fail("swarm argv did not refuse")
    except ValueError as exc:
        if "K4_MINT_CREATE" not in str(exc):
            return _fail("swarm: %s" % exc)

    from k4_mint import main as mint_main  # noqa: PLC0415

    if mint_main(["--help"]) != 0:
        return _fail("k4_mint --help must exit 0")

    try:
        argv_for_m4_terminator([])
        return _fail("empty M4 parents did not refuse")
    except ValueError as exc:
        if "K4_MINT_PARENT" not in str(exc):
            return _fail("empty M4 parents: %s" % exc)

    print("OK: K4 mint (serial create, M4 terminator, max-retries 1, no dest factory cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
