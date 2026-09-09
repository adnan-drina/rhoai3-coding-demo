"""Shared helpers for the fix-until-green loop (not a CLI)."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_ACCEPTED, LOOP_CARDS, LOOP_DEFERRED, LOOP_ISSUED, LOOP_STATE, LOOP_STEPS, MTA_RESCAN_FINDINGS, VERIFY_DIAGNOSTICS, VERIFY_RUN, VERIFY_SUREFIRE  # noqa: E402

PRODUCT_EXEMPT = ("evidence/", "verification/", ".hermes/", ".derived/", "target/", ".git/")
REPORTS = (VERIFY_DIAGNOSTICS, VERIFY_SUREFIRE, VERIFY_RUN, MTA_RESCAN_FINDINGS)


def _json_doc(root: Path, rel: Path, default: dict[str, Any]) -> dict[str, Any]:
    p = root / rel
    return load_json(p) if p.is_file() else default


def load_steps(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_STEPS, {"schema": "rhoai3.loop-steps/v1", "steps": [], "attempts": {}, "rejected": []})


def save_steps(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_STEPS, doc)


def load_deferred(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_DEFERRED, {"schema": "rhoai3.loop-deferred/v1", "clusters": [], "reasons": {}})


def save_deferred(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_DEFERRED, doc)


def load_state(root: Path) -> dict[str, Any] | None:
    p = root / LOOP_STATE
    return load_json(p) if p.is_file() else None


def save_state(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_STATE, doc)


def load_issued(root: Path) -> dict[str, Any] | None:
    p = root / LOOP_ISSUED
    return load_json(p) if p.is_file() else None


def load_cards(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_CARDS, {"schema": "rhoai3.loop-cards/v1", "control": {}})


def save_cards(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_CARDS, doc)


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def is_product_path(path: str) -> bool:
    p = path.replace("\\", "/")
    return not (p.startswith(PRODUCT_EXEMPT) or "/__pycache__/" in "/" + p or p.endswith(".pyc"))


def product_paths_changed(root: Path) -> list[str]:
    """Every product path that differs from HEAD: staged, unstaged, untracked."""
    proc = git(root, "status", "--porcelain", "--untracked-files=all")
    out: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if is_product_path(path):
            out.append(path)
    return sorted(set(out))


def candidate_sha256(root: Path) -> str:
    """Identity of the product tree as it is on disk (working tree, not the index)."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not is_product_path(rel):
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def revert_paths(root: Path, paths: list[str]) -> None:
    """Restore HEAD for tracked paths in BOTH index and working tree; delete untracked."""
    tracked = [p for p in paths if git(root, "ls-files", "--error-unmatch", "--", p).returncode == 0]
    untracked = [p for p in paths if p not in tracked]
    if tracked:
        git(root, "reset", "-q", "HEAD", "--", *tracked)
        git(root, "checkout", "--", *tracked)
    for p in untracked:
        target = root / p
        if target.is_file():
            target.unlink()
    git(root, "reset", "-q")


def snapshot_reports(root: Path) -> None:
    """Keep the accepted state's tool reports so a rejected candidate's reports never survive it."""
    dest = root / LOOP_ACCEPTED
    dest.mkdir(parents=True, exist_ok=True)
    for rel in REPORTS:
        src = root / rel
        if src.is_file():
            shutil.copy2(src, dest / rel.name)


def restore_reports(root: Path) -> None:
    dest = root / LOOP_ACCEPTED
    for rel in REPORTS:
        src = dest / rel.name
        target = root / rel
        if src.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        elif target.is_file():
            target.unlink()
