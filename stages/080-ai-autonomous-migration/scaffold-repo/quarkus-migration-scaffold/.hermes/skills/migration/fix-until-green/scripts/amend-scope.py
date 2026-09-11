#!/usr/bin/env python3
"""Widen a sealed batch card's write set by ONE file, on the record.

A repository repair sometimes cannot be finished inside the file the card
names: a derived query needs a field the entity does not expose, a member's
return type has moved. The worker must not simply reach for the other file —
the write set is what acceptance enforces, and a candidate that touched an
unadmitted path is discarded whole.

So the scope is AMENDED before the file becomes writable, never after. The
inventory itself is never rewritten: its seal is the thing acceptance checks,
and a seal that moves is not one. What changes is the transaction — the issued
card grows one path, with the reason recorded beside it, and the amendment
count is bounded so a card cannot walk the tree one justification at a time.

  python3 amend-scope.py --root . --cluster c:abc --card $HERMES_KANBAN_TASK \
      --path src/main/java/.../Vet.java --reason "findByLastName needs Vet.lastName"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib, load_issued, product_paths_changed  # noqa: E402

ensure_hermes_lib()

from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import LOOP_ISSUED, is_product_path  # noqa: E402
from planner.dest_model import DestModelUnavailable, dest_model, types_of  # noqa: E402
from planner.worklist import batch_scope_digest  # noqa: E402

# How far one card may reach beyond the file it was issued for. Two is enough
# for a repository whose queries need one collaborating entity; a third is the
# signal that the cluster was wrong, which is a planning answer, not a worker's.
AMENDMENT_LIMIT = 2


def _refuse(msg: str) -> int:
    print("REFUSE: SCOPE_AMENDMENT %s" % msg, file=sys.stderr)
    return 1


def _locus(root: Path, scope: dict, rel: str) -> tuple[str, str]:
    """Why this file is part of the failure the card carries, or why not.

    Eligibility comes from the SEALED inventory -- what the repository reached
    when the card was issued -- never from the tree as the candidate has left
    it. A reference the worker just wrote is not evidence that the file was
    always in scope; it is evidence that the worker wants it to be."""
    repo = str(scope.get("repository") or "")
    if not repo:
        return "", "the card carries no repository"
    if "reaches" not in scope:
        return "", ("this card's inventory predates sealed reachability (%s), so nothing in it can show a file is in "
                    "scope. Let the card be refused and re-planned." % scope.get("schema"))
    reachable = {str(x) for x in (scope.get("reaches") or [])}
    try:
        model = dest_model(root)
    except DestModelUnavailable as exc:
        return "", "the destination model is unavailable, so the file's types cannot be named (%s)" % exc
    wanted = types_of(model, rel)
    if not wanted:
        return "", "the model has no type for %s" % rel
    for t in wanted:
        fqn = str(t.get("fqn") or "")
        if not fqn:
            continue
        for r in reachable:
            if fqn == r or r.startswith(fqn + "<") or ("<" in r and fqn in r):
                return "sealed: %s reached %s when the card was issued" % (repo, fqn), ""
    return "", ("%s declares %s, which %s did not reach when this card was sealed. A relationship the repair itself "
                "introduced does not authorize anything; a card that needs this file is a card the planner has not "
                "minted yet." % (rel, ", ".join(sorted(str(t.get("fqn")) for t in wanted)) or "no type", repo))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--card", default="")
    ap.add_argument("--path", required=True, help="one repo-relative file to add to the write set")
    ap.add_argument("--reason", required=True, help="what the card cannot finish without it")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    issued = load_issued(root)
    if issued is None or str(issued.get("cluster")) != args.cluster:
        return _refuse("%r is not the issued card (%s)" % (args.cluster, (issued or {}).get("cluster", "none")))
    if issued.get("task_id") and args.card and args.card != issued["task_id"]:
        return _refuse("--card %r is not the minted card %s" % (args.card, issued["task_id"]))
    scope_ref = issued.get("batch_scope") or {}
    if not scope_ref:
        return _refuse("this card carries no sealed scope, so there is nothing to amend")
    scope_p = root / str(scope_ref.get("path") or "")
    if not scope_p.is_file():
        return _refuse("the sealed inventory %s is not on disk" % scope_ref.get("path"))
    if batch_scope_digest(load_json(scope_p)) != str(scope_ref.get("digest") or ""):
        return _refuse("the inventory on disk is not the one sealed with this card")

    rel = str(args.path).replace("\\", "/").lstrip("./")
    if not is_product_path(rel):
        return _refuse("%s is not a product path" % rel)
    if rel.startswith("src/test/") and not rel.endswith((".properties", ".yaml", ".yml")):
        return _refuse("a test source is never writable; an ADR and an Operator step are the only way")
    if rel == "pom.xml":
        return _refuse("the build file is its own cluster, never an amendment")
    if not (root / rel).is_file():
        return _refuse("%s is not a file of this tree" % rel)
    if len(str(args.reason).strip()) < 12:
        return _refuse("--reason must say what the card cannot finish without this file")

    amendments = list(issued.get("amendments") or [])
    if rel in set(issued.get("write_set") or []):
        print("OK: %s is already writable for %s" % (rel, args.cluster))
        return 0
    if len(amendments) >= AMENDMENT_LIMIT:
        return _refuse("this card has already been amended %d time(s) (limit %d); the cluster is wrong, "
                       "which is a planning answer: let the card be refused and re-planned"
                       % (len(amendments), AMENDMENT_LIMIT))

    # Authority is granted BEFORE the file moves, never after. A file that is
    # already edited cannot be authorized retrospectively: there would be
    # nothing left to authorize, only something to excuse.
    if rel in set(product_paths_changed(root)):
        return _refuse("%s has already been edited. An amendment authorizes a change that has not happened yet; "
                       "revert it, record the amendment, then make the change." % rel)

    # And the ask has to be about the failure this card carries. The locus is
    # the measured obligation's own file and the members named in the sealed
    # inventory: a file with no bearing on either is a different card.
    scope_doc = load_json(scope_p)
    locus, why = _locus(root, scope_doc, rel)
    if not locus:
        return _refuse("%s bears no relation to what this card measures: %s. A file the failure does not reach is a "
                       "planning answer, not an amendment." % (rel, why))

    amendments.append({"path": rel, "reason": str(args.reason).strip(), "attempt": issued.get("attempt"),
                       "granted_before_sha256": sha256_file(root / rel),
                       "dirty_at_grant": False,
                       "locus": locus})
    issued["amendments"] = amendments
    issued["write_set"] = sorted(set(issued.get("write_set") or []) | {rel})
    write_canonical(root / LOOP_ISSUED, issued)
    print("OK: SCOPE AMENDED %s + %s (%d of %d) — the sealed inventory is unchanged; "
          "every member in it is still assessed when the candidate is judged"
          % (args.cluster, rel, len(amendments), AMENDMENT_LIMIT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
