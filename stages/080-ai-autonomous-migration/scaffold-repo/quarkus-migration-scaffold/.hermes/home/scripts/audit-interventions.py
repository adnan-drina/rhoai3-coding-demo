#!/usr/bin/env python3
"""AD-010 / finding 7 — intervention ledger auditability.

Rules:
  - Binding path: migration/interventions.jsonl
  - Each row needs class A|B, type, detail, ts, event_id (immutable)
  - Classification that cites monitor_event_id(s) must match
    migration/monitor-events.jsonl when that file exists
  - Rows with class but missing event_id ⇒ INCONCLUSIVE (fail)
  - Reconstructed-after-the-fact rows (reconstructed=true) ⇒ INCONCLUSIVE

Exit 0 when ledger absent (idle) or all rows auditable.
Exit 1 on schema/audit failure (treat campaign A/B as INCONCLUSIVE).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            raise SystemExit(f"FAIL: {path}:{i}: invalid JSON ({e})") from e
        if not isinstance(obj, dict):
            raise SystemExit(f"FAIL: {path}:{i}: row must be object")
        rows.append(obj)
    return rows


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    ledger = root / "migration" / "interventions.jsonl"
    if not ledger.is_file():
        print("OK: interventions ledger absent — audit idle")
        return 0

    rows = load_jsonl(ledger)
    if not rows:
        print("OK: interventions ledger empty")
        return 0

    monitor_ids: set[str] = set()
    mon_path = root / "migration" / "monitor-events.jsonl"
    if mon_path.is_file():
        for obj in load_jsonl(mon_path):
            eid = obj.get("event_id") or obj.get("id")
            if eid:
                monitor_ids.add(str(eid))

    bad = 0
    for i, row in enumerate(rows, 1):
        label = f"interventions.jsonl:{i}"
        for req in ("ts", "class", "type", "detail", "event_id"):
            if row.get(req) in (None, ""):
                print(f"FAIL: {label}: missing {req}", file=sys.stderr)
                bad = 1
        clas = row.get("class")
        if clas not in ("A", "B"):
            print(f"FAIL: {label}: class must be A|B", file=sys.stderr)
            bad = 1
        if row.get("reconstructed") in (True, "true", "yes", 1):
            print(
                f"FAIL: {label}: reconstructed=true ⇒ INCONCLUSIVE "
                f"(live A/B required; AD-010 finding 7)",
                file=sys.stderr,
            )
            bad = 1
        cites = row.get("monitor_event_ids") or row.get("monitor_event_id")
        if cites is not None:
            if isinstance(cites, str):
                cites = [cites]
            if not isinstance(cites, list):
                print(f"FAIL: {label}: monitor_event_id(s) must be list/string", file=sys.stderr)
                bad = 1
            elif monitor_ids:
                for cid in cites:
                    if str(cid) not in monitor_ids:
                        print(
                            f"FAIL: {label}: monitor_event_id={cid!r} unmatched "
                            f"in monitor-events.jsonl ⇒ INCONCLUSIVE",
                            file=sys.stderr,
                        )
                        bad = 1
            # If monitor file absent, citation is recorded but not joinable —
            # do not hard-fail (Monitor may land later); warn.
            elif cites:
                print(
                    f"WARN: {label}: cites monitor events but "
                    f"migration/monitor-events.jsonl absent",
                    file=sys.stderr,
                )

    if bad:
        print(
            "Intervention ledger audit FAILED — treat A/B campaign claim as INCONCLUSIVE",
            file=sys.stderr,
        )
        return 1
    print(f"OK: interventions ledger auditable ({len(rows)} row(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
