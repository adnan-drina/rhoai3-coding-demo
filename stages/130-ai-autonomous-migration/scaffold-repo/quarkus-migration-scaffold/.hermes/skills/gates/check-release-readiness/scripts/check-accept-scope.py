#!/usr/bin/env python3
"""AD-H §18 — SCOPED_ACCEPT gate (Architect E-20260809T113120Z finding 3).

Full ACCEPT is mechanically impossible when entry_point_descope_count > 0.
Standing descopes ⇒ verdict must be SCOPED_ACCEPT (or accept_kind=scoped).

Idle (exit 0) when no M5 ACCEPT / SCOPED_ACCEPT verdict is present.

Usage:
  python3 check-accept-scope.py .
  python3 check-accept-scope.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — no full ACCEPT contradicts a standing entry-point descope, or
     gate idle (no M5 verdict present)
  1  BLOCK — full ACCEPT with entry_point_descope_count > 0 (only
     SCOPED_ACCEPT allowed), or a non-integer entry_point_descope_count
  2  usage / harness defect (bad or unknown argument)
"""


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def descope_count(root: Path) -> tuple[int, str]:
    """Return (count, source_label). Prefer explicit fields; else count ack rows."""
    # Explicit on inventory / residue
    for rel in (
        "evidence/entry-point-inventory.json",
        "migration/residue/entry-point-descopes.json",
        "evidence/acks/entry-point-descopes.json",
    ):
        path = root / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            for key in (
                "entry_point_descope_count",
                "descope_count",
                "standing_descope_count",
            ):
                if key in data:
                    try:
                        return int(data[key]), rel
                    except (TypeError, ValueError):
                        pass
            descopes = data.get("descopes") or data.get("entry_point_descopes")
            if isinstance(descopes, list):
                return len(descopes), rel
        if isinstance(data, list):
            return len(data), rel

    # Count descope ack files
    adir = root / "evidence/acks"
    if adir.is_dir():
        n = 0
        for path in adir.glob("*descope*"):
            if path.is_file():
                n += 1
        if n:
            return n, "evidence/acks/*descope*"
    return 0, "none"


def m5_verdicts(root: Path) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    vdir = root / "evidence/verdicts"
    if not vdir.is_dir():
        return out
    for path in sorted(vdir.glob("*.json")):
        try:
            for obj in load_items(path):
                if not isinstance(obj, dict):
                    continue
                if str(obj.get("phase") or "").upper() != "M5":
                    continue
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
        help="product root containing evidence/verdicts (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    verdicts = m5_verdicts(root)
    if not verdicts:
        print("OK: no M5 verdict — SCOPED_ACCEPT gate idle")
        return 0

    count, src = descope_count(root)
    bad = 0
    for label, obj in verdicts:
        v = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper().replace(
            "-", "_"
        )
        kind = str(obj.get("accept_kind") or obj.get("acceptKind") or "").lower()
        # Normalize scoped token
        is_scoped = v == "SCOPED_ACCEPT" or kind in {"scoped", "scoped_accept"}
        is_full = v == "ACCEPT" and kind in {"full", ""}
        # Explicit field on verdict wins if present
        declared = obj.get("entry_point_descope_count")
        try:
            effective = int(declared) if declared is not None else count
        except (TypeError, ValueError):
            effective = count
            bad = 1
            print(
                f"FAIL: {label}: entry_point_descope_count not an int",
                file=sys.stderr,
            )

        if is_full and effective > 0:
            print(
                f"FAIL: {label}: full ACCEPT with entry_point_descope_count="
                f"{effective} (source={src}) — only SCOPED_ACCEPT allowed "
                f"(Architect E-20260809T113120Z / AD-H §18)",
                file=sys.stderr,
            )
            bad = 1
        elif is_scoped and effective == 0 and declared is None and count == 0:
            # Scoped with zero descopes is odd but allowed (explicit claim)
            pass
        elif v == "ACCEPT" and kind == "scoped":
            # accept_kind scoped with verdict ACCEPT → treat as SCOPED_ACCEPT ok
            pass

    if bad:
        return 1
    print(
        f"OK: SCOPED_ACCEPT gate — descope_count={count} (source={src}); "
        f"checked {len(verdicts)} M5 verdict(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
