#!/usr/bin/env python3
"""SR-8 — every path has a declared producer; unattributed paths fail.

A deny-list catches the failure you already had. This lint inverts that:
path-producers.json names who may create a prefix. Anything else is
UNATTRIBUTED_PATH. Retired prefixes have no producer — presence is a
finding, not a gitignore hole (SR-8a: do not gitignore migration/).

Modes:
  golden  (no pom.xml/src) — also refuse golden_absent prefixes (run-state)
  seat    (destination workspace) — those prefixes may exist if declared

Usage:
  python3 check-sr8-path-producers.py --root .
  python3 check-sr8-path-producers.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "rhoai3.path-producers/v1"
TABLE_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "validate-contracts"
    / "references"
    / "path-producers.json"
)
SKIP = frozenset({".DS_Store", ".git"})
DESTINATION_MARKERS = ("pom.xml", "src")
SELF_NAME = "check-sr8-path-producers.py"
SKIP_PARTS = frozenset({"__pycache__", ".git", "tmp"})
# Default OUT_DIR/MTA_OUT_DIR assigned under a retired workspace-root prefix.
WRITE_DEFAULT = re.compile(
    r"(?:MTA_OUT_DIR|OUT_DIR)\s*=\s*\"\$\{[^}]*:-\$\{(?:ROOT|root)\}/"
    r"(migration)(?:/|\")"
)
MKDIR_RETIRED = re.compile(
    r"mkdir(?:\s+-p)?\s+\"\$\{(?:ROOT|root|PRODUCT_ROOT)\}/migration/"
)
MTA_DEFAULT = re.compile(
    r"MTA_OUT_DIR:-\$\{(?:ROOT|root)\}/([^\"}]+)"
)
COMMENT_SH = re.compile(r"^\s*#")
COMMENT_PY = re.compile(r"^\s*#")


def load_table(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("table must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    producers = data.get("producers")
    retired = data.get("retired")
    if not isinstance(producers, list) or not producers:
        raise ValueError("producers must be a non-empty list")
    if not isinstance(retired, list):
        raise ValueError("retired must be a list")
    return data


def norm_prefix(raw: str) -> str:
    p = str(raw).strip().replace("\\", "/").rstrip("/")
    if not p or p.startswith("/") or ".." in p.split("/"):
        raise ValueError(f"illegal prefix {raw!r}")
    return p


def prefixes_of(entries: list, key: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for ent in entries:
        if not isinstance(ent, dict):
            raise ValueError(f"{key} entry must be an object")
        for req in ("id", "prefixes"):
            if not ent.get(req):
                raise ValueError(f"{key} entry missing {req}")
        for p in ent["prefixes"]:
            out.append((norm_prefix(p), ent))
    return out


def matches(rel: str, prefix: str) -> bool:
    return rel == prefix or rel.startswith(prefix + "/")


def longest(rel: str, items: list[tuple[str, dict]]) -> tuple[str, dict] | None:
    hits = [(p, e) for p, e in items if matches(rel, p)]
    if not hits:
        return None
    hits.sort(key=lambda x: len(x[0]), reverse=True)
    return hits[0]


def detect_mode(root: Path, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    if any((root / m).exists() for m in DESTINATION_MARKERS):
        return "seat"
    return "golden"


def root_entries(root: Path) -> list[str]:
    names: list[str] = []
    for p in root.iterdir():
        if p.name in SKIP:
            continue
        names.append(p.name)
    return sorted(names)


def line_comment(path: Path, line: str) -> bool:
    if path.suffix == ".py":
        return bool(COMMENT_PY.match(line))
    return bool(COMMENT_SH.match(line))


def scan_writers(root: Path, retired_prefixes: set[str]) -> list[str]:
    errs: list[str] = []
    hermes = root / ".hermes"
    if not hermes.is_dir():
        return errs
    for path in hermes.rglob("*"):
        if not path.is_file() or path.suffix not in {".sh", ".py"}:
            continue
        if path.name == SELF_NAME:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if any(part in SKIP_PARTS for part in Path(rel).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if line_comment(path, line):
                continue
            if WRITE_DEFAULT.search(line) or MKDIR_RETIRED.search(line):
                errs.append(
                    f"UNATTRIBUTED_PATH:{rel}:{i}: writer default under "
                    f"retired prefix migration/ (no declared producer)"
                )
            m = MTA_DEFAULT.search(line)
            if m:
                dest = norm_prefix(m.group(1))
                if any(matches(dest, r) for r in retired_prefixes):
                    errs.append(
                        f"UNATTRIBUTED_PATH:{rel}:{i}: MTA_OUT_DIR default "
                        f"{dest} is retired (no declared producer)"
                    )
    return errs


def present(root: Path, prefix: str) -> bool:
    return (root / prefix).exists()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="SR-8: declared producer per path (not a deny-list).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=attributed, 1=unattributed/retired, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold or seat root")
    ap.add_argument("--table", default="", help="override path-producers.json")
    ap.add_argument(
        "--mode",
        choices=("auto", "golden", "seat"),
        default="auto",
        help="golden refuses golden_absent prefixes; seat allows them",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: --root must be a directory. Received: {args.root!r}", file=sys.stderr)
        return 2
    table_path = Path(args.table) if args.table else root / TABLE_REL
    if not table_path.is_file():
        print(f"FAIL: missing producer table {table_path}", file=sys.stderr)
        return 1
    try:
        data = load_table(table_path)
        producers = prefixes_of(data["producers"], "producers")
        retired = prefixes_of(data["retired"], "retired")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: producer table: {exc}", file=sys.stderr)
        return 1

    retired_set = {p for p, _ in retired}
    producer_set = {p for p, _ in producers}
    overlap = sorted(retired_set & producer_set)
    if overlap:
        print(
            f"FAIL: producer table lists retired prefixes as producers: {overlap}",
            file=sys.stderr,
        )
        return 1

    mode = detect_mode(root, args.mode)
    errs: list[str] = []

    for name in root_entries(root):
        rel = name.replace("\\", "/")
        rhit = longest(rel, retired)
        if rhit:
            _pfx, ent = rhit
            errs.append(
                f"UNATTRIBUTED_PATH:{rel} (retired {ent.get('retired_by', '?')}; "
                f"no declared producer)"
            )
            continue
        phit = longest(rel, producers)
        if phit is None:
            errs.append(f"UNATTRIBUTED_PATH:{rel} (no declared producer)")

    for pfx, ent in retired:
        if pfx in {n.replace("\\", "/") for n in root_entries(root)}:
            continue
        if present(root, pfx):
            errs.append(
                f"UNATTRIBUTED_PATH:{pfx} (retired {ent.get('retired_by', '?')}; "
                f"no declared producer)"
            )

    if mode == "golden":
        for pfx, ent in producers:
            if ent.get("golden_absent") and present(root, pfx):
                errs.append(
                    f"UNATTRIBUTED_PATH:{pfx} (producer {ent.get('id')} is "
                    f"run-state; must be absent from golden)"
                )

    errs.extend(scan_writers(root, retired_set))

    mta_script = (
        root
        / ".hermes"
        / "skills"
        / "analysis"
        / "scan-with-mta"
        / "scripts"
        / "mta-analyze-legacy.sh"
    )
    if mta_script.is_file():
        text = mta_script.read_text(encoding="utf-8", errors="replace")
        found = None
        for line in text.splitlines():
            if line_comment(mta_script, line):
                continue
            m = MTA_DEFAULT.search(line)
            if m:
                found = norm_prefix(m.group(1))
                break
        if not found:
            errs.append(
                "UNATTRIBUTED_PATH:mta-analyze-legacy.sh: MTA_OUT_DIR default "
                "missing (SR-8a)"
            )
        else:
            if longest(found, retired):
                errs.append(
                    f"UNATTRIBUTED_PATH:{found} (MTA_OUT_DIR default is retired; "
                    f"no declared producer)"
                )
            elif longest(found, producers) is None:
                errs.append(
                    f"UNATTRIBUTED_PATH:{found} (MTA_OUT_DIR default has no "
                    f"declared producer)"
                )

    # Do not gitignore the retired alias — that greenwashes resurrection.
    gi = root / ".gitignore"
    if gi.is_file():
        for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("#") or not s:
                continue
            if s.rstrip("/") == "migration" or s.startswith("migration/"):
                errs.append(
                    "UNATTRIBUTED_PATH:.gitignore: gitignore of migration/ "
                    "greenwashes SR-8a (fix the writer; do not ignore the path)"
                )

    for e in errs:
        print(e, file=sys.stderr)
    if errs:
        return 1
    print(
        f"OK: SR-8 path producers ({mode}; {len(producer_set)} prefixes, "
        f"{len(retired_set)} retired)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
