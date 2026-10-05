"""Read-only resolution of a check-schedule qualification id to its evidence.

check-schedule/v1 (compatibility_objectives.schedule_checks) names, for every
repository-effects check, the focused M-3 qualification that covers the
repository contract before any package exists:
``qualify:repository-contract:<fragment>``. This module binds that id to the
real M-3 test (skills/migration/fix-until-green/scripts/
reference-repository-strategy-runtime.test.py) and to the results document
its runner writes (reference-qualification.sh, schema
rhoai3.reference-qualification-results/v1).

It is evidence CONSUMPTION only: it never runs the test (it needs podman,
PostgreSQL 16 and the candidate bundle, none of which a workspace has), never
writes, and never feeds acceptance. The measured check on the running
application stays the only acceptance authority. What it cannot resolve is
``unknown`` with the missing input named -- never a pass.

The test's covered fragment is read from its own module constants
(``TEST_ID``, ``REL``) with ``ast`` -- the file is not executed -- so the
binding follows the test, not a copy of it.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

PREFIX = "qualify:repository-contract:"
RESULTS_SCHEMA = "rhoai3.reference-qualification-results/v1"
# where a workspace keeps a copied runner result, relative to the destination root
RESULTS = Path("evidence") / "qualification" / "reference-qualification" / "results.json"
SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "migration" / "fix-until-green" / "scripts"
STRATEGY_TEST = "reference-repository-strategy-runtime.test.py"
RUNNER = "reference-qualification.sh"
AUTHORITY = ("evidence only: a component qualification of the repository strategy on the reference candidate; "
             "acceptance stays with the measured check on the running application")
STATES = ("qualified", "failed", "unknown")


def _constants(path: Path) -> dict[str, str]:
    """The module-level string constants of a test file, without running it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                val = ast.literal_eval(node.value)
            except ValueError:
                continue
            if isinstance(val, str):
                out[node.targets[0].id] = val
    return out


def covered_fragment(scripts: Path = SCRIPTS) -> tuple[str, str]:
    """(test id, the repository fragment FQN the strategy test qualifies) or
    ('', '') when the test or its constants are missing. ``REL`` is the
    fragment's implementation source (``.../<Fragment>Impl.java``)."""
    c = _constants(Path(scripts) / STRATEGY_TEST)
    rel, tid = c.get("REL", ""), c.get("TEST_ID", "")
    marker = "src/main/java/"
    if not tid or not rel.startswith(marker) or not rel.endswith("Impl.java"):
        return "", ""
    return tid, rel[len(marker):-len("Impl.java")].replace("/", ".")


def resolve(qid: str, root: Path | None = None, *, tree: str = "", results: Path | None = None,
            scripts: Path = SCRIPTS) -> dict[str, Any]:
    """{"id", "status": qualified|failed|unknown, "test", "missing", "evidence",
    "authority"} for one qualification id. ``results`` defaults to RESULTS
    under ``root``; ``tree`` (the candidate being judged) says whether the
    results' measured candidate is this one (``candidate_bound``)."""
    out: dict[str, Any] = {"id": qid, "status": "unknown", "test": "", "missing": [], "evidence": {}, "authority": AUTHORITY}
    if not str(qid).startswith(PREFIX):
        out["missing"] = ["a qualification id of the form %s<fragment>" % PREFIX]
        return out
    fragment = str(qid)[len(PREFIX):]
    tid, covered = covered_fragment(scripts)
    if not tid:
        out["missing"] = ["the M-3 strategy test %s (or its TEST_ID/REL constants)" % STRATEGY_TEST]
        return out
    if covered != fragment:
        out["missing"] = ["a reference qualification of %s: %s covers only %s" % (fragment, tid, covered)]
        return out
    out["test"] = ".hermes/skills/migration/fix-until-green/scripts/%s" % STRATEGY_TEST
    path = Path(results) if results is not None else (Path(root) / RESULTS if root is not None else None)
    if path is None or not path.is_file():
        out["missing"] = ["the %s results at %s (the suite needs podman, PostgreSQL 16 and the candidate bundle; it does "
                          "not run inside the workspace)" % (RUNNER, (path.as_posix() if path is not None else RESULTS.as_posix()))]
        return out
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out["missing"] = ["readable %s results (%s)" % (RUNNER, exc)]
        return out
    if not isinstance(doc, dict) or doc.get("schema") != RESULTS_SCHEMA:
        out["missing"] = ["%s results of schema %s" % (RUNNER, RESULTS_SCHEMA)]
        return out
    suite = next((s for s in doc.get("suites") or [] if isinstance(s, dict) and s.get("test_id") == tid), None)
    if suite is None:
        out["missing"] = ["a %s row in the %s results" % (tid, RUNNER)]
        return out
    outcome = str(suite.get("outcome") or "")
    rows = [c for c in doc.get("cases") or [] if isinstance(c, dict) and str(c.get("test_id") or "").startswith(tid + "::")]
    trees = sorted({str((c.get("artifact") or {}).get("candidate_tree") or "") for c in rows} - {""})
    out["evidence"] = {"results": path.as_posix(), "suite_outcome": outcome, "summary": str(suite.get("summary") or "")[:300],
                       "cases": {str(c.get("case")): str(c.get("outcome")) for c in rows},
                       "candidate_trees": trees, "candidate_bound": bool(tree) and trees == [tree]}
    if outcome == "PASS":
        out["status"] = "qualified"
    elif outcome in ("FAIL", "TIMEOUT"):
        out["status"] = "failed"
    else:
        out["missing"] = ["an executed %s (outcome %s: %s)" % (tid, outcome or "none",
                                                              str(suite.get("reason") or suite.get("summary") or "")[:200])]
    return out
