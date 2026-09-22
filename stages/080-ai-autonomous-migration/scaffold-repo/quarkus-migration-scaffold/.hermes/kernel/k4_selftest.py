#!/usr/bin/env python3
"""K4 converter selftest (v3): one card per step from the sealed work list.

Emits zero payloads unless admission-receipt.json is ADMITTED and sealed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
sys.path.insert(0, str(KERNEL.parent / "lib"))
from k1_validate import validate_body  # noqa: E402
from k4_convert import convert_admitted, main as convert_main  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, WORKLIST  # noqa: E402

BOOTSTRAP = KERNEL.parent / "skills" / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"
ADVANCE = KERNEL.parent / "skills" / "migration" / "fix-until-green" / "scripts" / "advance.py"
VERIFY = KERNEL.parent / "skills" / "migration" / "fix-until-green" / "scripts" / "verify.py"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def prepare(root: Path, *, errors=None) -> None:
    specimens.prepare_loop(root, errors=errors or [])


def head_card_for_unit(worklist: dict) -> dict:
    """The head cluster as a card, without going through next_card: the unit
    block is what is under test, not the head derivation."""
    from planner.cards import CARD_SKILLS, card_title  # noqa: E402

    head = next(c for c in worklist["clusters"] if c["id"] == worklist["head"])
    return {"id": head["id"], "kind": head["kind"], "title": card_title(head, 1), "phase": "M3",
            "path": head["path"], "write_set": list(head["write_set"]), "items": list(head["items"]),
            "attempt": 1, "skills": list(CARD_SKILLS[head["kind"]])}


def main() -> int:
    for label in ("k4_convert.py", "k4_schema.py", "k4_mint.py"):
        for line in (KERNEL / label).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(("import ", "from ")) and "create_task" in s:
                return _fail("%s imports create_task" % label)
    with tempfile.TemporaryDirectory(prefix="k4-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "http", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        prepare(root)
        rec = load_json(root / ADMISSION_RECEIPT)
        if rec["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % rec["reasons"][:3])
        result, issues = convert_admitted(root)
        if issues or result is None:
            return _fail("convert: %s" % issues)
        if len(result["payloads"]) != 1 or result["manifest"]["created_cards"] != [result["payloads"][0]["logical_id"]]:
            return _fail("exactly one card per step")
        p = result["payloads"][0]
        wl = load_json(root / WORKLIST)
        head_cluster = next(c for c in wl["clusters"] if c["id"] == wl["head"])
        from planner.cards import card_title  # noqa: E402
        if p["logical_id"] != wl["head"] or p["title"] != card_title(head_cluster, 1) or not p["title"].startswith("M3 build pom.xml (") or p["kind"] != "build" or p["phase"] != "M3":
            return _fail("head payload %s" % {k: p[k] for k in ("logical_id", "title", "kind", "phase")})
        if p["idempotency_key"] != "k4:%s:1:%s" % (wl["head"], rec["receipt_digest"][:16]) or p["max_retries"] != 1 or p["assignee"] != "implementer":
            return _fail("key/retries/assignee %s" % p["idempotency_key"])
        if p["skills"] != ["paved-road-m3"]:
            return _fail("a loop card carries exactly one skill: %s" % p["skills"])
        from planner.cards import parse_body  # noqa: E402
        if not p["body"].startswith("## M3 ") or "```json" not in p["body"]:
            return _fail("card body must be readable Markdown with the machine body fenced: %r" % p["body"][:80])
        body = parse_body(p["body"])
        if parse_body(json.dumps(body)) != body:
            return _fail("parse_body must accept the pure-JSON form too")
        if validate_body(body, root=root):
            return _fail("body K1: %s" % validate_body(body, root=root))
        if body["receipt_sha256"] != rec["receipt_digest"] or body["worklist_sha256"] != rec["seals"]["worklist"] or body["files_writable"] != ["pom.xml"] or body["attempt"] != 1:
            return _fail("body fields")
        if {a["key"] for a in body["artifacts"]} != {"evidence-bundle", "worklist", "admission-receipt"}:
            return _fail("artifacts %s" % body["artifacts"])
        for key in ("nodes", "edges", "incidents", "violations"):
            if key in body:
                return _fail("body inlines %s" % key)
        if not (root / "evidence" / "bodies" / ("m3-%s.json" % wl["head"].replace(":", "-"))).is_file():
            return _fail("body file not written")
        # identical on rerun
        again, _ = convert_admitted(root)
        if again["payloads"][0]["body"] != p["body"] or again["payloads"][0]["idempotency_key"] != p["idempotency_key"]:
            return _fail("convert not idempotent")
        # CLI
        out = t / "k4.json"
        if convert_main(["--root", str(root), "--out", str(out)]) != 0 or len(json.loads(out.read_text())["payloads"]) != 1:
            return _fail("CLI convert")
        # The M4 VERIFY card: its own exits, in the phase's order, and its own
        # prose. Measured on v9 (t_32c82390): the close card carried the M3
        # loop's markdown -- "it views fix-until-green", "read the brief",
        # "run-verify then advance", "complete after ACCEPTED" -- while only
        # the machine body named M4's exits. The markdown is what the board
        # shows, so the worker ran the wrong phase and waited for a terminator
        # K2 refuses here.
        from k4_convert import TERMINATOR_M4, VERDICT_BINDER_SCRIPT, VERDICT_SCHEMA_SCRIPT, _body as build_body  # noqa: E402
        from planner.cards import CARD_SKILLS, CLOSE_ID, next_card, render_body  # noqa: E402
        empty = {"head": None, "clusters": [], "items": [], "deferred": [], "blocked_clusters": [],
                 "measure": {"known": True, "tuple": [0, 0, 0]}, "runtime": {"ready": True}}
        close = next_card(empty, {"steps": []})
        if close is None or close["id"] != CLOSE_ID or close["kind"] != "close" or close["phase"] != "M4" or close["skills"] != CARD_SKILLS["close"]:
            return _fail("an empty work list on a runnable tree mints M4 VERIFY: %s" % close)
        type_sha = next(r["sha256"] for r in body["refs"] if r["key"] == "type-inventory")
        cbody = build_body(close, rec, rec["seals"]["worklist"], body["artifacts"], type_sha)
        k1 = validate_body(cbody, root=root)
        if k1:
            return _fail("M4 body K1: %s" % k1)
        exits = {str(e.get("check")): e for e in cbody["exit_criteria"]}
        if exits["parity"]["cmd"] != "python3 .hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py --root .":
            return _fail("the parity exit must be the batch runner, not the composer: %s" % exits.get("parity"))
        order = [e["check"] for e in cbody["exit_criteria"]]
        # ADR-015: the generator runs after the parity runner and before the
        # pre-verdict runner, because the runner's m4-parity rebuild is what
        # executes the generated cases.
        # The rescan RUN precedes the rescan FLOOR: the floor judges the record
        # the run writes, and the tree changed at commit_tests.
        if order[:8] != ["skills", "terminator", "parity", "generate_tests", "commit_tests", "rescan", "mta_rescan", "pre_verdict"]:
            return _fail("the M4 exits are the phase's order: %s" % order)
        if "mta-rescan-destination.sh ." not in exits["rescan"]["cmd"]:
            return _fail("the rescan exit must run the destination analyzer: %s" % exits.get("rescan"))
        if "assert-mta-rescan.py ." not in exits["mta_rescan"]["cmd"] or "mta-rescan-destination" in exits["mta_rescan"]["cmd"]:
            return _fail("the rescan floor exit is the floor alone (it judges, it does not produce): %s" % exits.get("mta_rescan"))
        if "generate-product-tests.py --root ." not in exits["generate_tests"]["cmd"]:
            return _fail("the generate exit must be the producer itself: %s" % exits.get("generate_tests"))
        # The tree the verdict is composed over has to be retrievable, and the
        # generator is what made it dirty: the commit step is the exit that
        # closes that, immediately after it and before anything reads the tree.
        if "commit-generated-tests.py --root ." not in exits["commit_tests"]["cmd"]:
            return _fail("the commit exit must be the producer's own script: %s" % exits.get("commit_tests"))
        if "verdict_schema" not in exits or VERDICT_SCHEMA_SCRIPT not in exits["verdict_schema"]["cmd"]:
            return _fail("the verdict schema assertion is on disk and must be an exit: %s" % order)
        # The lint refuses an UNBOUND verdict as well as a malformed one, and
        # the exit is where the worker learns that. v9's second M4 card wrote
        # no card_id at all: the exit named a linter and nothing named what it
        # requires, so the binding was left to whatever the worker remembered.
        binding_assert = str(exits["verdict_schema"].get("assert") or "")
        for needle in ("card_id", "receipt_sha256", "parity_receipt_sha256", "issued.json",
                       "verification/parity/receipt.json", VERDICT_BINDER_SCRIPT):
            if needle not in binding_assert:
                return _fail("the verdict_schema exit must say the verdict carries its bindings (%r): %r"
                             % (needle, binding_assert[:160]))
        for needle in ("run-parity.py", "generate-product-tests", "commit-generated-tests.py", "src/parity-test/java",
                       "m4-parity", "assert-retrievable-tree",
                       "mta-rescan-destination.sh", "assert-mta-rescan.py", "run-m4-pre-verdict.sh", "compose-m4-verdict",
                       "kanban_request_review reviewer=reviewer", "REFUSE", "Never kanban_complete"):
            if needle not in TERMINATOR_M4:
                return _fail("TERMINATOR_M4 must name %r" % needle)
        prose = render_body(cbody).split("<details>")[0]
        if not prose.startswith("## M4 VERIFY"):
            return _fail("the close card's prose is its own: %r" % prose[:80])
        for needle in ("skill_view paved-road-m4", "run-parity.py", "skill_view generate-product-tests",
                       "generate-product-tests.py --root .", "commit-generated-tests.py --root .",
                       "src/parity-test/java", "-Pm4-parity", "assert-retrievable-tree",
                       "mta-rescan-destination.sh", "assert-mta-rescan.py", "run-m4-pre-verdict.sh",
                       "skill_view compose-m4-verdict", "evidence/verdicts/m4-verdict.json",
                       "kanban_request_review", "reviewer=reviewer", "REFUSE", "Never dest-dispatch M5"):
            if needle not in prose:
                return _fail("the close card's prose must name %r" % needle)
        for forbidden in ("brief.py", "advance.py", "run-verify", "paved-road-m3", "kanban_complete after ACCEPTED"):
            if forbidden in prose:
                return _fail("the close card's prose must not carry the M3 loop's %r" % forbidden)
        if parse_body(render_body(cbody)) != cbody:
            return _fail("the machine body must survive the close card's prose")
        # the loop card's prose is unchanged
        loop_prose = p["body"].split("<details>")[0]
        for needle in ("paved-road-m3", "brief.py", "run-verify", "advance.py", "kanban_complete` after ACCEPTED"):
            if needle not in loop_prose:
                return _fail("a loop card's prose must still be the loop's: %r missing" % needle)

        # A UNIT card: the body gains one additive block and stays K1-valid.
        # The MEMBER inventory is not in it -- it lives in the sealed
        # batch-scope document the refs already name, and K1 refuses a body
        # that inlines derived content. The loop card's prose is unchanged,
        # because a unit is still one of the existing increment kinds.
        from k4_convert import UNIT_BODY_EVIDENCE, UNIT_BODY_SYMBOLS, _unit_block  # noqa: E402
        unit_card = dict(head_card_for_unit(wl))
        unit_card["unit"] = {
            "unit_id": "u:0123456789ab", "rule": "unit/declaration-closure/v1",
            "family_key": "p.Svc#m(int)",
            "symbols": [{"kind": "member", "fqn": "p.Svc", "signature": "m(int)", "path": "src/main/java/p/Svc.java"}] * 12,
            "target_symbols": [{"from": "javax.ws.rs.core.Context", "to": "jakarta.ws.rs.core.Context",
                                "catalog_row": {"catalog": "compat-mapping.json", "block": "symbol_renames"}}],
            "evidence": [{"kind": "model", "ref": "p.Impl implements p.Svc"}] * 20,
            "size": {"files": 13, "sites": 107, "symbols": 2},
            "completion": ["every sealed identity gone", "assess_unit: no member violates"],
        }
        ubody = build_body(unit_card, rec, rec["seals"]["worklist"], body["artifacts"], type_sha)
        k1u = validate_body(ubody, root=root)
        if k1u:
            return _fail("a unit body must be K1-valid: %s" % k1u)
        if "unit" not in ubody or ubody["unit"]["unit_id"] != "u:0123456789ab":
            return _fail("the unit block is on the body: %s" % sorted(ubody))
        if "members" in ubody["unit"]:
            return _fail("the member inventory stays in the sealed document, never in the body")
        if len(ubody["unit"]["symbols"]) != UNIT_BODY_SYMBOLS or len(ubody["unit"]["evidence"]) != UNIT_BODY_EVIDENCE:
            return _fail("the body carries a bounded view: %d symbols, %d evidence"
                         % (len(ubody["unit"]["symbols"]), len(ubody["unit"]["evidence"])))
        if ubody["increment_kind"] not in ("build", "config", "compile", "incident", "test", "parity"):
            return _fail("a unit stays one of the existing increment kinds: %s" % ubody["increment_kind"])
        if ubody["files_writable"] != [w["path"] for w in ubody["write_set"]]:
            return _fail("write_set keeps its row shape and simply lists more paths")
        if _unit_block({"unit": {}}) or _unit_block({}):
            return _fail("a non-unit card gains nothing")
        plain = build_body(head_card_for_unit(wl), rec, rec["seals"]["worklist"], body["artifacts"], type_sha)
        if "unit" in plain or render_body(plain).split("<details>")[0] != p["body"].split("<details>")[0]:
            return _fail("the loop-card prose is unchanged for a non-unit card")

        # tampered work list → verify refuses → 0 payloads
        doc = load_json(root / WORKLIST)
        doc["head"] = "c:tampered"
        write_canonical(root / WORKLIST, doc)
        res, iss = convert_admitted(root)
        if res is not None or not any(i[0] == "K4_RECEIPT" for i in iss):
            return _fail("tampered work list must yield 0 payloads: %s" % iss)
        pipeline.plan(root)
        # inadmissible (missing decision) → 0 payloads
        inc = specimens.build_dest(t / "inc", specimens.specimen("http"), decisions=specimens.full_decisions(max_attempts=None))
        prepare(inc)
        res, iss = convert_admitted(inc)
        if res is not None or convert_main(["--root", str(inc)]) != 1:
            return _fail("inadmissible must yield 0 payloads")
        # the scheduled specimen: its head is a compile/incident cluster with the domain skills
        sch = specimens.build_dest(t / "sched", specimens.specimen("scheduled"), decisions=specimens.admitted_decisions())
        prepare(sch, errors=[("src/main/java/org/acme/clinic/inventory/InventorySyncJob.java", 4, "cannot find symbol Scheduled")])
        res, iss = convert_admitted(sch)
        if iss or res["payloads"][0]["kind"] not in ("compile", "incident") or res["payloads"][0]["skills"] != ["paved-road-m3"]:
            return _fail("scheduled head: %s %s" % (iss, res and res["payloads"][0]["kind"]))
    print("OK: K4 selftest (one receipt-bound card per step; K1 body; idempotent; tampered/inadmissible → 0 payloads; scheduled specimen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
