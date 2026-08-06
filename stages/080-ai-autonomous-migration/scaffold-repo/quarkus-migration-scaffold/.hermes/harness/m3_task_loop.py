#!/usr/bin/env python3
"""ADR-35 / ADR-40 — M3 write-inversion loop (Qwen port).

Same shape as profile_prose_loop / ADR-32 decide:
  harness enumerates typed tasks → model returns one judgment → harness writes.

Seat MUST NOT author task id or acceptance (F-taskid-generated /
F-acceptance-derived). Packet includes context_for SNIPPETs (O-M3SNIPPET).

Delivery (W4-556 / F-packet-by-value): pass packet TEXT as opencode argv
positional (by value), matching profile_prose_loop — never a path the seat
must Read. Disk write under migration/.m3-prompts/ is forensics only.

Backends:
  dry-run       — deterministic fixture judgment (instruments)
  opencode-qwen — OpenCode returns JSON; harness upserts + re-renders tasks.md

Usage:
  m3_task_loop.py run --root DIR [--sid SID] [--backend opencode-qwen|dry-run]
  m3_task_loop.py upsert --root DIR --unit-key K --goal '…' [--plan …] [--risk …]
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


class JudgmentError(RuntimeError):
    """Typed seat failure: EMPTY | REFUSED:<falsifier> | MALFORMED."""

    def __init__(self, kind: str, detail: str = "") -> None:
        self.kind = kind
        msg = kind if not detail else f"{kind}: {detail}"
        super().__init__(msg)


def _log(msg: str, *, err: bool = False) -> None:
    print(msg, file=sys.stderr if err else sys.stdout, flush=True)


def _write_progress(
    *,
    sid: str,
    active: str,
    ok: int,
    fail: int,
    total: int,
) -> None:
    """O-M3TYPEDHB — one-line status for outer-loop 60s heartbeat (demo UX).

    Same contract as O-PROFDECIDEHB /tmp/outer-heartbeat-progress.txt so the
    shared heartbeat appends ``m3=S04 seats=3/13 active=…`` instead of silence
    while OpenCode judges one typed task.
    """
    try:
        done = ok + fail
        simple = str(active or "?")
        if "/" in simple:
            simple = simple.rsplit("/", 1)[-1]
        line = (
            f"m3={sid} seats={done}/{total} active={simple} "
            f"ok={ok} fail={fail}"
        )
        Path("/tmp/outer-heartbeat-progress.txt").write_text(
            line + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def _load_model_api():
    sys.path.insert(0, str(HERE))
    import model as m  # type: ignore

    return m


def _unfilled(tasks: list[dict]) -> list[dict]:
    out = []
    for t in tasks:
        goal = (t.get("goal") or "").strip()
        if t.get("filled") and len(goal) >= 20:
            continue
        if "JUDGMENT" in goal or len(goal) < 20:
            out.append(t)
    return out


def _dry_run_judgment(task: dict) -> dict:
    keys = task.get("unit_keys") or []
    slug = keys[0].rsplit(".", 1)[-1] if keys else "unit"
    role = task.get("role") or "UNDECIDED"
    return {
        "unit_keys": keys,
        "goal": (
            f"Migrate {slug} ({role}) using projected SNIPPET/contract facts only; "
            f"harness-owned acceptance applies."
        ),
        "plan": f"Apply {task.get('class')}/{task.get('shape')} for {slug}",
        "risk": "low" if role == "HARVEST" else "medium",
    }


def _parse_judgment(blob: str, expect_keys: list[str]) -> dict:
    """Extract judgment or raise JudgmentError with EMPTY/REFUSED/MALFORMED."""
    text = (blob or "").strip()
    if not text:
        raise JudgmentError("EMPTY", "no seat response")

    candidates: list[dict] = []
    for m in re.finditer(r"\{.*?\}", text, re.S):
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            candidates.append(o)
    start, end = text.rfind("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            o = json.loads(text[start : end + 1])
            if isinstance(o, dict):
                candidates.append(o)
        except json.JSONDecodeError:
            pass

    if not candidates:
        raise JudgmentError("MALFORMED", "no JSON object in seat response")

    expect = sorted(expect_keys)
    refused: list[str] = []
    malformed_keys = 0
    # O-JUDGEHEDGE / plan-lint LINT:hedge — decided shapes, never options.
    _hedge = re.compile(
        r"\b(if needed|if necessary|as appropriate|as needed|"
        r"consider (?:using|adding)|optionally)\b",
        re.I,
    )
    for o in candidates:
        if o.get("id") not in (None, ""):
            refused.append("REFUSED:F-taskid-generated")
            continue
        if o.get("acceptance") not in (None, "", [], {}):
            refused.append("REFUSED:F-acceptance-derived")
            continue
        keys = o.get("unit_keys")
        if not keys and o.get("unit_key"):
            keys = [o["unit_key"]]
        if not isinstance(keys, list):
            malformed_keys += 1
            continue
        if sorted(str(k) for k in keys) != expect:
            malformed_keys += 1
            continue
        goal = o.get("goal")
        plan = str(o.get("plan") or "").strip()
        if isinstance(goal, str) and len(goal.strip()) >= 20:
            blob = f"{goal}\n{plan}"
            hm = _hedge.search(blob)
            if hm:
                refused.append("REFUSED:F-hedge")
                continue
            return {
                "unit_keys": [str(k) for k in keys],
                "goal": goal.strip(),
                "plan": plan,
                "risk": str(o.get("risk") or "").strip(),
            }
        malformed_keys += 1

    if refused:
        # Prefer first distinct refusal class
        raise JudgmentError(refused[0], "seat authored forbidden field")
    raise JudgmentError(
        "MALFORMED",
        f"candidates={len(candidates)} key_mismatch_or_short_goal={malformed_keys}",
    )


def _packet_fetch_reads(blob: str, prompt_rel: str) -> list[str]:
    """Detect seat tool Reads targeting the forensics prompt path (F-packet-by-value)."""
    hits: list[str] = []
    needle = prompt_rel.replace("\\", "/")
    for line in (blob or "").splitlines():
        if "m3-task-prompt" not in line and ".m3-prompts" not in line:
            continue
        if needle in line.replace("\\", "/") or "m3-task-prompt-" in line:
            if re.search(r"(?i)\b(read|Read|tool_use|filePath)\b", line):
                hits.append(line.strip()[:200])
    return hits


def _legacy_discovery_reads(blob: str) -> list[str]:
    """Detect seat Reads of /projects/legacy (F-no-discovery / ADR-38)."""
    hits: list[str] = []
    for line in (blob or "").splitlines():
        low = line.replace("\\", "/")
        if "/projects/legacy" not in low and "projects/legacy/" not in low:
            continue
        if re.search(r"(?i)\b(read|Read|tool_use|filePath|bash)\b", line):
            hits.append(line.strip()[:200])
    return hits


def _brief_fetch_reads(blob: str) -> list[str]:
    """Detect seat Reads of migration/briefs/** (F-brief-projected)."""
    hits: list[str] = []
    for line in (blob or "").splitlines():
        low = line.replace("\\", "/")
        if "migration/briefs" not in low and "/briefs/" not in low:
            continue
        if re.search(r"(?i)\b(read|Read|tool_use|filePath|glob|bash)\b", line):
            hits.append(line.strip()[:200])
    return hits


def _staging_reads(blob: str) -> list[str]:
    """Detect seat Reads of migration/staging/** (O-NOSTAGINGREAD / F-staging-projected).

    When STAGING FACTS are harness-projected, reading staging is conduct — same
    class as F-no-discovery (legacy) and F-brief-projected.
    """
    hits: list[str] = []
    for line in (blob or "").splitlines():
        low = line.replace("\\", "/")
        if "migration/staging" not in low and "/staging/" not in low:
            continue
        # Avoid matching unrelated "staging" words without a path-ish hit.
        if "migration/staging" not in low and not re.search(
            r"(?:^|[\s\"'])(?:\.?/)?(?:migration/)?staging/", low
        ):
            continue
        if re.search(r"(?i)\b(read|Read|tool_use|filePath|glob|bash|ls)\b", line):
            hits.append(line.strip()[:200])
    return hits


def _path_is_spec_or_migration(path: str) -> bool:
    """True when a tool path targets rendered specs or migration SoT (F-no-spec-edit)."""
    p = (path or "").replace("\\", "/")
    if not p:
        return False
    # Absolute or relative forms seen in OpenCode tool logs.
    if "/specs/" in p or p.startswith("specs/") or p == "specs":
        return True
    if "/migration/" in p or p.startswith("migration/") or p == "migration":
        return True
    return False


def _tool_and_path_from_line(line: str) -> tuple[str, str]:
    """Extract mutating/read tool name + path from an OpenCode JSON/tool line."""
    low = (line or "").replace("\\", "/")
    tool = ""
    path = ""
    try:
        o = json.loads(line)
    except json.JSONDecodeError:
        o = None
    if isinstance(o, dict):
        part = o.get("part") if isinstance(o.get("part"), dict) else o
        if isinstance(part, dict):
            tool = str(part.get("tool") or part.get("name") or "").lower()
            inp = part.get("input") if isinstance(part.get("input"), dict) else {}
            path = str(
                inp.get("filePath")
                or inp.get("path")
                or inp.get("file")
                or part.get("filePath")
                or ""
            )
    if not tool:
        m = re.search(
            r'"tool"\s*:\s*"(edit|write|apply_patch|create|read)"', low, re.I
        )
        if m:
            tool = m.group(1).lower()
    return tool, path


def _workspace_writes(blob: str) -> list[str]:
    """F-no-workspace-write (W4-592): refuse ANY mutating tool call.

    M3 seats return JSON only — permitted write surface is empty. Directory
    denylists (specs/migration) left a src/** hole that becomes real at M4.
    """
    hits: list[str] = []
    for line in (blob or "").splitlines():
        tool, _path = _tool_and_path_from_line(line)
        if not tool:
            low = line.replace("\\", "/")
            m = re.search(r'"tool"\s*:\s*"(edit|write|apply_patch|create)"', low, re.I)
            if m:
                tool = m.group(1).lower()
        if tool in ("edit", "write", "apply_patch", "create"):
            hits.append(line.strip()[:240])
    return hits


def _spec_or_migration_edits(blob: str) -> list[str]:
    """Detect seat edit/write of specs/** or migration/** (F-no-spec-edit / W4-576).

    Superseded at the loop gate by F-no-workspace-write (any mutate). Kept for
    path-specific selftests and instruments that still name this detector.
    """
    hits: list[str] = []
    for line in (blob or "").splitlines():
        low = line.replace("\\", "/")
        tool, path = _tool_and_path_from_line(line)
        if tool not in ("edit", "write", "apply_patch", "create"):
            continue
        if not path:
            m = re.search(
                r"(/projects/[^\"'\s]+/(?:specs|migration)/[^\"'\s]+|"
                r"(?:specs|migration)/[^\"'\s]+)",
                low,
            )
            path = m.group(1) if m else ""
        if _path_is_spec_or_migration(path) or (
            not path
            and re.search(r"(?:/specs/|/migration/|^specs/|^migration/)", low)
        ):
            hits.append(line.strip()[:240])
    return hits


def _story_brief_text(root: Path, sid: str, model: dict) -> str:
    """Inline story brief into the packet (F-brief-projected) — no seat Read."""
    m = _load_model_api()
    slug = m.brief_slug_for_story(root, sid, model)
    candidates = [
        root / "migration" / "briefs" / f"{slug}.md",
        root / "migration" / "briefs" / f"{sid}.md",
    ]
    # Also match sid-*.md if slug path missing
    if not any(p.is_file() for p in candidates):
        found = sorted((root / "migration" / "briefs").glob(f"{sid}-*.md"))
        candidates = found[:1] + candidates
    for p in candidates:
        if p.is_file():
            body = p.read_text(encoding="utf-8", errors="replace")
            # Cap to keep argv/packet bounded; full brief usually fits.
            if len(body) > 24000:
                body = body[:24000] + "\n…[brief truncated for packet]\n"
            return (
                f"===== BEGIN STORY BRIEF (authoritative — already inlined; "
                f"do NOT Read migration/briefs/) =====\n"
                f"brief_path: {p.relative_to(root)}\n\n"
                f"{body}\n"
                f"===== END STORY BRIEF ====="
            )
    return (
        f"===== BEGIN STORY BRIEF =====\n"
        f"(no migration/briefs/{sid}-*.md present — plan from DERIVED FACTS only)\n"
        f"===== END STORY BRIEF ====="
    )


def _seat_transcript_path(sid: str, seq: Any, attempt: int) -> Path:
    """ADR-43 — append-only journal path (never overwrite attempt N with N+1)."""
    unit = f"{sid}-{seq}"
    try:
        from run_journal import seat_log  # type: ignore

        return seat_log("m3", unit, attempt=attempt)
    except Exception:
        # Fallback keeps attempt in the name so retries cannot clobber failures.
        p = Path("/tmp/hj") / "fallback" / "m3"
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{unit}.attempt{max(1, int(attempt))}.log"


def _opencode_judgment(
    root: Path,
    *,
    task: dict,
    sid: str,
    worker_model: str,
    timeout: int,
    legacy: str,
    attempt: int = 1,
) -> dict:
    del legacy  # packet already inlines SNIPPETs; legacy path not passed to seat
    m = _load_model_api()
    model = m.load(root)
    # O-STAGINGOWNUNIT: per-seat projection so own unit staging is never
    # truncated by story-wide HARVEST neighbours filling the cap first.
    projected = m.context_for(model, sid, root=root, focus_task=task)
    brief = _story_brief_text(root, sid, model)
    keys = list(task.get("unit_keys") or [])
    packet = "\n".join(
        [
            "Author JUDGMENT for ONE typed M3 task. Harness owns id + acceptance.",
            f"story: {sid}",
            f"unit_keys: {json.dumps(keys)}",
            f"role: {task.get('role')}",
            f"class/shape: {task.get('class')}/{task.get('shape')}",
            f"owns: {task.get('owns')}",
            "Acceptance is ALREADY DERIVED — do NOT invent acceptance or task id.",
            "ALL code quotes are in SNIPPET lines in DERIVED FACTS — do NOT read legacy.",
            "STORY BRIEF is inlined below — do NOT Read migration/briefs/**.",
            "",
            brief,
            "",
            projected,
            "",
            "Reply with ONLY this JSON (no file edits, no tools required):",
            json.dumps(
                {
                    "unit_keys": keys,
                    "goal": "<one sentence from brief + SNIPPET>",
                    "plan": "<short plan>",
                    "risk": "low|medium|high",
                }
            ),
            "Rules:",
            "- do NOT include id or acceptance fields (refused)",
            "- do NOT edit/write ANY workspace path — JSON judgment only "
            "(F-no-workspace-write; subsumes F-no-spec-edit)",
            "- do NOT git commit",
            "- do NOT Read any prompt file — the full packet is already above",
            "- do NOT Read migration/briefs/** (brief already inlined)",
            "- do NOT Read migration/staging/** (STAGING FACTS projected — "
            "F-staging-projected / O-NOSTAGINGREAD)",
            "- do NOT Read /projects/legacy (SNIPPET only — F-no-discovery)",
            "- do NOT Read TASKS-TEMPLATE.md — typed seats return JSON only",
            "- goal ≥ 20 chars",
        ]
    )
    slog = _seat_transcript_path(sid, task.get("seq"), attempt)
    # Forensics only — never the delivery channel (W4-556 / F-packet-by-value).
    pdir = root / "migration" / ".m3-prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    pfile = pdir / f"m3-task-prompt-{sid}-{task.get('seq')}.txt"
    pfile.write_text(packet, encoding="utf-8")
    pref = str(pfile.relative_to(root))

    skilldir = HERE.parent / "skills" / "migration-harness"
    # O-M3JUDGMENTSKILL / W4-576: typed seats must NOT load PLANNING.md —
    # that file teaches legacy "edit specs/<NNN-slug>/tasks.md first" and
    # caused write-inversion bypass attempts (004- vs S04- path typo).
    skill = skilldir / "JUDGMENT.md"
    if not skill.is_file():
        skill = skilldir / "TASKS-TEMPLATE.md"
    if not skill.is_file():
        skill = skilldir / "ANALYSIS.md"
    cmd = [
        "timeout",
        str(int(timeout)),
        "opencode",
        "run",
        packet,  # by value — F-packet-by-value
        "-m",
        worker_model,
        "--auto",
        "--format",
        "json",
        "-f",
        str(skill),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            check=False,
            timeout=int(timeout) + 30,
        )
    except FileNotFoundError as e:
        raise RuntimeError("opencode binary not found for m3_task_loop") from e
    except subprocess.TimeoutExpired as e:
        raise JudgmentError("EMPTY", f"opencode timeout after {timeout}s") from e

    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    slog.write_text(blob, encoding="utf-8")

    fetches = _packet_fetch_reads(blob, pref)
    if fetches:
        raise JudgmentError(
            "REFUSED:F-packet-by-value",
            f"seat Read of own prompt ({len(fetches)} hit(s)); see {slog}",
        )
    # F-no-discovery (W4-565): legacy reads are refuse, not observation.
    legacy_hits = _legacy_discovery_reads(blob)
    if legacy_hits:
        raise JudgmentError(
            "REFUSED:F-no-discovery",
            f"seat Read of /projects/legacy ({len(legacy_hits)} hit(s)); see {slog}",
        )
    # F-brief-projected (W4-565): brief is in the packet — seat must not fetch it.
    brief_hits = _brief_fetch_reads(blob)
    if brief_hits:
        raise JudgmentError(
            "REFUSED:F-brief-projected",
            f"seat Read of migration/briefs ({len(brief_hits)} hit(s)); see {slog}",
        )
    # O-NOSTAGINGREAD / F-staging-projected: staging facts are projected.
    staging_hits = _staging_reads(blob)
    if staging_hits:
        raise JudgmentError(
            "REFUSED:F-staging-projected",
            f"seat Read of migration/staging ({len(staging_hits)} hit(s)); see {slog}",
        )
    # F-no-workspace-write (W4-592): any mutating tool — allowlist is empty.
    # Supersedes path-denylist F-no-spec-edit (specs/migration/src holes).
    ws_writes = _workspace_writes(blob)
    if ws_writes:
        raise JudgmentError(
            "REFUSED:F-no-workspace-write",
            f"seat mutating tool call ({len(ws_writes)} hit(s)); see {slog}",
        )
    # Defense-in-depth: path-specific F-no-spec-edit still named for instruments.
    spec_edits = _spec_or_migration_edits(blob)
    if spec_edits:
        raise JudgmentError(
            "REFUSED:F-no-spec-edit",
            f"seat edit/write of specs/** or migration/** ({len(spec_edits)} hit(s)); see {slog}",
        )

    # Prefer JSON-format text parts when present (same as prose loop).
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
    return _parse_judgment(parse_blob, keys)


def run_loop(
    root: Path,
    *,
    sid: str = "",
    backend: str = "opencode-qwen",
    worker_model: str = "",
    timeout: int = 180,
    legacy: str = "/projects/legacy",
    limit: int = 0,
) -> int:
    m = _load_model_api()
    model = m.load(root)
    if not (model.get("tasks") or []):
        model = m.assign_tasks(root, model)
    sids = [sid] if sid else sorted(
        {t.get("sid") for t in (model.get("tasks") or []) if t.get("sid")}
    )
    worker_model = worker_model or os.environ.get(
        "WORKER_MODEL", "qwen27b/qwen3-6-27b"
    )
    ok = fail = 0
    for s in sids:
        tasks = _unfilled(m.tasks_for_story(model, s))
        if limit > 0:
            tasks = tasks[:limit]
        total = len(tasks)
        _log(f"m3_task_loop: {s} unfilled={total} backend={backend}")
        _write_progress(sid=s, active="starting", ok=ok, fail=fail, total=total)
        # O-M3EMPTYRETRY: EMPTY/transient no-response gets N retries before
        # story fail (MALFORMED/REFUSED stay single-shot).
        empty_retries = int(os.environ.get("M3_EMPTY_RETRIES", "2"))
        for t in tasks:
            tid = str(t.get("id") or "?")
            keys = list(t.get("unit_keys") or [])
            _write_progress(sid=s, active=tid, ok=ok, fail=fail, total=total)
            attempts = 1 + max(0, empty_retries)
            for attempt in range(1, attempts + 1):
                try:
                    if backend == "dry-run":
                        j = _dry_run_judgment(t)
                    elif backend in ("opencode-qwen", "opencode", "qwen"):
                        j = _opencode_judgment(
                            root,
                            task=t,
                            sid=s,
                            worker_model=worker_model,
                            timeout=timeout,
                            legacy=legacy,
                            attempt=attempt,
                        )
                    else:
                        raise ValueError(f"unknown backend {backend}")
                    m.upsert_task_judgment(
                        root,
                        task_id=tid,
                        unit_keys=j["unit_keys"],
                        goal=j["goal"],
                        plan=j.get("plan") or "",
                        risk=j.get("risk") or "",
                        payload=j,
                    )
                    ok += 1
                    if attempt > 1:
                        _log(f"  OK {tid} keys={keys} (after EMPTY retry {attempt})")
                    else:
                        _log(f"  OK {tid} keys={keys}")
                    break
                except JudgmentError as e:
                    if e.kind == "EMPTY" and attempt < attempts:
                        _log(
                            f"  RETRY {tid}: EMPTY attempt {attempt}/{attempts} — {e}",
                            err=True,
                        )
                        continue
                    fail += 1
                    _log(f"  FAIL {tid}: {e.kind} — {e}", err=True)
                    break
                except Exception as e:
                    fail += 1
                    _log(f"  FAIL {tid}: {e}", err=True)
                    break
            _write_progress(sid=s, active=tid, ok=ok, fail=fail, total=total)
        model = m.load(root)
        m.render_tasks_md(root, s, model)
    _write_progress(
        sid=sids[-1] if sids else "?",
        active="done",
        ok=ok,
        fail=fail,
        total=ok + fail,
    )
    _log(f"m3_task_loop: done ok={ok} fail={fail}")
    return 1 if fail else 0


def cmd_upsert(args: argparse.Namespace) -> int:
    m = _load_model_api()
    keys = [k for k in (args.unit_key or []) if k]
    if args.unit_keys_json:
        keys = json.loads(args.unit_keys_json)
    try:
        t = m.upsert_task_judgment(
            Path(args.root).resolve(),
            task_id=getattr(args, "task_id", "") or "",
            unit_keys=keys,
            goal=args.goal,
            plan=args.plan or "",
            risk=args.risk or "",
            payload={
                k: v
                for k, v in {
                    "id": args.forbid_id,
                    "acceptance": args.forbid_acceptance,
                }.items()
                if v
            }
            if (args.forbid_id or args.forbid_acceptance)
            else {},
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "id": t.get("id"),
                "filled": t.get("filled"),
                "goal_source": t.get("goal_source"),
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-35 M3 write-inversion loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("--root", default=".")
    r.add_argument("--sid", default="")
    r.add_argument("--backend", default="opencode-qwen")
    r.add_argument("--worker-model", default="")
    r.add_argument("--timeout", type=int, default=180)
    r.add_argument("--legacy", default="/projects/legacy")
    r.add_argument("--limit", type=int, default=0)
    r.set_defaults(
        func=lambda a: run_loop(
            Path(a.root).resolve(),
            sid=a.sid,
            backend=a.backend,
            worker_model=a.worker_model,
            timeout=a.timeout,
            legacy=a.legacy,
            limit=a.limit,
        )
    )

    u = sub.add_parser("upsert")
    u.add_argument("--root", default=".")
    u.add_argument(
        "--task-id",
        default="",
        help="harness-owned task id (required when unit_keys are shared; O-UPSERTID)",
    )
    u.add_argument("--unit-key", action="append", default=[])
    u.add_argument("--unit-keys-json", default="")
    u.add_argument("--goal", required=True)
    u.add_argument("--plan", default="")
    u.add_argument("--risk", default="")
    u.add_argument("--forbid-id", default="", help="instruments: inject id to refuse")
    u.add_argument(
        "--forbid-acceptance",
        default="",
        help="instruments: inject acceptance to refuse",
    )
    u.set_defaults(func=cmd_upsert)

    # instruments helpers
    p = sub.add_parser("parse-selftest")
    p.set_defaults(func=lambda _a: _selftest_parse())

    args = ap.parse_args()
    return int(args.func(args))


def _selftest_parse() -> int:
    """Instrument helper: EMPTY / REFUSED / MALFORMED distinct messages."""
    try:
        _parse_judgment("", ["a.b.C"])
        print("expected EMPTY", file=sys.stderr)
        return 1
    except JudgmentError as e:
        assert e.kind == "EMPTY", e.kind
    try:
        _parse_judgment(
            '{"id":"S01-T-001","unit_keys":["a.b.C"],"goal":"' + ("x" * 25) + '"}',
            ["a.b.C"],
        )
        print("expected REFUSED id", file=sys.stderr)
        return 1
    except JudgmentError as e:
        assert e.kind == "REFUSED:F-taskid-generated", e.kind
    try:
        _parse_judgment(
            '{"unit_keys":["a.b.C"],"acceptance":["x"],"goal":"' + ("y" * 25) + '"}',
            ["a.b.C"],
        )
        print("expected REFUSED acceptance", file=sys.stderr)
        return 1
    except JudgmentError as e:
        assert e.kind == "REFUSED:F-acceptance-derived", e.kind
    try:
        _parse_judgment("not json at all", ["a.b.C"])
        print("expected MALFORMED", file=sys.stderr)
        return 1
    except JudgmentError as e:
        assert e.kind == "MALFORMED", e.kind
    ok = _parse_judgment(
        '{"unit_keys":["a.b.C"],"goal":"Migrate C with enough characters here."}',
        ["a.b.C"],
    )
    assert ok["goal"].startswith("Migrate")
    # F-packet-by-value detector
    hits = _packet_fetch_reads(
        'Read migration/.m3-prompts/m3-task-prompt-S01-1.txt',
        "migration/.m3-prompts/m3-task-prompt-S01-1.txt",
    )
    assert hits, hits
    assert not _packet_fetch_reads("goal ok no tools", "migration/.m3-prompts/x.txt")
    # F-no-discovery / F-brief-projected detectors (W4-565)
    assert _legacy_discovery_reads(
        'Read /projects/legacy/src/main/java/org/example/Foo.java'
    )
    assert not _legacy_discovery_reads("goal ok no tools")
    assert _brief_fetch_reads('Read migration/briefs/S02-repository-layer.md')
    assert not _brief_fetch_reads("goal ok no tools")
    # F-no-spec-edit (W4-576): edit/write of specs/** or migration/** refuse.
    edit_line = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "tool": "edit",
                "input": {
                    "filePath": "/projects/modernized/specs/S04-rest/tasks.md",
                    "oldString": "x",
                    "newString": "y",
                },
            },
        }
    )
    assert _spec_or_migration_edits(edit_line), edit_line
    write_mig = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "tool": "write",
                "input": {"filePath": "migration/model.json", "content": "{}"},
            },
        }
    )
    assert _spec_or_migration_edits(write_mig), write_mig
    # Reads of specs are not F-no-spec-edit (separate residual).
    read_spec = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "tool": "read",
                "input": {"filePath": "/projects/modernized/specs/S04/tasks.md"},
            },
        }
    )
    assert not _spec_or_migration_edits(read_spec), read_spec
    assert not _spec_or_migration_edits("goal ok no tools")
    # F-no-workspace-write (W4-592): any mutate, including src/**.
    src_edit = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "tool": "edit",
                "input": {
                    "filePath": "/projects/modernized/src/main/java/com/demo/model/PetType.java",
                    "oldString": "x",
                    "newString": "y",
                },
            },
        }
    )
    assert _workspace_writes(src_edit), src_edit
    assert _workspace_writes(edit_line), edit_line
    assert not _workspace_writes(read_spec), read_spec
    assert not _workspace_writes("goal ok no tools")
    # O-NOSTAGINGREAD / F-staging-projected
    assert _staging_reads(
        "Read migration/staging/src/main/java/org/example/Foo.java"
    )
    assert _staging_reads(
        'Read /projects/modernized/migration/staging/src/main/java/Foo.java'
    )
    assert not _staging_reads("goal ok no tools")
    assert not _staging_reads("STAGING FACTS projected — do NOT Read")
    # O-JUDGEHEDGE
    try:
        _parse_judgment(
            '{"unit_keys":["a.b.C"],"goal":"'
            + ("Migrate C with enough characters here.")
            + '","plan":"add extension if needed"}',
            ["a.b.C"],
        )
        print("expected REFUSED hedge", file=sys.stderr)
        return 1
    except JudgmentError as e:
        assert e.kind == "REFUSED:F-hedge", e.kind
    print("m3-parse-selftest-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
