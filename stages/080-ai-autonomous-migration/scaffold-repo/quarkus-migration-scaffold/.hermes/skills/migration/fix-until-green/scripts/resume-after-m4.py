#!/usr/bin/env python3
"""Resume the loop after an M4 verdict: repair what a card can repair, record what it cannot.

M4 is a measurement, and `REFUSE` is one of its answers. Until now nothing
consumed that answer: `advance.py` mints only after an ACCEPTED M3 step, the
close card ends on `kanban_request_review`, and the parity mismatches the
phase measured sat in `verification/parity/` as obligations nobody minted. So
the run stopped at its own first honest result.

This tool is the missing edge. It reads THE PARITY RECEIPT for the work a card
can do and the verdict's failed floors for the decisions no card discharges,
and acts on each:

  * an OBLIGATION is what `planner.worklist.parity_items` makes of the current
    receipt and the verdicts beside it, when its locus is a file of this tree.
    It is read from the receipt itself and never from the verdict's floor list:
    v9's runner-driven road composed a REFUSE naming `check-empty-security` and
    `check-product-tests` and did NOT name `compose-parity-receipt`, while the
    receipt on disk was FAIL with thirteen FAIL rows -- and a resume that asks
    the floor list what to repair finds nothing to mint over evidence that is
    right there. Those obligations are already in the work list the moment it
    is rebuilt (`kind: parity` / `config`, category `mandatory`), so resuming
    is: close the M4 card on the record, rebuild, re-seal admission, and let K4
    mint the head cluster -- exactly the transaction `advance.py` runs after an
    accepted step;

  * a DECISION is everything a card cannot discharge. `check-product-tests`
    and `assert-surefire-results` are ADR-015 territory (a harness capability
    owns the generated product tests; a worker card cannot author them and must
    not weaken them); `check-empty-security` and every receipt row whose
    read-back answered 401/403 are ADR-014 territory (method security with no
    identity provider behind it: the security switch, one bounded Operator
    step). Those are recorded in `verification/loop/release-blockers.json` and
    named on stderr. They are not minted, because a card is not what discharges
    them -- and they are not hidden either, because a floor nobody names is a
    floor nobody fixes.

A row the destination REFUSED (401/403) is an ADR-014 obligation whichever
verdict the receipt gives it. It began as INCONCLUSIVE -- the comparison could
not be made -- and on the v9 receipt it is typed FAIL, because a destination
that answers 403 where the source answered 200 IS a difference. Either way the
parity item it would mint is withheld from the mint: sending a worker to a
controller to make a security decision is the one repair this loop must not
ask for.

Both kinds at once (v9's first M4 verdict) is the normal case: the loop
continues on the parity obligations AND writes the blockers file. One printed
line per class, so the Operator reads what moved and what did not.

Refuses, and changes nothing, unless the verdict belongs to THIS run. Three
bindings say so, and all three are read from artifacts rather than from a
worker's memory (compose-m4-verdict's `bind-m4-verdict.py` writes them and its
`assert-m4-verdict-schema.py` requires them):

  * `card_id` is the issued close card (`verification/loop/issued.json`
    `task_id`) -- WHO answered;
  * `receipt_sha256` is the admission receipt that card was minted under (the
    same file's `receipt_sha256`) -- WHICH TREE was measured;
  * `parity_receipt_sha256` is the digest of `verification/parity/receipt.json`
    itself -- WHICH EVIDENCE was judged. A parity phase that ran again after
    the verdict was composed moves it, and the verdict is then answering for
    evidence this tree no longer holds.

Beside them: the parity receipt itself is bound to the admission receipt that
seals the tree on disk, no candidate is retained for the close card, and the
product tree is clean. A second run after a resume refuses: the close card is
on the record.

One reason the receipt can be unauthoritative is NOT a broken chain, and v9
stopped on it: a harness generation installed between the M4 verdict and this
resume rewrites a contract file the receipt seals, and the seal moves under a
tree nobody touched. When the gaps name contracts and nothing else -- the
evidence bundle, the work list, the bootstrap receipt, decisions.yaml and the
pins all still hash to their seals, and the product tree is clean -- admission
is RE-SEALED here (`pipeline.admit`, the same call made after the close), what
moved and the two receipts are recorded on the close row and in
release-blockers.json, and the run continues. The verdict is still the verdict
of the issued close card on this tree: `card_id` binds it to the card and the
parity receipt's digest to the seal it was measured under, which is why that
binding accepts the superseded receipt as well as the new one. Any other gap
refuses as before.

A CLEAN ACCEPTANCE is the fourth answer, and until H16 it had no terminator.
Measured on v9 (t_7740ad21, 2026-09-22): the M4 close card composed
PROVISIONAL_ACCEPT, bound, with `failed_floors: []`, eleven floors at rc 0 and
`ship: false`; the board card went `done`; and this tool REFUSED it -- "the
parity receipt names no obligation ... there is nothing to resume". Nothing was
wrong with the verdict. The consequences were: `verification/loop/issued.json`
still named the close card, so the loop believed a card was open and nothing
could be minted beside it; and `release-blockers.json` still listed a floor
from the PREVIOUS, superseded REFUSE verdict, which the run report reads as
current. A run's success path has to close, or its record keeps describing a
question the run has answered.

So a verdict the road treats as ACCEPTING (`ACCEPT_TOKENS`, read from
compose-m4-verdict's own lint) with an empty `failed_floors`, no obligation a
card may repair and no floor a decision owns CLOSES the run: the close row goes
on the record, the issued card is cleared, and release-blockers.json is
rewritten FROM THIS VERDICT -- an explicit empty record naming the verdict that
cleared it and when, never a superseded file left in place.

Closed is not shipped, and the close-out says so from the evidence rather than
from a claim: `ship: false` at M4 means the floors were met. What is still
outstanding -- the parity receipt's verdict and its entry-point coverage, the
capability gaps it recorded, the coverage account's remaining gaps, the
verdict's own reason -- is read off those artifacts and printed, and kept in
the blockers file under `outstanding`. A closed run with coverage gaps is not a
shipped run.

Exit 0 resumed (a card was minted) or closed (a clean acceptance); 1 refused;
2 blocked (nothing a card may repair once the ADR-014 rows are withheld).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import PARITY_SOURCE_SCHEMA, ensure_hermes_lib, git, load_issued, load_steps, pending_for, publish_loop_state, save_steps, snapshot_parity  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.admission import ADMITTED, verify_receipt  # noqa: E402
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.cards import CLOSE_ID  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, LOOP_DIR, LOOP_ISSUED, PARITY_DIR  # noqa: E402
from planner.worklist import build_worklist, head_cluster, parity_items  # noqa: E402

M4_VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
# bind-m4-verdict.py's record of the verdict AS BOUND (digest + copy + bindings)
M4_VERDICT_BINDING = Path("evidence") / "verdicts" / "m4-verdict.bound.json"
M4_VERDICT_BINDING_SCHEMA = "rhoai3.m4-verdict-binding/v1"
PARITY_RECEIPT = PARITY_DIR / "receipt.json"
RELEASE_BLOCKERS = LOOP_DIR / "release-blockers.json"
BLOCKERS_SCHEMA = "rhoai3.release-blockers/v1"
PARITY_RECEIPT_SCHEMA = "rhoai3.parity-receipt/v1"

# The verdict tokens the ROAD treats as accepting. They are not invented here:
# compose-m4-verdict's `assert-m4-verdict-schema.py` owns the vocabulary
# (`ACCEPT_TOKENS`) and its ACCEPT_WITH_FAILED_FLOOR code refuses any of them
# beside a failed floor. resume-after-m4.test.py asserts this set IS that one,
# so a token the road adds arrives here rather than being guessed at.
M4_VERDICT_LINT = (Path(".hermes") / "skills" / "gates" / "compose-m4-verdict" / "scripts"
                   / "assert-m4-verdict-schema.py")
ACCEPT_TOKENS = frozenset({"PROVISIONAL_ACCEPT", "ACCEPT", "SCOPED_ACCEPT"})

# `planner.admission.verify_receipt` reports one gap per sealed contract whose
# file no longer hashes to its seal, in exactly this shape. It is reconstructed
# here rather than matched by prefix so that the test below is an equality over
# a set and not a guess about a string: if that message ever changes, the set
# stops matching and the resume refuses, which is the safe direction.
CONTRACT_GAP = "contract %s changed after admission"

# The floors a parity FAIL composes. A floor in this set is a decision only
# when the receipt yields no obligation a card can carry; the obligations
# themselves are read from the receipt, not from this list.
PARITY_FLOORS = frozenset({"compose-parity-receipt"})

# ADR-014: a request the destination REFUSED (401/403) where the source
# answered is the security switch, not a destination defect -- method security
# declared with no identity provider behind it. The comparator writes its
# findings as "status <have> vs <want>" diffs, so an unauthorized read-back is
# recognised by that shape and nothing else.
SECURITY_ADR = "ADR-014"
SECURITY_OWNER = "Operator step"
SECURITY_DETAIL = ("the destination refused a request the source answered; ADR-014 gives one bounded Operator step the "
                   "conditional authorization adapter, the Basic/JPA identity mapping and both modes' captures. A card "
                   "cannot decide who may call an entry point")
INCONCLUSIVE_DETAIL = ("the read-back was refused by the source security switch; ADR-014 gives one bounded Operator step the "
                       "conditional authorization adapter, the Basic/JPA identity mapping and both modes' captures. A card "
                       "cannot compare an entry point nobody may call")
_UNAUTHORIZED = re.compile(r"status 40[13] vs")

# The closed table of release floors that are NOT cards, with the decision
# that owns each and the seat that discharges it. Specimen-agnostic: these are
# harness floor names and ADR ids, never a specimen's files or symbols.
DECISION_FLOORS = {
    "check-empty-security": (SECURITY_ADR, SECURITY_OWNER, "method security is declared with no identity provider behind it, so every guarded request answers 401/403; ADR-014 owns the conditional authorization adapter and the Basic/JPA identity mapping in ONE bounded Operator step, and refuses deleting an authorization semantic, permitting all, or manufacturing a privileged identity"),
    "check-product-tests": ("ADR-015", "harness capability", "the product acceptance tests are generated deterministically from qualified source scenarios; a worker card gets no authority to author or weaken them"),
    "assert-surefire-results": ("ADR-015", "harness capability", "the surefire floor needs its own evidence-based diagnosis; a fresh report with zero skips is a harness output, not a patch"),
}
UNKNOWN_FLOOR_OWNER = "Operator"


def _refuse(msg: str) -> int:
    print("REFUSE: LOOP_RESUME %s" % msg, file=sys.stderr)
    return 1


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def close_rows(steps: dict) -> list:
    """Every M4 close this record already carries.

    They live in `steps["rejected"]`, which is the loop's ledger of CLOSED
    CARDS rather than of rejections: `rewind.py` already files rewound
    ACCEPTED steps there for the same reason, and `live_board.expected_from_loop`
    reads exactly that list to decide which minted cards may still be on the
    board. A close recorded anywhere else would leave the M4 card with no
    expected entry, and the very next `k4_mint.py --verify-board` would call
    it foreign. The rows carry `kind: "close"`, spend no attempt and name no
    M3 cluster, so nothing that reads this list for attempts (planner.budget)
    or for a cluster's previous attempts (brief.py) ever matches one."""
    return [r for r in (steps.get("rejected") or [])
            if isinstance(r, dict) and str(r.get("kind") or "") == "close"]


def already_resumed(steps: dict, card: str) -> bool:
    return any(str(r.get("card") or "") == card and r.get("resumed") for r in close_rows(steps))


def already_closed(steps: dict, card: str) -> bool:
    """A clean acceptance closes the run once. The close row is the record of
    it, and a second close-out would rewrite a blockers file this run has
    already answered."""
    return any(str(r.get("card") or "") == card and r.get("closed") for r in close_rows(steps))


def outstanding_rows(verdict: dict, preceipt: dict) -> list:
    """What a CLOSED run still owes before it could ship.

    `ship: false` on a PROVISIONAL_ACCEPT says the floors were met, not that
    the run is released, and this is where the difference is stated honestly.
    Every row is READ off an artifact -- the parity receipt's own verdict and
    coverage summary, the capability gaps it recorded, the coverage account the
    verdict carries, the verdict's own reason -- so nothing here asserts a
    completeness the evidence does not hold."""
    out: list = []
    rows = [r for r in (preceipt.get("entry_points") or []) if isinstance(r, dict)]
    rv = str(preceipt.get("verdict") or "")
    if rv and rv != "PASS":
        not_passed = sum(1 for r in rows if str(r.get("verdict") or "") != "PASS")
        cov = preceipt.get("coverage_summary") if isinstance(preceipt.get("coverage_summary"), dict) else {}
        detail = "the parity receipt is %s: %d of %d entry point(s) did not pass" % (rv, not_passed, len(rows))
        if cov:
            detail += (" (%d covered by read oracle, %d by qualified scenario, %d not compared at all)"
                       % (int(cov.get("by_oracle") or 0), int(cov.get("by_scenario") or 0), int(cov.get("uncovered") or 0)))
        out.append({"kind": "parity-receipt", "count": not_passed, "detail": detail})
    gaps = [g for g in (preceipt.get("coverage_gaps") or []) if isinstance(g, dict)]
    if gaps:
        out.append({"kind": "capability-gap", "count": len(gaps),
                    "detail": "%d capability gap(s) the source never demonstrated: %s"
                              % (len(gaps), ", ".join(sorted({str(g.get("scenario") or "") for g in gaps}))[:200])})
    cors = [str(g) for g in ((preceipt.get("cors") or {}).get("gaps") or []) if str(g)]
    if cors:
        out.append({"kind": "cors-gap", "count": len(cors), "detail": "; ".join(cors)[:300]})
    acct = verdict.get("coverage_account") if isinstance(verdict.get("coverage_account"), dict) else {}
    try:
        remaining, retired = int(acct.get("remaining_gaps") or 0), int(acct.get("retired") or 0)
    except (TypeError, ValueError):
        remaining, retired = 0, 0
    if remaining:
        out.append({"kind": "coverage-account", "count": remaining,
                    "detail": "%d of %d retired source(s) still have a remaining gap (evidence/verdicts/coverage-account.json)"
                              % (remaining, retired)})
    reason = str(verdict.get("reason") or "").strip()
    if reason:
        out.append({"kind": "verdict-reason", "count": 0, "detail": reason[:400]})
    if not verdict.get("ship"):
        out.append({"kind": "not-shipped", "count": 0,
                    "detail": "the verdict does not ship (M4 never does): the floors are met and the run is closed, "
                              "and a release is M5's answer, not this one"})
    return out


def moved_contracts(root: Path, receipt: dict, gaps: list) -> list:
    """The sealed contract files whose bytes moved, when that is the WHOLE gap.

    A harness generation installed between the M4 verdict and the resume
    rewrites contracts -- schemas, catalogs, MTA rules -- and the admission
    receipt seals every one of them. `verify_receipt` then reports the receipt
    as not authoritative, and v9 stopped there: the verdict of the issued close
    card, bound to that card by `card_id` and to the tree by the parity
    receipt's digest, was discarded because a file NOBODY MEASURED had changed.

    Only the seal moved in that case, and a seal is re-sealable. So this
    answers one question precisely: is the set of gaps exactly the set of
    contracts whose file no longer hashes to its seal? If it is, then the
    evidence bundle, the work list, the bootstrap receipt, `decisions.yaml` and
    the pins all still hash to their seals and the receipt's digest still
    matches its body -- every other reason the chain could be broken is absent,
    because each of them is a gap and there are no other gaps. Anything else,
    including a contract the tree has LOST rather than changed, returns the
    empty list and the caller refuses exactly as before."""
    seals = ((receipt or {}).get("seals") or {}).get("contracts") or {}
    changed = []
    for rel, sha in sorted(seals.items()):
        p = Path(root) / rel
        if not p.is_file():
            return []  # a contract that is gone is not a contract that moved
        if sha256_file(p) != sha:
            changed.append(rel)
    if not changed or {str(g) for g in gaps} != {CONTRACT_GAP % rel for rel in changed}:
        return []
    return changed


def repairable_obligations(root: Path, bundle: dict) -> list:
    """Parity obligations whose locus is a file of THIS tree.

    An obligation the work list would place on `GLOBAL` (an entry point the
    bundle carries no path for) has no derivable write scope: admission blocks
    it as SCOPE_UNDERIVED and nothing mints. Such a parity FAIL is not a card,
    so it is counted with the decisions, not with the repairs. An obligation
    OWED a harness adapter (ADR-019) is placed on the adapter's contract path,
    which need not exist yet: its sealed obligation is the write scope."""
    out = []
    for item in parity_items(root, bundle):
        rel = str(item.get("path") or "")
        owed = item.get("owed") if isinstance(item.get("owed"), dict) else {}
        if rel and ((root / rel).is_file() or str(owed.get("path") or "") == rel):
            out.append(item)
    return out


def unauthorized_entry_points(receipt: dict) -> list:
    """The receipt's rows whose reason is a 401/403 read-back (ADR-014).

    The verdict such a row carries is NOT what types it. A refused read-back
    began as INCONCLUSIVE, because a comparison nobody was allowed to make is
    not a comparison; on the v9 receipt the same rows are FAIL, because a
    destination answering 403 where the source answered 200 is a difference
    like any other. The diff shape is the invariant across both readings, so
    it is the only thing matched here -- and both readings name the same
    seat, ADR-014's one bounded Operator step."""
    out = []
    seen = set()
    for row in receipt.get("entry_points") or []:
        if not isinstance(row, dict):
            continue
        verdict = str(row.get("verdict") or "")
        if verdict not in ("FAIL", "INCONCLUSIVE"):
            continue
        reason = str(row.get("reason") or "")
        ep = str(row.get("entry_point") or "")
        if not ep or ep in seen or not _UNAUTHORIZED.search(reason):
            continue
        seen.add(ep)
        out.append({"entry_point": ep, "verdict": verdict, "reason": reason[:400], "adr": SECURITY_ADR,
                    "owner": SECURITY_OWNER, "detail": SECURITY_DETAIL if verdict == "FAIL" else INCONCLUSIVE_DETAIL})
    return out


def withhold(obligations: list, unauthorized: list) -> tuple:
    """Split the repairable obligations into (mintable, withheld by ADR-014).

    An entry point the destination refuses is ADR-014's, and the obligation
    `parity_items` derives from its row would put a worker in front of a
    controller with a security decision to make -- exactly what the ruling
    reserves for one bounded Operator step. The row is recorded as a blocker
    instead, and its obligation is withheld: not repaired, not hidden, and not
    counted as a reason to resume."""
    blocked = {r["entry_point"] for r in unauthorized}
    mintable = [i for i in obligations if str(i.get("entry_point") or "") not in blocked]
    held = [i for i in obligations if str(i.get("entry_point") or "") in blocked]
    return mintable, held


def floor_rows(decision_floors: list, parity_unrepairable: list, unauthorized: list) -> list:
    """One row per floor no card discharges, each naming the ADR that owns it.

    A floor is recorded ONCE however many receipt rows explain it: twelve
    refused read-backs are twelve entry points and one `check-empty-security`,
    and `explained_by` says how many of them the receipt carries."""
    rows = []
    for name in decision_floors:
        adr, owner, detail = DECISION_FLOORS.get(name, ("", UNKNOWN_FLOOR_OWNER, "release floor %s is not a card" % name))
        row = {"floor": name, "class": "decision", "adr": adr, "owner": owner, "detail": detail}
        if adr == SECURITY_ADR and unauthorized:
            row["explained_by"] = len(unauthorized)
        rows.append(row)
    for name in parity_unrepairable:
        if unauthorized:
            rows.append({"floor": name, "class": "parity", "adr": SECURITY_ADR, "owner": SECURITY_OWNER,
                         "explained_by": len(unauthorized),
                         "detail": "release floor %s is not a card: every parity verdict under it that names a file of this tree is a request the destination refused, which is ADR-014's bounded Operator step" % name})
        else:
            rows.append({"floor": name, "class": "parity", "adr": "", "owner": UNKNOWN_FLOOR_OWNER,
                         "detail": "release floor %s is not a card: the parity verdicts under it name no obligation whose locus is a file of this tree" % name})
    return rows


def blocker_line(row: dict) -> str:
    who = "owned by %s (%s)" % (row["adr"], row["owner"]) if row.get("adr") else "owned by no ADR (%s)" % row["owner"]
    return "BLOCKED: LOOP_RELEASE_FLOOR %s %s — %s" % (row["floor"], who, row["detail"])


def entry_point_line(row: dict) -> str:
    return ("BLOCKED: LOOP_RELEASE_FLOOR %s owned by %s (%s) — %s: %s"
            % (row["entry_point"], row["adr"], row["owner"], row["detail"], row["reason"]))


def write_blockers(root: Path, doc: dict) -> Path:
    path = root / RELEASE_BLOCKERS
    write_canonical(path, doc)
    return path


def mint(root: Path, hermes: str, execute: bool) -> int:
    """K4 mints the next card. `--exec` is advance.py's own mint, unchanged."""
    if execute:
        import advance  # noqa: E402  (heavy; only the exec path needs it)

        return advance._mint(root, hermes)
    kernel = root / ".hermes" / "kernel" / "k4_mint.py"
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)  # control cards come from verification/loop/cards.json
    proc = subprocess.run([sys.executable, str(kernel), "--root", str(root), "--hermes", hermes],
                          text=True, capture_output=True, env=env)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        return 1
    try:
        dry = json.loads(proc.stdout)
        row = (dry.get("argv") or [])[0]
        argv = list(row["argv"])
    except (ValueError, KeyError, IndexError, TypeError):
        sys.stdout.write(proc.stdout)
        return 1
    key = argv[argv.index("--idempotency-key") + 1] if "--idempotency-key" in argv else ""
    body = argv[argv.index("--body") + 1] if "--body" in argv else ""
    print("MINT (dry-run) card=%s key=%s receipt=%s" % (row.get("logical_id"), key, str(dry.get("receipt_sha256") or "")[:16]))
    print("  argv: %s" % " ".join(shlex.quote(a) for a in argv))
    print("--- card body ---")
    print(body)
    print("--- end card body ---")
    return 0


def close_out(root: Path, args: Any, verdict: dict, preceipt: dict, steps: dict, *, card_id: str, token: str,
              receipt: dict, corpus_sha: str, parity_on_disk: str, reseal: dict | None) -> int:
    """Close the run on a clean acceptance. Exit 0.

    Four things, in the order that keeps the record readable if any of them is
    the last to run:

      1. the close row on the loop record (`kind: close`, `closed: true`,
         `resumed: false`), carrying the verdict and its three bindings. It is
         what `already_closed` reads, and what `live_board.expected_from_loop`
         needs to stop calling the M4 card foreign;
      2. the comparison this verdict closed on becomes the accepted parity
         baseline, exactly as the resume path does it -- the close is what
         decides what the baseline IS;
      3. `verification/loop/issued.json` is cleared. On v9 it still named
         t_7740ad21 after the board closed the card, so the loop believed a
         card was open and nothing could be minted or recorded beside it;
      4. release-blockers.json is rewritten FROM THIS VERDICT. v9's copy still
         listed `assert-mta-rescan` from a superseded REFUSE, and the run
         report reads that file: a cleared floor left on disk is a false
         record. This verdict names no blocker, so the file becomes an
         explicit empty record saying which verdict cleared it and when -- and
         what is still outstanding, which is not the same thing."""
    now = _now()
    left = outstanding_rows(verdict, preceipt)
    blockers = {
        "schema": BLOCKERS_SCHEMA,
        "at": now,
        "operator": args.operator,
        "verdict_card": card_id,
        "verdict": token,
        "verdict_file": M4_VERDICT.as_posix(),
        "failed_floors": [],
        "receipt_sha256": str(receipt.get("receipt_digest") or ""),
        "corpus_sha256": corpus_sha,
        "floors": [],
        "entry_points": [],
        "owners": [],
        "resumed": False,
        "closed": True,
        "parity_obligations": [],
        "withheld_obligations": [],
        # WHICH verdict cleared this file, and when: an empty blockers file
        # with no such record is indistinguishable from one nobody wrote
        "cleared_by": {"verdict": token, "card": card_id, "at": now,
                       "detail": "every release floor this verdict measured returned rc 0 and it names no blocker; any "
                                 "floor a superseded verdict listed is cleared by this one"},
        # closed is not shipped, and this is the difference
        "outstanding": left,
    }
    if reseal:
        blockers["contract_reseal"] = reseal
    close_row = {
        "kind": "close", "cluster": CLOSE_ID, "card": card_id, "verdict": token,
        "failed_floors": [], "resumed": False, "closed": True, "operator": args.operator, "at": now,
        "receipt_sha256": str(receipt.get("receipt_digest") or ""), "corpus_sha256": corpus_sha,
        "parity_receipt_sha256": parity_on_disk,
        "parity_obligations": [], "withheld_obligations": [], "release_blockers": [],
        "outstanding": [r["kind"] for r in left],
        "measure": None, "changed": [],
        "reason": "M4 %s: every floor measured rc 0, the receipt names no obligation a card repairs and no floor a "
                  "decision owns; the run is CLOSED (ship %s) with %d outstanding item(s)"
                  % (token, bool(verdict.get("ship")), len(left)),
    }
    if reseal:
        close_row["contract_reseal"] = reseal
    steps.setdefault("rejected", []).append(close_row)
    save_steps(root, steps)
    snapshot_parity(root, {
        "schema": PARITY_SOURCE_SCHEMA, "at": now, "card": card_id, "verdict": token,
        "binding": {"mode": "sealed", "card": card_id},
        "receipt_sha256": parity_on_disk, "corpus_sha256": corpus_sha,
        "reason": "the M4 verdict for %s closed the run on this comparison" % card_id,
    })
    if (root / LOOP_ISSUED).is_file():
        (root / LOOP_ISSUED).unlink()
    publish_loop_state(root)
    path = write_blockers(root, blockers)
    print("CLOSED %s: M4 %s, %d floor(s) measured, none failed; the issued card is cleared and %s is rewritten from "
          "this verdict" % (card_id, token, len(verdict.get("floors") or []), RELEASE_BLOCKERS))
    for row in left:
        print("  - outstanding (%s): %s" % (row["kind"], row["detail"]))
    print("OK: run CLOSED on %s for card %s — closed is not shipped: %d item(s) remain before a release → %s"
          % (token, card_id, len(left), path))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--exec", dest="execute", action="store_true", help="shell hermes through k4_mint.py (default: dry-run argv + card body)")
    ap.add_argument("--hermes", default=os.environ.get("HERMES_BIN", "hermes"))
    ap.add_argument("--operator", default="", help="who ran this, recorded on the close row and in release-blockers.json")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    # --- the verdict, and that it is THIS run's -------------------------------
    vp = root / M4_VERDICT
    if not vp.is_file():
        return _refuse("no composed M4 verdict at %s; nothing to resume from (M4 has not run, or it could not measure)" % M4_VERDICT)
    try:
        verdict = load_json(vp)
    except (OSError, ValueError) as exc:
        return _refuse("%s is not readable JSON: %s" % (M4_VERDICT, exc))
    if not isinstance(verdict, dict):
        return _refuse("%s is not a verdict object" % M4_VERDICT)
    card_id = str(verdict.get("card_id") or "").strip()
    token = str(verdict.get("verdict") or "").strip().upper().replace("-", "_")
    steps = load_steps(root)
    # Asked first, and of the RECORD rather than of the issued card: a resume
    # replaces the issued close card with the card it mints, so by the time a
    # second run reads issued.json the close card is already gone. The record
    # is where the close is, and the record is what binds.
    if card_id and already_resumed(steps, card_id):
        return _refuse("already resumed for verdict %s; the close is on the record and the next card was minted from it" % card_id)
    if card_id and already_closed(steps, card_id):
        return _refuse("already closed for verdict %s; the run was closed on this verdict and its record is written" % card_id)

    issued = load_issued(root)
    if issued is None:
        return _refuse("no issued card (%s); the close card this verdict belongs to is not the loop's current card" % LOOP_ISSUED)
    if str(issued.get("kind") or "") != "close" or str(issued.get("cluster") or "") != CLOSE_ID:
        return _refuse("the issued card is %s (%s), not the M4 close card; resume only from a closed M4"
                       % (issued.get("cluster"), issued.get("kind")))
    task = str(issued.get("task_id") or "").strip()
    if not card_id:
        return _refuse("the verdict names no card_id, so it cannot be bound to the issued close card %s; a verdict that "
                       "names no card is a verdict for no run" % (task or "(unminted)"))
    if not task:
        return _refuse("the issued close card carries no task_id (it was converted but never minted); nothing binds "
                       "verdict card %s to this tree" % card_id)
    if card_id != task:
        return _refuse("the verdict was composed for card %s; the issued close card is %s" % (card_id, task))

    # The card is one of three bindings, and alone it says only WHO answered.
    # The admission receipt the card was minted under says WHICH TREE was
    # measured, and the parity receipt's own digest says WHICH EVIDENCE was
    # judged. compose-m4-verdict's lint requires all three and its binder
    # writes them from these same two files, so a disagreement here is a
    # verdict composed against something other than what is on disk now.
    minted_under = str(issued.get("receipt_sha256") or "").strip()
    verdict_receipt = str(verdict.get("receipt_sha256") or "").strip()
    if not verdict_receipt:
        return _refuse("the verdict names no receipt_sha256, so it cannot be bound to the admission receipt card %s "
                       "was minted under (%s); run compose-m4-verdict's bind-m4-verdict.py"
                       % (card_id, minted_under[:12] or "(none recorded)"))
    if not minted_under:
        return _refuse("the issued close card records no receipt_sha256; nothing says which admission receipt card %s "
                       "was minted under" % card_id)
    if verdict_receipt != minted_under:
        return _refuse("the verdict was composed under admission receipt %s; the issued close card %s was minted "
                       "under %s" % (verdict_receipt[:12], card_id, minted_under[:12]))

    # --- the parity receipt the verdict was composed from ---------------------
    pp = root / PARITY_RECEIPT
    if not pp.is_file():
        return _refuse("no %s; the verdict's parity floor cites a receipt that is not on disk" % PARITY_RECEIPT)
    preceipt = load_json(pp)
    if not isinstance(preceipt, dict) or str(preceipt.get("schema") or "") != PARITY_RECEIPT_SCHEMA:
        return _refuse("%s is not a %s document" % (PARITY_RECEIPT, PARITY_RECEIPT_SCHEMA))
    verdict_parity = str(verdict.get("parity_receipt_sha256") or "").strip()
    parity_on_disk = sha256_file(pp)
    if not verdict_parity:
        return _refuse("the verdict names no parity_receipt_sha256, so nothing binds it to the parity evidence it "
                       "judged (%s is %s); run compose-m4-verdict's bind-m4-verdict.py"
                       % (PARITY_RECEIPT, parity_on_disk[:12]))
    if verdict_parity != parity_on_disk:
        return _refuse("the verdict judged parity receipt %s; %s now digests to %s — the parity phase ran again "
                       "after this verdict was composed, so it answers for evidence this tree no longer holds"
                       % (verdict_parity[:12], PARITY_RECEIPT, parity_on_disk[:12]))

    # --- the verdict is byte-for-byte what was bound --------------------------
    # The composer's output is the verdict. bind-m4-verdict.py records the
    # digest of the file it bound with a copy of it; a verdict that no longer
    # digests to that record was edited after binding (v9's t_caf2ad51 revised
    # a bound verdict into a REFUSE with card_id "" by hand), and a verdict
    # with no record was bound by hand, which is not a binding.
    rp = root / M4_VERDICT_BINDING
    if not rp.is_file():
        return _refuse("no binding record %s; bind-m4-verdict.py writes it when it binds a verdict, so a verdict "
                       "without one was bound by hand -- a hand binding is not a binding" % M4_VERDICT_BINDING)
    try:
        record = load_json(rp)
    except (OSError, ValueError) as exc:
        return _refuse("%s is not readable JSON: %s" % (M4_VERDICT_BINDING, exc))
    if not isinstance(record, dict) or str(record.get("schema") or "") != M4_VERDICT_BINDING_SCHEMA:
        return _refuse("%s is not a %s record" % (M4_VERDICT_BINDING, M4_VERDICT_BINDING_SCHEMA))
    bound_sha = str(record.get("verdict_sha256") or "")
    on_disk_sha = sha256_file(vp)
    if on_disk_sha != bound_sha:
        copy = record.get("verdict") if isinstance(record.get("verdict"), dict) else {}
        drift = sorted(k for k in set(copy) | set(verdict) if copy.get(k) != verdict.get(k))
        return _refuse("the verdict was edited after binding: bound %s at %s, on disk %s; fields that differ: %s -- "
                       "the bound verdict is the verdict, and a revision is composed anew and bound, never edited in"
                       % (bound_sha[:12], record.get("bound_at") or "?", on_disk_sha[:12], ", ".join(drift) or "(byte-level only)"))

    # --- no live worker holds the tree ---------------------------------------
    # Asked BEFORE the seal is examined, because the contract re-seal below
    # writes to the tree: nothing is re-sealed while a candidate is retained or
    # while the product tree carries a change nobody measured.
    held = pending_for(steps, CLOSE_ID)
    if held is not None:
        return _refuse("a candidate is retained for the close card (%s, %s); restore-pending.py owns that protocol"
                       % (held.get("card"), held.get("cause")))
    dirty = git(root, "status", "--porcelain", "--", "src", "pom.xml").stdout.strip()
    if dirty:
        return _refuse("the product tree is not clean (%s); a worker may still hold it, and a resume must re-seal the "
                       "tree M4 measured" % ", ".join(ln[3:].strip() for ln in dirty.splitlines()[:3]))

    receipt, gaps = verify_receipt(root, require_admitted=True)
    reseal: dict | None = None
    if receipt is not None and gaps:
        moved = moved_contracts(root, receipt, gaps)
        if moved:
            # A harness generation moved a sealed contract between the verdict
            # and this resume. The verdict is still the verdict of the issued
            # close card on this tree -- `card_id` binds it to the card and the
            # parity receipt's digest binds it to the seal it was measured
            # under -- so the seal is re-taken here, with what moved recorded,
            # and the run continues. (This is `pipeline.admit`, the same call
            # the resume already makes after the close.)
            old_digest = str(receipt.get("receipt_digest") or "")
            rec0 = pipeline.admit(root)
            receipt, gaps = verify_receipt(root, require_admitted=True)
            if receipt is None or gaps or str(rec0.get("status") or "") != ADMITTED:
                for g in gaps:
                    print("  - " + g, file=sys.stderr)
                return _refuse("re-sealing admission over the changed contract(s) %s left the receipt %s and still not "
                               "authoritative; nothing binds to a seal that does not hold"
                               % (", ".join(moved), rec0.get("status")))
            reseal = {"changed": moved, "old_receipt": old_digest,
                      "new_receipt": str(receipt.get("receipt_digest") or "")}
            print("RESEAL %s: %d contract(s) changed after admission (%s); admission re-sealed %s → %s"
                  % (card_id, len(moved), ", ".join(moved), old_digest[:12], reseal["new_receipt"][:12]))
    if receipt is None or gaps:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        return _refuse("the admission receipt is not authoritative for the tree on disk; nothing is re-sealed from a broken chain")
    # The verdict itself carries no corpus digest (compose-m4-verdict's schema
    # has no slot for one), so what CAN be checked is the receipt binding the
    # parity receipt does carry: the corpus digest it was composed under, under
    # the admission receipt that seals this tree. A parity receipt bound to
    # another admission receipt describes another tree -- except the receipt
    # THIS run just superseded, which sealed this same tree under the contracts
    # as they were when M4 measured it.
    bound = {str(receipt.get("receipt_digest") or "")} | ({reseal["old_receipt"]} if reseal else set())
    if str(preceipt.get("receipt_sha256") or "") not in bound:
        return _refuse("the parity receipt is bound to admission receipt %s; this tree is sealed under %s"
                       % (str(preceipt.get("receipt_sha256"))[:12], str(receipt.get("receipt_digest"))[:12]))
    corpus_sha = str(preceipt.get("corpus_sha256") or "")

    # --- what a card can repair, and what a decision owns ---------------------
    # The obligations are read from the RECEIPT, never from the floor list. A
    # floor list is a runner's account of which checks it ran; the receipt is
    # the measurement. v9's verdict named `check-empty-security` and
    # `check-product-tests` and not `compose-parity-receipt`, over a receipt
    # that was FAIL with thirteen FAIL rows -- and asking the floor list what
    # to repair found nothing to mint over evidence that was on disk.
    failed = [str(x).strip() for x in (verdict.get("failed_floors") or []) if str(x).strip()]
    parity_floors = [f for f in failed if f in PARITY_FLOORS]
    decision_floors = [f for f in failed if f not in PARITY_FLOORS]
    bundle = load_json(root / EVIDENCE_BUNDLE) if (root / EVIDENCE_BUNDLE).is_file() else {}
    unauthorized = unauthorized_entry_points(preceipt)
    obligations, withheld = withhold(repairable_obligations(root, bundle), unauthorized)
    if obligations and withheld:
        # The mint takes the work list's HEAD, and nothing here chooses it. So
        # a head made of nothing but withheld obligations would send a worker
        # to a controller for a security decision anyway: it is refused as the
        # blocked class, with the same file written and the same exit, and the
        # Operator's ADR-014 step is what unblocks it.
        held_ids = {str(i.get("id")) for i in withheld}
        head = head_cluster(build_worklist(root, write=False)) or {}
        head_items = {str(x) for x in (head.get("items") or [])}
        if head_items and head_items <= held_ids:
            print("BLOCKED: LOOP_RELEASE_FLOOR %s owned by %s (%s) — the head cluster carries only requests the destination "
                  "refused, so the next card would be a security decision: %s"
                  % (head.get("id") or "(head)", SECURITY_ADR, SECURITY_OWNER, ", ".join(sorted(head_items))[:200]), file=sys.stderr)
            obligations = []
    parity_unrepairable = parity_floors if (parity_floors and not obligations) else []
    rows = floor_rows(decision_floors, parity_unrepairable, unauthorized)

    # --- a clean acceptance: the run's success path, and its terminator -------
    # Every floor measured rc 0, the verdict token is one the road accepts, and
    # there is neither an obligation a card repairs nor a floor a decision
    # owns. That is not "nothing to resume": it is the run's answer, and until
    # H16 it was refused (v9 t_7740ad21), leaving the close card issued and a
    # superseded REFUSE's blockers file on disk as if it were current.
    clean = (token in ACCEPT_TOKENS and not failed and not obligations
             and not withheld and not rows and not unauthorized)
    if clean:
        return close_out(root, args, verdict, preceipt, steps, card_id=card_id, token=token,
                         receipt=receipt, corpus_sha=corpus_sha, parity_on_disk=parity_on_disk, reseal=reseal)

    if not obligations and not rows and not unauthorized:
        return _refuse("verdict %s for card %s: the parity receipt names no obligation whose locus is a file of this "
                       "tree, and no failed floor a decision owns; there is nothing to resume" % (token or "(none)", card_id))

    blockers = {
        "schema": BLOCKERS_SCHEMA,
        "at": _now(),
        "operator": args.operator,
        "verdict_card": card_id,
        "verdict": token,
        "verdict_file": M4_VERDICT.as_posix(),
        "failed_floors": failed,
        "receipt_sha256": str(receipt.get("receipt_digest") or ""),
        "corpus_sha256": corpus_sha,
        "floors": rows,
        "entry_points": unauthorized,
        "owners": sorted({r["adr"] for r in rows if r.get("adr")} | {r["adr"] for r in unauthorized}),
        "resumed": bool(obligations),
        "parity_obligations": sorted(str(i.get("id")) for i in obligations),
        # what the receipt asked for and ADR-014 holds back: named, so the
        # record says which repairs this resume did NOT mint and why
        "withheld_obligations": sorted(str(i.get("id")) for i in withheld),
    }
    if reseal:
        # what moved, and between which two seals: the receipt the verdict was
        # measured under is not on disk any more, so the record is the only
        # place that still names it
        blockers["contract_reseal"] = reseal

    # --- nothing a card repairs: record the decisions and stop ----------------
    if not obligations:
        path = write_blockers(root, blockers)
        for row in rows:
            print(blocker_line(row), file=sys.stderr)
        for row in unauthorized:
            print(entry_point_line(row), file=sys.stderr)
        print("BLOCKED: %d release floor(s) and %d unauthorized entry point(s) owned by %s; nothing minted → %s"
              % (len(rows), len(unauthorized), ", ".join(blockers["owners"]) or "no ADR", RELEASE_BLOCKERS), file=sys.stderr)
        print("OK: release blockers recorded → %s" % path)
        return 2

    # --- the loop continues on what it can repair -----------------------------
    # The close is on the record BEFORE the mint: `--verify-board` compares the
    # live board against this record, and an M4 card with no expected entry is
    # a foreign card.
    close_row = {
        "kind": "close", "cluster": CLOSE_ID, "card": card_id, "verdict": token,
        "failed_floors": failed, "resumed": True, "operator": args.operator, "at": _now(),
        "receipt_sha256": str(receipt.get("receipt_digest") or ""), "corpus_sha256": corpus_sha,
        "parity_obligations": sorted(str(i.get("id")) for i in obligations),
        "withheld_obligations": sorted(str(i.get("id")) for i in withheld),
        "release_blockers": [r["floor"] for r in rows] + [r["entry_point"] for r in unauthorized],
        "measure": None, "changed": [],
        "reason": "M4 %s: %d parity obligation(s) resumed as cards; %d withheld to ADR-014; %d release floor(s) recorded"
                  % (token or "REFUSE", len(obligations), len(withheld), len(rows) + len(unauthorized)),
    }
    if reseal:
        close_row["contract_reseal"] = reseal
    steps.setdefault("rejected", []).append(close_row)
    save_steps(root, steps)
    # The comparison M4 composed is now the loop's ACCEPTED parity baseline: it
    # was measured on this sealed tree, it is the receipt the cards below are
    # minted from, and `_loop_common.restore_reports` puts the accepted
    # snapshot back over the live records every time a candidate is discarded.
    # Without this the baseline stays whatever the last accepted parity step
    # left -- on v9 a receipt composed by a run SCOPED to one scenario, taken
    # before M4 measured the phase -- and the first revert restores a baseline
    # older than the receipt the reverted card was issued against. Measured:
    # t_46556d5e was REVERTED for an edit after verification, the restore put
    # the scoped receipt back over the full one, and the rebuild reported zero
    # parity mismatches and zero open clusters. The obligation did not fail; it
    # vanished.
    snapshot_parity(root, {
        "schema": PARITY_SOURCE_SCHEMA, "at": _now(), "card": card_id, "verdict": token,
        "binding": {"mode": "sealed", "card": card_id},
        "receipt_sha256": parity_on_disk, "corpus_sha256": corpus_sha,
        "reason": "the M4 verdict for %s closed on this comparison; the obligations it names are minted from it" % card_id,
    })
    if (root / LOOP_ISSUED).is_file():
        (root / LOOP_ISSUED).unlink()
    rebuilt = build_worklist(root)
    rec = pipeline.admit(root)
    publish_loop_state(root, rebuilt)
    if rows or unauthorized:
        write_blockers(root, blockers)
        for row in rows:
            print(blocker_line(row), file=sys.stderr)
        for row in unauthorized:
            print(entry_point_line(row), file=sys.stderr)
        print("BLOCKED: %d release floor(s) and %d unauthorized entry point(s) owned by %s; recorded, not minted → %s"
              % (len(rows), len(unauthorized), ", ".join(blockers["owners"]) or "no ADR", RELEASE_BLOCKERS), file=sys.stderr)
    print("RESUMED %s: %d parity obligation(s)%s → head %s"
          % (card_id, len(obligations), (" (%d withheld to %s)" % (len(withheld), SECURITY_ADR)) if withheld else "",
             rebuilt.get("head") or "(none)"))
    if rec.get("status") != ADMITTED:
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec.get("status"), "; ".join((rec.get("reasons") or [])[:3])), file=sys.stderr)
        return 1
    return mint(root, args.hermes, args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
