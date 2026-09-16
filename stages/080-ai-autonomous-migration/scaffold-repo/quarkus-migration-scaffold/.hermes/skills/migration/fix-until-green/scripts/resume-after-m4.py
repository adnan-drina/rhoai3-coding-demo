#!/usr/bin/env python3
"""Resume the loop after an M4 verdict: repair what a card can repair, record what it cannot.

M4 is a measurement, and `REFUSE` is one of its answers. Until now nothing
consumed that answer: `advance.py` mints only after an ACCEPTED M3 step, the
close card ends on `kanban_request_review`, and the parity mismatches the
phase measured sat in `verification/parity/` as obligations nobody minted. So
the run stopped at its own first honest result.

This tool is the missing edge. It reads the composed verdict, splits its
failed floors into the two kinds the harness actually has, and acts on each:

  * a PARITY floor (`compose-parity-receipt`) is repairable BY A CARD when
    `planner.worklist.parity_items` turns the FAIL verdicts into obligations
    whose locus is a file of this tree. Those obligations are already in the
    work list the moment it is rebuilt (`kind: parity` / `config`, category
    `mandatory`), so resuming is: close the M4 card on the record, rebuild,
    re-seal admission, and let K4 mint the head cluster -- exactly the
    transaction `advance.py` runs after an accepted step;

  * a DECISION floor is everything else. `check-product-tests` and
    `assert-surefire-results` are ADR-015 territory (a harness capability owns
    the generated product tests; a worker card cannot author them and must not
    weaken them), and an entry point the parity receipt could not compare
    because the read-back answered 401/403 is ADR-014 territory (the security
    switch, one bounded Operator step). Those are recorded in
    `verification/loop/release-blockers.json` and named on stderr. They are
    not minted, because a card is not what discharges them -- and they are not
    hidden either, because a floor nobody names is a floor nobody fixes.

Both kinds at once (v9's first M4 verdict) is the normal case: the loop
continues on the parity obligations AND writes the blockers file. One printed
line per class, so the Operator reads what moved and what did not.

Refuses, and changes nothing, unless the verdict belongs to THIS run: the
verdict's `card_id` is the issued close card, the parity receipt it was
composed from is bound to the admission receipt that seals the tree on disk,
no candidate is retained for the close card, and the product tree is clean.
A second run after a resume refuses: the close card is on the record.

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

Exit 0 resumed (a card was minted); 1 refused; 2 blocked (decision floors
only, nothing a card can repair).
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
from _loop_common import ensure_hermes_lib, git, load_issued, load_steps, pending_for, publish_loop_state, save_steps  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.admission import ADMITTED, verify_receipt  # noqa: E402
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.cards import CLOSE_ID  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, LOOP_DIR, LOOP_ISSUED, PARITY_DIR  # noqa: E402
from planner.worklist import build_worklist, parity_items  # noqa: E402

M4_VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
PARITY_RECEIPT = PARITY_DIR / "receipt.json"
RELEASE_BLOCKERS = LOOP_DIR / "release-blockers.json"
BLOCKERS_SCHEMA = "rhoai3.release-blockers/v1"
PARITY_RECEIPT_SCHEMA = "rhoai3.parity-receipt/v1"

# `planner.admission.verify_receipt` reports one gap per sealed contract whose
# file no longer hashes to its seal, in exactly this shape. It is reconstructed
# here rather than matched by prefix so that the test below is an equality over
# a set and not a guess about a string: if that message ever changes, the set
# stops matching and the resume refuses, which is the safe direction.
CONTRACT_GAP = "contract %s changed after admission"

# The floors a parity FAIL composes. A floor in this set is repairable by a
# card exactly when the parity verdicts under it yield an obligation whose
# locus is a file of this tree; otherwise it joins the decision class.
PARITY_FLOORS = frozenset({"compose-parity-receipt"})

# The closed table of release floors that are NOT cards, with the decision
# that owns each and the seat that discharges it. Specimen-agnostic: these are
# harness floor names and ADR ids, never a specimen's files or symbols.
DECISION_FLOORS = {
    "check-product-tests": ("ADR-015", "harness capability", "the product acceptance tests are generated deterministically from qualified source scenarios; a worker card gets no authority to author or weaken them"),
    "assert-surefire-results": ("ADR-015", "harness capability", "the surefire floor needs its own evidence-based diagnosis; a fresh report with zero skips is a harness output, not a patch"),
}
UNKNOWN_FLOOR_OWNER = "Operator"

# ADR-014: an entry point the receipt could not compare because the read-back
# answered 401/403 is the security switch, not a destination defect. The
# comparator writes its findings as "status <have> vs <want>" diffs, so the
# unauthorized read-back is recognised by that shape and nothing else.
INCONCLUSIVE_ADR = "ADR-014"
INCONCLUSIVE_OWNER = "Operator step"
INCONCLUSIVE_DETAIL = ("the read-back was refused by the source security switch; ADR-014 gives one bounded Operator step the "
                       "conditional authorization adapter, the Basic/JPA identity mapping and both modes' captures. A card "
                       "cannot compare an entry point nobody may call")
_UNAUTHORIZED = re.compile(r"status 40[13] vs")


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
    so it is counted with the decisions, not with the repairs."""
    out = []
    for item in parity_items(root, bundle):
        rel = str(item.get("path") or "")
        if rel and (root / rel).is_file():
            out.append(item)
    return out


def unauthorized_entry_points(receipt: dict) -> list:
    """INCONCLUSIVE rows whose reason is a 401/403 on the read-back (ADR-014)."""
    out = []
    for row in receipt.get("entry_points") or []:
        if not isinstance(row, dict) or str(row.get("verdict") or "") != "INCONCLUSIVE":
            continue
        reason = str(row.get("reason") or "")
        if _UNAUTHORIZED.search(reason):
            out.append({"entry_point": str(row.get("entry_point") or ""), "reason": reason[:400],
                        "adr": INCONCLUSIVE_ADR, "owner": INCONCLUSIVE_OWNER, "detail": INCONCLUSIVE_DETAIL})
    return out


def floor_rows(decision_floors: list, parity_unrepairable: list) -> list:
    """One row per floor no card discharges, each naming the ADR that owns it."""
    rows = []
    for name in decision_floors:
        adr, owner, detail = DECISION_FLOORS.get(name, ("", UNKNOWN_FLOOR_OWNER, "release floor %s is not a card" % name))
        rows.append({"floor": name, "class": "decision", "adr": adr, "owner": owner, "detail": detail})
    for name in parity_unrepairable:
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

    # --- the parity receipt the verdict was composed from ---------------------
    pp = root / PARITY_RECEIPT
    if not pp.is_file():
        return _refuse("no %s; the verdict's parity floor cites a receipt that is not on disk" % PARITY_RECEIPT)
    preceipt = load_json(pp)
    if not isinstance(preceipt, dict) or str(preceipt.get("schema") or "") != PARITY_RECEIPT_SCHEMA:
        return _refuse("%s is not a %s document" % (PARITY_RECEIPT, PARITY_RECEIPT_SCHEMA))

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

    # --- classify the failed floors ------------------------------------------
    failed = [str(x).strip() for x in (verdict.get("failed_floors") or []) if str(x).strip()]
    parity_floors = [f for f in failed if f in PARITY_FLOORS]
    decision_floors = [f for f in failed if f not in PARITY_FLOORS]
    bundle = load_json(root / EVIDENCE_BUNDLE) if (root / EVIDENCE_BUNDLE).is_file() else {}
    obligations = repairable_obligations(root, bundle) if parity_floors else []
    parity_unrepairable = parity_floors if (parity_floors and not obligations) else []
    unauthorized = unauthorized_entry_points(preceipt)
    rows = floor_rows(decision_floors, parity_unrepairable)

    if not obligations and not rows and not unauthorized:
        return _refuse("verdict %s for card %s names no failed floor a card can repair and no floor a decision owns; "
                       "there is nothing to resume" % (token or "(none)", card_id))

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
        "release_blockers": [r["floor"] for r in rows] + [r["entry_point"] for r in unauthorized],
        "measure": None, "changed": [],
        "reason": "M4 %s: %d parity obligation(s) resumed as cards; %d release floor(s) recorded"
                  % (token or "REFUSE", len(obligations), len(rows) + len(unauthorized)),
    }
    if reseal:
        close_row["contract_reseal"] = reseal
    steps.setdefault("rejected", []).append(close_row)
    save_steps(root, steps)
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
    print("RESUMED %s: %d parity obligation(s) → head %s" % (card_id, len(obligations), rebuilt.get("head") or "(none)"))
    if rec.get("status") != ADMITTED:
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec.get("status"), "; ".join((rec.get("reasons") or [])[:3])), file=sys.stderr)
        return 1
    return mint(root, args.hermes, args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
