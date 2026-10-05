#!/usr/bin/env python3
"""K3 mint-verifier checker — full gap set on a graph snapshot.

Does not talk to a live board. Does not run dest PID reclaim.
Does not wrap hermes kanban daemon.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k3_schema import (  # noqa: E402
    ACK_GATE_MARKERS,
    IMPL,
    LEGAL_REFUSE,
    OBJECT_VERIFIER_REVIEW,
    ORCH,
    RELEASE_STATUSES,
    REMEDY,
    TERMINATORS,
    VERIFIER_ROLE,
    WRITER_ROLE,
)

Issue = tuple[str, str, str]


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def validate_graph(graph: Any) -> list[Issue]:
    """Return every K3_* violation. Never returns at the first fail."""
    out: list[Issue] = []
    if not isinstance(graph, dict):
        return [_issue("K3_SCHEMA", "graph must be a JSON object")]

    if graph.get("daemon_force") is True:
        out.append(_issue("K3_DAEMON", "daemon_force is true"))
    if graph.get("claimed_refuse_control") is True:
        out.append(
            _issue("K3_REFUSE_CLAIM", "claimed_refuse_control stamped true")
        )

    cards = graph.get("cards")
    if not isinstance(cards, list) or not cards:
        out.append(_issue("K3_SCHEMA", "cards[] missing or empty"))
        return out

    writers = [c for c in cards if str(c.get("role") or "") == WRITER_ROLE]
    verifiers = [c for c in cards if str(c.get("role") or "") == VERIFIER_ROLE]
    m3 = [
        c
        for c in cards
        if str(c.get("phase") or "").upper() == "M3"
        or str(c.get("role") or "") == IMPL
    ]

    blob = json.dumps(graph, sort_keys=True)
    for marker in ACK_GATE_MARKERS:
        if marker in blob:
            out.append(_issue("K3_ACK_GATE", "ack_gate marker %s present" % marker))
            break

    if len(writers) == 0 and len(verifiers) == 0:
        factory_present = False
    else:
        factory_present = True
        if len(writers) != 1:
            out.append(
                _issue("K3_SCHEMA", "need exactly one mint-writer, got %d" % len(writers))
            )
        if len(verifiers) != 1:
            out.append(
                _issue(
                    "K3_VERIFIER_MISSING",
                    "need exactly one mint-verifier, got %d" % len(verifiers),
                )
            )

    writer = writers[0] if writers else None
    verifier = verifiers[0] if verifiers else None
    manifest = graph.get("manifest")
    expected = []
    if isinstance(manifest, dict):
        expected = list(manifest.get("created_cards") or [])

    if writer is not None:
        if str(writer.get("assignee") or "") != ORCH:
            out.append(
                _issue("K3_ASSIGNEE", "mint-writer assignee must be %s" % ORCH)
            )
        created = list(writer.get("created_cards") or [])
        term = str(writer.get("terminator") or "")
        if str(writer.get("status") or "") == "done":
            if not created:
                out.append(
                    _issue("K3_CREATED_CARDS", "mint-writer done with empty created_cards")
                )
            elif expected and sorted(created) != sorted(expected):
                out.append(
                    _issue(
                        "K3_CREATED_CARDS",
                        "created_cards %s != manifest %s" % (created, expected),
                    )
                )
            if term and term != "kanban_complete":
                out.append(
                    _issue(
                        "K3_TERMINATOR",
                        "mint-writer done via %s (need kanban_complete)" % term,
                    )
                )
        if term == OBJECT_VERIFIER_REVIEW:
            out.append(
                _issue("K3_TERMINATOR", "same-card review on mint-writer is OBJECT")
            )

    vid = str(verifier.get("id") or "") if verifier else ""
    if verifier is not None:
        if str(verifier.get("assignee") or "") != ORCH:
            out.append(
                _issue("K3_ASSIGNEE", "mint-verifier assignee must be %s" % ORCH)
            )
        vterm = str(verifier.get("terminator") or "")
        vstatus = str(verifier.get("status") or "")
        if vterm == OBJECT_VERIFIER_REVIEW:
            out.append(
                _issue(
                    "K3_TERMINATOR",
                    "kanban_request_review on mint-verifier would let a reviewer complete release M3",
                )
            )
        if vstatus == "blocked":
            if vterm and vterm != LEGAL_REFUSE:
                out.append(
                    _issue(
                        "K3_TERMINATOR",
                        "verifier blocked via %s (need sticky %s)" % (vterm, LEGAL_REFUSE),
                    )
                )
            for card in m3:
                st = str(card.get("status") or "")
                if st in RELEASE_STATUSES or st in ("ready", "running"):
                    out.append(
                        _issue(
                            "K3_VERIFIER_PARENT",
                            "M3 %s is %s while verifier is blocked" % (card.get("id"), st),
                        )
                    )
        if vstatus in RELEASE_STATUSES and vterm and vterm != "kanban_complete":
            out.append(
                _issue(
                    "K3_TERMINATOR",
                    "verifier released via %s (ACCEPT is kanban_complete)" % vterm,
                )
            )
        if vterm and vterm not in TERMINATORS:
            out.append(_issue("K3_TERMINATOR", "unknown terminator %s" % vterm))

    if vid:
        for card in m3:
            parents = card.get("parents") or []
            if not isinstance(parents, list) or vid not in [str(p) for p in parents]:
                out.append(
                    _issue(
                        "K3_VERIFIER_PARENT",
                        "M3 %s missing mint-verifier parent %s" % (card.get("id"), vid),
                    )
                )
            if str(card.get("assignee") or "") != IMPL:
                out.append(
                    _issue("K3_ASSIGNEE", "M3 %s assignee must be %s" % (card.get("id"), IMPL))
                )

    if not factory_present:
        for card in cards:
            if str(card.get("phase") or "").upper() != "M3":
                continue
            if str(card.get("assignee") or "") != IMPL:
                out.append(
                    _issue(
                        "K3_ASSIGNEE",
                        "M3 %s assignee must be %s" % (card.get("id"), IMPL),
                    )
                )

    return out


def validate_file(path: Path) -> list[Issue]:
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [_issue("K3_SCHEMA", str(exc))]
    return validate_graph(graph)


def format_issues(issues: list[Issue]) -> str:
    lines = []
    for code, detail, remedy in issues:
        lines.append("%s: %s" % (code, detail))
        lines.append("  remedy: %s" % remedy)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    graphs: list[Path] = []
    i = 0
    while i < len(args):
        if args[i] in ("--graph", "--body") and i + 1 < len(args):
            graphs.append(Path(args[i + 1]))
            i += 2
            continue
        if args[i].startswith("-"):
            print("FAIL: unknown flag %s" % args[i], file=sys.stderr)
            return 1
        graphs.append(Path(args[i]))
        i += 1
    if not graphs:
        print("FAIL: pass --graph PATH", file=sys.stderr)
        return 1
    bad = 0
    n = 0
    for p in graphs:
        n += 1
        issues = validate_file(p)
        if issues:
            bad = 1
            print(format_issues(issues), file=sys.stderr)
    if bad:
        print("K3 graph checks FAILED (%d file(s))." % n, file=sys.stderr)
        return 1
    print("OK: K3 graph checks passed (%d file(s))." % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
