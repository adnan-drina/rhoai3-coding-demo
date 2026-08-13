#!/usr/bin/env python3
"""AD-H §16.3 / §18.1 — candidate SHA then promote (external review finding 4).

Rules when a factory ship / push_main claim exists:
  - claim must name immutable `candidate_sha` (40-char or abbreviated git sha)
  - factory oracles are evaluated against that SHA (recorded on the claim)
  - `promoted_to_main` may be true only if `factory_result` is green/pass
  - if `factory_result` is fail/red, `promoted_to_main` must be false/absent
    (main unchanged)

Idle when no factory claim present.

Usage:
  python3 check-candidate-promote.py .
  python3 check-candidate-promote.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — every factory claim names an immutable candidate_sha and any
     promotion is backed by a green factory_result, or gate idle (no claim)
  1  BLOCK — factory claim missing candidate_sha, or promoted_to_main with a
     failing / non-green factory_result
  2  usage / harness defect (bad or unknown argument)
"""

SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def factory_claims(root: Path) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for d in (root / "evidence/preflight", root / "evidence/verdicts"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    phase = str(obj.get("phase") or "").upper()
                    status = str(obj.get("status") or obj.get("state") or "").lower()
                    ship = obj.get("ship") in (True, "true", "yes", 1)
                    if (
                        phase == "FACTORY"
                        or status in {"factory", "factory_ready", "push_main", "promote_main"}
                        or (ship and phase in {"FACTORY", ""})
                    ):
                        out.append((str(path.relative_to(root)), obj))
            except Exception:
                continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing evidence/preflight + evidence/verdicts (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    claims = factory_claims(root)
    if not claims:
        print("OK: no factory claim — candidate→promote gate idle")
        return 0

    bad = 0
    for label, obj in claims:
        sha = (
            obj.get("candidate_sha")
            or obj.get("candidateSha")
            or obj.get("immutable_candidate_sha")
        )
        if not sha or not SHA_RE.match(str(sha)):
            print(
                f"FAIL: {label}: factory claim missing immutable candidate_sha "
                f"(AD-H §16.3 / finding 4)",
                file=sys.stderr,
            )
            bad = 1
            continue
        result = str(
            obj.get("factory_result")
            or obj.get("factoryResult")
            or obj.get("result")
            or ""
        ).lower()
        promoted = obj.get("promoted_to_main") in (True, "true", "yes", 1) or str(
            obj.get("status") or ""
        ).lower() in {"push_main", "promoted", "main_updated"}
        if promoted and result in {"", "fail", "failed", "red", "refuse", "error"}:
            print(
                f"FAIL: {label}: promoted_to_main with factory_result={result!r} "
                f"— main must stay unchanged when factory fails (finding 4)",
                file=sys.stderr,
            )
            bad = 1
        if promoted and result not in {"pass", "green", "ok", "success", "accept"}:
            print(
                f"FAIL: {label}: promote requires factory_result pass/green "
                f"(got {result!r})",
                file=sys.stderr,
            )
            bad = 1

    if bad:
        return 1
    print(f"OK: candidate→promote gate ({len(claims)} factory claim(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
