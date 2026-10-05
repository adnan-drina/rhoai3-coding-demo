#!/usr/bin/env python3
"""WC-5 — mta_rescan must prove the analyzer ran over the tree M4 judges, after M3.

v19 M5 named the rescan six times, ran check-findings-handoff.py only, and
wrote PASS. Presence of findings-handoff.json is not a rescan.

v9 M4 (t_caf2ad51, 2026-09-22) is the other half: this floor digested
evidence/mta-findings.json — the LEGACY scan M1 took of the frozen source —
by default, compared it with the M1 snapshot of that same file, and refused
every run whose destination rescans live where the loop writes them
(verification/mta-rescan/findings.json). The floor compared the legacy scan
with itself and could never pass.

What it judges now (the default): the destination rescan record,
``verification/mta-rescan/findings.json`` (planner.paths.MTA_RESCAN_FINDINGS,
written by mta-rescan-destination.sh after every loop step and by the M4
road after the generated tests are committed). Three facts, each printed:

  * ``execution_evidence.analyzer_ran`` is true — the analyzer ran;
  * ``execution_evidence.tree_sha256`` equals the digest of the product tree
    on disk now (planner.canonical.product_tree_sha256, the same function the
    loop records as an accepted step's candidate_sha256) — the analyzer ran
    over THIS tree, not an older one;
  * ``normalized_at`` is newer than the last M3 completion — the commit time
    of the last step the loop record (verification/loop/steps.json) holds a
    commit for. The loop stamps no clock on a step; the commit it records is
    what git dates, so that is the stamp read, never a clock this floor
    invents.

A copy of M1 is still not a rescan: when the record's input_digest equals the
M1 snapshot (evidence/derived/m1-findings-digest.json) the floor refuses by
name, whichever path --findings points at. The legacy path
(evidence/mta-findings.json), given explicitly, is judged as before: a re-run
of the analyzer over the frozen source carries the M1 input digest and is
refused as a copy of M1 — it is the source's scan, not the destination's.

--snapshot-m1 writes evidence/derived/m1-findings-digest.json if absent
(called from mta-analyze-legacy.sh after the first normalize). M4 assert
never snapshots.

Usage:
  python3 assert-mta-rescan.py ROOT
  python3 assert-mta-rescan.py ROOT --findings verification/mta-rescan/findings.json
  python3 assert-mta-rescan.py ROOT --findings evidence/mta-findings.json   (legacy; refused as M1)
  python3 assert-mta-rescan.py ROOT --snapshot-m1 --findings PATH
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import product_tree_sha256  # noqa: E402
from planner.paths import LOOP_STEPS, MTA_FINDINGS, MTA_RESCAN_FINDINGS  # noqa: E402

SCHEMA = "rhoai3.m1-findings-digest/v1"
SNAPSHOT_REL = "evidence/derived/m1-findings-digest.json"
FINDINGS_REL = MTA_FINDINGS.as_posix()  # the legacy M1 scan: snapshot source, never the default here
RESCAN_REL = MTA_RESCAN_FINDINGS.as_posix()  # the destination rescan record the floor judges
TRUE_VALUES = (True, "true", "yes", 1)

EXIT_CODES = """Exit codes:
  0  pass — the destination rescan record says analyzer_ran, its tree digest
     is this tree's, and its stamp is newer than the last M3 completion
     (or --snapshot-m1 wrote/kept the M1 snapshot)
  1  BLOCK — no rescan record, analyzer did not run, a copy of M1, a rescan
     of another tree, or a stamp not newer than the last M3 completion
  2  usage / harness defect
"""


def parse_ts(raw: object) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not an object")
    return data


def _fail(msg: str) -> int:
    print("FAIL: mta_rescan: " + msg, file=sys.stderr)
    return 1


def snapshot_payload(findings: dict, findings_path: Path) -> dict:
    ev = findings.get("execution_evidence") if isinstance(
        findings.get("execution_evidence"), dict
    ) else {}
    return {
        "schema": SCHEMA,
        "findings_path": str(findings_path),
        "input_digest": str(ev.get("input_digest") or ""),
        "normalized_at": str(findings.get("normalized_at") or ""),
        "analyzer_ran": bool(ev.get("analyzer_ran")),
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def commit_time(root: Path, sha: str) -> datetime | None:
    """When git says this commit was made (committer date). None when the
    commit is not in this repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", "-s", "--format=%cI", sha],
            text=True, capture_output=True, check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return parse_ts(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "")


def last_m3_completion(root: Path) -> tuple[dict | None, str]:
    """The last step the loop record holds a commit for, dated by git.

    Returns ({card, commit, verdict, at}, "") or (None, why). A step whose
    commit git cannot date is a defect, not an absence: the record names a
    tree this repository does not hold."""
    steps_path = root / LOOP_STEPS
    if not steps_path.is_file():
        return None, "no loop record (%s): no M3 completion on record" % LOOP_STEPS.as_posix()
    try:
        steps = load_json(steps_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return None, "unreadable loop record %s: %s" % (LOOP_STEPS.as_posix(), exc)
    rows = [s for s in (steps.get("steps") or []) if isinstance(s, dict) and str(s.get("commit") or "").strip()]
    if not rows:
        return None, "the loop record holds no step with a commit: no M3 completion on record"
    last = rows[-1]
    sha = str(last.get("commit") or "").strip()
    at = commit_time(root, sha)
    if at is None:
        return None, ("DEFECT: the last recorded loop step (card %s, verdict %s) names commit %s, which git cannot "
                      "date in this repository" % (last.get("card") or "-", last.get("verdict") or "-", sha[:12]))
    return {"card": str(last.get("card") or ""), "commit": sha, "verdict": str(last.get("verdict") or ""), "at": at}, ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--findings",
        default=RESCAN_REL,
        help="dest-relative or absolute findings record (default: %s, the destination rescan; "
             "%s is the legacy M1 scan and is refused as a copy of M1)" % (RESCAN_REL, FINDINGS_REL),
    )
    ap.add_argument(
        "--snapshot-m1",
        action="store_true",
        help="write M1 digest snapshot if absent (M1 analyze path only)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    findings_path = Path(args.findings)
    if not findings_path.is_absolute():
        findings_path = root / findings_path
    try:
        rel = findings_path.resolve().relative_to(root).as_posix()
    except ValueError:
        rel = str(findings_path)
    legacy = findings_path.resolve() == (root / MTA_FINDINGS).resolve() or findings_path.name == MTA_FINDINGS.name
    snap_path = root / SNAPSHOT_REL

    if args.snapshot_m1:
        if not findings_path.is_file():
            return _fail("mta findings missing: %s" % findings_path)
        try:
            findings = load_json(findings_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return _fail("unreadable findings %s: %s" % (findings_path, exc))
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        if snap_path.is_file():
            print(f"OK: M1 findings digest snapshot already present ({SNAPSHOT_REL})")
            return 0
        snap_path.write_text(
            json.dumps(snapshot_payload(findings, findings_path), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"OK: wrote {SNAPSHOT_REL}")
        return 0

    if not findings_path.is_file():
        if legacy:
            return _fail("mta findings missing: %s" % findings_path)
        return _fail("no destination rescan record at %s — the analyzer has not run over this tree; "
                     "mta-rescan-destination.sh writes it (WC-5: a rescan is an analyzer run, not a file)" % rel)
    try:
        findings = load_json(findings_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("unreadable findings %s: %s" % (findings_path, exc))

    ev = findings.get("execution_evidence")
    if not isinstance(ev, dict):
        return _fail("execution_evidence missing in %s (handoff presence is not a rescan; WC-5)" % rel)
    if ev.get("analyzer_ran") not in TRUE_VALUES:
        return _fail("execution_evidence.analyzer_ran is not true in %s (WC-5: the analyzer must have run)" % rel)
    digest = str(ev.get("input_digest") or "").strip()
    normalized_at = str(findings.get("normalized_at") or "").strip()
    if not digest:
        if legacy:
            return _fail("execution_evidence.input_digest missing in %s" % rel)
        return _fail("%s carries no execution_evidence.input_digest — a record written before the rescan recorded "
                     "what it scanned cannot be told apart from a copy of M1; re-run mta-rescan-destination.sh on "
                     "this tree" % rel)
    if not normalized_at:
        return _fail("normalized_at missing in %s" % rel)
    if "/fixtures/admission/" in str(findings_path).replace("\\", "/"):
        return _fail("findings path is an admission fixture (INCONCLUSIVE_FIXTURE; B-5/WC-5)")
    ts = parse_ts(normalized_at)
    if ts is None:
        return _fail("normalized_at=%r unparseable in %s" % (normalized_at, rel))

    # A copy of M1 is not a rescan, whichever path it sits at.
    snap_digest = ""
    if snap_path.is_file():
        try:
            snap = load_json(snap_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return _fail("unreadable M1 snapshot: %s" % exc)
        snap_digest = str(snap.get("input_digest") or "").strip()
    elif legacy:
        return _fail("missing %s — cannot prove this run is newer than M1 (first analyze must --snapshot-m1)" % SNAPSHOT_REL)
    if snap_digest and digest == snap_digest:
        return _fail("input_digest equals M1 snapshot — a copy of M1 without a new analyzer run is not a rescan "
                     "(WC-5); %s carries input_digest=%s, the M1 snapshot %s carries the same. "
                     "The destination rescan is judged at %s (the default)"
                     % (rel, digest[:24], SNAPSHOT_REL, RESCAN_REL))
    if legacy:
        return _fail("%s is the legacy scan of the frozen source (input_digest=%s), not a rescan of the destination; "
                     "the destination rescan record is %s (the default)" % (rel, digest[:24], RESCAN_REL))

    # The tree the analyzer ran over must be the tree M4 is judging.
    rec_tree = str(ev.get("tree_sha256") or "").strip()
    if not rec_tree:
        return _fail("%s carries no execution_evidence.tree_sha256 — a rescan that does not say which tree it "
                     "scanned cannot be matched to the tree M4 judges; re-run mta-rescan-destination.sh on this tree"
                     % rel)
    on_disk = product_tree_sha256(root)
    if rec_tree != on_disk:
        return _fail("the rescan is of another tree: %s scanned tree_sha256=%s (git_head=%s, normalized_at=%s), "
                     "the tree on disk digests to %s — the product tree changed after this rescan (generated tests "
                     "committed, a later card, an edit); re-run mta-rescan-destination.sh on this tree"
                     % (rel, rec_tree[:12], str(ev.get("git_head") or "-")[:12], normalized_at, on_disk[:12]))

    # The analyzer must have run after M3 finished with the tree.
    last, why = last_m3_completion(root)
    if last is None and why.startswith("DEFECT:"):
        return _fail(why)
    if last is not None and ts <= last["at"]:
        return _fail("normalized_at %s is not newer than the last M3 completion %s (card %s, verdict %s, commit %s "
                     "dated by git) (WC-5); re-run mta-rescan-destination.sh"
                     % (normalized_at, fmt_ts(last["at"]), last["card"] or "-", last["verdict"] or "-", last["commit"][:12]))

    print(
        "OK: mta_rescan PASS — %s: analyzer_ran cli=%s; tree_sha256=%s == tree on disk %s (git_head=%s); "
        "normalized_at=%s %s; input_digest=%s %s"
        % (rel, str(ev.get("cli") or "-"), rec_tree[:12], on_disk[:12], str(ev.get("git_head") or "-")[:12],
           normalized_at,
           ("> last M3 completion %s (card %s, commit %s)" % (fmt_ts(last["at"]), last["card"] or "-", last["commit"][:12]))
           if last is not None else "(%s)" % why,
           digest[:24],
           ("!= M1 snapshot %s" % snap_digest[:24]) if snap_digest else "(no M1 snapshot on record)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
