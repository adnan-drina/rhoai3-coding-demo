#!/usr/bin/env python3
"""AD-009 §3.3 / Deputy E-20260809T181500Z — prompt composition instrumentation.

Parse a Hermes kanban task log for per-call context estimates and emit a
JSON artifact under migration/derived/. Measures before further tuning.

Does not call the model. Offline over existing logs + optional hermes prompt-size.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CTX_RE = re.compile(
    r"Context:\s*(?P<msgs>\d+)\s*msgs,\s*~(?P<tokens>[\d,]+)\s*tokens",
    re.I,
)
WARN_RE = re.compile(
    r"context:\s*~(?P<tokens>[\d,]+)\s*tokens",
    re.I,
)
READ_RE = re.compile(r"\bread(?:_file)?\s+(\S+)", re.I)


def _int_commas(s: str) -> int:
    return int(s.replace(",", ""))


def parse_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    samples: list[dict] = []
    reads: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = CTX_RE.search(line)
        if m:
            samples.append(
                {
                    "line": i,
                    "msgs": int(m.group("msgs")),
                    "tokens_client": _int_commas(m.group("tokens")),
                    "kind": "elapsed_context",
                    "raw": line.strip()[:240],
                }
            )
            continue
        m = WARN_RE.search(line)
        if m and "No response from provider" in line:
            samples.append(
                {
                    "line": i,
                    "msgs": None,
                    "tokens_client": _int_commas(m.group("tokens")),
                    "kind": "stale_warn_context",
                    "raw": line.strip()[:240],
                }
            )
        for r in READ_RE.findall(line):
            if r.lower() in {"the", "this.", "a", "an", "file"}:
                continue
            reads.append(r)

    deltas: list[dict] = []
    prev = None
    for s in samples:
        tok = s["tokens_client"]
        if prev is not None:
            deltas.append(
                {
                    "from_line": prev["line"],
                    "to_line": s["line"],
                    "delta_tokens": tok - prev["tokens_client"],
                    "to_tokens": tok,
                }
            )
        prev = s

    from collections import Counter

    return {
        "log_path": str(path),
        "log_bytes": path.stat().st_size,
        "sample_count": len(samples),
        "samples": samples,
        "deltas": deltas,
        "peak_tokens_client": max((s["tokens_client"] for s in samples), default=None),
        "read_targets": dict(Counter(reads).most_common(40)),
        "mta_findings_mentions": text.lower().count("mta-findings"),
    }


def prompt_size_json() -> dict | None:
    try:
        out = subprocess.check_output(
            ["hermes", "prompt-size", "--json"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out[:4000]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/projects/modernized")
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--hermes-home",
        default="",
        help="Default: $HERMES_HOME or <root>/.hermes/home",
    )
    ap.add_argument("--include-prompt-size", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    import os

    hermes_home = Path(args.hermes_home) if args.hermes_home else None
    if hermes_home is None:
        env = os.environ.get("HERMES_HOME", "").strip()
        hermes_home = Path(env) if env else root / ".hermes" / "home"

    log = hermes_home / "kanban" / "logs" / f"{args.task_id}.log"
    if not log.is_file():
        print(f"audit-prompt-composition: missing log {log}", flush=True)
        return 1

    report = {
        "schema": "rhoai3.prompt-composition/v1",
        "ad": "AD-009",
        "task_id": args.task_id,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Measure per-call client context estimates + deltas before further "
            "context-budget tuning (Deputy E-20260809T181500Z)"
        ),
        "log": parse_log(log),
    }
    if args.include_prompt_size:
        report["fixed_prompt_budget"] = prompt_size_json()

    out_dir = root / "migration" / "derived"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"prompt-composition-{args.task_id}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    peak = report["log"]["peak_tokens_client"]
    print(
        f"audit-prompt-composition: wrote {out} "
        f"samples={report['log']['sample_count']} peak_tokens_client={peak}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
