#!/usr/bin/env python3
"""corpus_binding selftest: planning reads oracles only from a corpus bound to
THIS tree's evidence bundle and entry-point inventory (SYNTHETIC evidence).

1. A derived corpus whose receipt names this bundle, scenarios naming
   inventory entry points: no gap, the oracle map as before.
2. The bundle changed after derivation (a refreshed M1 structure): a named
   gap, _oracles is None (unknown), and plan_semantics' oracle input names the
   gap instead of "no captured scenario corpus".
3. A scenario naming an entry point the inventory no longer holds (v21: a
   classpath fix qualified 14 of 34 signatures): a named stale-binding gap.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/corpus_binding.test.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import outcome_checks as C  # noqa: E402
from planner import plan_semantics as PS  # noqa: E402
from planner.canonical import digest  # noqa: E402

EP = "ep:com.acme.shop.web.OrderApi#get(int):http"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def seed(root: Path, *, bound_to: str | None = None, entry_point: str = EP) -> None:
    (root / "evidence/planning").mkdir(parents=True, exist_ok=True)
    (root / "verification/scenarios").mkdir(parents=True, exist_ok=True)
    bundle = {"schema": "x", "entry_points": [{"id": EP}]}
    (root / "evidence/planning/evidence-bundle.json").write_text(json.dumps(bundle))
    (root / "evidence/entry-point-inventory.json").write_text(json.dumps({"entry_points": [{"entry_point_id": EP}]}))
    corpus = {"scenarios": [{"id": "sc:read-1", "entry_point": entry_point, "derived_from": {"entry_point": entry_point}}],
              "derived_from": {"bundle": "x"}}
    (root / "verification/scenarios/corpus.json").write_text(json.dumps(corpus))
    (root / "verification/scenarios/_derive.json").write_text(json.dumps(
        {"status": "ok", "evidence_bundle_sha256": bound_to if bound_to is not None else digest(bundle)}))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        ok = Path(tmp) / "ok"
        seed(ok)
        if C.corpus_binding_gaps(ok) or C._oracles(ok) != {EP: ["sc:read-1"]}:
            return _fail("a bound corpus must give its oracle map: %s %s" % (C.corpus_binding_gaps(ok), C._oracles(ok)))
        other = Path(tmp) / "other"
        seed(other, bound_to="0" * 64)
        gaps = C.corpus_binding_gaps(other)
        if len(gaps) != 1 or "not this tree's bundle" not in gaps[0] or C._oracles(other) is not None:
            return _fail("a corpus bound to another bundle must be a named gap and unknown oracles: %s" % gaps)
        comp = PS.input_components(other, bundle={"producers": {}}, decisions={}, oracles={}, oracles_known=False,
                                   oracle_gaps=gaps)["oracles"]
        if comp["complete"] or comp["unknowns"] != gaps:
            return _fail("the oracle input must name the binding gap: %s" % comp)
        stale = Path(tmp) / "stale"
        seed(stale, entry_point="ep:com.acme.shop.web.OrderApi#get(Integer):http")
        gaps = C.corpus_binding_gaps(stale)
        if len(gaps) != 1 or "stale binding" not in gaps[0] or C._oracles(stale) is not None:
            return _fail("a scenario bound to an entry point the inventory lacks must be a named gap: %s" % gaps)
        none = Path(tmp) / "none"
        none.mkdir()
        if C.corpus_binding_gaps(none) or C._oracles(none) is not None:
            return _fail("no corpus stays 'no corpus' (None, no gap)")
    print("OK: corpus binding (bound corpus maps oracles; another bundle and a stale entry point are named gaps and "
          "unknown oracles, never a silently partial map)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
