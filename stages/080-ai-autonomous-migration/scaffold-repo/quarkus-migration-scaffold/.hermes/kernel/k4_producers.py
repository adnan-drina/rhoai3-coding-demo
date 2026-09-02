#!/usr/bin/env python3
"""Producer-skill invariant (Architect 143941ZA / Operator 143706ZO).

Every M-stage card must pin at least one skill that owns producing its
primary artifact. Checkers (check-*, assert-*) do not count.

Not dest-apply. Does not import create_task. Does not kanban.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k4_schema import REMEDY, STAMP_ID  # noqa: E402

Issue = tuple[str, str, str]

ARTIFACT_M1 = "m1-analyze"
ARTIFACT_M2 = "m2-partition"
ARTIFACT_M4 = "m4-verdict"
ARTIFACT_POM = "dest-pom"
ARTIFACT_JAVA = "dest-java"
ARTIFACT_K8S = "dest-k8s"
ARTIFACT_COMMIT = "dest-commit"

# Explicit catalog. Verb prefixes are not the check (dest-8 M2 pinned
# derive-story-oracles and still had no producer for partition.json).
PRODUCERS: dict[str, str] = {
    "derive-legacy-boot3": ARTIFACT_M1,
    "scan-with-mta": ARTIFACT_M1,
    "inventory-legacy-surface": ARTIFACT_M1,
    "plan-migration-partition": ARTIFACT_M2,
    "author-destination-pom": ARTIFACT_POM,
    "reference-rh-quarkus-pom": ARTIFACT_POM,
    "manage-quarkus-extensions": ARTIFACT_POM,
    "configure-quarkus-profiles": ARTIFACT_POM,
    "spring-to-quarkus-patterns": ARTIFACT_JAVA,
    "form-entity-persistence": ARTIFACT_K8S,
    "commit-destination-tree": ARTIFACT_COMMIT,
    "compose-m4-verdict": ARTIFACT_M4,
}

# Convert uses this when partition story.skills[] is omitted.
# Planner-facing copy: plan-migration-partition/references/partition-schema.md
# (assert-partition-schema-sync.py). Not a second validity rule — mint still
# checks PRODUCERS against the card's primary artifact (Architect 102851ZA).
KIND_DEFAULTS: dict[str, list[str]] = {
    "setup": [
        "author-destination-pom",
        "reference-rh-quarkus-pom",
        "manage-quarkus-extensions",
        "configure-quarkus-profiles",
    ],
    "us": ["spring-to-quarkus-patterns"],
    "polish": ["spring-to-quarkus-patterns", "manage-quarkus-extensions"],
    "database": ["form-entity-persistence"],
}

DEST8_FIXTURE = _KERNEL / "fixtures" / "dest-8-six-cards.json"


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _writes(card: dict[str, Any]) -> list[str]:
    raw = card.get("files_writable") or []
    if isinstance(raw, list):
        return [str(p).replace("\\", "/").strip() for p in raw if str(p).strip()]
    return []


def _body_dict(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("body")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def card_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    body = _body_dict(payload)
    writes = _writes(payload) or _writes(body)
    phase = str(payload.get("phase") or body.get("phase") or "M3").upper()
    skills = [str(s).strip() for s in (payload.get("skills") or []) if str(s).strip()]
    lid = str(payload.get("logical_id") or body.get("task_id") or "").strip()
    return {
        "logical_id": lid,
        "phase": phase,
        "skills": skills,
        "files_writable": writes,
    }


def primary_artifact(card: dict[str, Any]) -> str:
    phase = str(card.get("phase") or "").upper()
    lid = str(card.get("logical_id") or "").strip()
    if phase == "M1":
        return ARTIFACT_M1
    if phase == "M2":
        return ARTIFACT_M2
    if phase == "M4":
        return ARTIFACT_M4
    if lid == STAMP_ID or lid.startswith("STAMP_"):
        return ARTIFACT_COMMIT
    writes = _writes(card)
    names = {Path(p).name for p in writes}
    if "pom.xml" in names:
        return ARTIFACT_POM

    def _k8s_rel(raw: str) -> bool:
        rel = raw.replace("\\", "/").lstrip("./")
        return rel == "k8s" or rel.startswith("k8s/")

    if writes and all(_k8s_rel(p) for p in writes):
        return ARTIFACT_K8S
    return ARTIFACT_JAVA


def producer_issues(card: dict[str, Any]) -> list[Issue]:
    skills = [str(s).strip() for s in (card.get("skills") or []) if str(s).strip()]
    if not skills:
        return []
    artifact = primary_artifact(card)
    hits = [s for s in skills if PRODUCERS.get(s) == artifact]
    if hits:
        return []
    lid = str(card.get("logical_id") or "?")
    phase = str(card.get("phase") or "?")
    return [
        _issue(
            "K4_NO_PRODUCER",
            "%s phase=%s artifact=%s skills=%s" % (lid, phase, artifact, skills),
        )
    ]


def check_cards(cards: list[dict[str, Any]]) -> list[tuple[str, list[Issue]]]:
    out: list[tuple[str, list[Issue]]] = []
    for card in cards:
        lid = str(card.get("logical_id") or "?")
        out.append((lid, producer_issues(card)))
    return out


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
