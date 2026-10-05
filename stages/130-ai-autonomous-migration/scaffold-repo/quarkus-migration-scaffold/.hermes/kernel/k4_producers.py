#!/usr/bin/env python3
"""Producer-skill invariant (Architect 143941ZA / Operator 143706ZO).

Every card must pin at least one skill that owns producing its primary
artifact. Checkers (check-*, assert-*, verify-*) do not count. Under the
v3 loop (SAD v3 §6) the edit that produces a pom, config or Java artifact
IS the fix-until-green step: brief → patch inside the write set →
run-verify → advance; so fix-until-green is the producer of every loop
artifact and the only skill a loop card pins (pilot v5 measured what the
story-era pom skills do on a loop card: scope creep and a whole-file rewrite).

Not dest-apply. Does not import create_task. Does not kanban.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for p in (_KERNEL, _LIB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from k4_schema import CLOSE_ID, REMEDY  # noqa: E402
from planner.cards import CARD_SKILLS  # noqa: E402

STAMP_ID = "STAMP_DESTINATION_TREE"  # historical dest-8 fixture card

Issue = tuple[str, str, str]

ARTIFACT_M1 = "m1-analyze"
ARTIFACT_M2 = "m2-admission"
ARTIFACT_M4 = "m4-verdict"
ARTIFACT_POM = "dest-pom"
ARTIFACT_CONFIG = "dest-config"
ARTIFACT_JAVA = "dest-java"
ARTIFACT_K8S = "dest-k8s"
ARTIFACT_COMMIT = "dest-commit"

# Explicit catalog. Verb prefixes are not the check.
PRODUCERS: dict[str, frozenset[str]] = {
    "freeze-migration-input": frozenset({ARTIFACT_M1}),
    "capture-build-evidence": frozenset({ARTIFACT_M1}),
    "inventory-legacy-surface": frozenset({ARTIFACT_M1}),
    "scan-with-mta": frozenset({ARTIFACT_M1}),
    "assemble-evidence-bundle": frozenset({ARTIFACT_M1}),
    "bootstrap-destination": frozenset({ARTIFACT_M2, ARTIFACT_POM}),
    "build-worklist": frozenset({ARTIFACT_M2}),
    "admit-migration-plan": frozenset({ARTIFACT_M2}),
    "author-destination-pom": frozenset({ARTIFACT_POM}),
    "reference-rh-quarkus-pom": frozenset({ARTIFACT_POM}),
    "manage-quarkus-extensions": frozenset({ARTIFACT_POM}),
    "configure-quarkus-profiles": frozenset({ARTIFACT_POM, ARTIFACT_CONFIG}),
    "spring-to-quarkus-patterns": frozenset({ARTIFACT_JAVA}),
    "form-entity-persistence": frozenset({ARTIFACT_K8S, ARTIFACT_JAVA}),
    "commit-destination-tree": frozenset({ARTIFACT_COMMIT}),
    "compose-m4-verdict": frozenset({ARTIFACT_M4}),
    # the M4 index: its steps.json names compose-m4-verdict as the producer
    "paved-road-m4": frozenset({ARTIFACT_M4}),
    "fix-until-green": frozenset({ARTIFACT_POM, ARTIFACT_CONFIG, ARTIFACT_JAVA, ARTIFACT_COMMIT}),
    # the M3 index: its steps.json names fix-until-green as the road and advance.py as the producer
    "paved-road-m3": frozenset({ARTIFACT_POM, ARTIFACT_CONFIG, ARTIFACT_JAVA, ARTIFACT_COMMIT}),
}

# One home for kind → pins: planner.cards.CARD_SKILLS (K4 stamps them).
KIND_DEFAULTS: dict[str, list[str]] = {k: list(v) for k, v in CARD_SKILLS.items()}

DEST8_FIXTURE = _KERNEL / "fixtures" / "dest-8-six-cards.json"


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _writes(card: dict[str, Any]) -> list[str]:
    raw = card.get("files_writable") or []
    if isinstance(raw, list):
        return [str(p).replace("\\", "/").strip() for p in raw if str(p).strip()]
    return []


def _body_dict(payload: dict[str, Any]) -> dict[str, Any]:
    from planner.cards import parse_body  # readable Markdown body with a fenced machine block, or pure JSON
    return parse_body(payload.get("body"))


def card_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    body = _body_dict(payload)
    writes = _writes(payload) or _writes(body)
    phase = str(payload.get("phase") or body.get("phase") or "M3").upper()
    skills = [str(s).strip() for s in (payload.get("skills") or []) if str(s).strip()]
    lid = str(payload.get("logical_id") or body.get("task_id") or "").strip()
    return {
        "logical_id": lid,
        "phase": phase,
        "kind": str(payload.get("kind") or body.get("increment_kind") or ""),
        "skills": skills,
        "files_writable": writes,
    }


def primary_artifact(card: dict[str, Any]) -> str:
    phase = str(card.get("phase") or "").upper()
    lid = str(card.get("logical_id") or "").strip()
    kind = str(card.get("kind") or "")
    if phase == "M1":
        return ARTIFACT_M1
    if phase == "M2":
        return ARTIFACT_M2
    if phase == "M4" or kind == "close" or lid == CLOSE_ID:
        return ARTIFACT_M4
    if lid == STAMP_ID or lid.startswith("STAMP_"):
        return ARTIFACT_COMMIT
    if kind == "build":
        return ARTIFACT_POM
    if kind == "config":
        return ARTIFACT_CONFIG
    writes = _writes(card)
    names = {Path(p).name for p in writes}
    if "pom.xml" in names:
        return ARTIFACT_POM

    def _k8s_rel(raw: str) -> bool:
        rel = raw.replace("\\", "/").lstrip("./")
        return rel == "k8s" or rel.startswith("k8s/")

    if writes and all(_k8s_rel(p) for p in writes):
        return ARTIFACT_K8S
    if writes and all(p.startswith("src/main/resources/") for p in writes):
        return ARTIFACT_CONFIG
    return ARTIFACT_JAVA


def producer_issues(card: dict[str, Any]) -> list[Issue]:
    skills = [str(s).strip() for s in (card.get("skills") or []) if str(s).strip()]
    if not skills:
        return []
    artifact = primary_artifact(card)
    hits = [s for s in skills if artifact in PRODUCERS.get(s, frozenset())]
    if hits:
        return []
    lid = str(card.get("logical_id") or "?")
    phase = str(card.get("phase") or "?")
    return [_issue("K4_NO_PRODUCER", "%s phase=%s artifact=%s skills=%s" % (lid, phase, artifact, skills))]


def check_cards(cards: list[dict[str, Any]]) -> list[tuple[str, list[Issue]]]:
    return [(str(card.get("logical_id") or "?"), producer_issues(card)) for card in cards]


def load_cards(path: Path) -> list[dict[str, Any]]:
    blob = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(blob, list):
        return [c for c in blob if isinstance(c, dict)]
    if isinstance(blob, dict) and isinstance(blob.get("cards"), list):
        return [c for c in blob["cards"] if isinstance(c, dict)]
    raise ValueError("cards JSON must be a list or {cards: [...]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cards", type=Path, help="JSON list of minted cards")
    args = ap.parse_args(argv)
    path = args.cards if args.cards is not None else DEST8_FIXTURE
    try:
        cards = load_cards(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    rows = check_cards(cards)
    bad = 0
    for lid, issues in rows:
        if issues:
            bad = 1
            for code, detail, remedy in issues:
                print("REFUSE %s %s: %s" % (lid, code, detail), file=sys.stderr)
                print("  remedy: %s" % remedy, file=sys.stderr)
        else:
            print("PASS %s" % lid)
    if bad:
        return 1
    print("OK: producer-skill invariant (%d card(s))" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
