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
        if isinstance(goal, str) and len(goal.strip()) >= 20:
            return {
                "unit_keys": [str(k) for k in keys],
                "goal": goal.strip(),
                "plan": str(o.get("plan") or "").strip(),
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


def _opencode_judgment(
    root: Path,
    *,
    task: dict,
    sid: str,
    worker_model: str,
    timeout: int,
    legacy: str,
) -> dict:
    del legacy  # packet already inlines SNIPPETs; legacy path not passed to seat
    m = _load_model_api()
    model = m.load(root)
    projected = m.context_for(model, sid, root=root)
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
            "- do NOT edit specs/**/tasks.md (harness writes)",
            "- do NOT git commit",
            "- do NOT Read any prompt file — the full packet is already above",
            "- do NOT Read migration/briefs/** (brief already inlined)",
            "- do NOT Read /projects/legacy (SNIPPET only — F-no-discovery)",
            "- goal ≥ 20 chars",
        ]
    )
    slog = Path("/tmp") / f"m3-task-{sid}-{task.get('seq')}.log"
    # Forensics only — never the delivery channel (W4-556 / F-packet-by-value).
    pdir = root / "migration" / ".m3-prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    pfile = pdir / f"m3-task-prompt-{sid}-{task.get('seq')}.txt"
    pfile.write_text(packet, encoding="utf-8")
    pref = str(pfile.relative_to(root))

    skilldir = HERE.parent / "skills" / "migration-harness"
    skill = skilldir / "PLANNING.md"
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
        _log(f"m3_task_loop: {s} unfilled={len(tasks)} backend={backend}")
        for t in tasks:
            keys = list(t.get("unit_keys") or [])
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
                    )
                else:
                    raise ValueError(f"unknown backend {backend}")
                m.upsert_task_judgment(
                    root,
                    unit_keys=j["unit_keys"],
                    goal=j["goal"],
                    plan=j.get("plan") or "",
                    risk=j.get("risk") or "",
                    payload=j,
                )
                ok += 1
                _log(f"  OK {t.get('id')} keys={keys}")
            except JudgmentError as e:
                fail += 1
                _log(f"  FAIL {t.get('id')}: {e.kind} — {e}", err=True)
            except Exception as e:
                fail += 1
                _log(f"  FAIL {t.get('id')}: {e}", err=True)
        model = m.load(root)
        m.render_tasks_md(root, s, model)
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
    print(json.dumps({"id": t.get("id"), "filled": t.get("filled")}, indent=2))
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
    print("m3-parse-selftest-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
