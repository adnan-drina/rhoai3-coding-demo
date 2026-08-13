#!/usr/bin/env python3
"""AD-H §18 — required oracle: factory must not contradict M5 ACCEPT.

Triggers when a factory advance/ship claim exists. Then requires a coherent
M5 ACCEPT verdict (or ack). Refuses factory ship if M5 is missing, REFUSE,
or INCONCLUSIVE.

Idle (exit 0) when no factory claim is present.

Usage:
  python3 check-factory-m5.py .
  python3 check-factory-m5.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — factory claim is coherent with a full M5 ACCEPT, or gate idle
     (no factory claim present)
  1  BLOCK — factory claim without M5 ACCEPT, factory contradicting an M5
     REFUSE/INCONCLUSIVE, or an M5 ACCEPT that is not composition-complete
     (provisional / scoped / standing descopes / unpinned kill-ratio)
  2  usage / harness defect (bad or unknown argument)
"""


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def factory_claims(root: Path) -> list[str]:
    claims: list[str] = []
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
                    if phase == "FACTORY" or status in {"factory", "factory_ready", "push_main"}:
                        claims.append(str(path.relative_to(root)))
                    elif ship and phase in {"FACTORY", ""}:
                        claims.append(str(path.relative_to(root)))
            except Exception:
                continue
    for d in (root / "evidence/tasks", root / "evidence/kanban"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    phase = str(obj.get("phase") or "").upper()
                    status = str(obj.get("status") or "").lower()
                    if phase == "FACTORY" and status in {
                        "done",
                        "complete",
                        "completed",
                        "shipped",
                        "closed",
                    }:
                        claims.append(str(path.relative_to(root)))
            except Exception:
                continue
    return claims


def typed_g1_waiver(root: Path) -> str | None:
    """Return relative path of a typed Operator g1 kill-ratio waiver ack, else None.

    Self-reported `g1_kill_ratio_waiver: true` on a verdict is NOT authority
    (Deputy E-20260813T144954Z P1). Waiver path is the pin contract location:
    evidence/acks/g1-kill-ratio-waiver*.ack.yaml
    """
    adir = root / "evidence" / "acks"
    if not adir.is_dir():
        return None
    for path in sorted(adir.glob("g1-kill-ratio-waiver*.ack.yaml")) + sorted(
        adir.glob("g1-kill-ratio-waiver*.ack.yml")
    ) + sorted(adir.glob("g1-kill-ratio-waiver*.ack.json")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if path.suffix == ".json":
            try:
                doc = json.loads(raw)
            except Exception:
                continue
        else:
            def field(name: str) -> str:
                import re

                m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
                return m.group(1).strip().strip("\"'") if m else ""

            doc = {
                "kind": field("kind"),
                "ack_type": field("ack_type"),
                "status": field("status"),
            }
        if doc.get("kind") != "migration-ack":
            continue
        if str(doc.get("status", "")).lower() != "acknowledged":
            continue
        # Filename already matched g1-kill-ratio-waiver*; status/kind checked above.
        return str(path.relative_to(root))
    return None


def pinned_kill_ratio_pass(root: Path) -> str | None:
    """Return label if a g1 kill-ratio pin artifact evaluates PASS, else None."""
    candidates = [
        root / "evidence" / "verdicts" / "g1-kill-ratio-pin.json",
        root / "evidence" / "derived" / "g1-kill-ratio-pin.json",
    ]
    vdir = root / "evidence" / "verdicts"
    if vdir.is_dir():
        candidates.extend(sorted(vdir.glob("*kill-ratio*pin*.json")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        ev = data.get("evaluation_against_measurement") or {}
        if isinstance(ev, dict) and ev.get("pass") in (True, "true", "yes", 1):
            pinned = data.get("status") == "PINNED" or data.get(
                "g1_kill_ratio_threshold_pinned"
            ) in (True, "true", "yes", 1)
            if pinned or data.get("schema", "").startswith("migration/g1-kill-ratio-pin"):
                return str(path.relative_to(root))
        if data.get("g1_kill_ratio") in ("PASS", "pass") and data.get(
            "g1_kill_ratio_threshold_pinned"
        ) in (True, "true", "yes", 1):
            return str(path.relative_to(root))
    return None


def load_migration_ack(path: Path) -> dict | None:
    """Parse a migration-ack artifact. Empty / touch'd files return None (P0)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return None
    if path.suffix == ".json" or path.name.endswith(".ack.json"):
        try:
            doc = json.loads(raw)
        except Exception:
            return None
        return doc if isinstance(doc, dict) else None
    import re

    def field(name: str) -> str:
        m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
        return m.group(1).strip().strip("\"'") if m else ""

    doc = {
        "kind": field("kind"),
        "ack_type": field("ack_type"),
        "status": field("status"),
        "accept_kind": field("accept_kind") or "full",
    }
    if not doc["kind"] and not doc["ack_type"] and not doc["status"]:
        return None
    return doc


def m5_accept_state(root: Path) -> tuple[str, str, dict]:
    """Return (state, label, obj) where state is ACCEPT|REFUSE|INCONCLUSIVE|MISSING.

    ACCEPT means **full** M5 ACCEPT (AD-H §18.0). Provisional is rejected.

    Authority sources (Deputy E-20260813T151402Z P0):
      1. A real M5 verdict JSON under evidence/verdicts/ (preferred).
      2. A non-empty migration-ack for m5-accept with kind/status acknowledged.
    A zero-byte `touch` of m5-accept.ack is NOT ACCEPT — Research reproduced
    that bypass; file presence alone is refused.
    Body `refs: [{key: m5_accept}]` is NOT proof of ACCEPT.
    """
    best: tuple[str, str, dict] = ("MISSING", "", {})
    vdir = root / "evidence/verdicts"
    if vdir.is_dir():
        for path in sorted(vdir.glob("*.json")):
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("phase") or "").upper() != "M5":
                        continue
                    v = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
                    if v in {"ACCEPT", "REFUSE", "INCONCLUSIVE"}:
                        best = (v, str(path.relative_to(root)), obj)
            except Exception:
                continue
    if best[0] != "MISSING":
        return best

    adir = root / "evidence" / "acks"
    candidates: list[Path] = []
    if adir.is_dir():
        for name in (
            "m5-accept.ack.yaml",
            "m5-accept.ack.yml",
            "m5-accept.ack.json",
            "m5-accept.ack",
        ):
            p = adir / name
            if p.is_file():
                candidates.append(p)
        candidates.extend(sorted(adir.glob("m5-accept*.ack.yaml")))
    for ack in candidates:
        doc = load_migration_ack(ack)
        if not doc:
            # Empty / unparseable — do NOT treat as ACCEPT (P0 touch bypass).
            continue
        if doc.get("kind") != "migration-ack":
            continue
        if str(doc.get("status", "")).lower() != "acknowledged":
            continue
        at = str(doc.get("ack_type") or "").lower().replace("_", "-")
        if at not in {"m5-accept", "m5_accept", "m5accept"}:
            continue
        kind = str(doc.get("accept_kind") or "full").lower()
        return (
            "ACCEPT",
            str(ack.relative_to(root)),
            {"accept_kind": kind or "full", "verdict": "ACCEPT"},
        )
    return best


def full_accept_ok(root: Path, obj: dict) -> str | None:
    """Return error string if M5 ACCEPT is not composition-complete, else None."""
    verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper().replace(
        "-", "_"
    )
    if verdict == "PROVISIONAL_ACCEPT":
        return "factory needs M5 ACCEPT, not PROVISIONAL_ACCEPT (AD-H §18.0)"
    if verdict == "SCOPED_ACCEPT":
        return (
            "factory needs full ACCEPT — SCOPED_ACCEPT is not factory-eligible "
            "(standing descopes; Architect E-20260809T113120Z)"
        )
    kind = str(obj.get("accept_kind") or obj.get("acceptKind") or "").lower()
    if kind == "provisional":
        return "M5 ACCEPT is provisional — factory needs full ACCEPT (AD-H §18.0)"
    if kind in {"scoped", "scoped_accept"}:
        return "factory needs full ACCEPT — accept_kind=scoped not eligible"
    if kind and kind not in {"full", ""}:
        return f"M5 ACCEPT accept_kind={kind!r} — need full"
    # Standing descopes block full ACCEPT even if accept_kind claims full
    try:
        descope = int(obj.get("entry_point_descope_count") or 0)
    except (TypeError, ValueError):
        descope = 0
    if descope > 0:
        return (
            f"entry_point_descope_count={descope} — full ACCEPT forbidden; "
            f"use SCOPED_ACCEPT (AD-H §18 / finding 3)"
        )
    kill = str(obj.get("g1_kill_ratio") or obj.get("g1KillRatio") or "").lower()
    pinned_field = obj.get("g1_kill_ratio_threshold_pinned") in (True, "true", "yes", 1)
    pin_art = pinned_kill_ratio_pass(root)
    waiver_art = typed_g1_waiver(root)
    self_waiver = obj.get("g1_kill_ratio_waiver") in (True, "true", "yes", 1) or (
        isinstance(obj.get("operator_waiver"), dict)
        and obj["operator_waiver"].get("g1_kill_ratio") in (True, "true", "yes", 1)
    )
    if kill == "pass" and not (pinned_field or pin_art):
        return "g1_kill_ratio=PASS without threshold pin artifact or field"
    if kill in {"", "pending_threshold"}:
        if waiver_art:
            return None
        if self_waiver and not waiver_art:
            return (
                "TRUST_UNVERIFIED: g1_kill_ratio_waiver on verdict is not authority — "
                "need evidence/acks/g1-kill-ratio-waiver*.ack.yaml or pin PASS "
                "(Deputy E-20260813T144954Z P1)"
            )
        if pin_art:
            return None
        return (
            "M5 full ACCEPT needs kill-ratio PASS (pinned artifact) or typed "
            "g1-kill-ratio-waiver ack"
        )
    if kill == "pass" and (pinned_field or pin_art):
        return None
    return None


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
        help="product root containing evidence/preflight, verdicts, tasks (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    claims = factory_claims(root)
    if not claims:
        print("OK: no factory advance claim — M5-contradict oracle idle")
        return 0
    state, where, obj = m5_accept_state(root)
    if state == "MISSING":
        print(
            "FAIL: factory claim without M5 ACCEPT "
            f"(claims={claims}; AD-H §18 must_not_contradict_m5_accept)",
            file=sys.stderr,
        )
        return 1
    if state in {"REFUSE", "INCONCLUSIVE"}:
        print(
            f"FAIL: factory contradicts M5 {state} at {where} (AD-H §18)",
            file=sys.stderr,
        )
        return 1
    err = full_accept_ok(root, obj)
    if err:
        print(f"FAIL: factory vs {where}: {err}", file=sys.stderr)
        return 1
    print(f"OK: factory coherent with M5 full ACCEPT ({where}; claims={len(claims)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
