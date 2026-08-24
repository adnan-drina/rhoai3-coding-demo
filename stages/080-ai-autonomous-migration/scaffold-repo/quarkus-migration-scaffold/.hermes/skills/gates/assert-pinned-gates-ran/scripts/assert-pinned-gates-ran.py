#!/usr/bin/env python3
"""Refuse M4 PROVISIONAL_ACCEPT when a pinned gate left no evidence.

Architect ``142524ZA`` / Operator ``141853Z-op`` / ``145539Z-op``.
Silence fails. ``specimen-n/a: no DB`` is a refusal reason, not a skip.
Do not require G-1 kill-ratio, Owner/Pet, or a runnable DB as proof a
gate ran. Do not idle-exit-0 on missing artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

PINNED_GATE_LEAVES = frozenset(
    {
        "check-spec-readiness",
        "check-domain-parity",
        "check-release-readiness",
        "assert-pinned-gates-ran",
        "assert-retrievable-tree",
    }
)
SELF = "assert-pinned-gates-ran"
VERDICT_DIR = Path("evidence") / "verdicts"
REFUSAL_DIR = VERDICT_DIR / "refusals"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def parse_skills(
    raw: str | None, skills_file: Path | None, card_json: Path | None
) -> list[str] | None:
    if raw and raw.strip():
        return [p.strip() for p in raw.split(",") if p.strip()]
    env = os.environ.get("M4_CARD_SKILLS", "").strip()
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    if skills_file is not None:
        data = json.loads(skills_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict) and isinstance(data.get("skills"), list):
            return [str(x) for x in data["skills"]]
        raise ValueError("skills file must be a JSON array or {\"skills\": [...]}")
    if card_json is not None:
        data = json.loads(card_json.read_text(encoding="utf-8"))
        skills = data.get("skills")
        if not isinstance(skills, list):
            raise ValueError("card JSON missing skills array")
        return [str(x) for x in skills]
    return None


def _json_names(doc: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(doc, dict):
        for key in ("gate", "skill", "name"):
            val = doc.get(key)
            if isinstance(val, str) and val.strip():
                names.add(val.strip())
        checks = doc.get("required_checks")
        if isinstance(checks, list):
            for item in checks:
                if isinstance(item, str) and item.strip():
                    names.add(item.strip())
    return names


def verdict_names_gate(path: Path, gate: str) -> bool:
    if path.stem == gate:
        return True
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return gate in _json_names(doc)


def iter_ran_verdicts(root: Path) -> Iterable[Path]:
    base = root / VERDICT_DIR
    if not base.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(base.rglob("*.json")):
        try:
            path.relative_to(root / REFUSAL_DIR)
            continue
        except ValueError:
            out.append(path)
    return out


def has_ran_verdict(root: Path, gate: str) -> bool:
    for path in iter_ran_verdicts(root):
        if verdict_names_gate(path, gate):
            return True
    return False


def refusal_ok(root: Path, gate: str) -> bool:
    path = root / REFUSAL_DIR / (gate + ".json")
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict):
        return False
    if doc.get("ran") is not False:
        return False
    reason = doc.get("reason")
    return isinstance(reason, str) and bool(reason.strip())


def write_self_verdict(root: Path, evidenced: list[str]) -> None:
    path = root / VERDICT_DIR / (SELF + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "gate": SELF,
        "ran": True,
        "verdict": "PASS",
        "reason": "all pinned gates evidenced",
        "evidenced": evidenced,
        "ship": False,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def check_root(root: Path, skills: list[str]) -> int:
    pinned = [s for s in skills if s in PINNED_GATE_LEAVES]
    missing: list[str] = []
    evidenced: list[str] = []
    for gate in pinned:
        if gate == SELF:
            continue
        if has_ran_verdict(root, gate) or refusal_ok(root, gate):
            evidenced.append(gate)
            continue
        missing.append(gate)
    if missing:
        return _fail(
            "pinned gate(s) left no verdict and no refusal: "
            + ", ".join(missing)
            + " (silence fails; specimen-n/a: no DB is a refusal, not a skip)"
        )
    if SELF in pinned:
        write_self_verdict(root, evidenced)
        if not has_ran_verdict(root, SELF):
            return _fail("self-verdict was not written")
        evidenced.append(SELF)
    print(
        "OK: assert-pinned-gates-ran ("
        + str(len(evidenced))
        + " gate(s) evidenced)",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="product / dest root")
    parser.add_argument(
        "--skills", default=None, help="comma-separated M4 card skills"
    )
    parser.add_argument("--skills-file", type=Path, default=None)
    parser.add_argument("--card-json", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    try:
        skills = parse_skills(args.skills, args.skills_file, args.card_json)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("could not read M4 skills list: " + str(exc))
    if skills is None:
        return _fail(
            "pass --skills, --skills-file, --card-json, or M4_CARD_SKILLS "
            "(missing list is fail-closed, not idle)"
        )
    return check_root(root, skills)


if __name__ == "__main__":
    sys.exit(main())
