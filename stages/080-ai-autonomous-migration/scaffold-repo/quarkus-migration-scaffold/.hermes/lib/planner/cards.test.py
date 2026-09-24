#!/usr/bin/env python3
"""M3 display titles: six kind mappings, security-mode subjects, strict validation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.cards import TITLE_ACTIONS, TITLE_DASH, card_title, loop_title_ok, next_card  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _package_debt_case() -> int:
    """B6: a unit accepted on a gate HANDOFF leaves the package and boot proof
    owed. However empty the work list and however clean the measure, M4 VERIFY
    is not minted until both gates pass on the same artifact."""
    empty = {"clusters": [], "items": [], "deferred": [], "blocked_clusters": [],
             "measure": {"known": True, "tuple": [0, 0, 0]}}
    handoff_steps = {"steps": [{"verdict": "accepted", "gate_handoff": {"debt": {"package": "owed", "boot": "owed"}}}]}
    for label, runtime in (("package owed", {"ready": False, "reasons": ["the full Maven verification failed"]}),
                           ("never run", {}),
                           ("different artifacts", {"ready": False, "reasons": ["startup evidence is for a different artifact"]})):
        if next_card(dict(empty, runtime=runtime), handoff_steps) is not None:
            return _fail("M4 is refused while package/boot debt is undischarged (%s)" % label)
    close = next_card(dict(empty, runtime={"ready": True}), handoff_steps)
    if not close or close.get("title") != "M4 VERIFY":
        return _fail("M4 VERIFY is minted once both gates pass on one artifact: %s" % close)
    return 0


def main() -> int:
    if _package_debt_case():
        return 1
    dash = TITLE_DASH
    cases = [
        ("build", "pom.xml", False, "M3 BUILD %s pom.xml (2 items, attempt 1)" % dash),
        ("config", "application.properties", False, "M3 CONFIGURE %s application.properties (1 item, attempt 2)" % dash),
        ("compile", "Owner.java", False, "M3 COMPILE %s Owner.java (4 items, attempt 1)" % dash),
        ("incident", "Pet.java", False, "M3 MIGRATE %s Pet.java (3 items, attempt 1)" % dash),
        ("test", "OwnerTest.java", False, "M3 TEST %s OwnerTest.java (1 item, attempt 1)" % dash),
        ("parity", "PetTypeRestController.java", False, "M3 REPAIR %s PetTypeRestController.java (5 items, attempt 3)" % dash),
    ]
    if set(TITLE_ACTIONS) != {"build", "config", "compile", "incident", "test", "parity"}:
        return _fail("TITLE_ACTIONS must be exactly the six cluster kinds: %s" % sorted(TITLE_ACTIONS))
    for kind, path, _labeled, want in cases:
        items = ["i%d" % i for i in range({"build": 2, "config": 1, "compile": 4, "incident": 3, "test": 1, "parity": 5}[kind])]
        attempt = {"config": 2, "parity": 3}.get(kind, 1)
        head = {"kind": kind, "path": "src/" + path, "items": items, "id": "c:%s" % kind}
        got = card_title(head, attempt)
        if got != want:
            return _fail("%s path title: got %r want %r" % (kind, got, want))
        if not loop_title_ok(got, kind):
            return _fail("%s path title failed validation: %r" % (kind, got))
        if "c:%s" % kind in got:
            return _fail("%s title must not carry the cluster id: %r" % (kind, got))

    labeled = card_title(
        {"kind": "compile", "label": "DataAccessException", "path": "src/a/A.java",
         "items": ["a", "b", "c"], "write_set": ["src/a/A.java", "src/b/B.java"]}, 1)
    if labeled != "M3 COMPILE %s DataAccessException (3 items, 2 files, attempt 1)" % dash:
        return _fail("labeled compile title: %r" % labeled)
    if not loop_title_ok(labeled, "compile"):
        return _fail("labeled compile title failed validation")

    disabled = card_title(
        {"kind": "config", "label": "source-cors-response-adapter/v1",
         "items": ["d1"], "write_set": ["a.java", "application.properties"]}, 1)
    enabled = card_title(
        {"kind": "config", "label": "source-cors-response-adapter/v1:enabled",
         "items": ["e1"], "write_set": ["a.java", "application.properties"]}, 1)
    if "source-cors-response-adapter/v1" not in disabled or ":enabled" in disabled:
        return _fail("disabled adapter subject must stay the existing label: %r" % disabled)
    if not enabled.endswith("attempt 1)") or "source-cors-response-adapter/v1:enabled" not in enabled:
        return _fail("enabled adapter subject must keep :enabled from the label: %r" % enabled)
    if disabled == enabled:
        return _fail("security-mode labels must not collapse into one title")
    if not loop_title_ok(disabled, "config") or not loop_title_ok(enabled, "config"):
        return _fail("security-mode titles must validate")

    if loop_title_ok("M4 VERIFY", "close") is not True:
        return _fail("M4 VERIFY must remain the close title")
    refusals = [
        ("build", "M3 build pom.xml (2 items, attempt 1)"),
        ("build", "M3 BUILD pom.xml (2 items, attempt 1)"),
        ("build", "M3 BUILD - pom.xml (2 items, attempt 1)"),
        ("build", "M3 BUILD %s pom.xml" % dash),
        ("build", "M3 BUILD %s  (2 items, attempt 1)" % dash),
        ("build", "M3 COMPILE %s pom.xml (2 items, attempt 1)" % dash),
        ("build", "M3 EXTRA %s pom.xml (2 items, attempt 1)" % dash),
        ("close", "M3 BUILD %s pom.xml (1 item, attempt 1)" % dash),
        ("close", "M4 ACCEPT"),
        ("story", "M3 BUILD %s pom.xml (1 item, attempt 1)" % dash),
    ]
    for kind, title in refusals:
        if loop_title_ok(title, kind):
            return _fail("strict validation accepted %r for kind %s" % (title, kind))
    try:
        card_title({"kind": "story", "path": "x", "items": ["a"]}, 1)
        return _fail("unknown kind must not mint a display title")
    except ValueError:
        pass
    print("OK: card titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
