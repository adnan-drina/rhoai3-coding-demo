"""Live-board comparator (K3, SAD v3 §8).

Before dispatch, the native Hermes board must equal the loop's expected
card set: every accepted step's card (from verification/loop/steps.json)
and the one open head card (or M4 VERIFY), each under its receipt-bound
key, with the recorded parent edges; no foreign cards; no missing cards.
Input is a board snapshot (``hermes kanban list --json`` enriched with
``show``), never a worker's claim.

Provenance is never inferred from a title or a body. A card is matched
only through a native idempotency key, or through the task-id → key
mapping K4 captured from its own create responses
(``evidence/receipts/k4/mint.json``). A card with neither is foreign.
"""
from __future__ import annotations

import json
from typing import Any

RECEIPT_STEM = 16


def enrich_card(card: dict[str, Any], detail: dict[str, Any] | None) -> dict[str, Any]:
    """One listed row plus what ``hermes kanban show --json`` adds.

    That payload keeps the EDGES BESIDE the task -- ``{"task": {...},
    "parents": [...], "children": [...]}`` -- so a task-only merge sees no
    parents at all. Measured twice: pilot v6 failed K4_BOARD this way, and on
    dest v8 (2026-09-12) the K3 path still had the task-only merge, so every
    card came back parentless and all nineteen edges "mismatched" while the
    board was in fact correct. Two copies of one merge; only one was fixed.
    This is now the only copy."""
    if not isinstance(detail, dict):
        return dict(card)
    merged = dict(card)
    task = detail.get("task")
    merged.update(task if isinstance(task, dict) else detail)
    for key in ("parents", "children"):
        if key not in merged and isinstance(detail.get(key), list):
            merged[key] = detail[key]
    return merged


def collect_board(run: Any, hermes: str = "hermes") -> list[dict[str, Any]]:
    """The live board as the comparator needs it: ``kanban list --json``, each
    row enriched with ``kanban show --json``.

    ``run(argv) -> (code, stdout, stderr)`` is the caller's own runner, so K3
    and K4 share this collection without sharing a subprocess policy. A
    listing that fails raises; a row whose ``show`` fails is kept as listed
    (it simply carries no edges, which the comparator then reports)."""
    code, out, err = run([hermes, "kanban", "list", "--json"])
    if code != 0:
        raise ValueError("hermes kanban list --json exit %s: %s" % (code, (err or "").strip()[:200]))
    cards: list[dict[str, Any]] = []
    for card in parse_snapshot(json.loads(out)):
        cid = _card_id(card)
        if not cid:
            continue
        code, out, _ = run([hermes, "kanban", "show", cid, "--json"])
        detail: dict[str, Any] | None = None
        if code == 0:
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = None
            detail = parsed if isinstance(parsed, dict) else None
        cards.append(enrich_card(card, detail))
    return cards


def _card_id(card: dict[str, Any]) -> str:
    for k in ("id", "task_id"):
        v = card.get(k)
        if v:
            return str(v)
    return ""


def _card_parents(card: dict[str, Any]) -> list[str]:
    for k in ("parents", "parent_ids", "depends_on", "blocked_by"):
        v = card.get(k)
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                if isinstance(item, dict):
                    pid = item.get("id") or item.get("task_id") or item.get("parent_id")
                    if pid:
                        out.append(str(pid))
                elif item:
                    out.append(str(item))
            return sorted(set(out))
    single = card.get("parent_id") or card.get("parent")
    if isinstance(single, str) and single:
        return [single]
    return []


def _native_key(card: dict[str, Any]) -> str:
    for k in ("idempotency_key", "idempotencyKey"):
        v = card.get(k)
        if v:
            return str(v)
    return ""


def mint_map_from_receipts(mints: list[dict[str, Any]]) -> dict[str, str]:
    """task_id → idempotency_key from every K4 mint receipt of this run."""
    out: dict[str, str] = {}
    for mint in mints:
        if not isinstance(mint, dict):
            continue
        for row in mint.get("created") or []:
            if isinstance(row, dict) and row.get("task_id") and row.get("idempotency_key"):
                out[str(row["task_id"])] = str(row["idempotency_key"])
    return out


def exempt_closure(cards: list[dict[str, Any]], exempt_ids: list[str]) -> set[str]:
    by_id = {_card_id(c): c for c in cards if _card_id(c)}
    out: set[str] = set(e for e in exempt_ids if e)
    stack = list(out)
    while stack:
        cid = stack.pop()
        for p in _card_parents(by_id.get(cid, {})):
            if p not in out:
                out.add(p)
                stack.append(p)
    return out


def expected_from_loop(steps: dict[str, Any] | None, open_card: dict[str, Any] | None, mint_keys: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Expected cards: accepted steps (key from the mint receipts by task id)
    plus the open card. Each entry: {key, parents(keys of expected), status}."""
    out: dict[str, dict[str, Any]] = {}
    prev_key = ""
    for st in (steps or {}).get("steps") or []:
        tid = str(st.get("card") or "")
        key = mint_keys.get(tid, "")
        if not tid or not key:
            continue  # the bootstrap baseline has no card
        out[key] = {"key": key, "parents": [prev_key] if prev_key else [], "status": "done", "task_id": tid, "cluster": st.get("cluster")}
        prev_key = key
    for st in (steps or {}).get("rejected") or []:
        # a reverted attempt's card stays on the board (review/done/archived);
        # it is an expected, closed card, never foreign (pilot v6 measured
        # --verify-board calling the reverted attempt-1 card foreign)
        tid = str(st.get("card") or "")
        key = mint_keys.get(tid, "")
        if tid and key and key not in out:
            out[key] = {"key": key, "parents": [], "status": "closed", "task_id": tid, "cluster": st.get("cluster")}
    if open_card:
        key = str(open_card["idempotency_key"])
        out[key] = {"key": key, "parents": [prev_key] if prev_key else [], "status": "open", "task_id": "", "cluster": open_card.get("logical_id")}
    return out


def compare_board(expected: dict[str, dict[str, Any]], cards: list[dict[str, Any]], *, exempt_ids: list[str] | None = None, mint_map: dict[str, str] | None = None) -> dict[str, Any]:
    exempt = exempt_closure(cards, list(exempt_ids or []))
    mint_map = dict(mint_map or {})
    by_key: dict[str, dict[str, Any]] = {}
    foreign: list[str] = []
    archived: list[str] = []
    for card in cards:
        cid = _card_id(card)
        if cid in exempt:
            continue
        if str(card.get("status") or "") == "archived":
            archived.append(cid)
            continue
        key = _native_key(card)
        via = "native-key"
        if not key and cid in mint_map:
            key, via = mint_map[cid], "k4-mint-receipt"
        if key and key in expected:
            if key in by_key:
                foreign.append("%s (duplicate key %s)" % (cid, key))
            else:
                by_key[key] = dict(card, _matched_via=via)
        elif key:
            foreign.append("%s (key %s is not in the expected set)" % (cid, key))
        else:
            foreign.append("%s (no idempotency key and not in the K4 mint receipts)" % cid)
    missing = sorted(k for k in expected if k not in by_key and expected[k].get("status") != "closed")  # a closed attempt may be archived
    id_of_key = {k: _card_id(c) for k, c in by_key.items()}
    edge_gaps: list[str] = []
    for key, exp in expected.items():
        if key not in by_key or exp.get("status") == "closed":
            continue  # a closed (rejected) attempt keeps whatever parents it was minted with
        want = sorted(id_of_key[p] for p in exp["parents"] if p in id_of_key)
        got = sorted(p for p in _card_parents(by_key[key]) if p not in exempt)
        if got != want:
            edge_gaps.append("%s parents %s != expected %s" % (key, got, want))
    ok = not missing and not foreign and not edge_gaps
    return {
        "verdict": "EQUAL" if ok else "MISMATCH",
        "expected_cards": len(expected),
        "matched_cards": len(by_key),
        "matched_via": {k: by_key[k]["_matched_via"] for k in sorted(by_key)},
        "missing_keys": missing,
        "foreign_cards": sorted(foreign),
        "edge_gaps": sorted(edge_gaps),
        "archived_ignored": sorted(archived),
        "exempt_closure": sorted(exempt),
        "claimed_control": False,
    }


def parse_snapshot(blob: Any) -> list[dict[str, Any]]:
    if isinstance(blob, list):
        return [c for c in blob if isinstance(c, dict)]
    if isinstance(blob, dict):
        for k in ("tasks", "cards", "items", "results"):
            if isinstance(blob.get(k), list):
                return [c for c in blob[k] if isinstance(c, dict)]
    raise ValueError("board snapshot must be a list or {tasks|cards|items: [...]}")
