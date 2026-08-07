#!/usr/bin/env python3
"""Derive Oracle present|absent from the filesystem (Wave4 §2.1 / O-ORACLEDERIVE).

Facts are derived; decisions are declared. Oracle is a fact:
  - does a legacy test exist for this Target?
  - does the Target exist in the destination?

Never silently default undeclared Oracle to present (that hid the
infer+absent wedge — O-INFERABSENT).

Used by plan-lint.py, task-packet.py, and supervisor.sh task_oracle.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_JAVA_PATH = re.compile(r"src/(?:main|test)/java/[A-Za-z0-9_./-]+\.java")
_OOS_LINE = re.compile(
    r"(?i)^\s*(?:\*\*)?(?:out\s*of\s*scope|absorbs|deferred|deferral)(?:\*\*)?\s*:"
)
_PROCEED_RE = re.compile(
    r"(?im)^\s*(?:\*\*)?Proceed(?:\*\*)?\s*:?\s*O-NULLACTION\b"
    r"|^\s*O-INFERABSENT-PROCEED\b"
    r"|\bProceed\s*:\s*O-NULLACTION\b"
)
_HARNESS_DIR = Path(__file__).resolve().parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))
from task_contract import SHAPE_LINE_ATOM_ORACLE  # type: ignore  # noqa: E402

_SHAPE_RE = re.compile(
    rf"(?im)^\*\*Shape\*\*\s*:?\s*({SHAPE_LINE_ATOM_ORACLE})\b"
    rf"|^\*\*Shape\s*:\s*({SHAPE_LINE_ATOM_ORACLE})\*\*"
    rf"|^Shape\s*:\s*({SHAPE_LINE_ATOM_ORACLE})\b"
)


def read_packages(root: Path) -> tuple[str, str]:
    """legacyPackage, targetPackage from migration.yaml (defaults empty)."""
    my = root / "migration.yaml"
    legacy = target = ""
    if my.is_file():
        text = my.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?m)^\s*legacyPackage:\s*(\S+)", text)
        if m:
            legacy = m.group(1).strip()
        m = re.search(r"(?m)^\s*targetPackage:\s*(\S+)", text)
        if m:
            target = m.group(1).strip()
    return legacy, target


def pkg_path_variants(rel: str, legacy_pkg: str, target_pkg: str) -> list[str]:
    rel = (rel or "").lstrip("./")
    out = [rel]
    if not legacy_pkg or not target_pkg or legacy_pkg == target_pkg:
        return out
    leg = legacy_pkg.replace(".", "/")
    tgt = target_pkg.replace(".", "/")
    for kind in ("main", "test"):
        lp = f"src/{kind}/java/{leg}/"
        tp = f"src/{kind}/java/{tgt}/"
        if rel.startswith(tp):
            out.append(lp + rel[len(tp) :])
        if rel.startswith(lp):
            out.append(tp + rel[len(lp) :])
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def target_java_paths(body: str) -> list[str]:
    """Work-Target .java destinations (skips Out-of-scope / Absorbs-only)."""
    paths: list[str] = []
    seen: set[str] = set()
    in_target = False
    for line in (body or "").splitlines():
        if _OOS_LINE.search(line):
            in_target = False
            continue
        hm = re.match(r"^\s*\*?\*?([A-Za-z][A-Za-z0-9 ]*?)\*?\*?\s*:", line)
        if hm:
            field = hm.group(1).strip().lower()
            if field.startswith("target") or field == "design":
                in_target = True
            elif field in (
                "absorbs",
                "owns",
                "class",
                "shape",
                "goal",
                "findings",
                "acceptance",
                "oracle",
                "port",
                "proceed",
                "out of scope",
            ):
                in_target = False
                if field in ("absorbs", "owns"):
                    continue
        if not in_target and "→" not in line and "->" not in line:
            continue
        if not in_target and not re.search(r"(?i)target", line):
            if not re.search(r"(?i)\btarget\b", line):
                continue
        rhs = [
            m.group(1).strip().strip("`").lstrip("./")
            for m in re.finditer(
                r"(?:→|->)\s*`?(src/(?:main|test)/java/[A-Za-z0-9_./-]+\.java)",
                line,
            )
        ]
        cands = rhs if rhs else [m.group(0) for m in _JAVA_PATH.finditer(line)]
        for p in cands:
            p = (p or "").strip().strip("`").lstrip("./")
            if not p or not p.endswith(".java") or p in seen:
                continue
            if Path(p).name == "package-info.java":
                continue
            seen.add(p)
            paths.append(p)
    return paths


def _char_oracle_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    for cand in (
        root / "migration" / "staging",
        Path("/projects/legacy"),
        root / "legacy",
        root.parent / "legacy",
    ):
        try:
            if cand.is_dir() and cand not in roots:
                roots.append(cand)
        except OSError:
            continue
    return roots


def _legacy_test_exists(stem: str, roots: list[Path]) -> bool:
    """True if a *{Stem}*Test.java (or *Tests.java) exists under a root."""
    if not stem:
        return False
    patterns = (
        f"**/{stem}Test.java",
        f"**/{stem}Tests.java",
        f"**/{stem}*Test.java",
    )
    for base in roots:
        for pat in patterns:
            try:
                for hit in base.glob(pat):
                    if hit.is_file() and "src/test" in str(hit).replace("\\", "/"):
                        return True
            except OSError:
                continue
    return False


def _dest_exists(
    rel: str, root: Path, legacy_pkg: str, target_pkg: str
) -> bool:
    for v in pkg_path_variants(rel, legacy_pkg, target_pkg):
        try:
            if (root / v).is_file():
                return True
        except OSError:
            continue
    return False


def derive_oracle(
    body: str,
    *,
    root: Path | None = None,
    legacy_pkg: str = "",
    target_pkg: str = "",
) -> str:
    """Compute Oracle present|absent from the filesystem.

    present — at least one Target .java has a legacy test OR exists in dest
    absent  — every Target .java lacks both (or no Target .java found)

    No silent default to present when the Oracle field is omitted from tasks.md.
    Non-.java-only tasks (properties/pom) with zero Target .java paths →
    absent (fail-closed; callers skip O-INFERABSENT when Shape=create/verify).
    """
    root = root or Path.cwd()
    if not legacy_pkg and not target_pkg:
        legacy_pkg, target_pkg = read_packages(root)
    targets = target_java_paths(body)
    if not targets:
        return "absent"
    roots = _char_oracle_roots(root)
    for rel in targets:
        stem = Path(rel).stem
        if _legacy_test_exists(stem, roots):
            return "present"
        if _dest_exists(rel, root, legacy_pkg, target_pkg):
            return "present"
    return "absent"


def task_shape(body: str) -> str:
    sm = _SHAPE_RE.search(body or "")
    if not sm:
        return ""
    return next(g for g in sm.groups() if g).lower()


def has_nullaction_proceed(body: str) -> bool:
    """One-line non-punitive proceed override (O-NULLACTION-shaped / fixtures)."""
    return bool(_PROCEED_RE.search(body or ""))


def inferabsent_blocks(
    *,
    cls: str,
    oracle: str,
    shape: str,
    body: str,
) -> bool:
    """True when infer + derived-absent must fail PLAN OK / skip worker.

    Proceed paths (documented remedies — not silent defaults):
      - Shape=create  (reshape to create)
      - Shape=verify  (explicit deferral)
      - Proceed: O-NULLACTION  (one-line fixture / honest stop marker)
    """
    if (cls or "").lower() != "infer":
        return False
    if (oracle or "").lower() != "absent":
        return False
    sh = (shape or "").lower() or task_shape(body)
    if sh in ("create", "verify"):
        return False
    if has_nullaction_proceed(body):
        return False
    return True


def declared_oracle(body: str) -> str:
    """Optional declared Oracle field (ignored for derivation; kept for tips)."""
    m = re.search(
        r"^\*\*Oracle\s*:\s*(absent|present)\*\*"
        r"|^\*\*Oracle\*\*\s*:?\s*(absent|present)"
        r"|^Oracle\s*:\s*(absent|present)",
        body or "",
        re.M | re.I,
    )
    if not m:
        return ""
    return next(g for g in m.groups() if g).lower()
