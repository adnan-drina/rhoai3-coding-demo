#!/usr/bin/env python3
"""K4 converter — sealed work list → one kanban_create payload.

Input: evidence/planning/worklist.json + an ADMITTED admission-receipt.json
whose seals match disk (+ verification/loop/steps.json for the parent and
the attempt). Output: exactly one payload — the head cluster as an M3 card
with a typed K1 body, or M4 VERIFY when the list is empty and nothing is
deferred — under a receipt-bound idempotency key. Zero payloads unless
admitted. K4 re-derives the activation/pilot verdict and the tool pins
from pins.json itself; the receipt text never overrides them.

Does not mint. Does not import create_task. Writes the body to
evidence/bodies/m3-<cluster>.json (m4-M4_VERIFY.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for p in (_KERNEL, _LIB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from k1_validate import validate_body  # noqa: E402
from k4_producers import card_from_payload, producer_issues  # noqa: E402
from k4_schema import CLOSE_ID, IMPL, REMEDY  # noqa: E402
from planner.admission import artifact_digests_on_disk, verify_receipt  # noqa: E402
from planner.canonical import load_json, sha256_file  # noqa: E402
from planner.cards import idempotency_key, next_card, parse_body, pending_cluster_ids, render_body  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, EVIDENCE_BUNDLE, LOOP_ISSUED, LOOP_STEPS, TYPE_INVENTORY, WORKLIST  # noqa: E402
from planner.pins import activation_gaps, load_pins, pin_gaps  # noqa: E402
from planner.worklist import gate_items  # noqa: E402
from planner.budget import budget as loop_budget  # noqa: E402
from planner.decisions import load_decisions, max_attempts  # noqa: E402

Issue = tuple[str, str, str]
SKILLS_ASSERT = (
    "consult each skill pinned on this card; unused pins are legal (skills_unused). "
    "A false consult — claiming a skill that was not loaded — is a defect. Do not silence a missing pin."
)
TERMINATOR_M3 = (
    "skill_view paved-road-m3 first (the pinned index; it views fix-until-green). Read the brief "
    "(fix-until-green/scripts/brief.py): every item carries the rule's advice and, for pom items, the exact "
    "element, the advised artifacts already present and the BOM-unmanaged ones with their managed equivalent. "
    "Patch the write set one item at a time; never rewrite a whole file, never tests, never evidence/, never "
    "decisions.yaml, never a dependency or plugin the brief did not ask for. Then bash "
    "fix-until-green/scripts/run-verify.sh --root . and python3 fix-until-green/scripts/advance.py --root . "
    "--cluster <id> --card $HERMES_KANBAN_TASK. The measure decides: ACCEPTED commits and mints the next card; "
    "REVERTED re-mints this cluster; VERIFICATION_PENDING retains the candidate (no new attempt) when verification "
    "cannot conclude; DEFERRED stops the loop for the Operator. Terminator: kanban_complete after "
    "ACCEPTED or REVERTED (the loop record is the audit; K2 allows it once brief, run-verify and advance ran in "
    "this log); kanban_block kind=needs_input naming the cluster after VERIFICATION_PENDING, DEFERRED or REFUSE: LOOP_*. Never "
    "kanban_request_review on a loop card; never retry inside this card; never widen the write set."
)
TERMINATOR_M4 = (
    "skill_view paved-road-m4 first (the pinned index; its steps.json is the contract). "
    "Run capture-source-oracles parity for every entry point, run-m4-pre-verdict.sh, and the MTA rescan "
    "assertion; record results under verification/. Compose evidence/verdicts/m4-verdict.json from "
    "measured exits (compose-m4-verdict). Expected runtime values come only from verification/source-oracles. "
    "Checkers do not author the verdict; the body does not pre-specify it. Do not dest-dispatch M5."
)


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _body(card: dict[str, Any], receipt: dict[str, Any], worklist_sha: str, artifacts: list[dict[str, str]], type_sha: str) -> dict[str, Any]:
    exits: list[dict[str, str]] = [{"check": "skills", "assert": SKILLS_ASSERT}]
    if card["kind"] == "close":
        exits.append({"check": "terminator", "assert": TERMINATOR_M4})
        exits.append({"check": "pre_verdict", "cmd": "bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh /projects/modernized"})
        exits.append({"check": "mta_rescan", "cmd": "python3 .hermes/skills/analysis/scan-with-mta/scripts/assert-mta-rescan.py ."})
        exits.append({"check": "parity", "cmd": "python3 .hermes/skills/gates/capture-source-oracles/scripts/compose-parity-receipt.py --root ."})
    else:
        exits.append({"check": "terminator", "assert": TERMINATOR_M3})
        exits.append({"check": "verify", "cmd": "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root ."})
        exits.append({"check": "advance", "cmd": "python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster %s --card $HERMES_KANBAN_TASK" % card["id"]})
    write_set = [{"path": p, "source_path": p, "source_sha256": ""} for p in card["write_set"]]
    paths = [w["path"] for w in write_set]
    refs = [
        {"key": "type-inventory", "path": str(TYPE_INVENTORY), "sha256": type_sha},
        {"key": "worklist", "path": str(WORKLIST), "sha256": worklist_sha},
    ]
    scope = card.get("batch_scope") or {}
    if scope.get("path") and scope.get("file_sha256"):
        refs.append({"key": "batch-scope", "path": str(scope["path"]), "sha256": str(scope["file_sha256"])})
    return {
        "task_id": card["id"],
        "role": IMPL,
        "phase": card["phase"],
        "refs": refs,
        "identity": {"increment_id": card["id"], "increment_kind": card["kind"], "path": card["path"], "attempt": card["attempt"]},
        "receipt_sha256": receipt["receipt_digest"],
        "worklist_sha256": worklist_sha,
        "increment_id": card["id"],
        "increment_kind": card["kind"],
        "attempt": card["attempt"],
        "write_set": write_set,
        "item_ids": list(card["items"]),
        "artifacts": artifacts,
        "files_in_scope": list(paths),
        "files_writable": list(paths),
        "exit_criteria": exits,
    }


def _payload(card: dict[str, Any], body: dict[str, Any], receipt_digest: str, parents: list[str]) -> dict[str, Any]:
    return {
        "logical_id": card["id"],
        "kind": card["kind"],
        "phase": card["phase"],
        "title": card["title"],
        "assignee": IMPL,
        "skills": list(card["skills"]),
        "parents": list(parents),
        "body": render_body(body),
        "idempotency_key": idempotency_key(card["id"], card["attempt"], receipt_digest),
        "attempt": card["attempt"],
        "max_retries": 1,
    }


def validate_result(result: Any) -> list[Issue]:
    out: list[Issue] = []
    if not isinstance(result, dict) or not isinstance(result.get("payloads"), list):
        return [_issue("K4_SCHEMA", "result must be {payloads: [...]}")]
    payloads = result["payloads"]
    if len(payloads) != 1:
        out.append(_issue("K4_CREATED_CARDS", "K4 emits exactly one card per step, got %d" % len(payloads)))
    for p in payloads:
        if not isinstance(p, dict):
            out.append(_issue("K4_SCHEMA", "payload must be an object"))
            continue
        if p.get("assignee") != IMPL:
            out.append(_issue("K4_ASSIGNEE", "%s assignee=%s" % (p.get("logical_id"), p.get("assignee"))))
        if p.get("max_retries") != 1:
            out.append(_issue("K4_MINT_RETRIES", "%s max_retries %s" % (p.get("logical_id"), p.get("max_retries"))))
        if p.get("kind") != "close" and not (parse_body(p["body"]).get("files_writable") or []):
            out.append(_issue("K4_SCOPE", "%s has an empty write set" % p.get("logical_id")))
    created = (result.get("manifest") or {}).get("created_cards")
    if created != [p.get("logical_id") for p in payloads if isinstance(p, dict)]:
        out.append(_issue("K4_CREATED_CARDS", "created_cards must equal the payload logical_id list"))
    return out


def write_bodies(root: Path, payloads: list[dict[str, Any]]) -> None:
    dest = root / "evidence" / "bodies"
    dest.mkdir(parents=True, exist_ok=True)
    for p in payloads:
        prefix = "m4" if p["kind"] == "close" else "m3"
        (dest / ("%s-%s.json" % (prefix, p["logical_id"].replace(":", "-")))).write_text(json.dumps(parse_body(p["body"]), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def convert_admitted(root: Path, *, write_root: bool = True) -> tuple[dict[str, Any] | None, list[Issue]]:
    """One payload for the loop's next card, or issues and zero payloads."""
    root = Path(root).resolve()
    receipt, gaps = verify_receipt(root, require_admitted=True)
    if gaps or receipt is None:
        return None, [_issue("K4_RECEIPT", g) for g in (gaps or ["missing receipt"])]
    pins = load_pins(root)
    act = activation_gaps(pins, str((receipt.get("seals") or {}).get("evidence_bundle") or ""))
    if act:
        return None, [_issue("K4_ACTIVATION", g) for g in act]
    bundle_doc = load_json(root / EVIDENCE_BUNDLE)
    pin_issues = pin_gaps(pins, (bundle_doc or {}).get("producers") or {})
    if pin_issues:
        return None, [_issue("K4_PINS", "%s: %s" % (g["class"], g["detail"])) for g in pin_issues]
    worklist = load_json(root / WORKLIST)
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else None
    card = next_card(worklist, steps)
    if card is None:
        pending = pending_cluster_ids(steps)
        if pending:
            return None, [_issue("K4_LOOP", "VERIFICATION_PENDING on %s; restore-pending.py then run-verify.sh --mode acceptance; do not mint a new attempt" % ",".join(pending))]
        deferred = worklist.get("deferred") or []
        return None, [_issue("K4_LOOP", "deferred cluster(s) %s block the run" % ",".join(deferred) if deferred else "measure not known or list not empty; nothing to mint")]
    digests = artifact_digests_on_disk(root)
    artifacts = [
        {"key": "evidence-bundle", "path": str(EVIDENCE_BUNDLE), "sha256": digests.get("evidence-bundle", "")},
        {"key": "worklist", "path": str(WORKLIST), "sha256": digests.get("worklist", "")},
        {"key": "admission-receipt", "path": str(ADMISSION_RECEIPT), "sha256": sha256_file(root / ADMISSION_RECEIPT)},
    ]
    ti = root / TYPE_INVENTORY
    if not ti.is_file():
        return None, [_issue("K4_SCHEMA", "missing %s (inventory-legacy-surface did not run)" % TYPE_INVENTORY)]
    parents: list[str] = []
    for st in reversed((steps or {}).get("steps") or []):
        if st.get("card"):
            parents = [str(st["card"])]
            break
    body = _body(card, receipt, digests.get("worklist", ""), artifacts, sha256_file(ti))
    issues: list[Issue] = []
    k1 = [(c, d) for c, d, _ in validate_body(body, root=root)]
    if k1:
        issues.append(_issue("K4_SCHEMA", "%s body failed K1: %s" % (card["id"], "; ".join("%s:%s" % x for x in k1))))
    payload = _payload(card, body, receipt["receipt_digest"], parents)  # a rewind changes the receipt (loop_epoch), so the key too
    issues.extend(producer_issues(card_from_payload(payload)))
    result = {"payloads": [payload], "manifest": {"created_cards": [payload["logical_id"]]}, "receipt_sha256": receipt["receipt_digest"], "claimed_control": False}
    issues.extend(validate_result(result))
    if issues:
        return None, issues
    if write_root:
        write_bodies(root, result["payloads"])
        # the issued card: advance.py promotes a candidate only for this cluster/attempt/key
        issued_path = root / LOOP_ISSUED
        prev = load_json(issued_path) if issued_path.is_file() else {}
        write_canonical(issued_path, {
            "schema": "rhoai3.loop-issued/v1",
            "cluster": card["id"],
            "kind": card["kind"],
            "attempt": card["attempt"],
            "idempotency_key": payload["idempotency_key"],
            "receipt_sha256": receipt["receipt_digest"],
            "write_set": list(card["write_set"]),
            "gate": str(card.get("gate") or ""),
            "items": list(card.get("items") or []),
            # what the gate held when this card was issued: acceptance compares
            # against that, not against the last accepted step (a gate can
            # start failing long after the last acceptance)
            "gate_items": sorted(gate_items(worklist, str(card.get("gate") or ""))) if card.get("gate") else [],
            # the sealed scope inventory this card is judged against; acceptance
            # re-reads it from disk and refuses a digest that is not this one
            "batch_scope": dict(card.get("batch_scope") or {}),
            "retry_key": str(card.get("retry_key") or card["id"]),
            # the one budget answer (planner.budget), recorded where the card is issued
            "budget": loop_budget(load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else {}, card["id"],
                                  str(card.get("retry_key") or card["id"]), max_attempts(load_decisions(root))),
            # each issued compile failure's identity WITHOUT its line: acceptance
            # asks whether THIS is still reported, not whether its err: id is
            "item_identities": {str(i["id"]): str(i["identity"]) for i in (worklist.get("items") or [])
                                if str(i.get("id")) in set(card.get("items") or []) and i.get("identity")},
            "task_id": str(prev.get("task_id") or "") if prev.get("idempotency_key") == payload["idempotency_key"] else "",
        })
    return result, []


def format_issues(issues: list[Issue]) -> str:
    lines = []
    for code, detail, remedy in issues:
        lines.append("%s: %s" % (code, detail))
        lines.append("  remedy: %s" % remedy)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write("k4_convert.py --root PATH [--out PATH]\nConvert the sealed work list to the loop's next kanban_create payload. Does not mint.\nEmits zero payloads unless admission-receipt.json is ADMITTED and sealed.\n")
        return 0 if args else 2
    root: Path | None = None
    out: Path | None = None
    i = 0
    while i < len(args):
        if args[i] == "--root" and i + 1 < len(args):
            root = Path(args[i + 1]); i += 2; continue
        if args[i] == "--out" and i + 1 < len(args):
            out = Path(args[i + 1]); i += 2; continue
        print("FAIL: unknown arg %s" % args[i], file=sys.stderr)
        return 1
    if root is None:
        print("FAIL: pass --root PATH", file=sys.stderr)
        return 1
    result, issues = convert_admitted(root)
    if issues or result is None:
        print(format_issues(issues), file=sys.stderr)
        print("K4 convert REFUSED (0 payloads).", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if out is not None:
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("OK: K4 convert (1 payload, receipt %s)." % result["receipt_sha256"][:16], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
