#!/usr/bin/env python3
"""O-OWNSTAGE / O-OWNSTAGEALL — emit stageable Owns/Target paths for a task.

Used by supervisor stage_for_task_commit to allowlist-stage instead of
`git add -A`, so sibling entities stay untracked for their owning tip.

O-OWNSTAGEALL: collect paths from the *whole* Owns/Target/Absorbs section
(multi-line bullets), not only the text after `:` on the header line.
Skips "Verification of:" / Shape=verify check-only cites (O-VERIFYCREATE /
O-ATTRSWEEP — those are not create deliverables).

Exit 0 always when the task is found (even with zero paths — caller falls
back). Exit 1 if the task id is missing from tasks.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_JAVA = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java")
_GITKEEP = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+/\.gitkeep")
_SHARED = re.compile(
    r"(?<![\w./])(?:pom\.xml|"
    r"src/(?:main|test)/resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml)|"
    r"k8s/[A-Za-z0-9_./-]+)"
)
_SECTION_HEAD = re.compile(
    r"(?i)^\s*\*?\*?(Owns|Target\s*design|Target|Design|Absorbs)\*?\*?\s*:?\s*(.*)$"
)
_STOP_HEAD = re.compile(
    r"(?i)^\s*\*?\*?(?:Class|Shape|Oracle|Goal|Findings|Constraints|Acceptance|"
    r"Out of scope|Assumes|Port|Inputs|Actor|ADDITIONAL-WORK)\*?\*?\s*:"
)
_VERIFY_OF = re.compile(r"(?i)\bVerification\s+of\s*:")
try:
    from task_contract import HEADING_TASK_ID_ATOM  # type: ignore
except ImportError:
    HEADING_TASK_ID_ATOM = (
        r"(?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*)"
    )

_OOS = re.compile(
    r"(?i)(?:^\s*\*?\*?Out of scope\*?\*?\s*:)"
    r"|(?:\bdo NOT touch\b)"
    rf"|(?:\bowned by {HEADING_TASK_ID_ATOM})"
)
_STAGING = re.compile(r"(?:^|/)(?:migration/staging|legacy)(?:/|$)")
_ARROW = re.compile(r"(?:→|->)\s*`?(?:src/|pom\.xml|k8s/)")


def _task_body(tasks_file: Path, tid: str) -> str:
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(
            rf"^#{{2,6}}\s+({HEADING_TASK_ID_ATOM})\s*:\s*(.+)$", text, re.M
        )
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        body = re.split(r"^##\s+", body, maxsplit=1, flags=re.M)[0]
        return body
    return ""


def _shape_is_verify(body: str) -> bool:
    m = re.search(r"(?im)^\s*\*?\*?Shape\*?\*?\s*:\s*(\S+)", body)
    if not m:
        return False
    return m.group(1).strip().lower() in {"verify", "absent", "remove"}


def _extract_paths_from_text(text: str, *, skip_verify_of: bool) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        p = p.strip().strip("`").rstrip(",.;")
        if not p or _STAGING.search(p):
            return
        if "/" not in p and p != "pom.xml":
            return
        # O-OWNSTAGEDIR: bare package dirs (…/model/) are not tip deliverables.
        # Emitting them made O-OWNSTAGEALL REFUSE after staging the real .java
        # files (S01-T-002 Role/User preseed → empty stage → MiniMax).
        # Structure work must declare …/.gitkeep (or a suffixed file).
        p_norm = p.rstrip("/")
        if p.endswith("/") or (
            p_norm.startswith("src/")
            and "/java/" in p_norm
            and "." not in Path(p_norm).name
        ):
            if not p_norm.endswith(".gitkeep"):
                return
            p = p_norm if p_norm.endswith(".gitkeep") else p
        if p in seen:
            return
        seen.add(p)
        out.append(p)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or _OOS.search(line):
            continue
        if skip_verify_of and _VERIFY_OF.search(line):
            continue
        for tok in re.split(r"[,;\s]+", line):
            tok = tok.strip().strip("`")
            if tok.startswith("src/") or tok == "pom.xml" or tok.startswith("k8s/"):
                _add(tok)
        for p in _JAVA.findall(line):
            _add(p)
        for p in _GITKEEP.findall(line):
            _add(p)
        for p in _SHARED.findall(line):
            _add(p)
    return out


def stage_paths(body: str) -> list[str]:
    """Declared Owns/Target/Absorbs paths that may land in a T-NNN tip."""
    out: list[str] = []
    seen: set[str] = set()
    verify_shape = _shape_is_verify(body)

    def _extend(paths: list[str]) -> None:
        for p in paths:
            if p not in seen:
                seen.add(p)
                out.append(p)

    lines = body.splitlines()
    i = 0
    while i < len(lines):
        m = _SECTION_HEAD.match(lines[i])
        if not m:
            # Arrow cites on any line still count (legacy → dest).
            if _ARROW.search(lines[i]) and not _OOS.search(lines[i]):
                _extend(
                    _extract_paths_from_text(
                        lines[i], skip_verify_of=True
                    )
                )
            i += 1
            continue
        label = re.sub(r"\s+", " ", m.group(1).strip().lower())
        rest = m.group(2) or ""
        block = [rest] if rest.strip() else []
        i += 1
        while i < len(lines):
            if _SECTION_HEAD.match(lines[i]) or _STOP_HEAD.match(lines[i]):
                break
            if lines[i].strip().startswith("#"):
                break
            block.append(lines[i])
            i += 1
        # Design-alone headers that are really "Target Design" already handled.
        skip_verify = True
        if label == "absorbs" and verify_shape:
            # Absorbs under verify still may name create leftovers — keep.
            skip_verify = True
        _extend(_extract_paths_from_text("\n".join(block), skip_verify_of=skip_verify))

    # Constraints often list MANDATORY destination paths (.gitkeep) outside
    # the Target Design block — still create deliverables for structure/create.
    if not verify_shape:
        for ln in body.splitlines():
            if re.search(r"(?i)MANDATORY|Target destination|package-structure", ln):
                _extend(
                    _extract_paths_from_text(ln, skip_verify_of=True)
                )

    # Shape=verify with only "Verification of:" paths → empty allowlist
    # (caller must not tip-commit prior-task orphans as this task).
    if verify_shape:
        # Drop any path that only appears on Verification-of lines.
        verify_only = set(
            _extract_paths_from_text(
                "\n".join(
                    ln for ln in body.splitlines() if _VERIFY_OF.search(ln)
                ),
                skip_verify_of=False,
            )
        )
        createish = [
            p
            for p in out
            if p not in verify_only
            or p.endswith(".gitkeep")
            or "package-info.java" in p
        ]
        # If everything was verification-of, return empty (O-VERIFYCREATE).
        if not createish and verify_only:
            return []
        if createish:
            return createish
    return out


def _maybe_add_harvest_pom(paths: list[str], root: Path) -> list[str]:
    """O-HARVESTREADY: stage pom.xml when owned Targets imply an ensurer.

    Shared policy in harvest_ready.needs_pom_stage (validation|mapstruct|jpa).
    """
    if "pom.xml" in paths:
        return paths
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from harvest_ready import needs_pom_stage  # type: ignore
    except ImportError:
        return paths
    if needs_pom_stage(root, paths):
        return paths + ["pom.xml"]
    return paths


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: task-stage-paths.py <tasks.md> <T-NNN>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2].strip()
    m = re.match(rf"({HEADING_TASK_ID_ATOM})", tid)
    if m:
        tid = m.group(1)
    if not tasks.is_file():
        print("no-tasks-file", file=sys.stderr)
        return 1
    body = _task_body(tasks, tid)
    if not body:
        print("no-task", file=sys.stderr)
        return 1
    for p in _maybe_add_harvest_pom(stage_paths(body), Path.cwd()):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
