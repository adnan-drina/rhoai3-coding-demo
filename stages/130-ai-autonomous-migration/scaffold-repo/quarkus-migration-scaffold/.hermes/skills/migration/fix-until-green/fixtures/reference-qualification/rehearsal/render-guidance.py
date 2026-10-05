#!/usr/bin/env python3
"""Render, through the harness's own functions, the guidance each rehearsal
step implements (rehearsal.json), so the patches can be read against the text
a worker receives -- not against a paraphrase.

  render-guidance.py --root <tree> [--out rendered-guidance.json]

<tree> is the rehearsal base (candidate 70f2c9f3) with v28's frozen M1/M2
evidence unpacked (evidence/structure, evidence/planning, and
.derived/frozen-input/pom.xml from v28-frozen-evidence.tgz), THIS harness's
.hermes in place of the tree's own (a run reads the golden .hermes; the
v28 tree carries v28's older one), and the rehearsal work list at
evidence/planning/worklist.json (the PARITY_CORS / PARITY_CONTENT_TYPE items
typed from the M-3 differences). REHEARSAL evidence: not a run's brief.

Each entry says which harness function rendered it; where the harness cannot
render the unit's text from what this tree holds, the entry says why and gives
the catalog row it would render. Python 3.9 compatible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = next(p for p in HERE.parents if (p / "lib" / ".hermes-lib").is_file())
sys.path.insert(0, str(HERMES / "lib"))
sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))

import response_adapters as ra  # noqa: E402
from planner import static_triggers as st  # noqa: E402


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cat_here = HERMES / "planning" / "catalogs" / "compat-mapping.json"
    cat_root = root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
    if not cat_root.is_file() or _sha(cat_root) != _sha(cat_here):
        print("REFUSE: %s does not carry this harness's compat-mapping.json (sha256 %s)" % (root, _sha(cat_here)[:12]),
              file=sys.stderr)
        return 1
    import brief  # noqa: E402  (after the path check: brief reads <root>/.hermes)
    catalog = json.loads(cat_here.read_text(encoding="utf-8"))
    bundle = json.loads((root / "evidence" / "planning" / "evidence-bundle.json").read_text(encoding="utf-8"))
    wl = json.loads((root / "evidence" / "planning" / "worklist.json").read_text(encoding="utf-8"))
    rep = [d for it in wl.get("items") or [] if it.get("rule_id") == "PARITY_CONTENT_TYPE"
           for d in (it.get("owed") or {}).get("differences") or []]
    cors_rows, cors_basis = ra.rows_for(root, ra.CORS)
    decision = ra.media_type_decision(rep)
    rro, rro_notes = st.required_read_only_items(root, bundle)
    vh = catalog["validation_helpers"]["org.springframework.validation.BindingResult"]
    adv = catalog["exception_advice"]["request-body-unreadable"]
    out = {
        "schema": "rhoai3.reference-rehearsal-guidance/v1",
        "label": "REHEARSAL (not a migration output, not a run result)",
        "harness_catalog_sha256": _sha(cat_here),
        "steps": {
            "R1": {"rendered_by": "response_adapters.contract + rows_for (install-response-adapter.py --print)",
                   "owed": ra.contract(ra.CORS), "rows": len(cors_rows),
                   "source_policies": cors_basis.get("source_policies"), "security": cors_basis.get("security")},
            "R2": {"rendered_by": "response_adapters.media_type_decision over the rehearsal PARITY_CONTENT_TYPE items",
                   "owed": ra.contract(ra.MEDIA_TYPE), "decision": decision,
                   "rows": ra.media_type_properties(decision)},
            "R3": {"rendered_by": "brief.absent_result_semantics (the line a fragment card's brief carries)",
                   "text": brief.absent_result_semantics(root),
                   "check": "static_triggers.absent_result_verdict (needs the destination compiler model; not rendered here)"},
            "R4": {"rendered_by": "compat-mapping validation_helpers (the planner renders the row at a member taking the type)",
                   "action": vh["action"], "getObjectName": vh["mapping"]["getObjectName()"], "object_name": vh["object_name"]},
            "R5": {"rendered_by": "static_triggers.required_read_only_items (plan:gbro, its first_action)",
                   "items": [{"id": i["id"], "path": i["path"], "cases": i["planned"]["cases"],
                              "first_action": i["advice"]["first_action"]} for i in rro], "notes": rro_notes},
            "R6": {"rendered_by": "compat-mapping exception_advice.request-body-unreadable (brief.advice_guidance renders "
                                  "this row when the card's SOURCE capture is the advice's 400; the v28 frozen evidence "
                                  "holds no verification/source-oracles, so the selection is not re-run here)",
                   "action": adv["action"], "source_semantics": adv["source_semantics"]},
        },
    }
    text = json.dumps(out, indent=1, sort_keys=True) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
