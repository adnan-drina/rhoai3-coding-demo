#!/usr/bin/env python3
"""UPLIFT-7 / R-SK.13 companion — golden tree must not accumulate run-state.

Gates and composites historically wrote under:
  evidence/fixtures/admission/out/**
  evidence/derived/free-primitives-apply-log.json
Those paths regenerate on validate/derive and must never be tip-committed
(regression of e3925b3b). R-SK.13 skips `out/` so hermeticity alone cannot
catch this — this lint does.

Rules (fail-closed):
  G1  forbidden paths must not be git-tracked
  G2  if present on disk under the golden root, they must be gitignored
      (so `git add -A` cannot sweep them)
  G3  presence under the golden root is itself a violation (Deputy
      E-20260813T183214Z) — gitignore alone must not greenwash run-state
      that regenerates into the tip tree (e.g. free-primitives apply log).
      Gitignoring `.rhoai3-free-primitives-apply-log.json` is a sweep-guard,
      not the FP-1 fix (Deputy E-20260816T160604Z).
  G4  governance/**/target directories must be absent (E-193314Z;
      gitignore alone hid Maven fixture build dirt from G1/G3 file scan)

Usage:
  python3 check-golden-cleanliness.py --root .
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Exact files + directory prefixes relative to scaffold root.
FORBIDDEN_FILES = (
    "evidence/derived/free-primitives-apply-log.json",
    "evidence/derived/review-adhere-observe-needed.yaml",
    ".rhoai3-free-primitives-apply-log.json",
)
FORBIDDEN_PREFIXES = (
    "evidence/fixtures/admission/out/",
)
FORBIDDEN_NAME_GLOBS = (
    ("evidence/derived", "phase-*-task-id.txt"),
    ("evidence/derived", "created-cards-*.json"),
)


def governance_target_dirs(root: Path) -> list[Path]:
    """E-193314Z — Maven target/ under governance fixtures re-dirties the tip tree.

    GOLDEN_CLEANLINESS was blind because target/ is gitignored. Presence under
    governance/ is itself a violation; fixtures must build in a temp copy.
    """
    gov = root / "governance"
    if not gov.is_dir():
        return []
    return sorted(p for p in gov.rglob("target") if p.is_dir())


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
    )


def on_disk_forbidden(root: Path) -> list[Path]:
    hits: list[Path] = []
    for rel in FORBIDDEN_FILES:
        p = root / rel
        if p.is_file():
            hits.append(p)
    out_root = root / "evidence/fixtures/admission/out"
    if out_root.is_dir():
        hits.extend(sorted(p for p in out_root.rglob("*") if p.is_file()))
    for parent, pattern in FORBIDDEN_NAME_GLOBS:
        hits.extend(sorted((root / parent).glob(pattern)))
    # de-dupe
    seen: set[Path] = set()
    out: list[Path] = []
    for p in hits:
        if p not in seen and p.is_file():
            seen.add(p)
            out.append(p)
    return out


def tracked_forbidden(root: Path) -> list[str]:
    """Return tracked paths that match forbidden prefixes/names."""
    ls = git(root, "ls-files", "-z", "--", "evidence/", ".rhoai3-free-primitives-apply-log.json")
    if ls.returncode != 0:
        err = (ls.stderr or "").strip()
        # checkout-index snapshots have no .git. Nothing is tracked there, so
        # G1 (must not be git-tracked) is idle — not a violation. Treating
        # "not a git repository" as FAIL made SR-14's ship-artifact run
        # exit 1 with FAIL=0 (Deputy E-20260815T101500Z).
        if "not a git repository" in err:
            return []
        return [f"G1:git-ls-files-failed:{err}"]
    bad: list[str] = []
    for raw in (ls.stdout or "").split("\0"):
        rel = raw.strip()
        if not rel:
            continue
        if any(rel == f or rel.startswith(f + "/") for f in FORBIDDEN_FILES):
            bad.append(rel)
            continue
        if any(rel.startswith(pfx) for pfx in FORBIDDEN_PREFIXES):
            bad.append(rel)
            continue
        parent = str(Path(rel).parent)
        name = Path(rel).name
        for pdir, pattern in FORBIDDEN_NAME_GLOBS:
            if parent.replace("\\", "/") == pdir and Path(name).match(pattern.split("/")[-1]):
                bad.append(rel)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=clean, 1=contamination, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: bad root {root}", file=sys.stderr)
        return 2

    errs: list[str] = []
    for rel in tracked_forbidden(root):
        if rel.startswith("G1:"):
            errs.append(rel)
        else:
            errs.append(f"G1:tracked:{rel}")

    files = on_disk_forbidden(root)

    for p in governance_target_dirs(root):
        rel = str(p.relative_to(root)).replace("\\", "/")
        errs.append(f"G4:governance-target-present:{rel}")
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        # G3: presence is a violation even when gitignored (regenerating dirt).
        errs.append(f"G3:present:{rel}")
        ig = git(root, "check-ignore", "-q", rel)
        if ig.returncode != 0:
            errs.append(f"G2:not-gitignored:{rel}")

    for e in errs:
        print(e)
    print(f"GOLDEN_CLEANLINESS_FILES={len(files)} VIOLATIONS={len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
