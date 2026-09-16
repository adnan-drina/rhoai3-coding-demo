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

A UNIT card is revised the same way and on the same record, with one addition:
the revision must cite EVIDENCE a tool states (--evidence javac:<identity> |
model:<sealed symbol> | runtime:<rt id>), because a coordinated repair spanning
several files can always be argued into one more, and prose is not a fact. The
revision is bounded by the same size rule that formed the unit (UNIT_MAX_FILES)
and recorded on the issued card as ``revisions[]`` beside the amendment; the
sealed inventory, the unit_id, the budget and the idempotency key do not move.

  python3 amend-scope.py --root . --cluster u:abc123 --card $HERMES_KANBAN_TASK \
      --path src/main/java/.../Owner.java --reason "the sealed throws surface is declared here" \
      --evidence javac:diag:src/main/java/.../Owner.java|compiler.err...|9f3c

A path that does not exist yet is admissible in exactly one case: the unit's
seal records an IMPLEMENTATION OBLIGATION for it — a parent owed a concrete
implementation, plus the naming contract that fixes the new type and its file.
A repair whose whole purpose is to write an adapter cannot be authorized by the
model, because the model has no type for a file nobody has written. The
relationship the path was authorized on (the new type implements the parent) is
verified from the model once the file exists: here on a later ask, and at the
checkpoint by worklist.assess_unit, which refuses the unit without it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib, load_issued, product_paths_changed  # noqa: E402

ensure_hermes_lib()

from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import LOOP_ISSUED, WORKLIST, is_product_path  # noqa: E402
from planner.dest_model import DestModelUnavailable, dest_model, types_of  # noqa: E402
from planner.worklist import UNIT_KIND, UNIT_MAX_FILES, batch_scope_digest, resolve_compile_symbol  # noqa: E402

# How far one card may reach beyond the file it was issued for. Two is enough
# for a repository whose queries need one collaborating entity; a third is the
# signal that the cluster was wrong, which is a planning answer, not a worker's.
AMENDMENT_LIMIT = 2
# A UNIT is already several files by construction, so the same number would
# refuse a legitimate revision of a coordinated repair after one collaborator.
# Four, and never past the former's own file bound: the size rule that formed
# the unit is the size rule that bounds its revisions, or a card could walk to
# a width the former would have refused to mint.
UNIT_AMENDMENT_LIMIT = 4
EVIDENCE_KINDS = ("javac", "model", "runtime", "parity")


def _refuse(msg: str) -> int:
    print("REFUSE: SCOPE_AMENDMENT %s" % msg, file=sys.stderr)
    return 1


def _sealed_symbols(scope: dict) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    """(symbol fqns, (declaring fqn, signature) pairs, sealed member paths)."""
    fqns: set[str] = set()
    members: set[tuple[str, str]] = set()
    for s in scope.get("symbols") or []:
        if not isinstance(s, dict) or not s.get("fqn"):
            continue
        fqns.add(str(s["fqn"]))
        if str(s.get("kind") or "") == "member" and s.get("signature"):
            members.add((str(s["fqn"]), str(s["signature"])))
    paths = {str(m.get("path") or "") for m in (scope.get("members") or []) if m.get("path")}
    return fqns, members, paths


def _worklist_items(root: Path) -> list[dict]:
    p = root / WORKLIST
    if not p.is_file():
        return []
    doc = load_json(p)
    return [i for i in (doc.get("items") or []) if isinstance(i, dict)]


def _evidence(root: Path, scope: dict, raw: str) -> tuple[dict, str]:
    """(the evidence row, why it is not evidence).

    Prose alone stops being sufficient for a unit. What counts is a fact one of
    the tools states NOW: a javac identity the current work list carries, a
    relation the sealed inventory and the model state, or a runtime obligation
    the current work list carries. A stale identity is refused by name -- an
    amendment justified by a diagnostic nobody reports any more is justified by
    nothing."""
    kind, _, ref = str(raw or "").partition(":")
    kind, ref = kind.strip(), ref.strip()
    if kind not in EVIDENCE_KINDS or not ref:
        return {}, ("--evidence must be <kind>:<ref> with kind one of %s; %r is not"
                    % ("|".join(EVIDENCE_KINDS), raw))
    items = _worklist_items(root)
    if kind == "javac":
        hit = next((i for i in items if str(i.get("identity") or "") == ref or str(i.get("id") or "") == ref), None)
        if hit is None:
            return {}, ("no javac diagnostic with identity %r is in the current work list; an amendment justified by a "
                        "diagnostic nobody reports any more is justified by nothing" % ref)
        return {"kind": kind, "ref": ref, "path": str(hit.get("path") or ""), "tool_named": True}, ""
    if kind in ("runtime", "parity"):
        hit = next((i for i in items if str(i.get("id") or "") == ref and str(i.get("source") or "") == kind), None)
        if hit is None:
            return {}, "no %s obligation %r is in the current work list" % (kind, ref)
        return {"kind": kind, "ref": ref, "path": str(hit.get("path") or ""), "tool_named": True}, ""
    fqns, members, _paths = _sealed_symbols(scope)
    named = ref.split("#", 1)[0]
    if named not in fqns and not any(named == f for f, _s in members):
        return {}, ("%r is not a symbol this unit sealed (%s); the model may state a relation, but only about what the "
                    "card was issued for" % (ref, ", ".join(sorted(fqns)[:3]) or "no sealed symbol"))
    return {"kind": kind, "ref": ref, "tool_named": False}, ""


def _implementation_obligation(scope: dict, rel: str) -> dict:
    """The sealed obligation that names this file, if the unit records one.

    A repair that has to CREATE a file cannot be authorized by the model: the
    model has no type for a file nobody has written, so the adapter the card
    exists to produce was refused for not existing yet. What authorizes it is
    the seal -- the recorded obligation (a parent declares a member no
    implementer answers) together with the naming contract that fixes the type
    and the path. The worker chooses neither."""
    for row in scope.get("implementation_obligations") or []:
        if not isinstance(row, dict) or str(row.get("path") or "") != rel or not row.get("type"):
            continue
        # a parent owed an implementation (the fragment contract), or a harness
        # adapter owed byte-for-byte from its template (ADR-019)
        if row.get("parent") or (row.get("verify") == "template" and row.get("template_sha256")):
            return dict(row)
    return {}


def _unit_locus(root: Path, scope: dict, rel: str) -> tuple[str, str]:
    """Why this file is part of the UNIT the card carries, or why not.

    Shapes, each read from the SEALED inventory and the model -- never from a
    reference the candidate has just written:

      * the inventory already carries the path (a member the card was issued
        with, outside the write set only because the bound narrowed it);
      * the seal records an IMPLEMENTATION OBLIGATION for it: a parent owed a
        concrete implementation, and a naming contract that says what the new
        type and its file must be called. This is the one shape that authorizes
        a path before it exists -- and once it does exist, the promised
        relationship is checked, here and again at the checkpoint;
      * a type declared here implements or extends a sealed declaring type;
      * a member declared here calls a sealed member;
      * a javac diagnostic the CURRENT work list reports at this path names a
        sealed symbol (tool-named, so nothing the worker wrote can forge it);
      * a type here reads the sealed configuration property."""
    fqns, members, sealed_paths = _sealed_symbols(scope)
    obligation = _implementation_obligation(scope, rel)
    if not fqns and not sealed_paths and not obligation:
        return "", "the unit seal carries no symbol and no member, so nothing in it can show a file is in scope"
    if rel in sealed_paths:
        return "sealed: %s is a member of the unit's own inventory" % rel, ""
    try:
        model = dest_model(root)
    except DestModelUnavailable as exc:
        return "", "the destination model is unavailable, so the file's types cannot be named (%s)" % exc
    here = types_of(model, rel)
    if obligation and obligation.get("verify") == "template":
        want = str(obligation["type"])
        if not here:
            return ("sealed: %s is owed at %s under %s (the harness template, sha256 %s)"
                    % (want, rel, obligation.get("contract") or "naming contract",
                       str(obligation.get("template_sha256") or "")[:12])), ""
        if not any(str(t.get("fqn") or "") == want for t in here):
            return "", ("%s was authorized to declare %s and declares %s instead; the naming contract is what made the "
                        "path admissible" % (rel, want, ", ".join(sorted(str(t.get("fqn")) for t in here))))
        return "sealed: %s declares %s, the adapter its obligation names" % (rel, want), ""
    if obligation:
        want, parent = str(obligation["type"]), str(obligation["parent"])
        if not here:
            # before creation: the obligation and the contract are the authority
            return ("sealed: %s is owed a concrete implementation and %s names %s at %s (%s)"
                    % (parent, "the unit's seal", want, rel, obligation.get("contract") or "naming contract")), ""
        # after creation: the promised relationship is a fact or it is not
        typ = next((t for t in here if str(t.get("fqn") or "") == want), None)
        if typ is None:
            return "", ("%s was authorized to declare %s and declares %s instead; the naming contract is what made the "
                        "path admissible" % (rel, want, ", ".join(sorted(str(t.get("fqn")) for t in here))))
        if parent not in [str(s).split("<", 1)[0] for s in (typ.get("supertypes") or [])]:
            return "", ("%s does not implement %s; the path was authorized on that relationship and the model does not "
                        "state it" % (want, parent))
        return "sealed: %s implements %s, the parent its obligation names" % (want, parent), ""
    if not here:
        return "", "the model has no type for %s" % rel
    for t in here:
        for sup in (t.get("supertypes") or []):
            base = str(sup).split("<", 1)[0]
            if base in fqns or any(base == f for f, _s in members):
                return "sealed: %s extends or implements %s, which this unit seals" % (t.get("fqn"), base), ""
        for m in (t.get("declared") or []):
            for call in (m.get("calls") or []):
                for fqn, sig in members:
                    if str(call).startswith(fqn + ".") and str(call).endswith(sig):
                        return "sealed: %s.%s calls %s, a member this unit seals" % (t.get("fqn"), m.get("name"), call), ""
    annotations: dict = {}
    for it in _worklist_items(root):
        if str(it.get("source") or "") != "javac" or str(it.get("path") or "") != rel:
            continue
        key, _kind = resolve_compile_symbol(model, it, annotations)
        if key and key in fqns:
            return "sealed: javac reports %s at %s, and %s is a symbol this unit seals" % (it.get("rule_id"), rel, key), ""
    for t in here:
        for m in (t.get("declared") or []):
            for ann in (m.get("annotations") or []):
                for value in (ann.get("values") or {}).values():
                    if str(value) in fqns:
                        return "sealed: %s.%s reads %s, the property this unit seals" % (t.get("fqn"), m.get("name"), value), ""
    return "", ("%s declares %s, which the unit's sealed symbols do not reach: it does not implement or extend one, does "
                "not call one, is named by no javac diagnostic about one, and reads no sealed property. A relationship "
                "the repair itself introduced authorizes nothing; a card that needs this file is a card the planner has "
                "not minted yet." % (rel, ", ".join(sorted(str(t.get("fqn")) for t in here)) or "no type"))


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
    ap.add_argument("--evidence", default="",
                    help="required for a unit card: <kind>:<ref> where kind is javac (a diagnostic identity the current "
                         "work list carries), model (a relation the sealed inventory states about a sealed symbol), "
                         "runtime (an rt: obligation the current work list carries) or parity (a parity: obligation "
                         "the current work list carries)")
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

    scope_doc = load_json(scope_p)
    unit = str(scope_doc.get("kind") or "") == UNIT_KIND
    limit = UNIT_AMENDMENT_LIMIT if unit else AMENDMENT_LIMIT

    rel = str(args.path).replace("\\", "/").lstrip("./")
    if not is_product_path(rel):
        return _refuse("%s is not a product path" % rel)
    if rel.startswith("src/test/") and not rel.endswith((".properties", ".yaml", ".yml")):
        return _refuse("a test source is never writable; an ADR and an Operator step are the only way")
    if rel == "pom.xml":
        return _refuse("the build file is its own cluster, never an amendment")
    # A path the unit is OWED may be authorized before it exists -- and only
    # such a path. Everything else must be a file of this tree: an amendment is
    # about work the measured tree carries, not about a file a worker imagines.
    obligation = _implementation_obligation(scope_doc, rel) if unit else {}
    if not (root / rel).is_file() and not obligation:
        return _refuse("%s is not a file of this tree, and this card's seal records no implementation obligation for it; "
                       "a new path is authorized by an obligation and a naming contract, never by a request" % rel)
    if len(str(args.reason).strip()) < 12:
        return _refuse("--reason must say what the card cannot finish without this file")

    amendments = list(issued.get("amendments") or [])
    if rel in set(issued.get("write_set") or []):
        # asked again about a path authorized before it existed, and it exists
        # now: say whether the relationship it was authorized on is a fact. The
        # checkpoint asks the same question of the model and is the judge; this
        # is the worker's early answer.
        if obligation and (root / rel).is_file():
            why = _unit_locus(root, scope_doc, rel)[1]
            held = ("%s declares %s, the adapter its obligation names" % (rel, obligation["type"])
                    if obligation.get("verify") == "template" else
                    "%s implements %s, the parent its obligation names" % (obligation["type"], obligation["parent"]))
            print("OK: %s is already writable for %s%s"
                  % (rel, args.cluster, (" — but %s" % why) if why else " — and " + held),
                  file=sys.stderr if why else sys.stdout)
            return 0
        print("OK: %s is already writable for %s" % (rel, args.cluster))
        return 0
    # A unit's scope may be REVISED, but never past the size rule that formed
    # it: the former refuses to mint a unit wider than UNIT_MAX_FILES, and an
    # amendment that walked past it would produce by hand exactly the card the
    # former declined to produce.
    if unit and len(set(issued.get("write_set") or []) | {rel}) > UNIT_MAX_FILES:
        return _refuse("UNIT_OVERSIZE: %s would take this unit to %d file(s) (max %d); a repair this wide is a planning "
                       "answer, not a revision" % (rel, len(set(issued.get("write_set") or []) | {rel}), UNIT_MAX_FILES))
    if len(amendments) >= limit:
        return _refuse("this card has already been amended %d time(s) (limit %d); the %s is wrong, "
                       "which is a planning answer: let the card be refused and re-planned"
                       % (len(amendments), limit, "unit" if unit else "cluster"))
    evidence: dict = {}
    if unit:
        # Prose alone stops being sufficient for a unit: a revision of a sealed
        # scope is recorded WITH the fact that justifies it, from a tool.
        evidence, why = _evidence(root, scope_doc, args.evidence)
        if not evidence:
            return _refuse("a unit's scope is revised on evidence, never on a reason alone: %s" % why)

    # Authority is granted BEFORE the file moves, never after. A file that is
    # already edited cannot be authorized retrospectively: there would be
    # nothing left to authorize, only something to excuse.
    if rel in set(product_paths_changed(root)):
        return _refuse("%s has already been edited. An amendment authorizes a change that has not happened yet; "
                       "revert it, record the amendment, then make the change." % rel)

    # And the ask has to be about the failure this card carries. The locus is
    # the measured obligation's own file and the members named in the sealed
    # inventory: a file with no bearing on either is a different card.
    locus, why = (_unit_locus(root, scope_doc, rel) if unit else _locus(root, scope_doc, rel))
    if not locus:
        return _refuse("%s bears no relation to what this card measures: %s. A file the failure does not reach is a "
                       "planning answer, not an amendment." % (rel, why))

    row = {"path": rel, "reason": str(args.reason).strip(), "attempt": issued.get("attempt"),
           # a path owed but not yet written has no content to seal; what is
           # recorded instead is that it did not exist when authority was given
           "granted_before_sha256": sha256_file(root / rel) if (root / rel).is_file() else "",
           "dirty_at_grant": False,
           "locus": locus}
    if evidence:
        row["evidence"] = evidence
    if obligation and not (root / rel).is_file():
        row["creates"] = {"parent": obligation.get("parent") or "", "type": obligation["type"],
                          "contract": obligation.get("contract") or "", "source": obligation.get("source") or ""}
        if obligation.get("verify") == "template":
            row["creates"]["template_sha256"] = str(obligation.get("template_sha256") or "")
    amendments.append(row)
    issued["amendments"] = amendments
    if unit:
        # The REVISION record: what was added, why, and the tool fact that
        # justified it. It lives on the issued card, never in the inventory --
        # the inventory's seal is what acceptance re-checks, and a seal that
        # moves is not one. The unit_id and the idempotency key are untouched,
        # so the budget does not reset and the card does not become another.
        revisions = list(issued.get("revisions") or [])
        revisions.append({"n": len(revisions) + 1, "path": rel, "evidence": evidence,
                          "locus": locus, "reason": row["reason"], "attempt": issued.get("attempt"),
                          "unit_id": str(scope_doc.get("unit_id") or ""), "rule": str(scope_doc.get("rule") or "")})
        issued["revisions"] = revisions
    issued["write_set"] = sorted(set(issued.get("write_set") or []) | {rel})
    write_canonical(root / LOOP_ISSUED, issued)
    print("OK: SCOPE %s %s + %s (%d of %d)%s — the sealed inventory is unchanged; "
          "every member in it is still assessed when the candidate is judged"
          % ("REVISED" if unit else "AMENDED", args.cluster, rel, len(amendments), limit,
             (" on %s evidence %s" % (evidence["kind"], evidence["ref"])) if evidence else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
