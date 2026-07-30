#!/usr/bin/env python3
"""Build an OpenCode task packet from tasks.md (V7 model routing + K2 evidence).

Prints a single packet string on stdout for:
  opencode run "<packet>" -m <worker> ...

Used by supervisor.sh so mechanical rewrite/infer coding runs on the
worker (Qwen) without MiniMax applying file edits directly.

K2: when migration/mta-findings.json is available, inject a bounded
Analysis evidence section (rule message + file:line + code snip) so the
worker sees MTA remediation guidance, not bare Findings ids.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# K2 — mandatory hard caps (64K worker context). Tune only with A/B evidence.
MAX_EVIDENCE_INCIDENTS = 6
MAX_EVIDENCE_CHARS = 400  # per message OR code field
# Combined message+code budget across the whole evidence section (K2-CAP):
# equals "≤6 incidents × ≤400 chars" as documented — not 6×(400+400).
MAX_EVIDENCE_CONTENT_CHARS = MAX_EVIDENCE_INCIDENTS * MAX_EVIDENCE_CHARS


def task_block(text: str, tid: str) -> tuple[str, str]:
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return title, text[start:end].strip()
    return "", ""


def field(body: str, *names: str) -> str:
    for name in names:
        m = re.search(
            rf"^\*\*{re.escape(name)}\*\*\s*:?\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
        m = re.search(
            rf"^{re.escape(name)}\s*:\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
    return ""


def parse_finding_ids(findings_field: str) -> list[str]:
    """Split a Findings: field into rule-id tokens (skip placeholders)."""
    if not findings_field:
        return []
    raw = findings_field.strip()
    if raw.startswith("(") or raw.lower() in {"n/a", "none", "-", "see tasks.md"}:
        return []
    parts = re.split(r"[,;\s]+", raw)
    out: list[str] = []
    for p in parts:
        p = p.strip().strip("`")
        if not p or p.startswith("("):
            continue
        # Drop prose glue words that sometimes appear in Findings lines
        if p.lower() in {"and", "or", "see", "tasks.md", "findings"}:
            continue
        out.append(p)
    return out


def resolve_findings_path(tasks_path: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    candidates = [
        Path("migration/mta-findings.json"),
        tasks_path.resolve().parent / "migration" / "mta-findings.json",
        tasks_path.resolve().parent.parent / "migration" / "mta-findings.json",
        tasks_path.resolve().parent.parent.parent / "migration" / "mta-findings.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _uri_display(uri: str) -> str:
    u = (uri or "?").replace("file:///", "/").replace("file://", "")
    # Prefer a repo-relative-looking tail when absolute
    for marker in ("/src/", "/projects/legacy/", "/projects/modernized/"):
        i = u.find(marker)
        if i >= 0:
            if marker == "/src/":
                return u[i + 1 :]  # src/...
            return u[i + len(marker) :]
    return u


def _trim(s: str, n: int = MAX_EVIDENCE_CHARS) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _rule_matches(rid: str, wanted: list[str]) -> bool:
    """Exact → prefix → guarded substring (K2-MATCH). No bare `w in rid`.

    Prefix/substring require a rule-id-shaped token (contains '-'): prose
    like `springboot` must not pull `springboot-web-to-quarkus-*`.
    """
    for w in wanted:
        if rid == w:
            return True
    for w in wanted:
        if "-" in w and len(w) >= 8 and rid.startswith(w):
            return True
    for w in wanted:
        if "-" in w and len(w) >= 12 and w in rid:
            return True
    return False


def _inc_dict(rid: str, desc: str, inc: dict) -> dict:
    msg = (inc.get("message") or desc or "").strip()
    snip = (inc.get("codeSnip") or inc.get("code") or "").strip()
    return {
        "rule": rid,
        "uri": _uri_display(str(inc.get("uri") or "?")),
        "line": str(inc.get("lineNumber") or "?"),
        "message": msg,
        "code": snip,
    }


def collect_evidence(findings_path: Path, wanted: list[str]) -> list[dict]:
    """Return up to MAX_EVIDENCE_INCIDENTS incidents (K2-RR: round-robin)."""
    if not wanted:
        return []
    try:
        data = json.loads(findings_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    # Preserve Findings-field order: group incidents per matched rule.
    by_rule: dict[str, list[dict]] = {}
    order: list[str] = []
    for rs in data:
        if not isinstance(rs, dict):
            continue
        for rid, v in (rs.get("violations") or {}).items():
            if not _rule_matches(rid, wanted):
                continue
            desc = (v.get("description") or "").strip()
            bucket = by_rule.setdefault(rid, [])
            if rid not in order:
                order.append(rid)
            for inc in v.get("incidents") or []:
                if isinstance(inc, dict):
                    bucket.append(_inc_dict(rid, desc, inc))

    # Prefer order of tokens in the Findings field when possible.
    preferred: list[str] = []
    for w in wanted:
        for rid in order:
            if rid not in preferred and _rule_matches(rid, [w]):
                preferred.append(rid)
    for rid in order:
        if rid not in preferred:
            preferred.append(rid)

    cursors = {rid: 0 for rid in preferred}
    hits: list[dict] = []
    # Round 1+: one incident per rule per pass until cap (K2-RR).
    while len(hits) < MAX_EVIDENCE_INCIDENTS:
        progressed = False
        for rid in preferred:
            if len(hits) >= MAX_EVIDENCE_INCIDENTS:
                break
            bucket = by_rule.get(rid) or []
            i = cursors[rid]
            if i < len(bucket):
                hits.append(bucket[i])
                cursors[rid] = i + 1
                progressed = True
        if not progressed:
            break
    return hits


def format_evidence(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = [
        "Analysis evidence (from MTA — the authoritative description of the problem):"
    ]
    content_used = 0
    for h in hits:
        lines.append(f"- {h['rule']} at {h['uri']}: line {h['line']}")
        msg = _trim(h["message"]) if h["message"] else ""
        code = _trim(h["code"]) if h["code"] else ""
        # K2-CAP: combined message+code budget across the section.
        for label, chunk in (("message", msg), ("code", code)):
            if not chunk:
                continue
            room = MAX_EVIDENCE_CONTENT_CHARS - content_used
            if room <= 0:
                break
            if len(chunk) > room:
                chunk = chunk[: max(0, room - 1)].rstrip() + "…"
            lines.append(f"  {label}: {chunk}")
            content_used += len(chunk)
        if content_used >= MAX_EVIDENCE_CONTENT_CHARS:
            break
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: task-packet.py <tasks.md> <T-xxx> [worker-model] [mta-findings.json]",
            file=sys.stderr,
        )
        return 2
    path, tid = sys.argv[1], sys.argv[2]
    worker = sys.argv[3] if len(sys.argv) > 3 else "qwen27b/qwen3-6-27b"
    # Optional 4th arg is findings path; if argv[3] looks like a json path, treat as findings
    findings_arg: str | None = None
    if len(sys.argv) > 4:
        findings_arg = sys.argv[4]
    elif len(sys.argv) > 3 and sys.argv[3].endswith(".json"):
        worker = "qwen27b/qwen3-6-27b"
        findings_arg = sys.argv[3]

    tasks_path = Path(path)
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    title, body = task_block(text, tid)
    if not body:
        print(f"FATAL: task {tid} not found in {path}", file=sys.stderr)
        return 1
    cls = field(body, "Class", "Type") or "infer"
    cls_m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    cls = cls_m.group(1).lower() if cls_m else "infer"
    goal = field(body, "Goal") or title
    findings = field(body, "Findings") or "(see tasks.md)"
    acceptance = field(body, "Acceptance") or "mvn -q clean test passes; commit ready"
    # Keep packet bounded — full body is attached via -f tasks.md
    design = ""
    for label in ("Target design", "Target Design", "Target", "Design"):
        chunk = field(body, label)
        if chunk:
            design = chunk
            break
    if not design:
        # First 1200 chars of body as design context
        design = re.sub(r"\s+", " ", body)[:1200]

    # O-TGTNAME: extract destination .java basenames from the task body so the
    # worker cannot invent CartResource when the plan says CartEndpoint.
    dest_names = sorted(
        {
            Path(m).name
            for m in re.findall(
                r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java", f"{title}\n{body}"
            )
        }
    )
    dest_line = (
        f"- Target destination basename(s) are MANDATORY: {', '.join(dest_names)} "
        f"— create/edit exactly those file names (O-TGTNAME; never rename "
        f"Endpoint→Resource or invent alternate class names)"
        if dest_names
        else "- When Target design names a destination .java path, use that exact basename"
    )

    evidence_block = ""
    fpath = resolve_findings_path(tasks_path, findings_arg)
    if fpath is not None:
        wanted = parse_finding_ids(findings)
        evidence_block = format_evidence(collect_evidence(fpath, wanted))

    evidence_section = f"\n{evidence_block}\n" if evidence_block else "\n"

    packet = f"""Task ID: {tid}
Class: {cls}
Goal: {goal}
Findings: {findings}{evidence_section}Target Design: {design}
Constraints:
- Follow AGENTS.md and the repo skills; no scope creep
- Package rename is full legacyPackage → targetPackage prefix replace (never invent targetPackage.coolstore)
{dest_line}
- Never git add or commit .hermes/ or migration/staging/ (harness/runtime only; O-HERMNEST)
- For Class rewrite: use .hermes/skills/migration-harness/scripts/harvest-from-staging.sh for harvests; do not re-run OpenRewrite
- Worker model for this run is {worker}
Inputs: tasks.md (attached), AGENTS.md (attached), migration/staging when harvesting
Acceptance: {acceptance}
Out of scope: do not push; do not start other tasks; finish with changes ready for a commit whose message STARTS with '{tid}:'
"""
    print(packet.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
