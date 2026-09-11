#!/usr/bin/env python3
"""K3 live-board comparator (SAD v3 §8).

Proves exact equality between the loop's expected card set — every
accepted step's card (verification/loop/steps.json, keyed through the K4
mint receipts) plus the one open card K4 would mint now — and the native
Hermes board: same receipt-bound keys, same parent chain, no foreign
cards, no missing cards. Logic lives in ``.hermes/lib/planner/live_board.py``.

Usage:
  k3_live.py --root R (--snapshot FILE | --live) [--exempt t_x]... [--out PATH] [--hermes BIN]
Exit 0 EQUAL; 1 MISMATCH / non-authoritative receipt; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for p in (_KERNEL, _LIB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from k4_convert import convert_admitted  # noqa: E402
from k4_mint import load_mint_receipts  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.live_board import collect_board, compare_board, expected_from_loop, mint_map_from_receipts, parse_snapshot  # noqa: E402
from planner.paths import LOOP_CARDS, LOOP_STEPS  # noqa: E402

FORBIDDEN = ("swarm", "decompose", "daemon", "create_task", "link", "create")
DEFAULT_OUT = Path("evidence") / "receipts" / "k3" / "live-board.json"


def _run(argv: list[str]) -> tuple[int, str, str]:
    for tok in argv[1:]:
        if tok in FORBIDDEN:
            raise ValueError("K3_LIVE: argv contains OBJECT verb %r" % tok)
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def collect_live(hermes: str) -> list[dict[str, Any]]:
    """The live board, enriched -- ONE implementation, shared with K4
    (planner.live_board.collect_board)."""
    return collect_board(_run, hermes)


def expected_cards(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
    """(expected, mint_map, issues). The open card is whatever K4 would mint now."""
    result, issues = convert_admitted(root, write_root=False)
    mint_map = mint_map_from_receipts(load_mint_receipts(root))
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else None
    open_card = result["payloads"][0] if result and result.get("payloads") else None
    return expected_from_loop(steps, open_card, mint_map), mint_map, [d for _, d, _ in issues]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--snapshot", default="")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--exempt", action="append", default=[])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if bool(args.snapshot) == bool(args.live):
        print("FAIL: pass exactly one of --snapshot FILE or --live", file=sys.stderr)
        return 2
    receipt, gaps = verify_receipt(root, require_admitted=True)
    if gaps or receipt is None:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: K3_LIVE receipt not authoritative", file=sys.stderr)
        return 1
    try:
        cards = collect_live(args.hermes) if args.live else parse_snapshot(load_json(Path(args.snapshot)))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("FAIL: K3_LIVE %s" % exc, file=sys.stderr)
        return 1
    expected, mint_map, issues = expected_cards(root)
    registry = load_json(root / LOOP_CARDS) if (root / LOOP_CARDS).is_file() else {}
    exempt_ids = sorted({e for e in args.exempt if e} | {str(v) for v in (registry.get("control") or {}).values() if v})
    verdict = compare_board(expected, cards, exempt_ids=exempt_ids, mint_map=mint_map)
    verdict["receipt_sha256"] = receipt["receipt_digest"]
    verdict["exempt"] = exempt_ids
    verdict["k4_issues"] = issues
    out = Path(args.out)
    out = out if out.is_absolute() else root / out
    write_canonical(out, verdict)
    if verdict["verdict"] != "EQUAL":
        for m in verdict["missing_keys"]:
            print("  - missing card for %s" % m, file=sys.stderr)
        for f in verdict["foreign_cards"]:
            print("  - foreign card %s" % f, file=sys.stderr)
        for e in verdict["edge_gaps"]:
            print("  - edge %s" % e, file=sys.stderr)
        print("REFUSE: K3_LIVE board != expected loop cards (%s)" % out, file=sys.stderr)
        return 1
    print("OK: K3 live board equals the loop's expected cards (%d, receipt %s) → %s" % (verdict["expected_cards"], receipt["receipt_digest"][:16], out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
