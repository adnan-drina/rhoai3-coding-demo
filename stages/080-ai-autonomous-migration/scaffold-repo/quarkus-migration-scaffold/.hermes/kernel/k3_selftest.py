#!/usr/bin/env python3
"""K3 land-time selftest. Not pytest. Not dest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
sys.path.insert(0, str(KERNEL.parent / "lib"))
from k3_verify import validate_file  # noqa: E402
from planner.live_board import collect_board, compare_board  # noqa: E402


def _board_enrichment_case() -> int:
    """The live board's EDGES arrive beside the task, not inside it.

    `hermes kanban show --json` answers {"task": {...}, "parents": [...]}. The
    K3 collector used to merge only the task, so every card came back
    parentless and every edge "mismatched" against a board that was correct
    (measured on dest v8, 2026-09-12; the K4 mint path had its own, fixed,
    copy of the same merge). One implementation now, and this is its test."""
    board = {
        "t_parent": {"id": "t_parent", "idempotency_key": "k4:c:a:1:aaaa", "status": "done"},
        "t_child": {"id": "t_child", "idempotency_key": "k4:c:b:1:bbbb", "status": "todo"},
    }

    def run(argv: list[str]) -> tuple[int, str, str]:
        if argv[1:3] == ["kanban", "list"]:
            return 0, json.dumps(list(board.values())), ""
        if argv[1:3] == ["kanban", "show"]:
            tid = argv[3]
            return 0, json.dumps({"task": dict(board[tid]),
                                  "parents": ["t_parent"] if tid == "t_child" else [],
                                  "children": []}), ""
        return 1, "", "unexpected argv %s" % argv

    cards = collect_board(run, "hermes")
    got = {c.get("id"): sorted(c.get("parents") or []) for c in cards}
    if got != {"t_parent": [], "t_child": ["t_parent"]}:
        print("FAIL: the collector must carry the edges beside the task: %s" % got, file=sys.stderr)
        return 1
    expected = {
        "k4:c:a:1:aaaa": {"key": "k4:c:a:1:aaaa", "parents": [], "status": "done", "task_id": "t_parent"},
        "k4:c:b:1:bbbb": {"key": "k4:c:b:1:bbbb", "parents": ["k4:c:a:1:aaaa"], "status": "open", "task_id": "t_child"},
    }
    verdict = compare_board(expected, cards)
    if verdict["verdict"] != "EQUAL" or verdict["edge_gaps"]:
        print("FAIL: a correct board must compare EQUAL: %s" % verdict, file=sys.stderr)
        return 1
    # and the counterexample: the task-only merge the defect had
    blind = [dict(c, parents=[]) for c in cards]
    if compare_board(expected, blind)["verdict"] != "MISMATCH":
        print("FAIL: a parentless board must NOT compare EQUAL", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    hold = KERNEL / "fixtures" / "k3-valid-hold.json"
    refuse = KERNEL / "fixtures" / "k3-valid-refuse-hold.json"
    retired = KERNEL / "fixtures" / "k3-valid-no-factory.json"
    bad = KERNEL / "fixtures" / "k3-bad-gap.json"
    for path in (hold, refuse, retired):
        issues = validate_file(path)
        if issues:
            print("FAIL: %s %s" % (path.name, issues), file=sys.stderr)
            return 1
    bad_codes = {c for c, _, _ in validate_file(bad)}
    need = {
        "K3_CREATED_CARDS",
        "K3_VERIFIER_PARENT",
        "K3_TERMINATOR",
        "K3_ACK_GATE",
        "K3_DAEMON",
        "K3_ASSIGNEE",
        "K3_REFUSE_CLAIM",
    }
    missing = need - bad_codes
    if missing:
        print("FAIL: bad fixture missed %s got %s" % (missing, bad_codes), file=sys.stderr)
        return 1
    if len(bad_codes) < 6:
        print("FAIL: expected full gap set, got %s" % bad_codes, file=sys.stderr)
        return 1
    if _board_enrichment_case():
        return 1
    print("OK: K3 selftest (%d codes on bad fixture; the live collector carries the edges `show --json` keeps beside the task, and a parentless board is a MISMATCH)" % len(bad_codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
