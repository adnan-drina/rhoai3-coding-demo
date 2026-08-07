#!/usr/bin/env python3
"""O-WIREUP — redesigned components must stay attached (reachability, not shape).

Wave 3 S07: CallMonitoringAspect preserved method names (O-REDESIGNSIG GREEN)
but shipped with 0 interceptor bindings, 0 metrics API, and 0 consumers.
OpenApiConfig shipped as @ApplicationScoped with an empty body.

When staging/legacy carried a framework attachment (@Around/@Aspect/
@Scheduled/@EventListener/@ManagedResource), the destination class must
carry a destination-side attachment OR be referenced by ≥1 other source
file. Empty singleton beans (no members) also fail.

Usage: wireup-check.py [staging-root] [dest-src-root]
Exit 0 = clean; exit 1 = violation(s) on stdout.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

LEGACY_ATTACH = re.compile(
    r"@(?:Around|Aspect|Scheduled|EventListener|ManagedResource)\b"
)
DEST_ATTACH = re.compile(
    r"@(?:Interceptor|InterceptorBinding|AroundInvoke|Observes|Scheduled|"
    r"Incoming|Outgoing|ActivateRequestContext)\b"
)
SINGLETON = re.compile(r"@(?:ApplicationScoped|Singleton)\b")
CLASS_RE = re.compile(r"\b(?:class|interface)\s+(\w+)")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _class_body(text: str, cls: str) -> str:
    m = re.search(
        rf"\b(?:class|interface)\s+{re.escape(cls)}\b[^{{]*\{{",
        text,
    )
    if not m:
        return ""
    depth, i = 0, m.end() - 1
    start = m.end()
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return text[start:]


def _has_members(body: str) -> bool:
    """True when the class body declares a field or method (not only braces).

    Quarkus idiom: package-private `@ConfigProperty` / `@Inject` fields have
    no access modifier — requiring private|protected|public false-REDs real
    config beans (W3-150 / OptionalAuthorizationController-shaped).
    """
    bare = _strip_comments(body)
    if re.search(r"\b\w+\s*\([^;]*\)\s*\{", bare):
        return True
    # Annotated field (any visibility, including package-private).
    if re.search(
        r"^\s*@(?:ConfigProperty|Inject|RestClient|Claim|Channel)\b",
        bare,
        re.M,
    ):
        return True
    # Field declaration: optional modifiers + type + name;
    if re.search(
        r"^\s*(?:(?:private|protected|public|static|final|volatile)\s+)*"
        r"(?:[\w.<>,\[\]?]+\s+)+\w+\s*(?:=[^;]*)?;",
        bare,
        re.M,
    ):
        return True
    return False


def _referenced_elsewhere(cls: str, dest_root: Path, self_path: Path) -> bool:
    for p in dest_root.rglob("*.java"):
        if p.resolve() == self_path.resolve():
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf"\b{re.escape(cls)}\b", t):
            return True
    return False


def _find_dest(cls: str, dest_root: Path) -> Optional[Path]:
    hits = list(dest_root.rglob(f"{cls}.java"))
    return hits[0] if hits else None


def main() -> int:
    staging = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("migration/staging")
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("src/main/java")
    if not dest.is_dir():
        print("wireup-check skipped — missing dest tree")
        return 0

    problems: list[str] = []

    # Pass 1: staging attachment → dest must attach or be consumed.
    if staging.is_dir():
        for sp in staging.rglob("*.java"):
            try:
                st = sp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not LEGACY_ATTACH.search(st):
                continue
            cm = CLASS_RE.search(st)
            if not cm:
                continue
            cls = cm.group(1)
            dp = _find_dest(cls, dest)
            if dp is None:
                continue  # not harvested yet — redesign-sig / already-complete own that
            try:
                dt = dp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if DEST_ATTACH.search(dt):
                continue
            if _referenced_elsewhere(cls, dest, dp):
                continue
            problems.append(
                f"{dp}: O-WIREUP — staging had framework attachment "
                f"(@Around/@Aspect/…) but dest has no CDI attachment and "
                f"no consumer references '{cls}'"
            )

    # Pass 2: empty singleton beans under dest (ceremonial @ApplicationScoped).
    for dp in dest.rglob("*.java"):
        try:
            dt = dp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not SINGLETON.search(dt):
            continue
        cm = CLASS_RE.search(dt)
        if not cm:
            continue
        cls = cm.group(1)
        body = _class_body(dt, cls)
        if body and not _has_members(body):
            problems.append(
                f"{dp}: O-WIREUP — @{SINGLETON.search(dt).group(0)[1:]} '{cls}' "
                f"has no fields/methods (ceremonial empty bean)"
            )

    if problems:
        for p in problems:
            print(p)
        return 1
    print("wireup-check GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
