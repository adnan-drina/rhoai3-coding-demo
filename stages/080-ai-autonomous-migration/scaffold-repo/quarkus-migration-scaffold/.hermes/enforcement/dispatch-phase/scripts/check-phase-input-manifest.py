#!/usr/bin/env python3
"""R0 input-manifest lint for planner cards (Operator E-20260811T113700Z).

M2a/M2b bodies must enumerate:
  ## Input manifest
  ### Required present
  - path…
  ### Forbidden absent
  - path or glob…

At create/dispatch: every Required path must exist; every Forbidden path/glob
must match zero files. Stale specimen bodies under evidence/bodies/ fail closed
(R-HX.15 promoted pre-M2).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PHASES = ("M2a", "M2b")
MANIFEST_RE = re.compile(
    r"## Input manifest.*?(?=^## |\Z)",
    re.M | re.S,
)
REQUIRED_RE = re.compile(
    r"### Required present\s*\n(.*?)(?=^### |\Z)",
    re.M | re.S,
)
FORBIDDEN_RE = re.compile(
    r"### Forbidden absent\s*\n(.*?)(?=^### |\Z)",
    re.M | re.S,
)
ITEM_RE = re.compile(r"^-\s+(`?)([^`\n]+)\1\s*$", re.M)


def extract_body(dispatch_sh: Path, phase: str) -> str | None:
    text = dispatch_sh.read_text(encoding="utf-8")
    m = re.search(
        rf"^\s+{re.escape(phase)}\)\s*\n"
        rf"((?:(?!^\s+(?:M[1-5][ab]?|factory)\)).)*)",
        text,
        re.M | re.S,
    )
    if not m:
        return None
    hm = re.search(r"<<'EOF'\n(.*?)EOF", m.group(1), re.S)
    return hm.group(1) if hm else None


def parse_items(section: str) -> list[str]:
    return [m.group(2).strip() for m in ITEM_RE.finditer(section)]


def resolve_dispatch(root: Path) -> Path | None:
    candidates = [
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "scripts"
        / "dispatch-phase.sh",
        root / ".hermes" / "skills" / "dispatch-phase" / "scripts" / "dispatch-phase.sh",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    only = sys.argv[2] if len(sys.argv) > 2 else ""
    dispatch = resolve_dispatch(root)
    if dispatch is None:
        print("INPUT_MANIFEST: missing dispatch-phase.sh", file=sys.stderr)
        return 1
    # Tip-bank B4 (Operator E-20260813T111910Z / V13_M4_SKIP_NON_PLANNER):
    # Planner manifests (M2a/M2b) only. Passing M1/M3/M4/M5 must NOT re-lint
    # M2a/M2b forbidden globs after M3 bodies exist.
    if only and only not in PHASES:
        print(f"OK: phase input manifests N/A for non-planner phase {only}")
        return 0
    live_ws = (root / "evidence" / "findings-handoff.json").is_file() or (
        root / "evidence" / "acks" / "m1-findings.ack.yaml"
    ).is_file()
    phases = (only,) if only in PHASES else PHASES
    bad = 0
    for phase in phases:
        body = extract_body(dispatch, phase)
        if not body:
            print(f"FAIL: {phase} body missing", file=sys.stderr)
            bad = 1
            continue
        mm = MANIFEST_RE.search(body)
        if not mm:
            print(f"FAIL: {phase} missing ## Input manifest section", file=sys.stderr)
            bad = 1
            continue
        block = mm.group(0)
        req_m = REQUIRED_RE.search(block)
        forb_m = FORBIDDEN_RE.search(block)
        if not req_m or not forb_m:
            print(
                f"FAIL: {phase} Input manifest needs ### Required present "
                f"and ### Forbidden absent",
                file=sys.stderr,
            )
            bad = 1
            continue
        required = parse_items(req_m.group(1))
        forbidden = parse_items(forb_m.group(1))
        if not required or not forbidden:
            print(f"FAIL: {phase} empty required/forbidden lists", file=sys.stderr)
            bad = 1
            continue
        # Tip golden tree never ships M1 outputs / Operator acks / M2a partition.
        # Declare + live-enforce; hard-fail only scaffold-shipped contracts.
        LIVE_ENFORCED_PREFIXES = (
            "evidence/acks/",
            "evidence/findings-handoff.json",
            "evidence/entry-point-inventory.json",
            "evidence/mta-findings.json",
        )
        for rel in required:
            if rel.endswith(" (after M2a)") or rel.startswith("OPTIONAL:"):
                print(f"OK: {phase} required deferred/optional {rel}")
                continue
            path = root / rel
            if path.is_file() or path.is_dir():
                print(f"OK: {phase} present {rel}")
            else:
                # Partition is only hard when dispatching M2b specifically.
                if rel == "evidence/briefs/partition.json" and only != "M2b":
                    print(f"OK: {phase} partition declared (hard on M2b dispatch)")
                    continue
                soft = (not live_ws) and any(
                    rel.startswith(p) or rel == p for p in LIVE_ENFORCED_PREFIXES
                )
                if soft:
                    print(f"OK: {phase} declared (tip soft / live-enforced) {rel}")
                    continue
                print(f"FAIL: {phase} required missing {rel}", file=sys.stderr)
                bad = 1
        for pattern in forbidden:
            # glob relative to root
            hits = sorted(root.glob(pattern)) if any(c in pattern for c in "*?[") else (
                [root / pattern] if (root / pattern).exists() else []
            )
            hits = [h for h in hits if h.is_file()]
            if hits:
                print(
                    f"FAIL: {phase} forbidden present {pattern} → "
                    f"{[str(h.relative_to(root)) for h in hits[:8]]}",
                    file=sys.stderr,
                )
                bad = 1
            else:
                print(f"OK: {phase} absent {pattern}")
        if "execute-as-defined" not in body.lower() and "needs_input" not in body:
            print(
                f"FAIL: {phase} missing execute-as-defined / needs_input stop rule",
                file=sys.stderr,
            )
            bad = 1
        else:
            print(f"OK: {phase} execute-as-defined-or-stop language")
    if bad:
        print("FAIL: phase input manifests (Operator E-20260811T113700Z)", file=sys.stderr)
        return 1
    print("OK: phase input manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
