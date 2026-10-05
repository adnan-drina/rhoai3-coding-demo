#!/usr/bin/env python3
"""Refuse an M4 verdict that does not account for what the ADRs retired.

The account itself (evidence/verdicts/coverage-account.json) is written by
compose-coverage-account.py from decisions.yaml and the parity receipt. This
checker is the lint that makes it impossible to skip or to misreport:

  * the account must exist and cover EVERY retired source in decisions.yaml
    (a retirement with no row is the silence this gate exists to prevent);
  * a row that claims a replacement must name entry points the parity receipt
    measured as PASS -- the account is recomputed here from the same inputs and
    must equal what is on disk, so an edited account refuses;
  * the verdict must carry coverage_account: {remaining_gaps, retired} equal to
    the account's summary, so a reader of the verdict cannot miss a gap.

A remaining gap is NOT a refusal: an accepted ADR may knowingly drop coverage.
Hiding one is.

Exit 0 PASS, 1 REFUSE, 2 usage."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: COVERAGE_ACCOUNT .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json  # noqa: E402
from planner.decisions import DecisionsError, load_decisions  # noqa: E402
from planner.paths import DECISIONS  # noqa: E402

ACCOUNT = Path("evidence") / "verdicts" / "coverage-account.json"
VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
COMPOSER = Path(__file__).resolve().parents[2] / "compose-m4-verdict" / "scripts" / "compose-coverage-account.py"


def _refuse(msgs: list[str]) -> int:
    for m in msgs:
        print("  - %s" % m, file=sys.stderr)
    print("REFUSE: COVERAGE_ACCOUNT (%d finding(s))" % len(msgs), file=sys.stderr)
    return 1


def check(root: Path) -> list[str]:
    out: list[str] = []
    if not (root / DECISIONS).is_file():
        return ["%s is absent; the retirements cannot be enumerated" % DECISIONS]
    try:
        doc = load_decisions(root)
    except DecisionsError as exc:
        return ["%s: %s" % (DECISIONS, exc)]
    retired = [str(r.get("path") or "") for r in (doc.get("retired_sources") or [])]
    if not (root / ACCOUNT).is_file():
        return ["%s is absent; %d retired source(s) are unaccounted (run compose-coverage-account.py)" % (ACCOUNT, len(retired))]
    account = load_json(root / ACCOUNT)
    rows = {str(r.get("path")): r for r in (account.get("rows") or []) if isinstance(r, dict)}
    for path in retired:
        if path not in rows:
            out.append("%s is retired by an ADR and has no row in the account" % path)
    for path, row in sorted(rows.items()):
        if path not in retired:
            out.append("%s has a row in the account but no ADR retires it" % path)
        if row.get("replaced_by") and not row.get("remaining_gap"):
            bad = [m for m in (row.get("replacement_measured") or []) if str(m.get("verdict")) != "PASS"]
            if bad:
                out.append("%s claims a replacement whose scenario did not pass: %s" % (path, bad))
    # the account must equal what the same inputs produce now. The recomputation
    # goes to a temporary file: a checker measures, it never authors.
    if COMPOSER.is_file():
        with tempfile.TemporaryDirectory(prefix="coverage-account-") as td:
            fresh_p = Path(td) / "coverage-account.json"
            proc = subprocess.run([sys.executable, str(COMPOSER), str(root), "--out", str(fresh_p)], text=True, capture_output=True)
            if proc.returncode != 0:
                out.append("the account could not be recomputed from decisions.yaml and the parity receipt: %s" % proc.stderr.strip()[-200:])
            elif json.dumps(load_json(fresh_p), sort_keys=True) != json.dumps(account, sort_keys=True):
                out.append("the account on disk is not what decisions.yaml and the parity receipt produce; re-run compose-coverage-account.py instead of editing it")
    else:
        out.append("compose-coverage-account.py is missing; the account cannot be verified against its inputs")
    if (root / VERDICT).is_file():
        verdict = load_json(root / VERDICT)
        carried = verdict.get("coverage_account")
        summary = account.get("summary") or {}
        want = {"retired": summary.get("retired"), "remaining_gaps": summary.get("remaining_gaps")}
        if not isinstance(carried, dict):
            out.append("%s does not carry coverage_account %s" % (VERDICT, want))
        else:
            got = {"retired": carried.get("retired"), "remaining_gaps": carried.get("remaining_gaps")}
            if got != want:
                out.append("%s carries coverage_account %s but the account says %s" % (VERDICT, got, want))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    findings = check(root)
    if findings:
        return _refuse(findings)
    account = load_json(root / ACCOUNT)
    s = account.get("summary") or {}
    print("PASS: coverage account complete (%s retired, %s replaced, %s remaining gap(s))" % (s.get("retired"), s.get("replaced"), s.get("remaining_gaps")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
