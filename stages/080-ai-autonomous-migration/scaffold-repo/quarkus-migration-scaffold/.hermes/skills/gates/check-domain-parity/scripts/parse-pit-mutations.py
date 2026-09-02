#!/usr/bin/env python3
"""Parse PIT mutations.xml — count mutants (dry-run NOT_STARTED included).

Fail closed if file missing or zero mutants (AD-H / W2 §5 — no fake floors).
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def count_mutations(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    # PIT uses <mutation> elements; namespace-agnostic
    mutants = [el for el in root.iter() if el.tag.endswith("mutation") or el.tag == "mutation"]
    by_status: dict[str, int] = {}
    for m in mutants:
        st = m.attrib.get("status") or m.findtext("status") or "UNKNOWN"
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "ran": True,
        "mutations_total": len(mutants),
        "by_status": by_status,
        "source": str(path),
        "tool": "pitest-maven",
        "pinned_version": "1.25.5",
        "mode": "dry_run_or_report",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse PIT mutations.xml (fail closed on empty)")
    ap.add_argument("mutations_xml", type=Path, help="path to mutations.xml")
    ap.add_argument("-o", "--output", type=Path, help="write JSON evidence")
    args = ap.parse_args()
    if not args.mutations_xml.is_file():
        print(
            f"FAIL: missing mutations.xml at {args.mutations_xml} "
            f"(PIT dry-run produced no report — refuse as floor evidence)",
            file=sys.stderr,
        )
        return 1
    data = count_mutations(args.mutations_xml)
    if data["mutations_total"] <= 0:
        print(
            "FAIL: mutations.xml has zero mutants — refuse as G-1 volume floor evidence",
            file=sys.stderr,
        )
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"OK: PIT mutants={data['mutations_total']} by_status={data['by_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
