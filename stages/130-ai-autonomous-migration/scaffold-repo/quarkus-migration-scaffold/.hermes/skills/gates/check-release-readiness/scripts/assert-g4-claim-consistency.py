#!/usr/bin/env python3
"""Refuse G-4 N/A when the verdict says INCONCLUSIVE (or M5 requires G-4).

Architect 114513ZA / 114539ZA: SAMPLE INCONCLUSIVE is honest at the M4
floor; refusal N/A is OBJECT. G-4 applies to GET /greeting. Do not dest-edit
dest-4 evidence — this gate fails the dest-4-shaped split on dest-5.

Idle (exit 0) when evidence/verdicts is absent or empty.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

G4_NA = re.compile(
    r"(?:g[\s-]?4|runtime parity).{0,160}(?:n\s*/\s*a|not\s+applicable)|"
    r"(?:n\s*/\s*a|not\s+applicable).{0,160}(?:g[\s-]?4|runtime parity)",
    re.IGNORECASE | re.DOTALL,
)
G4_INCON = re.compile(
    r"g4_hook\s*[=:]\s*INCONCLUSIVE|"
    r'"g4_hook"\s*:\s*"INCONCLUSIVE"',
    re.IGNORECASE,
)
G4_REQUIRED = re.compile(
    r"M5\s+(?:ACCEPT\s+)?(?:would\s+)?require[s]?\s+G-4|"
    r"M5 requires G-4",
    re.IGNORECASE,
)
GREETING = re.compile(r"GET\s+/greeting|/greeting|stateless HTTP", re.IGNORECASE)


def _text(obj: object) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, sort_keys=True)


def iter_verdict_files(root: Path) -> list[Path]:
    base = root / "evidence" / "verdicts"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.json") if p.is_file())


def check_root(root: Path) -> list[str]:
    files = iter_verdict_files(root)
    if not files:
        return []
    blobs: list[tuple[Path, str]] = []
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ["unreadable %s: %s" % (path, exc)]
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = raw
        blobs.append((path, _text(doc)))

    issues: list[str] = []
    na_files = [p for p, t in blobs if G4_NA.search(t)]
    incon_files = [p for p, t in blobs if G4_INCON.search(t)]
    require_files = [p for p, t in blobs if G4_REQUIRED.search(t)]
    for path, text in blobs:
        if G4_NA.search(text) and (
            G4_INCON.search(text) or G4_REQUIRED.search(text)
        ):
            issues.append(
                "%s claims G-4 N/A and also INCONCLUSIVE/M5-requires-G-4"
                % path
            )
        if G4_NA.search(text) and GREETING.search(text):
            issues.append(
                "%s claims G-4 N/A for GET /greeting (G-4 applies)" % path
            )
    if na_files and (incon_files or require_files):
        issues.append(
            "G-4 split: N/A in %s vs INCONCLUSIVE/required in %s"
            % (
                ",".join(str(p) for p in na_files),
                ",".join(str(p) for p in incon_files + require_files),
            )
        )
    # Unique while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            out.append(issue)
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("usage: assert-g4-claim-consistency.py <product-root>", file=sys.stderr)
        return 2
    root = Path(args[0]).resolve()
    if not root.is_dir():
        print("FAIL: not a directory %s" % root, file=sys.stderr)
        return 2
    issues = check_root(root)
    if not iter_verdict_files(root):
        print("OK: G-4 claim consistency idle (no verdict artifacts)")
        return 0
    if issues:
        for issue in issues:
            print("FAIL: %s" % issue, file=sys.stderr)
        print(
            "G-4 SAMPLE INCONCLUSIVE is honest; N/A is OBJECT "
            "(Architect 114513ZA). G-4 applies to GET /greeting.",
            file=sys.stderr,
        )
        return 1
    print("OK: G-4 claims consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
