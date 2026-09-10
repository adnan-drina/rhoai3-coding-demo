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
