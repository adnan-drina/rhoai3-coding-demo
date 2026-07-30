#!/usr/bin/env python3
"""V6 P2.4 already-complete probe (strict).

Exit 0 and print `REASON` when the supervisor may skip opencode.
Exit 1 when the task must still run.

V6 cart evidence: the previous bash heuristic treated the first Capitalized
word in the task body as a class name (`Convert`, `Port`) and, because those
.java files do not exist, auto-committed "ALREADY COMPLETE — Convert already
absent" for real CDI conversion work. That is forbidden.

Allowed skip paths (only):
1. preserve: token that is the *subject* of the task (title or Goal /
   Acceptance / Target design — O-AC2) is already present in the tree
   (and in k8s/ when STORY_DEPLOY=true for ENV_STYLE tokens). Waiver
   prose must not trigger this path. O-AC3: blocked when Target design
   names a destination .java that is still missing (class conversion).
2. Explicit removal task (title or body) naming a concrete src/.../*.java
   path whose basename is absent under src/main/java and src/test/java.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(os.environ.get("ALREADY_COMPLETE_ROOT", ".")).resolve()


def task_body(tasks_file: Path, tid: str) -> tuple[str, str]:
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        # O-AC2: last-task bodies used to swallow story-level waiver appendices
        # (e.g. "CATALOG_ENDPOINT … waived"), falsely triggering preserve skip.
        body = re.split(
            r"^##\s+(Story Scope Waivers|Waivers|Notes|Appendix)\b",
            body,
            maxsplit=1,
            flags=re.M | re.I,
        )[0]
        return title, body
    return "", ""


def preserve_is_task_subject(title: str, body: str, item: str) -> bool:
    """O-AC2: preserve fast-path only when the task is ABOUT that item.

    Mentions in waiver prose, or incidental body text outside Goal /
    Acceptance / Target design, must not skip real work.
    """
    if item in title:
        return True
    focus_parts = [title]
    for m in re.finditer(
        r"(?is)\*\*(?:Goal|Acceptance|Target design)\*\*.*?(?=\n\*\*|\n#{2,6}\s|\Z)",
        body,
    ):
        focus_parts.append(m.group(0))
    focus = "\n".join(focus_parts)
    if item not in focus:
        return False
    # Explicit waiver of this item is not a preserve task.
    if re.search(
        rf"(?is)\bwaiv\w*.{{0,120}}{re.escape(item)}|{re.escape(item)}.{{0,120}}\bwaiv\w*",
        focus,
    ):
        return False
    return True


def preserve_items(myaml: str) -> list[str]:
    m = re.search(r"^preserve:(.*?)(^\S|\Z)", myaml, re.M | re.S)
    if not m:
        return []
    return re.findall(r"^\s*-\s*([A-Za-z0-9_./:-]+)", m.group(1), re.M)


def tree_has(token: str) -> bool:
    for rel in ("src/main", "pom.xml", "k8s"):
        p = ROOT / rel
        if p.is_file():
            try:
                if token in p.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                pass
        elif p.is_dir():
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    if token in f.read_text(encoding="utf-8", errors="replace"):
                        return True
                except OSError:
                    continue
    return False


def k8s_has(token: str) -> bool:
    k8s = ROOT / "k8s"
    if not k8s.is_dir():
        return False
    for f in k8s.rglob("*"):
        if not f.is_file():
            continue
        try:
            if token in f.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _target_java_paths(body: str) -> list[str]:
    """Destination .java paths cited on Target/→ lines (not staging/legacy)."""
    paths: list[str] = []
    for line in body.splitlines():
        if not re.search(r"(?:Target|→|->)", line, re.I):
            continue
        paths.extend(
            re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./]+\.java", line)
        )
    return [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]


def missing_target_java(body: str) -> bool:
    """O-AC3: True when a Target destination .java is still absent under src/.

    Preserve tokens (e.g. CATALOG_ENDPOINT) often appear in Goal/Target of
    class-conversion tasks; that must not skip creating the missing class
    (V9 S03 T-006 CatalogService false already-complete).
    """
    src_root = ROOT / "src"
    for path in _target_java_paths(body):
        if (ROOT / path).is_file():
            continue
        leaf = Path(path).name
        if src_root.is_dir() and list(src_root.rglob(leaf)):
            continue
        return True
    return False


def java_basenames_absent(body: str) -> Optional[str]:
    """Return basename if an explicit java path is named and absent in tree."""
    # Prefer TARGET-side paths (after → / -> / Target).
    targetish = _target_java_paths(body)
    paths = targetish or re.findall(
        r"src/(?:main|test)/java/[A-Za-z0-9_./]+\.java", body
    )
    # Ignore staging/legacy sources — absence there is meaningless.
    paths = [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]
    if not paths:
        return None
    for path in paths:
        leaf = Path(path).name
        if list((ROOT / "src").rglob(leaf) if (ROOT / "src").is_dir() else []):
            return None  # still present somewhere under src/
    return Path(paths[0]).stem


def is_removal_task(title: str, body: str) -> bool:
    if re.search(
        r"^\s*(Remove|Delete|Drop|Eliminate)\b", title, re.I
    ) or re.search(r"\b(already absent|must not exist)\b", body, re.I):
        return True
    # Body-led removal of a named class/file — require remove/delete near a .java path.
    for m in re.finditer(
        r"\b(remove|delete|drop|eliminate)\b(.{0,80}?src/(?:main|test)/java/[A-Za-z0-9_./]+\.java)",
        body,
        re.I | re.S,
    ):
        return True
    return False


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: already-complete.py <tasks.md> <T-xxx>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    deploy = os.environ.get("STORY_DEPLOY", "false").lower() == "true"
    title, body = task_body(tasks, tid)
    if not body:
        return 1

    myaml = ""
    myp = ROOT / "migration.yaml"
    if myp.is_file():
        myaml = myp.read_text(encoding="utf-8", errors="replace")

    # O-AC3: missing destination .java blocks preserve fast-path.
    if not missing_target_java(body):
        for item in preserve_items(myaml):
            if not preserve_is_task_subject(title, body, item):
                continue
            if re.fullmatch(r"[A-Z][A-Z0-9_]+", item) and deploy:
                if not k8s_has(item):
                    continue
            elif not tree_has(item):
                continue
            print(f"present:{item}")
            return 0

    if is_removal_task(title, body):
        leaf = java_basenames_absent(body)
        if leaf:
            # Refuse verb-looking "leaves" even if somehow extracted.
            if leaf.lower() in {
                "convert",
                "port",
                "ensure",
                "preserve",
                "create",
                "update",
                "implement",
                "migrate",
                "replace",
                "verify",
            }:
                return 1
            print(f"absent:{leaf}")
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
