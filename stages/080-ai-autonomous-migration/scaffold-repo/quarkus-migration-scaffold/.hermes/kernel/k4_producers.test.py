#!/usr/bin/env python3
"""Operator 143706ZO: dest-8 six cards are the producer-bar fixture.

REFUSE M2 and M4. Pass M1, T001, T002, STAMP. A check that PASSes all
six has not implemented the invariant. Not dest.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k4_producers import (  # noqa: E402
    DEST8_FIXTURE,
    KIND_DEFAULTS,
    PRODUCERS,
    card_from_payload,
    check_cards,
    load_cards,
    producer_issues,
)

SCRIPT = KERNEL / "k4_producers.py"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    cards = load_cards(DEST8_FIXTURE)
    lids = [c["logical_id"] for c in cards]
    expect = ["M1", "M2", "T001", "T002", "STAMP_DESTINATION_TREE", "M4"]
    if lids != expect:
        return _fail("dest-8 fixture order %s != %s" % (lids, expect))

    rows = check_cards(cards)
    refused = {lid for lid, issues in rows if issues}
    passed = {lid for lid, issues in rows if not issues}
    if refused != {"M2", "M4"}:
        return _fail("dest-8 must REFUSE only M2+M4, got %s" % refused)
    if passed != {"M1", "T001", "T002", "STAMP_DESTINATION_TREE"}:
        return _fail("dest-8 must PASS M1/T001/T002/STAMP, got %s" % passed)
    if not refused:
        return _fail("a check that PASSes all six has not implemented the bar")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--cards", str(DEST8_FIXTURE)],
        text=True,
        capture_output=True,
    )
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        return _fail("dest-8 CLI must exit 1, got %s: %s" % (proc.returncode, blob))
    if "REFUSE M2" not in blob or "REFUSE M4" not in blob:
        return _fail("dest-8 CLI must name REFUSE M2 and M4: %s" % blob)
    if "K4_NO_PRODUCER" not in blob:
        return _fail("dest-8 CLI must name K4_NO_PRODUCER: %s" % blob)

    reminted_m2 = {
        "logical_id": "M2",
        "phase": "M2",
        "skills": ["plan-migration-partition", "check-spec-readiness"],
        "files_writable": ["evidence/partition.json"],
    }
    if producer_issues(reminted_m2):
        return _fail("M2 pinning plan-migration-partition must PASS")

    reminted_m4 = {
        "logical_id": "M4",
        "phase": "M4",
        "skills": [
            "compose-m4-verdict",
            "check-release-readiness",
            "check-domain-parity",
        ],
        "files_writable": ["evidence/verdicts/m4-verdict.json"],
    }
    if producer_issues(reminted_m4):
        return _fail("M4 pinning compose-m4-verdict must PASS")

    checkers_only = {
        "logical_id": "US1",
        "phase": "M3",
        "skills": ["check-spec-readiness"],
        "files_writable": ["src/main/java/com/demo/A.java"],
    }
    issues = producer_issues(checkers_only)
    if not issues or issues[0][0] != "K4_NO_PRODUCER":
        return _fail("checker-only M3 must K4_NO_PRODUCER: %s" % issues)

    payload = {
        "logical_id": "US1",
        "skills": ["spring-to-quarkus-patterns"],
        "body": json.dumps(
            {
                "phase": "M3",
                "files_writable": ["src/main/java/com/demo/A.java"],
            }
        ),
    }
    if producer_issues(card_from_payload(payload)):
        return _fail("K4 US payload with spring-to-quarkus-patterns must PASS")

    db_card = {
        "logical_id": "PROVISION_DATABASE",
        "phase": "M3",
        "skills": ["form-entity-persistence"],
        "files_writable": ["k8s/postgres.yaml", "k8s/app.yaml"],
    }
    if producer_issues(db_card):
        return _fail("k8s-only form-entity-persistence must PASS dest-k8s")
    if "form-entity-persistence" not in PRODUCERS:
        return _fail("catalog must name form-entity-persistence")

    if "compose-m4-verdict" not in PRODUCERS:
        return _fail("catalog must name compose-m4-verdict")
    if "plan-migration-partition" not in PRODUCERS:
        return _fail("catalog must name plan-migration-partition")
    if "check-release-readiness" in PRODUCERS or "check-spec-readiness" in PRODUCERS:
        return _fail("checkers must not be catalog producers")
    if "spring-to-quarkus-patterns" not in KIND_DEFAULTS.get("polish", []):
        return _fail("polish KIND_DEFAULTS must include spring-to-quarkus-patterns")
    for kind, skills in KIND_DEFAULTS.items():
        for skill in skills:
            if skill not in PRODUCERS:
                return _fail("KIND_DEFAULTS %s/%s missing from PRODUCERS" % (kind, skill))
    polish_java = {
        "logical_id": "polish",
        "phase": "M3",
        "skills": list(KIND_DEFAULTS["polish"]),
        "files_writable": ["src/test/java/com/demo/HealthTest.java"],
    }
    if producer_issues(polish_java):
        return _fail("polish KIND_DEFAULTS must produce dest-java HealthTest")

    named = KERNEL / "assert-skill-scripts-named.py"
    proc = subprocess.run(
        [sys.executable, str(named)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return _fail(
            "unreferenced-script bar: %s%s" % (proc.stdout, proc.stderr)
        )

    print("OK: dest-8 producer bar REFUSE M2+M4; remint pins PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
