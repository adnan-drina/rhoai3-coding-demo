#!/usr/bin/env python3
"""admission selftest: a typed refusal surfaces under its OWN block class.

What is asked here is narrow and it is the thing that went wrong before: the
classes an Operator reads are the loop's vocabulary for "what stopped, and what
would clear it". Two refusals that need two different answers must not arrive
under one name. UNIT_OVERSIZE (the scope WAS derived, narrowed, and is still
wider than one coherent repair) is a planning answer; SCOPE_UNDERIVED (no
production write scope exists at all) is a human or an ADR. UNIT_MODE_SWITCH is
neither: it is decisions.yaml asking for a formation mode the work list may not
adopt while a card is issued, and it arrives in the measure's blocked list where
it would otherwise read only as MEASURE_UNKNOWN.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.admission import CLUSTER_BLOCK_CLASSES, MEASURE_BLOCK_CLASSES, blocks_for, typed_class  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _worklist(clusters: list[dict], blocked_measure: list[str]) -> dict:
    return {
        "schema": "rhoai3.worklist/v1",
        "clusters": clusters,
        "blocked_clusters": [c["id"] for c in clusters if c.get("status") == "blocked"],
        "deferred": [],
        "measure": {"tuple": [0, 0, 0], "known": not blocked_measure, "blocked": list(blocked_measure)},
        "evidence_bundle_sha256": "b" * 64,
    }


def _classes(doc: dict) -> dict[str, str]:
    # blocks_for reads the tree only for the bootstrap receipt and the
    # decisions; an empty root produces the rest of the boundaries as blocks
    # too, which is exactly the point -- the new classes must not displace them.
    rows = blocks_for(Path("/nonexistent-destination"), {}, doc, None, {}, "b" * 64)
    return {r["class"]: r["detail"] for r in rows}


def _typed_class_case() -> int:
    if typed_class("UNIT_OVERSIZE: too wide", CLUSTER_BLOCK_CLASSES, "SCOPE_UNDERIVED") != "UNIT_OVERSIZE":
        return _fail("a typed refusal names its own class")
    if typed_class("", CLUSTER_BLOCK_CLASSES, "SCOPE_UNDERIVED") != "SCOPE_UNDERIVED":
        return _fail("an untyped block keeps the default class")
    # a class is a NAME, not a prefix match: a refusal that merely mentions one
    # is not one, or any message could rename itself
    if typed_class("the cluster is blocked because UNIT_OVERSIZE was near", CLUSTER_BLOCK_CLASSES, "SCOPE_UNDERIVED") != "SCOPE_UNDERIVED":
        return _fail("only the leading token is the class")
    if typed_class("UNIT_MODE_SWITCH: decisions.yaml asks for v1", MEASURE_BLOCK_CLASSES, "") != "UNIT_MODE_SWITCH":
        return _fail("the measure's own classes are read the same way")
    return 0


def _unit_oversize_case() -> int:
    """A cluster the former could not bound is UNIT_OVERSIZE, with the tools'
    own words, and a cluster with no derivable scope is still SCOPE_UNDERIVED."""
    wide = {"id": "u:abc123", "status": "blocked",
            "block": "UNIT_OVERSIZE: unit/package-leaf/v1 over src/main/java/p reaches 31 file(s)/402 site(s)/9 "
                     "symbol(s) (max 20/160/8); a repair this wide is a planning answer"}
    tests_only = {"id": "c:tests", "status": "blocked", "block": ""}
    rows = _classes(_worklist([wide, tests_only], []))
    if "UNIT_OVERSIZE" not in rows:
        return _fail("a bounded-out unit must surface under its own class: %s" % sorted(rows))
    if "reaches 31 file(s)" not in rows["UNIT_OVERSIZE"]:
        return _fail("and it must carry the former's own refusal, not a paraphrase: %s" % rows["UNIT_OVERSIZE"])
    if "SCOPE_UNDERIVED" not in rows or "no production write scope" not in rows["SCOPE_UNDERIVED"]:
        return _fail("a cluster with no derivable scope keeps the class and the wording it had: %s" % sorted(rows))
    return 0


def _unit_mode_switch_case() -> int:
    """The refused flip is a block of its own, not a nameless unknown measure."""
    text = ("UNIT_MODE_SWITCH: decisions.yaml asks for loop.unit_formation 'v1' while this list was formed 'off' and "
            "cluster c:1 is still issued or pending; the flip changes every cluster id, so the outstanding candidate "
            "would be discarded as not-issued. Finish c:1, then the switch takes effect at the next clean boundary.")
    rows = _classes(_worklist([], [text]))
    if "UNIT_MODE_SWITCH" not in rows:
        return _fail("the refused flip must surface under its own class: %s" % sorted(rows))
    if "c:1" not in rows["UNIT_MODE_SWITCH"]:
        return _fail("and it must name the card to finish first: %s" % rows["UNIT_MODE_SWITCH"])
    if "MEASURE_UNKNOWN" not in rows:
        return _fail("the measure is still unknown, and that block stands beside it: %s" % sorted(rows))
    # an ordinary blocked reason mints no class of its own
    plain = _classes(_worklist([], ["tests did not run in this verification"]))
    if set(plain) & set(MEASURE_BLOCK_CLASSES):
        return _fail("an untyped blocked reason must not be given a class: %s" % sorted(plain))
    return 0


def main() -> int:
    if _typed_class_case() or _unit_oversize_case() or _unit_mode_switch_case():
        return 1
    print("OK: admission block classes (a bounded-out unit is UNIT_OVERSIZE carrying the former's own refusal, a "
          "cluster with no derivable scope is still SCOPE_UNDERIVED with its own wording, a refused formation flip is "
          "UNIT_MODE_SWITCH naming the card to finish first and stands beside MEASURE_UNKNOWN rather than hiding in "
          "it, and a class is the leading token of a typed refusal -- never a message that merely mentions one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
