#!/usr/bin/env python3
"""O-PROFPROSEDECOMP / W4-495 — harness-owned §§1–6 prose loop.

Same shape as ADR-32 decide: harness enumerates work → model returns one
judgment → harness writes. Monolithic wchat §§1–6 left skeleton placeholders
after read-only seats (22×read / 0×edit). Per-section calls make a failure
cost one section, and the harness always persists the body.

ADR-37: each section packet carries **projected facts** (checklist, not
recall). F-prose-no-discovery: a seat that read/bash-es the legacy tree is a
packet defect — attempt fails.

Backends:
  dry-run       — deterministic fixture prose (instruments)
  opencode-qwen — OpenCode returns JSON {section, body}; harness writes

Usage:
  profile_prose_loop.py run --root DIR --legacy PATH \\
      [--backend opencode-qwen|dry-run] [--retries N] [--section-timeout SECS]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent

# (number, heading title after "## N. ", compose hint — facts come from ADR-37)
# Titles match profile_sections_log.SECTIONS so outer-loop / heartbeat / OK lines
# stay demo-readable (§N alone means nothing to workshop viewers).
SECTIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Purpose & Domain",
        "Summarize domain from PROJECTED FACTS only (entities/anchors).",
    ),
    (
        2,
        "Components & Relationships",
        "Describe layers/relationships from the projected dependency graph only.",
    ),
    (
        3,
        "Integration Surfaces",
        "Describe HTTP/DB/security/config surfaces from projected facts only.",
    ),
    (
        4,
        "Behavioral Contract Sources",
        "Locate contracts from projected tests + targetContract + carriers only.",
    ),
    (
        5,
        "Modernization Surface",
        "Ground modernization claims in projected findings/recipe facts only.",
    ),
    (
        6,
        "Domain Boundaries",
        "Describe package/SCC boundaries from projected histogram/order only. "
        "§7 roles out of scope.",
    ),
]

_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
_SKELETON_RE = re.compile(r"LLM fills|^\(LLM fills", re.M)
_MIN_BODY_CHARS = 80
# O-PROFPROSECITE / W4-512 B2 — same shape as profile-rubric.CITE. A section
# that the prose loop marks OK must already satisfy the rubric uncited check.
_CITE = re.compile(
    r"(src/(?:main|test)/\S+|/projects/legacy/\S+|"
    r"migration/(?:dependency-order|findings-inventory|mta-findings|"
    r"recipe-log|ruleset-coverage)\.md\S*|"
    r"\b(?:dependency-order|findings-inventory|recipe-log|"
    r"ruleset-coverage)\.md(?::\d[\d,.\-]*)?|"
    r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+-\d+|"
    r"\b[A-Z]\w+Test\b)"
)


def _log(msg: str, *, err: bool = False) -> None:
    print(msg, file=sys.stderr if err else sys.stdout, flush=True)


def _body_has_cite(body: str) -> bool:
    """True when body contains a profile-rubric evidence citation."""
    return bool(body and _CITE.search(body))


def _profile_path(root: Path) -> Path:
    return root / "migration" / "architecture-profile.md"


def _split_sections(text: str) -> list[tuple[int, str, str, int, int]]:
    """Return (num, title, body, start, end) for each ## N. heading span."""
    matches = list(_HEADING_RE.finditer(text))
    out: list[tuple[int, str, str, int, int]] = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end]
        out.append((num, title, body, start, end))
    return out


def _section_body(text: str, num: int) -> Optional[str]:
    for n, _t, body, _s, _e in _split_sections(text):
        if n == num:
            return body
    return None


def _needs_fill(body: Optional[str]) -> bool:
    if body is None:
        return True
    if _SKELETON_RE.search(body):
        return True
    # Strip whitespace / comments-only
    compact = re.sub(r"\s+", " ", body).strip()
    if len(compact) < _MIN_BODY_CHARS:
        return True
    # O-PROFPROSECITE: uncited bodies are not "filled" — rewrite on resume.
    return not _body_has_cite(body)


def _body_ok(body: str) -> bool:
    if not body or not str(body).strip():
        return False
    if _SKELETON_RE.search(body):
        return False
    if len(re.sub(r"\s+", " ", body).strip()) < _MIN_BODY_CHARS:
        return False
    # Refuse if model included a ## heading (would corrupt structure)
    if re.search(r"^##\s+\d+\.", body, re.M):
        return False
    # O-PROFPROSECITE / W4-512 — do not OK a section the rubric will uncited-RED.
    if not _body_has_cite(body):
        return False
    return True


def _replace_section(text: str, num: int, title: str, body: str) -> str:
    body = body.strip() + "\n\n"
    parts = _split_sections(text)
    for n, _t, _b, start, end in parts:
        if n == num:
            heading = f"## {num}. {title}\n\n"
            return text[:start] + heading + body + text[end:]
    # Section missing — append before §7 or at end
    heading = f"## {num}. {title}\n\n{body}"
    m7 = re.search(r"^##\s+7\.\s+", text, re.M)
    if m7:
        return text[: m7.start()] + heading + text[m7.start() :]
    return text.rstrip() + "\n\n" + heading


def _minimal_skeleton_text() -> str:
    parts = ["# Architecture profile\n"]
    for num, title, _hint in SECTIONS:
        parts.append(f"## {num}. {title}\n\n(LLM fills.)\n")
    parts.append(
        "## 7. Class Roles & Target Contract\n\n"
        "(Harness renders from typed decisions — out of prose scope.)\n"
    )
    return "\n".join(parts)


def _ensure_skeleton(root: Path) -> None:
    path = _profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and _HEADING_RE.search(path.read_text(encoding="utf-8")):
        return
    # Prefer ADR-27 emit when model.json exists; else write a minimal §§1–7
    # skeleton so instruments / early PROFILE can exercise the loop alone.
    model = root / "migration" / "model.json"
    if model.is_file():
        sys.path.insert(0, str(HERE))
        from model import emit_profile_skeleton  # type: ignore

        emit_profile_skeleton(root)
        if path.is_file() and _HEADING_RE.search(path.read_text(encoding="utf-8")):
            return
    path.write_text(_minimal_skeleton_text(), encoding="utf-8")


def _sec_label(num: int, title: str) -> str:
    """Demo-facing section id — never emit bare §N without a title."""
    return f"§{num} ({title})"


def _write_progress(*, active: str, ok: int, fail: int) -> None:
    """O-PROFDECIDEHB sibling — section cadence for outer 60s heartbeat."""
    try:
        Path("/tmp/outer-heartbeat-progress.txt").write_text(
            f"prose_ok={ok}/6 fail={fail} active={active}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _dry_run_body(num: int, title: str, hint: str) -> str:
    # Include a CITE-shaped path so O-PROFPROSECITE accepts dry-run bodies.
    return (
        f"Prose dry-run §{num} ({title}). "
        f"{hint} "
        f"Composed from harness-projected facts for this section "
        f"(no legacy-tree discovery). "
        f"Evidence: src/main/java/com/example/DryRunSection{num}.java:1. "
        f"Section authored by harness dry-run backend for instruments."
    )


def _parse_prose_payload(blob: str, expect_num: int) -> Optional[str]:
    # Prefer fenced JSON
    for m in re.finditer(r"\{[^{}]*\"section\"[^{}]*\}", blob, re.S):
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if int(o.get("section") or -1) != expect_num:
            continue
        body = o.get("body")
        if isinstance(body, str) and _body_ok(body):
            return body
    # Broader scan
    try:
        # last JSON object in blob
        start = blob.rfind("{")
        end = blob.rfind("}")
        if start >= 0 and end > start:
            o = json.loads(blob[start : end + 1])
            if int(o.get("section") or -1) == expect_num and isinstance(
                o.get("body"), str
            ):
                body = o["body"]
                if _body_ok(body):
                    return body
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _legacy_discovery_reads(stdout: str, legacy: str) -> list[str]:
    """F-prose-no-discovery — tool reads/bash against the legacy tree."""
    legacy_n = str(Path(legacy).resolve()) if legacy else ""
    hits: list[str] = []
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("type") != "tool_use":
            continue
        part = o.get("part") if isinstance(o.get("part"), dict) else {}
        name = str(part.get("tool") or part.get("name") or "").lower()
        if name not in ("read", "read_file", "bash", "glob", "grep", "list"):
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        inp = part.get("input") or state.get("input") or {}
        if isinstance(inp, str):
            try:
                inp = json.loads(inp)
            except json.JSONDecodeError:
                inp = {"_raw": inp}
        if not isinstance(inp, dict):
            continue
        target = str(
            inp.get("filePath")
            or inp.get("path")
            or inp.get("pattern")
            or inp.get("command")
            or inp.get("_raw")
            or ""
        )
        tnorm = target.replace("\\", "/")
        if not tnorm:
            continue
        # Legacy tree markers (workspace + fixture layouts)
        if (
            "/legacy/" in tnorm
            or tnorm.startswith("legacy/")
            or (legacy_n and legacy_n in tnorm)
            or "/src/main/java/" in tnorm
            or tnorm.startswith("src/main/java/")
            or "/src/main/resources/" in tnorm
            or tnorm.startswith("src/main/resources/")
        ):
            hits.append(f"{name}:{tnorm[:160]}")
    return hits


def _opencode_section(
    root: Path,
    *,
    num: int,
    title: str,
    hint: str,
    worker_model: str,
    section_timeout: int,
    skilldir: Path,
    legacy: str,
) -> str:
    sys.path.insert(0, str(HERE))
    from profile_prose_project import project_section  # type: ignore

    projected = project_section(root, num, legacy=legacy)
    packet = "\n".join(
        [
            "Author ONE architecture-profile section only.",
            f"Section number: {num}",
            f"Section title: {title}",
            "Write path (harness will write; do NOT edit files): "
            "migration/architecture-profile.md",
            "ALL facts for this section are in PROJECTED FACTS below.",
            "Do NOT read/bash/glob the legacy tree or re-open analysis files to "
            "rediscover facts — that is F-prose-no-discovery RED.",
            "O-PROFPROSECITE: body MUST contain ≥1 evidence citation copied "
            "verbatim from the REQUIRED CITE / path lines in PROJECTED FACTS "
            "(full src/main|test/... path, migration/*.md, windup rule id, or "
            "*Test name). Short forms like `model/Foo.java` do NOT count. "
            "Harness refuses uncited bodies (same predicate as profile-rubric).",
            f"Guidance: {hint}",
            "",
            projected,
            "",
            "Reply with ONLY this JSON object (no tools required, no file edits):",
            f'{{"section": {num}, "body": "<markdown paragraphs for this section only>"}}',
            "Rules:",
            "- body must be real prose (≥80 chars), no '(LLM fills' placeholders",
            "- do NOT include a ## heading in body",
            "- do NOT author §7 / roles / profile-decisions / model.units",
            "- do NOT run git commit",
            "- MUST copy ≥1 REQUIRED CITE / src/... path from PROJECTED FACTS "
            "into the body verbatim (O-PROFPROSECITE)",
        ]
    )
    slog = Path("/tmp") / f"profile-prose-s{num}.log"
    # Persist projection for forensics / instruments
    try:
        Path("/tmp").joinpath(f"profile-prose-s{num}.project.txt").write_text(
            projected, encoding="utf-8"
        )
    except OSError:
        pass
    cmd = [
        "timeout",
        str(section_timeout),
        "opencode",
        "run",
        packet,
        "-m",
        worker_model,
        "--auto",
        "--format",
        "json",
        "-f",
        str(skilldir / "ANALYSIS.md"),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=section_timeout + 30,
        )
        blob = (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or "")
        slog.write_text(blob, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(
            f"opencode prose {_sec_label(num, title)} failed: {e}"
        ) from e

    # F-prose-no-discovery (default on)
    no_disc = os.environ.get("PROFILE_PROSE_NO_DISCOVERY", "1") not in (
        "0",
        "false",
        "no",
    )
    if no_disc:
        hits = _legacy_discovery_reads(proc.stdout or "", legacy)
        if hits:
            raise RuntimeError(
                f"F-prose-no-discovery {_sec_label(num, title)}: legacy tool use "
                f"{hits[:8]} (packet incomplete or model rediscovered; see {slog})"
            )

    texts: list[str] = []
    for line in (proc.stdout or "").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            texts.append(line)
            continue
        part = o.get("part") if isinstance(o, dict) else None
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(str(part.get("text") or ""))
        elif isinstance(o, dict) and "text" in o:
            texts.append(str(o.get("text") or ""))
    parse_blob = "\n".join(texts) if texts else blob
    body = _parse_prose_payload(parse_blob, num)
    if not body:
        raise RuntimeError(
            f"opencode prose {_sec_label(num, title)} returned no usable body "
            f"(rc={proc.returncode}; see {slog})"
        )
    return body


def run_loop(
    root: Path,
    *,
    legacy: str,
    backend: str,
    retries: int,
    section_timeout: int,
    worker_model: str,
    only_section: int = 0,
) -> int:
    root = root.resolve()
    skilldir = HERE.parent / "skills" / "migration-harness"
    _ensure_skeleton(root)
    path = _profile_path(root)
    text = path.read_text(encoding="utf-8")
    ok = 0
    fail = 0
    _write_progress(active="starting", ok=0, fail=0)
    _log(
        f"O-PROFPROSEDECOMP: backend={backend} retries={retries} "
        f"timeout={section_timeout}s profile={path}"
    )
    for num, title, hint in SECTIONS:
        if only_section and num != only_section:
            continue
        label = _sec_label(num, title)
        # Heartbeat: include title so outer-loop.log is demo-readable.
        _write_progress(active=label, ok=ok, fail=fail)
        body_now = _section_body(text, num)
        if not _needs_fill(body_now):
            _log(f"O-PROFPROSEDECOMP: SKIP {label} already filled")
            ok += 1
            continue
        landed = False
        last_err = ""
        for attempt in range(1, max(1, retries) + 1):
            try:
                if backend == "dry-run":
                    body = _dry_run_body(num, title, hint)
                elif backend in ("opencode-qwen", "opencode"):
                    body = _opencode_section(
                        root,
                        num=num,
                        title=title,
                        hint=hint,
                        worker_model=worker_model,
                        section_timeout=section_timeout,
                        skilldir=skilldir,
                        legacy=legacy,
                    )
                else:
                    raise RuntimeError(f"unknown backend {backend}")
                if not _body_ok(body):
                    why = "unknown"
                    if not body or not str(body).strip():
                        why = "empty"
                    elif _SKELETON_RE.search(body):
                        why = "skeleton"
                    elif len(re.sub(r"\s+", " ", body).strip()) < _MIN_BODY_CHARS:
                        why = "thin"
                    elif re.search(r"^##\s+\d+\.", body, re.M):
                        why = "heading"
                    elif not _body_has_cite(body):
                        why = "F-prose-uncited"
                    raise RuntimeError(f"{label} body failed validation ({why})")
                # W4-504: re-read before splice so a concurrent writer cannot
                # silently revert other sections from a stale in-memory snapshot.
                text = path.read_text(encoding="utf-8")
                text = _replace_section(text, num, title, body)
                path.write_text(text, encoding="utf-8")
                _log(
                    f"O-PROFPROSEDECOMP: OK {label} attempt={attempt} "
                    f"chars={len(body.strip())}"
                )
                landed = True
                ok += 1
                break
            except Exception as e:  # noqa: BLE001 — per-section park
                last_err = str(e)
                _log(
                    f"O-PROFPROSEDECOMP: RETRY {label} "
                    f"attempt={attempt}/{retries}: {e}",
                    err=True,
                )
        if not landed:
            fail += 1
            _log(
                f"O-PROFPROSEDECOMP: FAIL {label}: {last_err}",
                err=True,
            )
        _write_progress(active=label, ok=ok, fail=fail)
    # Final skeleton gate (same predicate as O-PROFPROSENOOP)
    final = path.read_text(encoding="utf-8")
    # Only check §§1–6 spans
    leftover = []
    for num, title, _h in SECTIONS:
        b = _section_body(final, num)
        if _needs_fill(b):
            leftover.append(_sec_label(num, title))
    _log(
        f"O-PROFPROSEDECOMP: done ok={ok} fail={fail} "
        f"leftover_sections={leftover or 'none'}"
    )
    _write_progress(active="done", ok=ok, fail=fail)
    if leftover or fail:
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="O-PROFPROSEDECOMP §§1–6 prose loop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--root", default=".")
    p.add_argument("--legacy", default="/projects/legacy")
    p.add_argument(
        "--backend",
        default=os.environ.get("PROFILE_PROSE_BACKEND", "opencode-qwen"),
    )
    p.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("PROFILE_PROSE_RETRIES", "2")),
    )
    p.add_argument(
        "--section-timeout",
        type=int,
        default=int(os.environ.get("PROFILE_PROSE_TIMEOUT", "180")),
    )
    p.add_argument(
        "--worker-model",
        default=os.environ.get("WORKER_MODEL", "qwen27b/qwen3-6-27b"),
    )
    p.add_argument(
        "--only-section",
        type=int,
        default=0,
        help="If 1–6, only that section (instruments)",
    )
    args = ap.parse_args()
    if args.cmd == "run":
        return run_loop(
            Path(args.root),
            legacy=args.legacy,
            backend=args.backend,
            retries=args.retries,
            section_timeout=args.section_timeout,
            worker_model=args.worker_model,
            only_section=args.only_section,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
