"""Why a native worker run ended, classified (M-5, MIGRATION-IMPROVEMENTS.md; v31).

A stop is a product outcome, a harness inconsistency, a source qualification, a provider/runtime availability problem
or a worker crash -- and they need different responses. v31 had 10 runs blocked on ISSUE_BASELINE_DRIFT (one crashed
card's leftovers stranding the others, H-15), 6 crashes and a timeout, which an outcome count reads as product
failures. Classification reads only the native run row (outcome, status, summary, error); a reason it cannot place is
``unclassified`` with the text kept, never folded into another class.

Classes:
  completed            the run handed off (completed / review_requested)
  review-rework        the reviewer asked for changes (spends the family budget, by native semantics)
  dependency-wait      a routed wait (OWNER_REPAIR_PENDING): not a failure, spends nothing
  harness-refusal      a typed harness/control refusal (baseline drift, release mismatch, plan or record contract ...)
  source-qualification the source evidence could not decide (capture, oracle, corpus)
  provider             the model provider or runtime was unavailable (rate limit, stream, gateway)
  worker-blocked       the worker blocked with its own diagnosis (its stop rule, a write set that cannot reach the
                       evidenced failure); the text is the evidence
  worker-crash         the worker ended without a terminal call: tool-loop stop, protocol violation, timeout, gave up
  operator             an Operator reclaim
  unclassified         anything else, named
"""
from __future__ import annotations

import re
from typing import Any, Iterable

HARNESS_CODES = ("ISSUE_BASELINE_DRIFT", "HARNESS_RELEASE_MISMATCH", "RUN_CONTROL_", "ACCEPTANCE_CYCLE", "PLAN_",
                 "RECORD_EVIDENCE_MISMATCH", "VERIFICATION_PENDING", "BLOCK_LEAVES_CANDIDATE", "PARK_INCOMPLETE",
                 "ISSUE_", "ACCEPT_", "UNPLANNED_SOURCE_COMPONENT", "CARD_PRESENTATION_REPINNED", "ADAPTER_UNRENDERABLE",
                 "LOOP_", "HERMES_RUNTIME_", "STAGE_EVIDENCE_")
SOURCE_CODES = ("SOURCE_", "CAPTURE_", "ORACLE_", "CORPUS_", "SCENARIO_PARITY", "QUALIFICATION_")
WAIT_CODES = ("OWNER_REPAIR_PENDING",)
PROVIDER_RE = re.compile(r"\b(429|rate[ _-]?limit|too many requests|stream (?:stale|stalled)|upstream|bad gateway|"
                         r"gateway timeout|service unavailable|connection (?:reset|refused)|read timed out)\b", re.I)
CODE_RE = re.compile(r"^\s*(?:native_gate\.py issue refused:\s*)?([A-Z][A-Z0-9_]{3,})\b")
WRITE_SET_RE = re.compile(r"(write set|outside (?:this|the) card|cannot be (?:repaired|satisfied) (?:within|through))", re.I)


def _starts(code: str, prefixes: Iterable[str]) -> bool:
    return any(code == p or (p.endswith("_") and code.startswith(p)) for p in prefixes)


def classify(row: dict[str, Any]) -> dict[str, str]:
    """{"class", "subtype", "code", "detail"} for one native run row (keys: outcome, status, summary, error)."""
    outcome = str(row.get("outcome") or row.get("status") or "")
    text = str(row.get("error") or row.get("summary") or "").strip()
    m = CODE_RE.match(text)
    code = m.group(1) if m else ""
    detail = " ".join(text.split())[:240]

    def out(cls: str, subtype: str = "") -> dict[str, str]:
        return {"class": cls, "subtype": subtype, "code": code, "detail": detail}

    if outcome in ("completed", "review_requested"):
        return out("completed")
    if outcome == "changes_requested":
        return out("review-rework")
    if outcome == "reclaimed" or text.startswith("manual_reclaim"):
        return out("operator", "reclaim")
    if outcome == "rate_limited" or (PROVIDER_RE.search(text) and outcome in ("crashed", "gave_up", "timed_out", "failed")):
        return out("provider")
    if outcome in ("crashed", "gave_up", "timed_out"):
        if "WORKER_TOOL_LOOP" in text:
            return out("worker-crash", "tool-loop")
        if "protocol violation" in text or "without calling kanban_complete or kanban_block" in text:
            return out("worker-crash", "protocol")
        if outcome == "timed_out" or re.search(r"elapsed \d+s > limit", text):
            return out("worker-crash", "timeout")
        return out("worker-crash", outcome)
    if outcome == "blocked":
        if code and _starts(code, WAIT_CODES):
            return out("dependency-wait")
        if code and _starts(code, SOURCE_CODES):
            return out("source-qualification")
        if code and _starts(code, HARNESS_CODES):
            return out("harness-refusal", code)
        if code == "STOP" and "WORKER_TOOL_LOOP" in text:
            return out("worker-crash", "tool-loop")
        if WRITE_SET_RE.search(text):
            return out("worker-blocked", "scope")
        if text:
            return out("worker-blocked", "diagnosis")
    if not outcome or outcome == "running":
        return out("running")
    return out("unclassified", outcome)


def summarize(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """{"by_class": {class: {"count", "runs": [...]}}, "by_subtype": {...}} over run rows carrying id and task_id."""
    by_class: dict[str, dict[str, Any]] = {}
    by_sub: dict[str, int] = {}
    for r in rows:
        c = classify(r)
        if c["class"] == "running":
            continue
        ent = by_class.setdefault(c["class"], {"count": 0, "runs": []})
        ent["count"] += 1
        ent["runs"].append("%s/run %s%s" % (r.get("task_id"), r.get("id"), (" " + c["subtype"]) if c["subtype"] else ""))
        if c["subtype"]:
            k = "%s/%s" % (c["class"], c["subtype"])
            by_sub[k] = by_sub.get(k, 0) + 1
    return {"by_class": dict(sorted(by_class.items())), "by_subtype": dict(sorted(by_sub.items()))}
