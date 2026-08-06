#!/usr/bin/env python3
"""O-MONSCHEMA — enrich monitor trails with per-seat efficiency fields.

Parses OpenCode JSONL (`/tmp/oc-T-*.json`), optional `.err`, failure-sig, and
supervisor/outer snippets. Emits markdown (default) or key=value lines.

Cheapest high-value fields (W4-006):
  tools read/write/edit/glob/bash
  time_to_first_write (s, % of budget)
  sensor_delta before→after (when failure-sig / sensor logs available)

Also: rc / signal / killer, last_utterance, budget_used, guard_refusals.

Usage:
  python3 scripts/track-b/v10-monitor-seat-enrich.py \\
    --json /tmp/oc-T-003.json [--err /tmp/oc-T-003.err] \\
    [--failure-sig /tmp/failure-sig-before-T-003.txt] \\
    [--budget-s 1800] [--role qwen|hermes] [--format md|kv]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

READ_TOOLS = frozenset({"read", "read_file", "view"})
GLOB_TOOLS = frozenset({"glob", "grep", "list", "ls"})
EDIT_TOOLS = frozenset({"edit", "strreplace", "apply_patch", "multiedit"})
WRITE_TOOLS = frozenset({"write", "create", "write_file"})
BASH_TOOLS = frozenset({"bash", "shell", "exec", "run_terminal_cmd"})
# bash that usually mutates the tree (secondary first-write signal)
BASH_MUTATE_RE = re.compile(
    # Prefer real file mutators — bare `mkdir`/`ls` alone are not first-write.
    r"(>>?|tee\b|harvest-from-staging|git\s+commit|touch\b|\bcat\s*>|printf\s+.*>|sed\s+-i|"
    r"cp\s+\S+\s+\S+|mv\s+\S+\s+\S+|python3\s+\S*harvest)",
    re.I,
)


def _events(raw: str) -> list[dict]:
    evs: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list):
            evs.extend(x for x in obj if isinstance(x, dict))
        elif isinstance(obj, dict):
            evs.append(obj)
    if not evs:
        try:
            blob = json.loads(raw)
            if isinstance(blob, list):
                evs = [x for x in blob if isinstance(x, dict)]
            elif isinstance(blob, dict):
                evs = [blob]
        except json.JSONDecodeError:
            pass
    return evs


def _tool_name(ev: dict) -> str:
    part = ev.get("part") or ev.get("message") or {}
    if isinstance(part, dict):
        t = part.get("tool") or part.get("name")
        if isinstance(t, str) and t.lower() not in ("tool", "tool_use", ""):
            return t.lower()
    for k in ("tool", "name"):
        v = ev.get(k)
        if isinstance(v, str) and v.lower() not in ("tool", "tool_use", ""):
            return v.lower()
    return ""


def _tool_input(ev: dict) -> str:
    part = ev.get("part") if isinstance(ev.get("part"), dict) else {}
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inp = state.get("input") or part.get("input") or {}
    if isinstance(inp, dict):
        return str(inp.get("command") or inp.get("path") or inp.get("file_path") or "")
    return str(inp or "")


def _ts_ms(ev: dict) -> int | None:
    for key in ("timestamp", "time"):
        v = ev.get(key)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, dict) and isinstance(v.get("start"), (int, float)):
            return int(v["start"])
    part = ev.get("part") if isinstance(ev.get("part"), dict) else {}
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    for blob in (part.get("time"), state.get("time")):
        if isinstance(blob, dict) and isinstance(blob.get("start"), (int, float)):
            return int(blob["start"])
    return None


def _text_line(ev: dict) -> str:
    part = ev.get("part") if isinstance(ev.get("part"), dict) else {}
    text = ev.get("text") or part.get("text") or ""
    if not isinstance(text, str):
        return ""
    for line in text.strip().splitlines():
        s = line.strip()
        if len(s) >= 12:
            return s[:160]
    return ""


def parse_oc_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    evs = _events(raw)
    tools: collections.Counter[str] = collections.Counter()
    first_mutate_ms: int | None = None
    first_mutate_via = ""
    seat_start_ms: int | None = None
    seat_end_ms: int | None = None
    last_utt = ""
    for ev in evs:
        tms = _ts_ms(ev)
        if tms is not None:
            if seat_start_ms is None or tms < seat_start_ms:
                seat_start_ms = tms
            if seat_end_ms is None or tms > seat_end_ms:
                seat_end_ms = tms
        utt = _text_line(ev)
        if utt:
            last_utt = utt
        name = _tool_name(ev)
        if not name:
            continue
        if name in READ_TOOLS:
            tools["read"] += 1
        elif name in GLOB_TOOLS:
            tools["glob"] += 1
        elif name in EDIT_TOOLS:
            tools["edit"] += 1
        elif name in WRITE_TOOLS:
            tools["write"] += 1
        elif name in BASH_TOOLS:
            tools["bash"] += 1
        else:
            tools[name[:24]] += 1

        mutated = name in EDIT_TOOLS or name in WRITE_TOOLS
        via = name
        if not mutated and name in BASH_TOOLS and BASH_MUTATE_RE.search(_tool_input(ev)):
            mutated = True
            via = "bash-mutate"
            tools["bash_mutate"] += 1
        if mutated and first_mutate_ms is None and tms is not None:
            first_mutate_ms = tms
            first_mutate_via = via

    ttfw_s: float | None = None
    if first_mutate_ms is not None and seat_start_ms is not None:
        ttfw_s = max(0.0, (first_mutate_ms - seat_start_ms) / 1000.0)
    elapsed_s: float | None = None
    if seat_start_ms is not None and seat_end_ms is not None:
        elapsed_s = max(0.0, (seat_end_ms - seat_start_ms) / 1000.0)

    return {
        "events": len(evs),
        "tools": dict(tools),
        "time_to_first_write_s": ttfw_s,
        "first_mutate_via": first_mutate_via,
        "elapsed_s": elapsed_s,
        "last_utterance": last_utt,
        "json_bytes": path.stat().st_size,
        "json_path": str(path),
    }


def parse_err(path: Path | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "rc": None,
        "signal": None,
        "killer": None,
        "guard_refusals": [],
        "err_tail": "",
    }
    if path is None or not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    out["err_tail"] = " | ".join(
        ln.strip() for ln in text.strip().splitlines()[-3:] if ln.strip()
    )[:240]
    m = re.search(r"\brc=(\d+)\b", text)
    if m:
        out["rc"] = int(m.group(1))
    m = re.search(r"\b(SIGINT|SIGTERM|SIGKILL|KeyboardInterrupt)\b", text, re.I)
    if m:
        out["signal"] = m.group(1)
    m = re.search(
        r"(O-WORKERREAD|O-FIRSTMUT|O-WORKERWEDGE|O-M3EMPTY|O-SFIXLOOP|read-thrash|"
        r"worker killed|harness_kill|timeout)",
        text,
        re.I,
    )
    if m:
        out["killer"] = m.group(1)
    for pat in (
        r"O-SFIXLOOP\s+REFUSED[^\n]*",
        r"REFUSED[^\n]*milestone[^\n]*",
        r"O-T6d[^\n]*",
        r"unexpected-paths[^\n]*",
        r"redesign-sig\s+RED[^\n]*",
    ):
        for hit in re.findall(pat, text, re.I):
            if hit not in out["guard_refusals"]:
                out["guard_refusals"].append(hit[:120])
    return out


def parse_failure_sig(path: Path | None) -> dict[str, Any]:
    """Best-effort sensor_delta from failure-sig-before / after snippets."""
    out: dict[str, Any] = {"sensor_before": None, "sensor_after": None, "sensor_delta": None}
    if path is None or not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    # Common shapes: "sonar violations: 22" / "FINDINGS RED: 3" / rule counts
    before = None
    m = re.search(r"(?:violations?|issues?|findings?)[=:\s]+(\d+)", text, re.I)
    if m:
        before = int(m.group(1))
    m2 = re.search(r"NEW:\s*(\d+)", text)
    if before is None and m2:
        before = int(m2.group(1))
    out["sensor_before"] = before
    # Keep a short fingerprint for the monitor trail
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    out["failure_sig_head"] = first[:160]
    return out


def parse_supervisor_snip(text: str, task: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "actor": None,
        "sensor_after": None,
        "discarded": None,
        "escalation_cause": None,
    }
    if not text:
        return out
    if re.search(rf"{re.escape(task)}:.*MiniMax", text, re.I):
        out["actor"] = "minimax"
    elif re.search(rf"{re.escape(task)}:.*(?:Qwen|OpenCode|worker)", text, re.I):
        out["actor"] = "qwen"
    if re.search(r"O-SFIXDIRTY|discarding uncommitted", text, re.I):
        out["discarded"] = "src-dirt-discarded"
    if re.search(rf"{re.escape(task)}:.*GREEN", text):
        out["sensor_after"] = "GREEN"
    elif re.search(rf"{re.escape(task)}:.*RED", text):
        out["sensor_after"] = "RED"
    m = re.search(r"O-ESCALCAUSE\s+(\S+)", text)
    if m:
        out["escalation_cause"] = m.group(1)
    refusals = re.findall(r"O-SFIXLOOP[^\n]*REFUSED[^\n]*", text, re.I)
    out["sup_guard_refusals"] = [r[:120] for r in refusals[:5]]
    return out


def format_md(role: str, task: str, budget_s: int | None, data: dict[str, Any]) -> str:
    tools = data.get("tools") or {}
    r = int(tools.get("read", 0))
    w = int(tools.get("write", 0))
    e = int(tools.get("edit", 0))
    g = int(tools.get("glob", 0))
    b = int(tools.get("bash", 0))
    bm = int(tools.get("bash_mutate", 0))
    ttfw = data.get("time_to_first_write_s")
    elapsed = data.get("elapsed_s")
    budget = budget_s
    ttfw_pct = None
    budget_used = None
    if ttfw is not None and budget:
        ttfw_pct = 100.0 * ttfw / budget
    if elapsed is not None and budget:
        budget_used = f"{elapsed:.0f}/{budget}s ({100.0 * elapsed / budget:.0f}%)"
    elif elapsed is not None:
        budget_used = f"{elapsed:.0f}s (cap unknown)"

    delta = data.get("sensor_delta")
    if delta is None and data.get("sensor_before") is not None and data.get("sensor_after") is not None:
        delta = f"{data['sensor_before']}→{data['sensor_after']}"
    elif data.get("sensor_before") is not None and data.get("sensor_after") is None:
        delta = f"{data['sensor_before']}→?"

    lines = [
        f"**Seat ({role}):** `{task}` — events={data.get('events', 0)} json={data.get('json_bytes', 0)}B",
        f"**tools:** read={r} write={w} edit={e} glob={g} bash={b}"
        + (f" bash_mutate={bm}" if bm else ""),
    ]
    if ttfw is None:
        # O-MONSEATRESOLVE: do not scream "wedged" on a quiet/incomplete
        # artifact — that false-negative poisoned green M2/M3 runs (W4-258).
        if int(data.get("events") or 0) == 0:
            hint = " — no tool events in artifact yet (unresolved or not started)"
        elif r + g + b > 0 and w + e + bm == 0:
            hint = " — reads only so far (may still be exploring; not proven wedged)"
        else:
            hint = " — no mutate yet"
        lines.append(
            "**time_to_first_write:** none yet"
            + (f" / budget={budget}s" if budget else "")
            + hint
        )
    else:
        pct = f" ({ttfw_pct:.0f}% of budget)" if ttfw_pct is not None else ""
        lines.append(
            f"**time_to_first_write:** {ttfw:.0f}s{pct} via `{data.get('first_mutate_via') or '?'}`"
        )
    if budget_used:
        lines.append(f"**budget_used:** {budget_used}")
    rc = data.get("rc")
    sig = data.get("signal")
    killer = data.get("killer")
    if rc is not None or sig or killer:
        lines.append(
            f"**rc/signal/killer:** {rc if rc is not None else '—'} / {sig or '—'} / {killer or '—'}"
        )
    if data.get("sensor_delta") or delta:
        lines.append(f"**sensor_delta:** {data.get('sensor_delta') or delta}")
    if data.get("discarded"):
        lines.append(f"**discarded:** {data['discarded']}")
    refusals = list(data.get("guard_refusals") or []) + list(data.get("sup_guard_refusals") or [])
    if refusals:
        lines.append("**guard_refusals:** " + "; ".join(refusals[:4]))
    if data.get("escalation_cause"):
        lines.append(f"**escalation_cause:** {data['escalation_cause']}")
    if data.get("last_utterance"):
        lines.append(f"**last_utterance:** {data['last_utterance']}")
    # Derived efficiency one-liner
    mutate = w + e + bm
    if mutate == 0 and (r + g) >= 8:
        lines.append(
            f"**efficiency:** 0 mutates after {r}+{g} read/glob — high READ_THRASH / MiniMax-escalation risk"
        )
    elif ttfw is not None and budget and ttfw_pct is not None and ttfw_pct > 50:
        lines.append(
            f"**efficiency:** late first write ({ttfw_pct:.0f}% of budget) — slow-to-mutate seat"
        )
    elif mutate > 0 and ttfw is not None and ttfw < 60:
        lines.append("**efficiency:** early mutate (<60s) — productive seat shape")
    return "\n".join(lines)


def format_kv(data: dict[str, Any]) -> str:
    tools = data.get("tools") or {}
    rows = [
        f"events={data.get('events', 0)}",
        f"tools_read={tools.get('read', 0)}",
        f"tools_write={tools.get('write', 0)}",
        f"tools_edit={tools.get('edit', 0)}",
        f"tools_glob={tools.get('glob', 0)}",
        f"tools_bash={tools.get('bash', 0)}",
        f"ttfw_s={data.get('time_to_first_write_s')}",
        f"elapsed_s={data.get('elapsed_s')}",
        f"rc={data.get('rc')}",
        f"signal={data.get('signal')}",
        f"killer={data.get('killer')}",
        f"sensor_delta={data.get('sensor_delta')}",
    ]
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True, type=Path)
    ap.add_argument("--err", type=Path, default=None)
    ap.add_argument("--failure-sig", type=Path, default=None)
    ap.add_argument("--supervisor-snip", type=Path, default=None)
    ap.add_argument("--budget-s", type=int, default=None)
    ap.add_argument("--task", default="")
    ap.add_argument("--role", choices=("qwen", "hermes"), default="qwen")
    ap.add_argument("--format", choices=("md", "kv"), default="md")
    ap.add_argument("--sensor-after", default=None, help="GREEN|RED|count override")
    args = ap.parse_args()

    if not args.json.is_file():
        print(f"(no oc json: {args.json})", file=sys.stderr)
        return 1

    data = parse_oc_json(args.json)
    data.update(parse_err(args.err))
    fs = parse_failure_sig(args.failure_sig)
    data.update({k: v for k, v in fs.items() if v is not None})
    if args.supervisor_snip and args.supervisor_snip.is_file():
        snip = args.supervisor_snip.read_text(encoding="utf-8", errors="replace")
        task = args.task or "T"
        data.update(parse_supervisor_snip(snip, task))
    if args.sensor_after:
        data["sensor_after"] = args.sensor_after
        if data.get("sensor_before") is not None:
            data["sensor_delta"] = f"{data['sensor_before']}→{args.sensor_after}"

    task = args.task or Path(args.json).stem.replace("oc-", "")
    if args.format == "kv":
        print(format_kv(data))
    else:
        print(format_md(args.role, task, args.budget_s, data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
