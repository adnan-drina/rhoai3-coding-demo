#!/usr/bin/env python3
"""M2 Done oracle (Architect E-20260818T221200Z form a).

Copy tasks.md + evidence/ into a throwaway dir and run handover-mint.py
--write *there*. Require that exit, then reverse-diff invented endpoints
(assert-partition-invented-routes.py; Architect 067420Z). When
evidence/type-inventory.json is present, every dest twin must appear in
the minted partition (same coverage class as HTTP rows; skip if absent).
When scratch has legacy-at-3, run existing stamp-body-dependencies.py +
assert-dependency-closure.py on minted bodies (V34-8; no second gate),
then existing assert-partition-topological-order.py (M2 must not exit
done with a partition the holder would refuse), then existing
relocate-descendant-import-writesets.py (MULTI_OWNER must fail M2 assemble,
not the holder).
Never write dest partition.json. Dest workers do not grow handover-mint.py.

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
_REVERSE = _SCRIPTS / "assert-partition-invented-routes.py"


def _find_under_skills(*parts: str) -> Path:
    cur = _SCRIPTS
    for _ in range(8):
        cand = cur.joinpath(*parts)
        if cand.is_file():
            return cand
        cur = cur.parent
    return Path("/nonexistent").joinpath(*parts)


_STAMP = _find_under_skills(
    "sdd", "check-spec-readiness", "scripts", "stamp-body-dependencies.py"
)
_CLOSURE = _find_under_skills(
    "sdd", "check-spec-readiness", "scripts", "assert-dependency-closure.py"
)
_UPTAKE = _find_under_skills(
    "sdd", "check-spec-readiness", "scripts", "assert-tasks-generator-uptake.py"
)
_TOPO = _find_under_skills(
    "sdd", "check-spec-readiness", "scripts", "assert-partition-topological-order.py"
)
_RELOCATE = _find_under_skills(
    "sdd",
    "check-spec-readiness",
    "scripts",
    "relocate-descendant-import-writesets.py",
)


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
        cur = _SCRIPTS
        hermes_src = Path("/nonexistent")
        for _ in range(8):
            if (cur / ".hermes" / "skills").is_dir():
                hermes_src = cur / ".hermes"
                break
            if cur.name == ".hermes" and (cur / "skills").is_dir():
                hermes_src = cur
                break
            cur = cur.parent
    if (hermes_src / "skills").is_dir():
        _copy_tree(hermes_src, modern / ".hermes")
    derived = None
    for cand in (
        src.parent / ".derived" / "legacy-at-3",
        Path("/projects/.derived/legacy-at-3"),
        src / ".derived" / "legacy-at-3",
        src / "legacy-at-3",
    ):
        if cand.is_dir():
            derived = cand
            break
    if derived is not None:
        _copy_tree(derived, wrap / ".derived" / "legacy-at-3")
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


def _body_rank(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if "setup" in name:
        return (0, name)
    if "foundational" in name:
        return (1, name)
    return (2, name)


def _run_type_closure(modern: Path) -> int:
    """Reuse M3 stamp + dependency-closure on scratch bodies (V34-8)."""
    bodies_dir = modern / "evidence" / "bodies"
    bodies = []
    if bodies_dir.is_dir():
        bodies = sorted(
            (
                p
                for p in bodies_dir.glob("m3-*.json")
                if not p.name.endswith(".sha256.json")
            ),
            key=_body_rank,
        )
    if not bodies:
        print("OK: type-closure skipped (no scratch bodies)")
        return 0
    legacy = modern.parent / ".derived" / "legacy-at-3"
    if not legacy.is_dir():
        print("OK: type-closure skipped (no legacy-at-3 in scratch)")
        return 0
    if not _STAMP.is_file() or not _CLOSURE.is_file():
        print("FAIL: missing stamp-body-dependencies / assert-dependency-closure", file=sys.stderr)
        return 1
    for body in bodies:
        rel = str(body.relative_to(modern))
        stamp = subprocess.run(
            [sys.executable, str(_STAMP), str(modern), "--body", rel, "--write"],
            cwd=str(modern),
            capture_output=True,
            text=True,
        )
        blob = (stamp.stdout or "") + (stamp.stderr or "")
        if stamp.returncode != 0:
            print(blob, file=sys.stderr)
            print(f"FAIL: M2 type-closure stamp rc={stamp.returncode} {rel}", file=sys.stderr)
            return 1
        clos = subprocess.run(
            [sys.executable, str(_CLOSURE), str(modern), "--body", rel],
            cwd=str(modern),
            capture_output=True,
            text=True,
        )
        cblob = (clos.stdout or "") + (clos.stderr or "")
        if clos.returncode != 0:
            print(cblob, file=sys.stderr)
            print(f"FAIL: M2 type-closure assert rc={clos.returncode} {rel}", file=sys.stderr)
            return 1
    print(f"OK: type-closure stamp+assert n={len(bodies)}")
    return 0


def _run_topo(modern: Path) -> int:
    """Existing M3 topological gate as M2 exit (family-fix wiring)."""
    if not _TOPO.is_file():
        print(f"FAIL: missing {_TOPO}", file=sys.stderr)
        return 1
    part = modern / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        print("FAIL: scratch missing partition.json for topological order", file=sys.stderr)
        return 1
    proc = subprocess.run(
        [sys.executable, str(_TOPO), str(modern)],
        cwd=str(modern),
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    if proc.returncode != 0:
        print(
            f"FAIL: partition topological order rc={proc.returncode}",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_relocate(modern: Path) -> int:
    """Existing MULTI_OWNER / facade-relocate gate as M2 exit (LV-5 wiring)."""
    if not _RELOCATE.is_file():
        print(f"FAIL: missing {_RELOCATE}", file=sys.stderr)
        return 1
    part = modern / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        print("FAIL: scratch missing partition.json for MULTI_OWNER", file=sys.stderr)
        return 1
    proc = subprocess.run(
        [sys.executable, str(_RELOCATE), str(modern)],
        cwd=str(modern),
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    return 0 if proc.returncode == 0 else 1


def _run_type_inventory_coverage(modern: Path) -> int:
    """Plan coverage of type-inventory dest twins (skip if the file is absent)."""
    if str(_STAMP.parent) not in sys.path:
        sys.path.insert(0, str(_STAMP.parent))
    from specimen_agnostic import dest_path_as_written, type_inventory_uncovered

    part = modern / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        print("FAIL: scratch missing evidence/briefs/partition.json", file=sys.stderr)
        return 1
    try:
        data = json.loads(part.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: scratch partition.json: {exc}", file=sys.stderr)
        return 1
    owned: set[str] = set()
    for story in data.get("stories") or []:
        if not isinstance(story, dict):
            continue
        for key in ("files_writable", "files", "files_in_scope"):
            raw = story.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                if isinstance(item, str) and item.strip():
                    owned.add(dest_path_as_written(item))
    missing = type_inventory_uncovered(modern, owned)
    if missing is None:
        print("OK: type-inventory coverage skipped (no evidence/type-inventory.json)")
        return 0
    if missing:
        print(
            f"FAIL: types_uncovered={len(missing)} " + " ".join(missing[:12]),
            file=sys.stderr,
        )
        return 1
    print("OK: type-inventory dest twins covered")
    return 0


def _run_generator_uptake(modern: Path, tasks: Path) -> int:
    if not _UPTAKE.is_file():
        print("FAIL: missing assert-tasks-generator-uptake.py", file=sys.stderr)
        return 1
    proc = subprocess.run(
        [
            sys.executable,
            str(_UPTAKE),
            str(modern),
            "--tasks",
            str(tasks),
        ],
        cwd=str(modern),
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    if proc.returncode != 0:
        print("FAIL: M2-UPTAKE generated types without plugin token in tasks.md", file=sys.stderr)
        return 1
    return 0


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
        if not _REVERSE.is_file():
            print(f"FAIL: missing {_REVERSE}", file=sys.stderr)
            return 1
        rev = subprocess.run(
            [sys.executable, str(_REVERSE), str(modern)],
            cwd=str(modern),
            capture_output=True,
            text=True,
        )
        if rev.returncode != 0:
            print((rev.stdout or "") + (rev.stderr or ""), file=sys.stderr)
            print(
                "FAIL: invented plan routes vs inventory (067420Z reverse-diff)",
                file=sys.stderr,
            )
            return 1
        tic = _run_type_inventory_coverage(modern)
        if tic != 0:
            return tic
        uptake = _run_generator_uptake(modern, tasks)
        if uptake != 0:
            return uptake
        tc = _run_type_closure(modern)
        if tc != 0:
            return tc
        topo = _run_topo(modern)
        if topo != 0:
            return topo
        reloc = _run_relocate(modern)
        if reloc != 0:
            return reloc
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
