"""Behaviour coverage by scenario KIND (R-1; M-3 "the known-risk cases have actual executable tests ... report
unsupported cases explicitly").

The M-3 reference qualification covered one hand-picked path (Owner: no refused create, no referenced delete, no
create carrying an id) and so missed every class v31 met on the other entities. Coverage is derived from the run's OWN
corpus instead: every distinct (security mode, scenario kind, resource) the derivation produced is a coverage cell,
with one representative; a comparison of a candidate (the harness's own comparator, the lab or M4) answers each cell
PASS / FAIL / not compared. A cell nobody compared is listed, never assumed covered. Nothing here knows a specimen:
kinds are the derivation's ``derived_from.kind`` and resources the first segment after the API root.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any



def _layout() -> tuple[dict[str, Path], dict[str, Path]]:
    """(mode -> corpus, mode -> its comparison records), from the harness paths (planner.worklist)."""
    from planner.worklist import PARITY_SCENARIO_SUBDIRS, SCENARIO_CORPORA, SECURITY_MODES
    from planner.paths import PARITY_DIR
    return (dict(zip(SECURITY_MODES, SCENARIO_CORPORA)),
            {m: PARITY_DIR / sub for m, sub in zip(SECURITY_MODES, PARITY_SCENARIO_SUBDIRS)})


def resource(path: str) -> str:
    """The resource a request addresses: the first path segment that is not an API prefix or a template/number."""
    segs = [s for s in str(path or "").split("?", 1)[0].split("/") if s]
    for s in segs:
        if s.lower() in ("api", "v1", "v2", "rest") or s.startswith("{") or s.isdigit():
            continue
        return s
    return "(root)"


def cells(corpora: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str, str], list[str]]:
    """(mode, kind, resource) -> the scenario ids in that cell, sorted."""
    out: dict[tuple[str, str, str], list[str]] = {}
    for mode, scenarios in sorted(corpora.items()):
        for sc in scenarios or []:
            if not isinstance(sc, dict) or not sc.get("id"):
                continue
            kind = str((sc.get("derived_from") or {}).get("kind") or "unknown")
            out.setdefault((mode, kind, resource(str(sc.get("path") or ""))), []).append(str(sc["id"]))
    return {k: sorted(v) for k, v in out.items()}


def coverage(corpora: dict[str, list[dict[str, Any]]], verdicts: dict[str, dict[str, str]]) -> dict[str, Any]:
    """The coverage table: per cell its scenarios, representative and the verdicts compared; per kind the totals;
    the cells nobody compared. ``verdicts``: mode -> scenario id -> PASS | FAIL | INCONCLUSIVE."""
    rows, by_kind = [], {}
    for (mode, kind, res), ids in sorted(cells(corpora).items()):
        got = {sid: (verdicts.get(mode) or {}).get(sid) for sid in ids}
        compared = {s: v for s, v in got.items() if v}
        state = ("not-compared" if not compared else "FAIL" if any(v == "FAIL" for v in compared.values())
                 else "INCONCLUSIVE" if any(v != "PASS" for v in compared.values()) else "PASS")
        rows.append({"mode": mode, "kind": kind, "resource": res, "scenarios": ids, "representative": ids[0],
                     "compared": len(compared), "state": state,
                     "failing": sorted(s for s, v in compared.items() if v == "FAIL")})
        k = by_kind.setdefault("%s/%s" % (mode, kind), {"cells": 0, "PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "not-compared": 0})
        k["cells"] += 1
        k[state] += 1
    return {"schema": "rhoai3.rehearsal-coverage/v1", "cells": rows, "by_kind": by_kind,
            "uncovered": [r for r in rows if r["state"] == "not-compared"],
            "summary": {"cells": len(rows), "pass": sum(1 for r in rows if r["state"] == "PASS"),
                        "fail": sum(1 for r in rows if r["state"] == "FAIL"),
                        "not_compared": sum(1 for r in rows if r["state"] == "not-compared")}}


def of_root(root: Path) -> dict[str, Any]:
    """The coverage of the corpora and the comparison records under ``root``."""
    root = Path(root)
    corpus_of, records_of = _layout()
    corpora, verdicts = {}, {}
    for mode, rel in corpus_of.items():
        try:
            corpora[mode] = (json.loads((root / rel).read_text(encoding="utf-8")) or {}).get("scenarios") or []
        except (OSError, ValueError):
            continue
        verdicts[mode] = {}
        for f in sorted((root / records_of[mode]).glob("*.json")) if (root / records_of[mode]).is_dir() else []:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(doc, dict) and doc.get("scenario") and doc.get("verdict"):
                verdicts[mode][str(doc["scenario"])] = str(doc["verdict"])
    return coverage(corpora, verdicts)
