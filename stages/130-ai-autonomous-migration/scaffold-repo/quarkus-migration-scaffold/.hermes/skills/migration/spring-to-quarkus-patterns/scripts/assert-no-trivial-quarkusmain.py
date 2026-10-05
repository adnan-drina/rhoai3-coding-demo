#!/usr/bin/env python3
"""Refuse dest @QuarkusMain when the legacy Boot main has no custom startup.

W6 (Operator ``190602ZO`` / ``194657ZO``): dest-8 wrote ``@QuarkusMain`` +
``QuarkusApplication`` / ``waitForExit`` for a trivial
``SpringApplication.run`` wrapper. Quarkus already generates main. This
is the check, not more bootstrap prose.

Exit 0: no dest ``@QuarkusMain`` (idle), or legacy main has custom startup.
Exit 1: dest ``@QuarkusMain`` and every legacy Boot main is trivial, or
legacy tree missing while dest has ``@QuarkusMain``.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CUSTOM = re.compile(
    r"CommandLineRunner|ApplicationRunner|ApplicationReadyEvent"
    r"|ApplicationListener|@PostConstruct\b"
)
BOOT = re.compile(r"@SpringBootApplication\b")
QMAIN = re.compile(r"@QuarkusMain\b")
MAIN = re.compile(
    r"public\s+static\s+void\s+main\s*\([^)]*\)\s*\{(.*?)\}",
    re.S,
)
RUN = re.compile(r"SpringApplication\s*\.\s*run\s*\([^;]*\)\s*;")
COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
COMMENT_LINE = re.compile(r"//.*?$", re.M)


def _fail(msg: str) -> int:
    print("REFUSE: TRIVIAL_QUARKUSMAIN " + msg, file=sys.stderr)
    return 1


def strip_comments(text: str) -> str:
    return COMMENT_LINE.sub("", COMMENT_BLOCK.sub("", text))


def java_files(root: Path) -> list[Path]:
    java = root / "src" / "main" / "java"
    if not java.is_dir():
        return []
    return [p for p in java.rglob("*.java") if p.is_file()]


def dest_quarkus_main(root: Path) -> list[Path]:
    hits: list[Path] = []
    for path in java_files(root):
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        if QMAIN.search(text):
            hits.append(path)
    return hits


def main_trivial(text: str) -> bool:
    if CUSTOM.search(text):
        return False
    bodies = MAIN.findall(text)
    if not bodies:
        return True
    for body in bodies:
        rest = RUN.sub("", body)
        rest = re.sub(r"\s+", "", rest)
        if rest not in {"", "{}"}:
            return False
    return True


def legacy_all_trivial(legacy: Path) -> bool:
    saw_boot = False
    for path in java_files(legacy):
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        if not BOOT.search(text):
            continue
        saw_boot = True
        if not main_trivial(text):
            return False
    return True if saw_boot else True


def resolve_legacy(dest: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.is_dir() else None
    env = (os.environ.get("LEGACY_ROOT") or "").strip()
    if env:
        path = Path(env)
        if path.is_dir():
            return path
    for cand in (dest / "legacy", dest.parent / "legacy"):
        if cand.is_dir() and (cand / "src" / "main" / "java").is_dir():
            return cand
    fallback = Path("/projects/legacy")
    if fallback.is_dir():
        return fallback
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".", help="destination product root")
    ap.add_argument("--legacy", default="", help="legacy Boot tree")
    args = ap.parse_args(argv)
    dest = Path(args.root).resolve()
    if not dest.is_dir():
        return 2
    qmains = dest_quarkus_main(dest)
    if not qmains:
        print("OK: assert-no-trivial-quarkusmain (no dest @QuarkusMain; idle)")
        return 0
    legacy = resolve_legacy(dest, args.legacy or None)
    if legacy is None:
        return _fail(
            "dest @QuarkusMain but legacy tree missing (cannot prove custom startup): %s"
            % ", ".join(str(p.relative_to(dest)) for p in qmains)
        )
    if not legacy_all_trivial(legacy):
        print("OK: assert-no-trivial-quarkusmain (legacy has custom startup)")
        return 0
    named = ", ".join(str(p.relative_to(dest)) for p in qmains)
    return _fail(
        "dest @QuarkusMain %s with no custom startup in the legacy main "
        "(Quarkus generates main; do not wrap SpringApplication.run)" % named
    )


if __name__ == "__main__":
    raise SystemExit(main())
