#!/usr/bin/env python3
"""Mechanical verification of the destination tree → work list + measure.

Inputs are tool outputs, never a worker's claim:
  --diagnostics FILE   rhoai3.diagnostics/v1 from JdkDiagnostics (run-verify.sh)
  --surefire-dir DIR   target/surefire-reports (parsed with ElementTree)
  --surefire-json FILE an already-parsed rhoai3.surefire/v1 summary (tests)
  --test-rc N          exit status of `mvn test` (required with either surefire input)
  --findings FILE      destination MTA rescan findings (mta-rescan-destination.sh)
  --run FILE           tool outcomes recorded by run-verify.sh (rc per tool)

Every component of the measure is known only when its tool ran in THIS
verification (recorded in verification/build/run.json); a missing report
never means success. The candidate tree identity is recorded so
advance.py can refuse a tree that changed after verification.

Writes verification/build/{run,diagnostics,surefire}.json, rebuilds
evidence/planning/worklist.json and verification/loop/state.json.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import candidate_sha256, ensure_hermes_lib, publish_loop_state  # noqa: E402

ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import MTA_RESCAN_FINDINGS, VERIFY_DIAGNOSTICS, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST  # noqa: E402
from planner.worklist import build_worklist, surefire_from_reports  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--diagnostics", default="")
    ap.add_argument("--surefire-dir", default="")
    ap.add_argument("--surefire-json", default="")
    ap.add_argument("--test-rc", type=int, default=None)
    ap.add_argument("--findings", default="")
    ap.add_argument("--run", default="", help="rhoai3.verify-run/v1 outcomes from run-verify.sh")
    ap.add_argument("--mode", choices=("acceptance", "diagnostic"), default="", help="what this verification WAS; an unstated mode is treated as diagnostic and cannot promote")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    run = load_json(Path(args.run)) if args.run and Path(args.run).is_file() else {}
    run = dict(run) if isinstance(run, dict) else {}
    run.setdefault("schema", "rhoai3.verify-run/v1")
    # An unstated mode is NOT an acceptance pass. Everything else unknown in
    # this harness ranks as not-clean -- an unrun gate, an absent surefire
    # report, a skipped rescan -- and a run receipt that does not say it was a
    # full pass must not be able to promote one. run-verify.sh records the mode
    # it ran in; a caller that has no receipt states it with --mode.
    run["mode"] = args.mode or str(run.get("mode") or "") or "diagnostic"
    run.setdefault("diagnostics", {"ran": False, "rc": None})
    run.setdefault("tests", {"ran": False, "rc": None})
    run.setdefault("rescan", {"ran": False, "rc": None})
    for rel in (VERIFY_DIAGNOSTICS, VERIFY_SUREFIRE):
        p = root / rel
        if p.is_file():
            p.unlink()  # fresh outputs: nothing from a previous attempt survives
    if args.diagnostics:
        src = Path(args.diagnostics)
        if not src.is_file():
            print("FAIL: VERIFY_NO_DIAGNOSTICS %s" % src, file=sys.stderr)
            return 1
        doc = load_json(src)
        if not isinstance(doc, dict) or doc.get("schema") != "rhoai3.diagnostics/v1":
            print("FAIL: VERIFY_DIAGNOSTICS_SCHEMA %s" % src, file=sys.stderr)
            return 1
        write_canonical(root / VERIFY_DIAGNOSTICS, doc)
        run["diagnostics"] = {"ran": True, "rc": run["diagnostics"].get("rc", 0) if run["diagnostics"].get("ran") else 0, "errors": doc.get("errors"), "build_unresolvable": bool(doc.get("build_unresolvable"))}
    if args.surefire_dir or args.surefire_json:
        if args.test_rc is None:
            print("FAIL: VERIFY_TEST_RC a surefire input needs --test-rc (the mvn test exit status)", file=sys.stderr)
            return 1
        sure = load_json(Path(args.surefire_json)) if args.surefire_json else surefire_from_reports(Path(args.surefire_dir), root)
        if not isinstance(sure, dict) or sure.get("schema") != "rhoai3.surefire/v1":
            print("FAIL: VERIFY_SUREFIRE_SCHEMA", file=sys.stderr)
            return 1
        sure.setdefault("ran", int(sure.get("reports") or 0) > 0)
        write_canonical(root / VERIFY_SUREFIRE, sure)
        run["tests"] = {"ran": True, "rc": args.test_rc, "reports": sure.get("reports")}
    if args.findings:
        src = Path(args.findings)
        if not src.is_file():
            print("FAIL: VERIFY_NO_FINDINGS %s" % src, file=sys.stderr)
            return 1
        dst = root / MTA_RESCAN_FINDINGS
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        run["rescan"] = {"ran": True, "rc": run["rescan"].get("rc", 0) if run["rescan"].get("ran") else 0}
    run["candidate_sha256"] = candidate_sha256(root)
    write_canonical(root / VERIFY_RUN, run)
    doc = build_worklist(root)
    m = doc["measure"]
    publish_loop_state(root, doc)
    print("OK: verify measure=%s known=%s%s head=%s clusters=%d candidate=%s → %s" % (m["tuple"], m["known"], "" if m["known"] else " (%s)" % "; ".join(m["blocked"]), doc["head"] or "-", len(doc["clusters"]), run["candidate_sha256"][:12], WORKLIST))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
