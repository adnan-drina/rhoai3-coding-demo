#!/usr/bin/env python3
"""Producer bar: dest-8 six cards REFUSE M2 and M4; increment kinds pass with their defaults."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k4_producers import DEST8_FIXTURE, KIND_DEFAULTS, PRODUCERS, card_from_payload, check_cards, load_cards, producer_issues  # noqa: E402

SCRIPT = KERNEL / "k4_producers.py"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    cards = load_cards(DEST8_FIXTURE)
    lids = [c["logical_id"] for c in cards]
    if lids != ["M1", "M2", "T001", "T002", "STAMP_DESTINATION_TREE", "M4"]:
        return _fail("dest-8 fixture order %s" % lids)
    rows = check_cards(cards)
    refused = {lid for lid, issues in rows if issues}
    if refused != {"M2", "M4"}:
        return _fail("dest-8 must REFUSE only M2+M4, got %s" % refused)
    proc = subprocess.run([sys.executable, str(SCRIPT), "--cards", str(DEST8_FIXTURE)], text=True, capture_output=True)
    if proc.returncode != 1 or "REFUSE M2" not in proc.stderr or "REFUSE M4" not in proc.stderr or "K4_NO_PRODUCER" not in proc.stderr:
        return _fail("dest-8 CLI: %s" % proc.stderr)
    if producer_issues({"logical_id": "M2", "phase": "M2", "skills": ["bootstrap-destination", "build-worklist", "admit-migration-plan"], "files_writable": ["evidence/planning/admission-receipt.json"]}):
        return _fail("M2 pinning the planner producers must PASS")
    if producer_issues({"logical_id": "M4_VERIFY", "phase": "M4", "kind": "close", "skills": ["compose-m4-verdict", "capture-source-oracles"], "files_writable": ["evidence/verdicts/"]}):
        return _fail("M4 pinning compose-m4-verdict must PASS")
    if producer_issues({"logical_id": "c:x", "phase": "M3", "kind": "compile", "skills": ["fix-until-green"], "files_writable": ["src/main/java/com/demo/A.java"]}):
        return _fail("under the v3 loop fix-until-green IS the producer of a loop artifact (the edit under the transaction)")
    if not producer_issues({"logical_id": "M1", "phase": "M1", "skills": ["fix-until-green"], "files_writable": ["evidence/planning/evidence-bundle.json"]}):
        return _fail("fix-until-green does not produce the M1 bundle")
    for kind, skills in KIND_DEFAULTS.items():
        fw = {"build": ["pom.xml"], "config": ["src/main/resources/application.properties"], "compile": ["src/main/java/com/demo/A.java"], "incident": ["src/main/java/com/demo/A.java"], "test": ["src/main/java/com/demo/A.java"], "parity": ["src/main/java/com/demo/A.java"], "close": ["evidence/verdicts/"]}[kind]
        card = {"logical_id": "n", "phase": "M4" if kind == "close" else "M3", "kind": kind, "skills": list(skills), "files_writable": fw}
        if producer_issues(card):
            return _fail("KIND_DEFAULTS %s must satisfy the producer bar: %s" % (kind, producer_issues(card)))
        for s in skills:
            if s != "fix-until-green" and s != "capture-source-oracles" and s not in PRODUCERS and s not in ("check-release-readiness", "check-domain-parity"):
                return _fail("KIND_DEFAULTS %s/%s not in PRODUCERS" % (kind, s))
    payload = {"logical_id": "c:y", "kind": "compile", "skills": ["spring-to-quarkus-patterns", "fix-until-green"], "body": json.dumps({"phase": "M3", "files_writable": ["src/main/java/com/demo/A.java"]})}
    if producer_issues(card_from_payload(payload)):
        return _fail("cluster payload must PASS")
    for checker in ("check-release-readiness", "verify-live-kanban-loop", "admit-migration-plan-checker"):
        if checker in PRODUCERS and checker != "admit-migration-plan":
            return _fail("checker %s must not be a producer" % checker)
    named = subprocess.run([sys.executable, str(KERNEL / "assert-skill-scripts-named.py")], text=True, capture_output=True)
    if named.returncode != 0:
        return _fail("unreferenced-script bar: %s%s" % (named.stdout, named.stderr))
    print("OK: producer bar (dest-8 REFUSE M2+M4; kind defaults PASS; common procedure is not a producer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
