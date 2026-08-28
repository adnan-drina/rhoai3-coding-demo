#!/usr/bin/env python3
"""Refuse M4 PROVISIONAL_ACCEPT when a pinned gate left no *run* evidence.

Architect ``142524ZA`` / Operator ``141853Z-op`` / ``145539Z-op`` /
``162349ZO``. Silence fails. ``ran: false`` is not a run — dest-5 M4
minted ``refusals/check-domain-parity.json`` with ``ran: false`` and this
gate accepted it. Presence of an artifact is not evidence the gate ran.
``specimen-n/a: no DB`` is a refusal *reason* on a run (``ran: true``),
not a skip. Do not require G-1 kill-ratio, Owner/Pet, or a runnable DB
as proof a gate ran. Do not idle-exit-0 on missing artifacts. ``ran: true`` under
``evidence/verdicts/`` is self-attested. Require ``evidence/receipts/gates/``
(argv, rc, producer). M4 ``write_file`` of that path is fenced.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "write_gate_receipt", _HERE / "write-gate-receipt.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
RECEIPT_DIR = _mod.RECEIPT_DIR
is_runner_receipt = _mod.is_runner_receipt
write_receipt = _mod.write_receipt

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
RELEASE_TOKENS = frozenset(
    {"PROVISIONAL_ACCEPT", "ACCEPT", "SCOPED_ACCEPT"}
)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def parse_skills(
    raw: str | None, skills_file: Path | None, card_json: Path | None
) -> list[str] | None:
    env = os.environ.get("M4_CARD_SKILLS", "").strip()
    if env:
        raise ValueError(
            "M4_CARD_SKILLS override is OBJECT (Architect 130758ZA); "
            "pass --skills / --skills-file / --card-json from the card"
        )
    if raw and raw.strip():
        return [p.strip() for p in raw.split(",") if p.strip()]
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


def iter_verdict_json(root: Path) -> Iterable[Path]:
    base = root / VERDICT_DIR
    if not base.is_dir():
        return []
    return sorted(path for path in base.rglob("*.json") if path.is_file())


def _load_obj(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def authored_by_card(doc: dict, card_id: str) -> bool:
    if not card_id:
        return False
    return card_id in json.dumps(doc, sort_keys=True)


def is_run_evidence(doc: dict, card_id: str) -> bool:
    """A cited artifact evidences a run only when it says the gate ran.

    ``ran: false`` is a withdrawn claim (dest-5). Missing ``ran`` is
    presence-only. Release tokens are M4/M5 outputs, not gate-ran proof.
    Artifacts that name this M4 task id were minted on the card under test.
    """
    if doc.get("ran") is not True:
        return False
    verdict = str(doc.get("verdict") or "").strip().upper().replace("-", "_")
    if verdict in RELEASE_TOKENS:
        return False
    if authored_by_card(doc, card_id):
        return False
    return True


def iter_receipt_json(root: Path) -> Iterable[Path]:
    base = root / RECEIPT_DIR
    if not base.is_dir():
        return []
    return sorted(path for path in base.glob("*.json") if path.is_file())


def receipt_names_gate(path: Path, gate: str) -> bool:
    if path.stem == gate:
        return True
    doc = _load_obj(path)
    if doc is None:
        return False
    return str(doc.get("gate") or "").strip() == gate


def has_ran_verdict(root: Path, gate: str, card_id: str = "") -> bool:
    del card_id  # M4 task id on a runner receipt is correlation, not mint
    for path in iter_receipt_json(root):
        if not receipt_names_gate(path, gate):
            continue
        doc = _load_obj(path)
        if doc is None:
            continue
        if is_runner_receipt(doc):
            return True
    return False


def write_self_verdict(root: Path, evidenced: list[str]) -> None:
    argv = [sys.executable, str(Path(__file__).resolve()), str(root)]
    write_receipt(
        root,
        SELF,
        argv=argv,
        rc=0,
        producer=str(Path(__file__).resolve().name),
        run_id="assert-pinned-gates-ran:" + ",".join(evidenced),
    )


def check_root(root: Path, skills: list[str], card_id: str = "") -> int:
    pinned = [s for s in skills if s in PINNED_GATE_LEAVES]
    missing: list[str] = []
    evidenced: list[str] = []
    for gate in pinned:
        if gate == SELF:
            continue
        if has_ran_verdict(root, gate, card_id):
            evidenced.append(gate)
            continue
        missing.append(gate)
    if missing:
        return _fail(
            "pinned gate(s) left no run evidence: "
            + ", ".join(missing)
            + " (ran:true under evidence/verdicts/ is self-attested; "
            "require evidence/receipts/gates/ with argv, rc, producer; "
            "silence fails)"
        )
    if SELF in pinned:
        write_self_verdict(root, evidenced)
        if not has_ran_verdict(root, SELF, card_id):
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
    parser.add_argument(
        "--card-id",
        default=None,
        help="M4 task id; artifacts naming it are minted on this card",
    )
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
            "pass --skills, --skills-file, or --card-json "
            "(missing list is fail-closed, not idle; M4_CARD_SKILLS override is OBJECT)"
        )
    card_id = (args.card_id or os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    return check_root(root, skills, card_id)


if __name__ == "__main__":
    sys.exit(main())
