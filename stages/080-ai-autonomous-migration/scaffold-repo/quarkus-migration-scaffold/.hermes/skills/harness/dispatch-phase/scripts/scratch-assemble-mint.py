#!/usr/bin/env python3
"""M2 Done oracle (Architect E-20260818T221200Z form a).

Copy tasks.md + evidence/ into a throwaway dir and run handover-mint.py
--write *there*. Require that exit. Never write dest partition.json.
Does not grow handover-mint.py (freeze 1088).

Usage:
  python3 scratch-assemble-mint.py <dest-root>
  python3 scratch-assemble-mint.py <fixture-root> --expect-fail
  python3 scratch-assemble-mint.py <fixture-root> --assert-polish-excludes pom.xml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_MINT = _SCRIPTS / "handover-mint.py"


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_tasks(root: Path) -> Path:
    direct = root / "tasks.md"
    if direct.is_file():
        return direct
    # Never discover a tasks.md inside the harness tree. `.hermes` ships INSIDE
    # the dest (I-14), so on a real dest root this rglob also finds the
    # fixtures/scratch-assemble/*/tasks.md shipped with this very script --
    # len(hits) is then 3 (4 once M2 writes its plan) and the oracle dies on
    # "multiple", making the M2 Done criterion unreachable on every dest.
    # Fixture roots keep working because `direct` short-circuits above, which is
    # why validate.sh stayed green while a dest could not run this at all.
    hits = sorted(p for p in root.rglob("tasks.md") if ".hermes" not in p.parts)
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise SystemExit(f"FAIL: multiple tasks.md under {root}: {hits}")
    raise SystemExit(f"FAIL: no tasks.md under {root}")


def _copy_tree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_file():
        shutil.copy2(src, dst)


def _stage(src: Path, wrap: Path) -> Path:
    modern = wrap / "modernized"
    modern.mkdir()
    tasks = _find_tasks(src)
    try:
        rel = tasks.relative_to(src)
    except ValueError:
        rel = Path("tasks.md")
    _copy_tree(tasks, modern / rel)
    ev = src / "evidence"
    if ev.is_dir():
        _copy_tree(ev, modern / "evidence")
        part = modern / "evidence" / "briefs" / "partition.json"
        if part.is_file():
            part.unlink()
        bodies = modern / "evidence" / "bodies"
        if bodies.is_dir():
            shutil.rmtree(bodies)
    yaml = src / "migration.yaml"
    if yaml.is_file():
        shutil.copy2(yaml, modern / "migration.yaml")
    hermes_src = src / ".hermes"
    if not (hermes_src / "skills").is_dir():
        hermes_src = _SCRIPTS.parents[3]
    if (hermes_src / "skills").is_dir():
        _copy_tree(hermes_src, modern / ".hermes")
    legacy = src / "legacy-at-3"
    if legacy.is_dir():
        _copy_tree(legacy, wrap / ".derived" / "legacy-at-3")
    return modern


def _polish_files(modern: Path) -> list[str]:
    part = modern / "evidence" / "briefs" / "partition.json"
    data = json.loads(part.read_text(encoding="utf-8"))
    out: list[str] = []
    for s in data.get("stories") or []:
        if str(s.get("kind") or "").lower() != "polish":
            continue
        for p in s.get("files_in_scope") or []:
            if isinstance(p, str) and p.strip():
                out.append(p.replace("\\", "/"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    ap.add_argument(
        "--expect-fail",
        action="store_true",
        help="rehearsal: require --write to refuse (Verify-only polish / PB-2)",
    )
    ap.add_argument(
        "--assert-polish-excludes",
        metavar="PATH",
        help="after a successful --write, require PATH absent from polish files_in_scope",
    )
    args = ap.parse_args()
    src = Path(args.root).resolve()
    dest_part = src / "evidence" / "briefs" / "partition.json"
    before = _sha(dest_part)
    if not _MINT.is_file():
        print(f"FAIL: missing {_MINT}", file=sys.stderr)
        return 2
    wrap = Path(tempfile.mkdtemp(prefix="scratch-assemble-"))
    try:
        modern = _stage(src, wrap)
        tasks = _find_tasks(modern)
        inv = modern / "evidence" / "entry-point-inventory.json"
        if not inv.is_file():
            print("FAIL: scratch missing evidence/entry-point-inventory.json", file=sys.stderr)
            return 1
        proc = subprocess.run(
            [
                sys.executable,
                str(_MINT),
                str(modern),
                "--write",
                "--tasks",
                str(tasks),
                "--inventory",
                str(inv),
            ],
            cwd=str(modern),
            capture_output=True,
            text=True,
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        after = _sha(dest_part)
        if after != before:
            print(
                "FAIL: dest evidence/briefs/partition.json changed — oracle must "
                "write only the throwaway dir",
                file=sys.stderr,
            )
            return 1
        if args.expect_fail:
            if proc.returncode == 0:
                print("FAIL: expected --write refuse (Verify-only polish)", file=sys.stderr)
                print(blob, file=sys.stderr)
                return 1
            print(
                f"OK: scratch --write refused rc={proc.returncode} "
                f"(dest partition.json untouched)"
            )
            return 0
        if proc.returncode != 0:
            print(blob, file=sys.stderr)
            print(f"FAIL: scratch handover-mint --write rc={proc.returncode}", file=sys.stderr)
            return 1
        if args.assert_polish_excludes:
            want = args.assert_polish_excludes.replace("\\", "/")
            held = _polish_files(modern)
            if want in held:
                print(
                    f"FAIL: polish files_in_scope still holds {want}: {held}",
                    file=sys.stderr,
                )
                return 1
            print(
                f"OK: ownership stripped {want} from polish "
                f"(dest partition.json untouched)"
            )
            return 0
        print("OK: scratch handover-mint --write (dest partition.json untouched)")
        return 0
    finally:
        shutil.rmtree(wrap, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
