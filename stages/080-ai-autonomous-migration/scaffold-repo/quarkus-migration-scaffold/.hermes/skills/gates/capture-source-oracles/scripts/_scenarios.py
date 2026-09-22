#!/usr/bin/env python3
"""The scenario corpus: what is replayed, against the source and the destination.

A parity claim is only as good as the sameness of the two requests. The
comparator used to send the recorded method and path with NO body, so a POST
that the source answered 201 for was replayed as an empty POST the destination
answered 400 for, and identical services compared FAIL. The fix is a corpus
that carries the complete request, and a replay that reconstructs it from the
corpus and verifies its digest before sending it.

A scenario is derived from the frozen source's own evidence (the OpenAPI
document, the seed data and M1's structure model: derive-source-scenarios.py)
and bound to the evidence bundle by digest; a hand-authored corpus that names
an ``approved_by`` is the exception, kept for a specimen whose evidence cannot
be derived. The corpus used to be "Operator-approved intent" with a signature
standing in for provenance, which is a human sign-off by another name; the
project rule is verification gates and an audit trail, never a signature. A
scenario carries:

  method, path        the concrete URL, never a route pattern
  headers             what the request needs (content type, accept)
  identity            how the request authenticates, by ENV REFERENCE
  body_file/absent    the exact bytes, or an explicit statement that there
                      are none (a DELETE legitimately has no body)
  reset_before        whether the initial state is restored first
  effects             read-backs that prove what the write did; response
                      equality alone cannot (a DELETE answering 204 that
                      deleted nothing must fail its effect check)
  effects_identity    who the read-backs are taken as, when that differs from
                      the request's identity (a refused write's own caller
                      sees 401, and 401 proves nothing about the state)
  effects[].role      what a read-back proves when it is not the write's own
                      result: ``unchanged_under_refusal`` (a fixture
                      variant's refused write; before must equal after)
  effects_reader      for a refused variant write: who reads and how
                      (``strategy``: second_identity | revert_then_read)
  effects_unobservable why a write carries no read-back at all (no identity
                      to take them as); the comparator stays INCONCLUSIVE
                      and names it
  normalization       the permitted differences, named

Nothing here records an expected value. Expected values come only from the
captured source oracle.
"""
from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()
from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, EVIDENCE_BUNDLE, LOOP_ISSUED, STRUCTURE, VERIFY_RUN, is_product_path  # noqa: E402

CORPUS = Path("verification") / "scenarios" / "corpus.json"
DERIVE_RECEIPT = Path("verification") / "scenarios" / "_derive.json"
DERIVATION_SCHEMA = "rhoai3.scenario-derivation/v1"
SCENARIO_ORACLES = Path("verification") / "source-oracles" / "scenarios"
SCENARIO_PARITY = Path("verification") / "parity" / "scenarios"
QUALIFICATION = SCENARIO_ORACLES / "_qualification.json"
QUALIFICATION_SCHEMA = "rhoai3.scenario-qualification/v1"
SCHEMA = "rhoai3.scenario-corpus/v1"

# ---------------------------------------------------------------------------
# security mode (ADR-014)
# ---------------------------------------------------------------------------
# The frozen source has a security SWITCH, and the two settings are two
# different behaviours: with it disabled every request is anonymous, with it
# enabled the same request answers 401/403 unless it carries an identity the
# policy allows. A receipt that does not say which one it judged cannot be
# read: v9's captures were taken with the switch at its default and carried no
# mode at all, so an enabled-mode destination could have been "proved" against
# anonymous expectations. So the mode travels with every artifact, the
# comparison refuses to cross modes, and the two capture sets live in separate
# directories -- reuse is prevented by the path, not by remembering.
SECURITY_MODES = ("disabled", "enabled")
DEFAULT_SECURITY_MODE = "disabled"
CAPTURE_RECEIPT_NAME = "_capture.json"
QUALIFICATION_NAME = "_qualification.json"

# ---------------------------------------------------------------------------
# fixture variants of a mode's baseline (ADR-014)
# ---------------------------------------------------------------------------
# A mode's baseline is the source's declared dataset. Some behaviour the
# architect's exits ask about is not reachable from it -- an account the seed
# enables cannot show what the source does when the account is DISABLED -- and
# the answer is not to edit the baseline, which every other capture is taken
# against, but to record a separate VARIANT: the declared dataset plus the
# statements the Operator declares, captured into its own directory and
# followed by a restoration of the baseline. The variant travels in the path
# for the same reason the mode does: a variant capture must not be readable
# as the baseline's, and prevention by path needs nobody to remember.
VARIANT_NAME_CHARS = "a-z, 0-9 and -, starting with a letter or digit"
# What a variant corpus's derivation promises, versioned so a corpus derived
# under an older promise is derived AGAIN rather than silently mixed with
# captures and verdicts that assume the newer one. v2 (2026-09-16, measured on
# v9): a refused WRITE carries the base scenario's read-backs, read either as
# a declared identity the variant does not refuse (second_identity) or as the
# request's own identity on the baseline and again after the variant's
# computed revert (revert_then_read), so "the refused write changed nothing"
# is measured; v1 dropped them and every refused PUT/DELETE was INCONCLUSIVE
# for want of an effect.
# v3 (2026-09-16, v9 re-measure): every variant scenario declares
# reset_before -- a variant scenario is defined by its dataset state, and a
# read that inherited the state a revert-then-read write left (the baseline,
# account enabled) answered 200 where the source answered 401.
# v4 (2026-09-17, ADR-021): a refused write declares the database scope its
# no-effect claim covers (effects_db_scope) and its contract requires the
# before/after database comparison (db_unchanged); HTTP read-backs alone
# never qualify "unchanged".
VARIANT_DERIVATION = "rhoai3.fixture-variant-derivation/v4"
# The role a read-back plays when the request it follows is REFUSED: its
# before and after bodies are the source's, and the claim is that they are
# equal -- the write did not happen. Carried on the effect so a report can say
# what the read-back proves rather than only that it matched.
EFFECT_ROLE_UNCHANGED = "unchanged_under_refusal"
# how a refused write's read-backs are taken (``effects_reader.strategy``)
EFFECTS_REVERT_THEN_READ = "revert_then_read"
EFFECTS_SECOND_IDENTITY = "second_identity"


def effects_strategy_of(sc: dict[str, Any]) -> str:
    """The read-back strategy a scenario declares; "" for the ordinary one
    (before and after the request, in the state the request is sent in)."""
    reader = (sc or {}).get("effects_reader")
    return str(reader.get("strategy") or "") if isinstance(reader, dict) else ""
_VARIANT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# what a CORS-bearing scenario IS (``scenario_type``). A browser never sends
# credentials on a preflight (WHATWG Fetch, CORS protocol), so an OPTIONS that
# carries an identity is a DIAGNOSTIC PROBE: admitted by the loader under that
# type only, recorded and compared like any exchange, and never counted as
# browser-preflight coverage.
SCENARIO_BROWSER_PREFLIGHT = "browser-preflight"
SCENARIO_CORS_ACTUAL = "cors-actual"
SCENARIO_DIAGNOSTIC_PROBE = "diagnostic-probe"


class CorpusError(ValueError):
    pass


def normalize_security_mode(security_mode: Any) -> str:
    """The canonical mode name; a mode nobody declared is refused, never
    silently read as the default."""
    mode = str(security_mode if security_mode is not None else DEFAULT_SECURITY_MODE).strip().lower()
    if mode not in SECURITY_MODES:
        raise CorpusError("security mode %r is not one of %s" % (security_mode, ", ".join(SECURITY_MODES)))
    return mode


def normalize_variant(variant: Any, security_mode: Any = DEFAULT_SECURITY_MODE) -> str:
    """The canonical variant name, or "" for a mode's own baseline.

    The name becomes a directory, so it is checked as one: a name that could
    be read as a mode (``enabled``) would make the variant's captures
    indistinguishable from that mode's baseline, and a name carrying a
    separator would write outside the tree. A variant of the DEFAULT mode is
    refused as well -- the suffix would collide with the other mode's -- so a
    fixture variant is always a variant of a named mode's baseline."""
    name = str(variant or "").strip()
    if not name:
        return ""
    mode = normalize_security_mode(security_mode)
    if not _VARIANT_NAME.match(name):
        raise CorpusError("fixture variant %r is not a name a directory can carry (%s)" % (variant, VARIANT_NAME_CHARS))
    if name in SECURITY_MODES:
        raise CorpusError("fixture variant %r is the name of a security mode; a variant's directory must not be readable "
                          "as a mode's own" % variant)
    if mode == DEFAULT_SECURITY_MODE:
        raise CorpusError("fixture variant %r is declared for the %s mode, whose paths carry no mode suffix; a variant is a "
                          "variant of a named mode's baseline" % (variant, DEFAULT_SECURITY_MODE))
    return name


def _mode_suffix(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> str:
    """"" for the default mode and no variant, so every existing path stays
    exactly where it is and a tree captured before ADR-014 keeps working."""
    mode = normalize_security_mode(security_mode)
    name = normalize_variant(variant, mode)
    return ("" if mode == DEFAULT_SECURITY_MODE else "-%s" % mode) + ("-%s" % name if name else "")


def classification_ledger_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    """Where the first recorded classification of every compared scenario is
    kept (ADR-021): beside the receipt, not among the verdicts."""
    return Path("verification") / "parity" / ("classification%s.json" % _mode_suffix(security_mode, variant))


def is_diagnostic(sc: Any) -> bool:
    return isinstance(sc, dict) and str(sc.get("scenario_type") or "") == SCENARIO_DIAGNOSTIC_PROBE


def classification_conflict(root: Path, sc: dict[str, Any], security_mode: Any = DEFAULT_SECURITY_MODE,
                            variant: Any = "") -> str:
    """Why this scenario's gating classification may not be used; "" when
    it holds. A scenario is gating or diagnostic from the FIRST result
    recorded for it on: relabelling it afterwards -- in either direction --
    is refused, whatever the corpus now says (ADR-021)."""
    p = Path(root) / classification_ledger_path(security_mode, variant)
    try:
        ledger = load_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        return "%s cannot be read, so the scenario's recorded classification is unknown" % p.name
    row = ((ledger or {}).get("scenarios") or {}).get(str(sc.get("id"))) if isinstance(ledger, dict) else None
    if not isinstance(row, dict):
        return ""
    was = str(row.get("scenario_type") or "")
    now = str(sc.get("scenario_type") or "")
    if (was == SCENARIO_DIAGNOSTIC_PROBE) != (now == SCENARIO_DIAGNOSTIC_PROBE):
        return ("scenario %s was first compared as %s and the corpus now types it %s; a scenario's gating classification "
                "is fixed once a result exists" % (sc.get("id"), was or "a contract scenario", now or "a contract scenario"))
    return ""


def record_classification(root: Path, sc: dict[str, Any], corpus_sha: str, security_mode: Any = DEFAULT_SECURITY_MODE,
                          variant: Any = "") -> None:
    """Keep the first classification of a compared scenario; never rewrite it."""
    p = Path(root) / classification_ledger_path(security_mode, variant)
    try:
        ledger = load_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        return
    if not isinstance(ledger, dict):
        ledger = {}
    rows = ledger.setdefault("scenarios", {})
    ledger["schema"] = "rhoai3.scenario-classification/v1"
    sid = str(sc.get("id"))
    if sid in rows:
        return
    rows[sid] = {"scenario_type": str(sc.get("scenario_type") or ""), "first_corpus_sha256": corpus_sha,
                 "gating": not is_diagnostic(sc)}
    p.parent.mkdir(parents=True, exist_ok=True)
    from planner.canonical import write_canonical as _write
    _write(p, ledger)


def scenario_oracles_dir(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    """Where the captures of ONE mode (and one of its fixture variants) live.
    Every consumer resolves the directory through this function, so no two
    modes -- and no variant and the baseline it varies -- can ever share one."""
    return Path("verification") / "source-oracles" / ("scenarios" + _mode_suffix(security_mode, variant))


def capture_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return scenario_oracles_dir(security_mode, variant) / CAPTURE_RECEIPT_NAME


def qualification_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return scenario_oracles_dir(security_mode, variant) / QUALIFICATION_NAME


def scenario_parity_dir(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return Path("verification") / "parity" / ("scenarios" + _mode_suffix(security_mode, variant))


def parity_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return Path("verification") / "parity" / ("receipt%s.json" % _mode_suffix(security_mode, variant))


def scenarios_dir(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    """Where the corpus of ONE mode lives. The default mode resolves to the
    directory CORPUS and DERIVE_RECEIPT already name, so nothing moves; the
    enabled mode gets its own, each of its fixture variants gets its own
    again, and no two corpora can be confused for one another by forgetting
    which was derived last."""
    return Path("verification") / ("scenarios" + _mode_suffix(security_mode, variant))


def corpus_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return scenarios_dir(security_mode, variant) / "corpus.json"


def derive_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    return scenarios_dir(security_mode, variant) / "_derive.json"


def variant_dataset_path(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    """The dataset a variant capture STARTS the source with: the declared
    dataset with the fixture's statements after it. It is written beside the
    captures it produced, because it is what those captures are evidence
    of -- and its digest is on the capture receipt."""
    return scenario_oracles_dir(security_mode, variant) / "_variant-dataset.sql"


def scenario_bodies_dir(security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> Path:
    """Where a derivation writes request bodies. The enabled mode writes none:
    it REUSES the disabled corpus's requests, bodies included, so the two
    modes send the same bytes and a difference in the answer is the security
    switch and nothing else."""
    return scenarios_dir(security_mode, variant) / "bodies"


def capture_security_mode(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> tuple[str, str]:
    """(the mode the capture receipt in that directory RECORDS, why-unknown).

    "" with a reason is not "disabled": a capture taken before modes were
    bound recorded no mode, and the caller decides whether that is
    compatible with what it was asked for."""
    mode = normalize_security_mode(security_mode)
    rel = capture_receipt_path(mode, variant)
    p = Path(root) / rel
    if not p.is_file():
        return "", "no capture receipt %s in this tree" % rel.as_posix()
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return "", "%s could not be read: %s" % (rel.as_posix(), exc)
    recorded = str((doc or {}).get("security_mode") or "") if isinstance(doc, dict) else ""
    if not recorded:
        return "", "%s records no security_mode (a capture taken before the mode was bound)" % rel.as_posix()
    return recorded, ""


def capture_security_variant(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE,
                             variant: Any = "") -> tuple[str, str]:
    """(the fixture variant the capture receipt in that directory RECORDS,
    why-it-differs-from-what-was-asked).

    "" is the mode's own baseline, and a receipt that records a variant while
    the caller asked for the baseline (or for another variant) is evidence of
    a different database state -- the reason is the refusal, and it names
    both."""
    name = normalize_variant(variant, security_mode) if variant else ""
    rel = capture_receipt_path(security_mode, variant)
    p = Path(root) / rel
    if not p.is_file():
        return "", ""
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return "", ""
    recorded = str((doc or {}).get("security_variant") or "") if isinstance(doc, dict) else ""
    if recorded == name:
        return recorded, ""
    return recorded, ("%s was captured against the %s and this asks for the %s"
                      % (rel.as_posix(), "%s fixture variant" % recorded if recorded else "mode's baseline",
                         "%s fixture variant" % name if name else "mode's baseline"))


# ---------------------------------------------------------------------------
# what a verdict is BOUND to
# ---------------------------------------------------------------------------
# A parity verdict says "this destination answers what the source answered".
# WHICH destination is the question this section answers, and there are two
# right answers, one per road.
#
#   sealed     the M4 road. The tree is the accepted one, the admission
#              receipt still seals what is on disk, and the verdict binds to
#              that receipt digest. This is what every verdict has always
#              been, and it stays the default.
#
#   candidate  the fix-until-green acceptance path. run-verify.sh REBUILDS the
#              work list on the candidate before the parity stage runs, so the
#              live seal is stale by construction (its worklist digest is the
#              accepted tree's). Measured on destination v9, card t_222c582a:
#              the worker wrote the right CORS properties, the comparison ran,
#              and every scenario came back INCONCLUSIVE with "receipt not
#              authoritative: worklist digest ... != sealed ..." -- so the
#              composer refused, the stale FAIL stayed on disk, and the card
#              was REVERTED. Every parity card reverted that way.
#
# A candidate-bound verdict is not an unbound one: it names the tree it
# measured (the candidate digest this verification recorded) and the card it
# was measured for (the issued card, and the receipt that card was minted
# under). What can be bound is bound; what cannot be is refused by name.
BINDING_SEALED = "sealed"
BINDING_CANDIDATE = "candidate"


def sealed_binding() -> dict[str, Any]:
    """The binding of a verdict produced on the accepted tree (the M4 road)."""
    return {"mode": BINDING_SEALED}


def product_tree_digest(root: Path) -> str:
    """The identity of the PRODUCT tree on disk.

    The same recipe the loop's own candidate identity uses
    (fix-until-green/scripts/_loop_common.py candidate_sha256), over the same
    one definition of what a product path is (planner.paths.is_product_path),
    so "the candidate this verification recorded" and "the tree this
    comparison is about" are the same measurement. scenario-parity.test.py
    holds the two against each other."""
    import hashlib

    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not is_product_path(rel):
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def candidate_binding(root: Path, *, issued_path: Any = "", candidate_sha256: str = "",
                      issued_receipt_sha256: str = "", notes: list[str] | None = None) -> tuple[dict[str, Any], list[str]]:
    """(the candidate binding, why it cannot be made).

    ``issued_path`` defaults to the issued card of this tree; a relative path
    resolves against ``root``. ``candidate_sha256`` and ``issued_receipt_sha256``
    are the caller stating what it believes; they are CHECKED, never trusted.

    It refuses -- with the subject named -- only when the binding cannot be
    made at all: no issued card, or a candidate digest that is not the tree
    being compared. Everything else (a work list rebuilt on the candidate, a
    seal that no longer covers it, an admission receipt on disk that is not
    the one the card was minted under -- appended to ``notes``) is exactly
    what this mode exists for: the binding is to the ISSUED receipt (H10)."""
    root = Path(root)
    issued_p = Path(issued_path) if issued_path else Path(LOOP_ISSUED)
    if not issued_p.is_absolute():
        issued_p = root / issued_p
    if not issued_p.is_file():
        return {}, ["the issued card is absent (%s); a candidate-bound verdict has to say which card it was measured "
                    "for" % issued_p]
    try:
        issued = load_json(issued_p)
    except (OSError, ValueError) as exc:
        return {}, ["the issued card %s could not be read: %s" % (issued_p, exc)]
    if not isinstance(issued, dict):
        return {}, ["the issued card %s is not an object" % issued_p]
    gaps: list[str] = []
    minted = str(issued.get("receipt_sha256") or "")
    card = str(issued.get("task_id") or "") or str(issued.get("cluster") or "")
    if not minted:
        gaps.append("the issued card records no receipt_sha256; nothing says which receipt it was minted under")
    if not card:
        gaps.append("the issued card names neither a card nor a cluster")
    if issued_receipt_sha256 and minted and str(issued_receipt_sha256) != minted:
        gaps.append("--issued-receipt %s is not the receipt the card was minted under (%s)"
                    % (str(issued_receipt_sha256)[:12], minted[:12]))
    on_disk = ""
    rp = root / ADMISSION_RECEIPT
    if rp.is_file():
        try:
            on_disk = str((load_json(rp) or {}).get("receipt_digest") or "")
        except (OSError, ValueError):
            on_disk = ""
    # H10 (dest v9 t_56adcd76): the binding is to the receipt the card was
    # MINTED under -- issued.json says which -- never to whatever
    # admission-receipt.json says now. A mid-card verification never re-seals
    # admission, but a concurrent writer can (a previous card's advance.py
    # outliving its terminal timeout), and a correct repair was parked as
    # unproven for it. A mismatch is said out loud, and the binding is made.
    if not on_disk:
        (notes if notes is not None else []).append(
            "no admission receipt on disk (%s); the binding is the receipt the card was minted under (%s)"
            % (ADMISSION_RECEIPT.as_posix(), minted[:12]))
    elif minted and on_disk != minted:
        (notes if notes is not None else []).append(
            "%s names another receipt (%s) than the one the card was minted under (%s): admission was re-sealed after the "
            "mint -- a mid-card verification never does that (advance, rewind, operator-step, refresh and resume do); the "
            "binding is to the issued receipt" % (ADMISSION_RECEIPT.as_posix(), on_disk[:12], minted[:12]))
    recorded = ""
    runp = root / VERIFY_RUN
    if not runp.is_file():
        gaps.append("%s is absent; this verification recorded no candidate" % VERIFY_RUN.as_posix())
    else:
        try:
            recorded = str((load_json(runp) or {}).get("candidate_sha256") or "")
        except (OSError, ValueError) as exc:
            gaps.append("%s could not be read: %s" % (VERIFY_RUN.as_posix(), exc))
        if runp.is_file() and not recorded:
            gaps.append("%s records no candidate_sha256" % VERIFY_RUN.as_posix())
    if candidate_sha256 and recorded and str(candidate_sha256) != recorded:
        gaps.append("--candidate %s is not the candidate this verification recorded (%s)"
                    % (str(candidate_sha256)[:12], recorded[:12]))
    if recorded:
        on_tree = product_tree_digest(root)
        if on_tree != recorded:
            gaps.append("the candidate digest in %s (%s) is not the tree this comparison is about (%s); the product "
                        "tree changed after it was verified" % (VERIFY_RUN.as_posix(), recorded[:12], on_tree[:12]))
    if gaps:
        return {}, gaps
    return {"mode": BINDING_CANDIDATE, "candidate_sha256": recorded, "issued_receipt_sha256": minted,
            "card": card}, []


def binding_of(doc: Any) -> dict[str, Any]:
    """The binding a record carries. A record written before this block existed
    carries none, and a record with no binding is a SEALED one: that is what
    every verdict was."""
    b = doc.get("binding") if isinstance(doc, dict) else None
    return dict(b) if isinstance(b, dict) and b else sealed_binding()


def binding_mismatch(doc: Any, binding: dict[str, Any]) -> str:
    """Why this record is not a measurement of ``binding``'s candidate and card.

    A record bound to the SEAL is admitted: on the acceptance path those are
    the verdicts the last full M4 run left for every scenario this run was not
    scoped to, and dropping them would make a scoped run look like a
    regression at every other entry point."""
    got = binding_of(doc)
    if str(got.get("mode") or BINDING_SEALED) != BINDING_CANDIDATE:
        return ""
    for key, what in (("card", "the card"), ("candidate_sha256", "the candidate"),
                      ("issued_receipt_sha256", "the receipt the card was minted under")):
        want = str(binding.get(key) or "")
        have = str(got.get(key) or "")
        if have != want:
            if key != "card":
                have, want = have[:12] or "none", want[:12] or "none"
            return "it was measured for %s %s and this one is %s" % (what, have or "none", want or "none")
    return ""


def scenario_slug(scenario_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(scenario_id))[:120]


# --- which parity records a receipt is composed FROM ------------------------
# The composer composes over the records on DISK, and that is deliberate: it is
# what lets a scoped run keep the verdicts the last full run left for every
# scenario the filter was not scoped to. What it must never mean is composing
# over records of another question. Measured on destination v9,
# verification/parity/scenarios/ still held cors-preflight-<digest>.json and
# cors-actual-<digest>.json from an earlier naming scheme beside the current
# sc_cors-preflight-<...>.json records: each of those became an INCONCLUSIVE
# row whose reason was "no scenario 'cors-preflight-<digest>' in the corpus",
# or a second result file for a scenario that already had one ("N result
# files") -- 33 of 34 rows INCONCLUSIVE after a scoped run that compared one
# scenario and changed nothing else. A record that does not belong to this
# corpus is not evidence against it; it is evidence of another one. So a record
# is composed over only when its FILE NAME is the slug of a scenario the
# current corpus declares, it holds that scenario, and it was compared against
# this corpus digest in this security mode and this fixture variant. Every
# other file is NAMED as an orphan and counted nowhere else.
PARITY_ORPHANS = Path("verification") / "parity" / "_orphaned"
ORPHAN_UNDECLARED = "undeclared-scenario"
ORPHAN_NAME = "name-mismatch"
ORPHAN_CORPUS = "stale-corpus"
ORPHAN_MODE = "other-mode"
ORPHAN_UNREADABLE = "unreadable"


def declared_slugs(declared: Any) -> dict[str, str]:
    """{file stem: scenario id} for every scenario a corpus declares.

    Takes the corpus's own scenario objects or bare ids, so a caller that has
    one and not the other never has to build the other."""
    out: dict[str, str] = {}
    for item in (declared or []):
        sid = str(item.get("id") or "") if isinstance(item, dict) else str(item or "")
        if sid:
            out[scenario_slug(sid)] = sid
    return out


def parity_record_orphan(doc: Any, name: str, *, slugs: dict[str, str], corpus_sha: str = "",
                         security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> dict[str, str]:
    """Why this record is not one of THIS receipt's, or {} when it is one.

    ``slugs`` is declared_slugs() of the corpus the receipt is of; ``name`` is
    the record's file name, which is checked and not merely read past: a record
    holding a declared scenario under a file name that is not that scenario's
    slug is a duplicate waiting to be counted twice."""
    mode = str(security_mode or "")
    want_variant = str(variant or "")
    if not isinstance(doc, dict):
        return {"kind": ORPHAN_UNREADABLE, "scenario": "",
                "reason": "%s is not a readable parity record" % name}
    sid = str(doc.get("scenario") or "")
    stem = name[:-len(".json")] if name.endswith(".json") else name
    declared = slugs.get(stem, "")
    if not declared:
        if sid and sid in slugs.values():
            return {"kind": ORPHAN_NAME, "scenario": sid,
                    "reason": "it holds scenario %r, whose record is %s.json" % (sid, scenario_slug(sid))}
        return {"kind": ORPHAN_UNDECLARED, "scenario": sid,
                "reason": "no scenario %r is declared by the corpus this receipt is of" % (sid or stem)}
    if sid != declared:
        return {"kind": ORPHAN_NAME, "scenario": sid,
                "reason": "it is the record of scenario %r and holds %r" % (declared, sid or "nothing")}
    dmode = str(doc.get("security_mode") or "")
    if dmode and dmode != mode:
        return {"kind": ORPHAN_MODE, "scenario": sid,
                "reason": "it compared the %s mode and this receipt is of the %s mode" % (dmode, mode)}
    dvariant = str(doc.get("security_variant") or "")
    if dvariant != want_variant:
        return {"kind": ORPHAN_MODE, "scenario": sid,
                "reason": "it compared the %s and this receipt is of the %s"
                          % (("%s fixture variant" % dvariant) if dvariant else "mode baseline",
                             ("%s fixture variant" % want_variant) if want_variant else "mode baseline")}
    # A record that names ANOTHER corpus (or another mode) is evidence of
    # another question and is set aside. A record that names NONE is evidence
    # of no question -- a comparison that refused before it could bind one,
    # which is this run's own measurement of a declared scenario. That is not
    # an orphan: it stays where it is, and the row refuses it by name.
    dcorpus = str(doc.get("corpus_sha256") or "")
    if corpus_sha and dcorpus and dcorpus != corpus_sha:
        return {"kind": ORPHAN_CORPUS, "scenario": sid,
                "reason": "it was compared against corpus %s and this receipt is of %s"
                          % (dcorpus[:12], corpus_sha[:12])}
    return {}


def partition_parity_records(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "", *,
                             declared: Any = (), corpus_sha: str = "") -> tuple[list[tuple[Path, dict[str, Any]]],
                                                                               list[dict[str, str]]]:
    """This mode's parity scenarios directory, split in two: the records the
    receipt is composed from, and the orphans it only names.

    Meta files (``_``-prefixed) and hidden files are neither: they are not
    records, so they are not judged as one and never moved aside."""
    base = Path(root)
    slugs = declared_slugs(declared)
    sdir = base / scenario_parity_dir(security_mode, variant)
    kept: list[tuple[Path, dict[str, Any]]] = []
    orphans: list[dict[str, str]] = []
    for p in sorted(sdir.iterdir()) if sdir.is_dir() else []:
        if not p.is_file() or p.name.startswith(("_", ".")):
            continue
        doc: Any = None
        if p.name.endswith(".json"):
            try:
                doc = load_json(p)
            except (OSError, ValueError):
                doc = None
        why = parity_record_orphan(doc, p.name, slugs=slugs, corpus_sha=corpus_sha,
                                   security_mode=security_mode, variant=variant)
        if why:
            orphans.append({"path": p.relative_to(base).as_posix(), **why})
        else:
            kept.append((p, doc))
    return kept, orphans


def load_corpus(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE, variant: Any = "") -> dict[str, Any]:
    """The corpus of one security mode (and one of its fixture variants). The
    default mode reads exactly the path (and states exactly the refusals) it
    always did."""
    corpus_rel = corpus_path(security_mode, variant)
    p = Path(root) / corpus_rel
    if not p.is_file():
        raise CorpusError("missing %s (the Operator-approved scenario corpus)" % corpus_rel)
    doc = load_json(p)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise CorpusError("%s is not a %s document" % (corpus_rel, SCHEMA))
    if doc.get("path_vars") is not None and not isinstance(doc.get("path_vars"), dict):
        raise CorpusError("%s path_vars must be a mapping of template variable to a value from the source's own seeded data" % corpus_rel)
    seen: set[str] = set()
    for i, sc in enumerate(doc.get("scenarios") or []):
        if not isinstance(sc, dict):
            raise CorpusError("scenarios[%d] is not an object" % i)
        for field in ("id", "entry_point", "method", "path"):
            if not str(sc.get(field) or "").strip():
                raise CorpusError("scenarios[%d] has no %s" % (i, field))
        if sc["id"] in seen:
            raise CorpusError("scenario id %r appears twice" % sc["id"])
        seen.add(str(sc["id"]))
        if "{" in str(sc["path"]) or "*" in str(sc["path"]):
            raise CorpusError("scenario %s has path %r: a scenario carries a concrete URL, never a route pattern (the route stays in the inventory)" % (sc["id"], sc["path"]))
        if not sc.get("body_file") and not sc.get("body_absent"):
            raise CorpusError("scenario %s must either name a body_file or state body_absent: true (an absent body is a fact, not an omission)" % sc["id"])
        if sc.get("body_file") and sc.get("body_absent"):
            raise CorpusError("scenario %s both names a body and says it has none" % sc["id"])
        hdrs = {str(k).lower(): str(v) for k, v in (sc.get("headers") or {}).items()}
        if str(sc["method"]).upper() == "OPTIONS":
            # a preflight asks permission; it must ask the way a browser does
            if "origin" not in hdrs or "access-control-request-method" not in hdrs:
                raise CorpusError("scenario %s is an OPTIONS preflight and must carry Origin and Access-Control-Request-Method "
                                  "(and Access-Control-Request-Headers when the actual request sends any)" % sc["id"])
            if (str((sc.get("identity") or {}).get("kind") or "none") != "none"
                    and str(sc.get("scenario_type") or "") != SCENARIO_DIAGNOSTIC_PROBE):
                raise CorpusError("scenario %s is a preflight: browsers send it without credentials, so it carries no identity "
                                  "(an authenticated OPTIONS is admitted only as scenario_type %s)"
                                  % (sc["id"], SCENARIO_DIAGNOSTIC_PROBE))
        identity_gap = identity_shape_gap(sc.get("identity"))
        if identity_gap:
            raise CorpusError("scenario %s %s" % (sc["id"], identity_gap))
        if sc.get("effects_identity") is not None:
            effects_gap = identity_shape_gap(sc.get("effects_identity"))
            if effects_gap:
                raise CorpusError("scenario %s effects_identity: %s" % (sc["id"], effects_gap))
            if not sc.get("effects"):
                raise CorpusError("scenario %s names an effects_identity and declares no effects: the identity names "
                                  "read-backs nobody takes" % sc["id"])
        if "origin" in hdrs and not sc.get("cors_policy"):
            raise CorpusError("scenario %s sends a cross-origin Origin and names no cors_policy; coverage is counted per policy" % sc["id"])
        if sc.get("cors_policy") and str(sc["cors_policy"]) not in {str(p.get("id")) for p in (doc.get("cors_policies") or [])}:
            raise CorpusError("scenario %s names cors_policy %r, which cors_policies does not declare" % (sc["id"], sc["cors_policy"]))
    # a corpus that names a mode must be the mode that was asked for: a
    # corpus is copied, and reading the enabled one as the disabled one would
    # judge 401s against anonymous expectations (the reuse ADR-014 forbids)
    recorded = str(doc.get("security_mode") or "")
    if recorded and recorded != normalize_security_mode(security_mode):
        raise CorpusError("%s records security_mode %r; this is the %s corpus"
                          % (corpus_rel, recorded, normalize_security_mode(security_mode)))
    # ... and a corpus derived for a fixture VARIANT is not the mode's
    # baseline corpus: its scenarios expect the source's behaviour under a
    # database state the baseline does not have
    want_variant = normalize_variant(variant, security_mode) if variant else ""
    recorded_variant = str(doc.get("security_variant") or "")
    if recorded_variant != want_variant:
        raise CorpusError("%s records security_variant %r; this is the %s corpus"
                          % (corpus_rel, recorded_variant,
                             ("%s fixture variant's" % want_variant) if want_variant else "mode baseline"))
    # a DERIVED variant corpus names the derivation it was made under; one
    # made under another is derived again, never read as though it made the
    # promises this one does (its refused writes may carry no read-back)
    if want_variant and is_derived(doc):
        made_by = str((doc.get("derived_from") or {}).get("variant_derivation") or "")
        if made_by != VARIANT_DERIVATION:
            raise CorpusError("%s was derived by fixture-variant derivation %r and this harness derives %r (a refused write "
                              "now carries read-backs that prove it changed nothing); derive the variant again, then "
                              "re-capture and re-qualify it" % (corpus_rel, made_by or "v1 (unversioned)", VARIANT_DERIVATION))
    # provenance last: it recomputes request digests, which assumes the
    # scenarios are well-formed (checked above)
    provenance_gap = corpus_provenance_gap(root, doc, security_mode, variant)
    if provenance_gap:
        raise CorpusError(provenance_gap)
    return doc


_PLACEHOLDER_MARKS = ("TODO", "<", ">")


def is_derived(doc: dict[str, Any]) -> bool:
    """A corpus that names its producer rather than a person."""
    return isinstance(doc.get("derived_from"), dict) and not doc.get("approved_by")


def corpus_provenance_gap(root: Path, doc: dict[str, Any], security_mode: Any = DEFAULT_SECURITY_MODE,
                          variant: Any = "") -> str:
    """Why this corpus may NOT be trusted; "" when its provenance holds.

    Two provenances are accepted. A DERIVED corpus (``derived_from``) is bound
    to the derivation receipt beside it: the receipt says ``status: ok``, its
    ``corpus_sha256`` equals this document's digest (a derived corpus edited
    after derivation no longer matches and is refused -- the edit is a hand
    author with no name) and its ``evidence_bundle_sha256`` equals the digest
    of the bundle in this tree (a corpus derived from another frozen source
    proves nothing about this one). A hand-AUTHORED corpus names a person in
    ``approved_by``; a placeholder (``TODO``, ``<who>``) is not a name. The
    wording never says "missing": capture-source-scenarios.py reads that word
    as "no corpus at all", which is idle, and a broken binding is not idle."""
    corpus_rel = corpus_path(security_mode, variant)
    receipt_rel = derive_receipt_path(security_mode, variant)
    approved = doc.get("approved_by")
    if approved:
        text = str(approved)
        if any(m in text for m in _PLACEHOLDER_MARKS):
            return "%s approved_by %r is a placeholder, not an approver" % (corpus_rel, text)
        return ""
    derived = doc.get("derived_from")
    if not isinstance(derived, dict):
        return ("%s is neither derived (derived_from) nor hand-authored (approved_by); "
                "derive it from the frozen source's evidence (derive-source-scenarios.py)" % corpus_rel)
    rp = Path(root) / receipt_rel
    if not rp.is_file():
        return "%s says it is derived but there is no derivation receipt %s beside it" % (corpus_rel, receipt_rel)
    try:
        receipt = load_json(rp)
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (receipt_rel, exc)
    if not isinstance(receipt, dict) or receipt.get("schema") != DERIVATION_SCHEMA:
        return "%s is not a %s document" % (receipt_rel, DERIVATION_SCHEMA)
    if receipt.get("status") != "ok":
        return "%s records status %r, so the derivation did not complete" % (receipt_rel, receipt.get("status"))
    have = corpus_digest(doc)
    if str(receipt.get("corpus_sha256") or "") != have:
        return ("%s digest %s is not the one the derivation receipt recorded (%s): the corpus was edited after derivation, "
                "and an edit has no provenance" % (corpus_rel, have[:12], str(receipt.get("corpus_sha256") or "")[:12]))
    bp = Path(root) / EVIDENCE_BUNDLE
    if not bp.is_file():
        return "%s is derived but there is no %s in this tree to bind it to" % (corpus_rel, EVIDENCE_BUNDLE)
    try:
        bundle_sha = digest(load_json(bp))
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (EVIDENCE_BUNDLE, exc)
    if str(receipt.get("evidence_bundle_sha256") or "") != bundle_sha:
        return ("%s was derived against evidence bundle %s, this tree's bundle is %s: derive it again"
                % (corpus_rel, str(receipt.get("evidence_bundle_sha256") or "")[:12], bundle_sha[:12]))
    # the corpus digest binds body FILENAMES only; the receipt binds the body
    # bytes and every complete request digest, and each is recomputed here (a
    # body edited after derivation passed the corpus digest: architect review
    # of 708cfef9, body_only_edit_after_derivation)
    bodies = receipt.get("bodies")
    requests = receipt.get("requests")
    if not isinstance(bodies, dict) or not isinstance(requests, dict):
        return "%s binds no body or request digests (bodies/requests); derive the corpus again" % receipt_rel
    for sc in doc.get("scenarios") or []:
        if not isinstance(sc, dict):
            continue
        sid = str(sc.get("id"))
        bf = str(sc.get("body_file") or "")
        if bf:
            bp = Path(root) / bf
            if not bp.is_file():
                return "body/request edited after derivation: %s names body_file %s, which is absent" % (sid, bf)
            if sha256_bytes(bp.read_bytes()) != str(bodies.get(bf) or ""):
                return "body/request edited after derivation: %s (%s) no longer has the bytes the derivation wrote" % (bf, sid)
        try:
            have = request_of(root, sc)["request_sha256"]
        except CorpusError as exc:
            return "body/request edited after derivation: %s" % exc
        if have != str(requests.get(sid) or ""):
            return "body/request edited after derivation: %s request digest %s is not the derived %s" % (sid, have[:12], str(requests.get(sid) or "")[:12])
    return ""


def cors_coverage(doc: dict[str, Any], source_policies: list[str] | None = None) -> list[str]:
    """What the corpus does NOT cover of the source's CORS behaviour; [] = covered.

    Per declared policy: an actual request carrying a cross-origin Origin, and
    an OPTIONS preflight with Origin, Access-Control-Request-Method and every
    request header the policy needs. A policy the SOURCE declares that the
    corpus does not name is a gap too. Missing coverage makes parity
    INCONCLUSIVE; it is never a pass on CORS."""
    gaps: list[str] = []
    scenarios = list(doc.get("scenarios") or [])
    declared = {str(p.get("id")): p for p in (doc.get("cors_policies") or []) if p.get("id")}
    for pid, pol in sorted(declared.items()):
        mine = [sc for sc in scenarios if str(sc.get("cors_policy") or "") == pid]
        lower = [(sc, {str(k).lower(): str(v) for k, v in (sc.get("headers") or {}).items()}) for sc in mine]
        actual = [sc for sc, h in lower if str(sc.get("method")).upper() != "OPTIONS" and "origin" in h]
        need = {str(x).strip().lower() for x in (pol.get("request_headers") or []) if str(x).strip()}
        # a diagnostic probe carries credentials no browser sends on a
        # preflight: it answers a question, and discharges no coverage
        pre = [sc for sc, h in lower if str(sc.get("method")).upper() == "OPTIONS" and "origin" in h
               and str(sc.get("scenario_type") or "") != SCENARIO_DIAGNOSTIC_PROBE
               and "access-control-request-method" in h
               and need <= {t.strip().lower() for t in h.get("access-control-request-headers", "").split(",") if t.strip()}]
        if not actual:
            gaps.append("cors policy %s has no actual cross-origin exchange" % pid)
        if not pre:
            gaps.append("cors policy %s has no preflight carrying Origin, Access-Control-Request-Method%s"
                        % (pid, (" and " + ", ".join(sorted(need))) if need else ""))
    for sp in sorted(set(source_policies or []) - set(declared)):
        gaps.append("the source declares cors policy %s and the corpus does not cover it" % sp)
    return gaps


_CORS_API = ("org.springframework.web.cors.", "org.springframework.web.servlet.config.annotation.CorsRegistry",
             "org.springframework.web.servlet.config.annotation.CorsRegistration")


def source_cors_policy_map(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """({policy id: {"kind", "values", "types"}}, why-unknown) -- the CORS
    policies the FROZEN source declares, with the annotation values and the
    types that carry each one.

    Read from M1's structural model of the source, never from text: every
    distinct @CrossOrigin configuration is one policy (the same annotation on
    six controllers is one policy, a different exposedHeaders is another), and
    a type wired to Spring's CORS configuration API is a global policy. The id
    is the digest of the annotation values, so the derivation, the coverage
    check and the parity receipt name the same policy. An unreadable model is
    a reason, not an empty map: "no policies" and "not read" must not look the
    same."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return {}, "M1's structural model %s is not in this tree, so the source's CORS policies are unknown" % STRUCTURE
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (STRUCTURE, exc)
    out: dict[str, dict[str, Any]] = {}
    for t in doc.get("types") or []:
        fqn_t = str(t.get("fqn") or "")
        anns = list(t.get("annotations") or [])
        for m in t.get("methods") or []:
            anns.extend(m.get("annotations") or [])
        for a in anns:
            fqn = str(a.get("fqn") or a.get("name") or "")
            if fqn == "org.springframework.web.bind.annotation.CrossOrigin" or fqn.rsplit(".", 1)[-1] == "CrossOrigin":
                values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
                pid = "crossorigin:%s" % sha256_bytes(canonical_bytes(values))[:12]
                row = out.setdefault(pid, {"kind": "crossorigin", "values": values, "types": []})
                if fqn_t and fqn_t not in row["types"]:
                    row["types"].append(fqn_t)
        refs = [str(x) for x in (t.get("type_refs") or t.get("refs") or [])] + [str(x) for x in (t.get("supertypes") or [])]
        if any(r.startswith(_CORS_API) for r in refs):
            out["global:%s" % fqn_t] = {"kind": "global", "values": {}, "types": [fqn_t]}
    for row in out.values():
        row["types"].sort()
    return dict(sorted(out.items())), ""


def source_cors_policies(root: Path) -> tuple[list[str], str]:
    """(the CORS policy ids the FROZEN source declares, why-unknown); see
    source_cors_policy_map."""
    policies, why = source_cors_policy_map(root)
    return sorted(policies), why


def source_exposed_headers(root: Path) -> tuple[list[str], str]:
    """(the response headers the FROZEN source exposes to cross-origin
    callers, why-unknown) -- every ``exposedHeaders`` value of every
    ``@CrossOrigin`` in M1's structure model, split on commas.

    A header the source chose to expose is part of its behaviour: petclinic
    answers a validation failure as 400 with the errors in an ``errors`` header
    and exposes exactly that header. Asserting the CORS permission set alone
    would let a destination drop or move those errors and still pass. Read
    from the model, never from text; unreadable is a reason, not an empty
    list."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return [], "M1's structural model %s is not in this tree, so the source's exposed headers are unknown" % STRUCTURE
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return [], "%s could not be read: %s" % (STRUCTURE, exc)
    out: set[str] = set()
    for t in doc.get("types") or []:
        anns = list(t.get("annotations") or [])
        for m in t.get("methods") or []:
            anns.extend(m.get("annotations") or [])
        for a in anns:
            fqn = str(a.get("fqn") or a.get("name") or "")
            if fqn.rsplit(".", 1)[-1] != "CrossOrigin":
                continue
            values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
            raw = values.get("exposedHeaders") if isinstance(values, dict) else None
            for item in (raw if isinstance(raw, list) else [raw] if raw else []):
                for tok in str(item).split(","):
                    if tok.strip():
                        out.add(tok.strip())
    return sorted(out), ""


def corpus_digest(doc: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(doc))


def scenario(doc: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    for sc in doc.get("scenarios") or []:
        if str(sc.get("id")) == scenario_id:
            return sc
    raise CorpusError("no scenario %r in %s" % (scenario_id, CORPUS))


def normalized_identity(identity: Any) -> dict[str, Any]:
    """One identity as the evidence carries it: NAMES only.

    ``credential_ref`` joins the two env names only when something names one:
    adding an empty key to every request would change the digest of every
    scenario already captured, and a shape nobody uses must not invalidate
    another mode's evidence."""
    ident = identity if isinstance(identity, dict) else {}
    out: dict[str, Any] = {"kind": str(ident.get("kind") or "none"),
                           "user_env": str(ident.get("user_env") or ""),
                           "password_env": str(ident.get("password_env") or "")}
    ref = str(ident.get("credential_ref") or "")
    if ref:
        out["credential_ref"] = ref
    return out


def effects_identity_of(sc: dict[str, Any]) -> dict[str, Any] | None:
    """The identity a scenario's effect READ-BACKS are taken with, or None
    when they are taken as the request itself.

    A negative authorization scenario is a request the source REFUSES, and
    its read-backs used to be taken with the refusing caller's identity: the
    before and after probes of an anonymous DELETE answered 401, so "the
    state is unchanged" -- the whole point of the scenario -- could not be
    judged (v9: 15 scenarios INCONCLUSIVE on ``after_equals_before``). A
    scenario may therefore declare ``effects_identity``, the identity the
    policy ACCEPTS, and the read-backs are taken as that one. It is not part
    of the request and never enters the request digest: the request the
    source refused is the same request either way."""
    ident = (sc or {}).get("effects_identity")
    return dict(ident) if isinstance(ident, dict) and ident else None


def request_of(root: Path, sc: dict[str, Any]) -> dict[str, Any]:
    """The complete request a scenario describes, with its digest.

    The digest covers method, path, headers, identity kind and the body bytes,
    so a replay can prove it is sending what was recorded rather than
    something that merely looks like it."""
    body: bytes | None = None
    if sc.get("body_file"):
        p = Path(root) / str(sc["body_file"])
        if not p.is_file():
            raise CorpusError("scenario %s names body_file %s, which does not exist" % (sc["id"], sc["body_file"]))
        body = p.read_bytes()
    headers = {str(k): str(v) for k, v in (sc.get("headers") or {}).items()}
    # The REFERENCES travel with the request and are digested: which account a
    # request runs as is part of what makes it the same request. The values
    # never appear here. Dropping password_env made every authenticated replay
    # INCONCLUSIVE with both credentials present.
    ident = normalized_identity(sc.get("identity"))
    digest_input = {
        "method": str(sc["method"]).upper(), "path": str(sc["path"]),
        "headers": dict(sorted(headers.items())),
        "identity": dict(ident),
        "body_sha256": sha256_bytes(body) if body is not None else "",
        "body_absent": body is None,
    }
    return {
        "method": digest_input["method"], "path": digest_input["path"], "headers": headers,
        "identity": dict(ident),
        "body": body, "body_sha256": digest_input["body_sha256"], "body_absent": body is None,
        "request_sha256": sha256_bytes(canonical_bytes(digest_input)),
    }


def auth_headers(identity: dict[str, Any]) -> tuple[dict[str, str], str]:
    """(headers, gap). Credentials come from the environment by NAME; a missing
    one is a gap the caller must report, never a silent anonymous request."""
    return auth_headers_for(identity, None)


# ---------------------------------------------------------------------------
# credentials: the evidence carries the REFERENCE (ADR-014)
# ---------------------------------------------------------------------------
# Two shapes name the same thing. ``user_env``/``password_env`` names the two
# halves separately; ``credential_ref`` names ONE variable holding
# ``user:password``, which is the shape the enabled-mode capture is driven
# with (``--credential-ref NAME``) because the capture then has a single name
# to declare, record and refuse to confuse with configuration. Neither shape
# ever puts a credential -- or the Authorization header built from one -- into
# a corpus, a capture or a receipt.
CREDENTIAL_SEPARATOR = ":"
_IDENTITY_VALUE_KEYS = ("password", "secret", "token", "authorization", "credential")
_IDENTITY_KINDS = ("none", "basic")


def identity_shape_gap(identity: Any) -> str:
    """Why this ``identity`` may not be used; "" when it is well-formed.

    Accepts ``none`` and ``basic``. A ``basic`` identity names either a
    ``credential_ref`` or both ``user_env`` and ``password_env``; a key that
    would hold the credential ITSELF is refused outright, because a corpus is
    read, digested and copied into every receipt downstream of it."""
    if identity in (None, {}):
        return ""
    if not isinstance(identity, dict):
        return "identity is not an object"
    for key in sorted(identity):
        if str(key).lower() in _IDENTITY_VALUE_KEYS:
            return ("identity carries %r: evidence names the environment variable that holds a credential "
                    "(credential_ref, or user_env/password_env), never the credential" % str(key))
    kind = str(identity.get("kind") or "none")
    if kind not in _IDENTITY_KINDS:
        return "declares identity kind %r; the loader accepts %s" % (kind, " and ".join(_IDENTITY_KINDS))
    if kind == "basic" and not str(identity.get("credential_ref") or "") and not (
            str(identity.get("user_env") or "") and str(identity.get("password_env") or "")):
        return ("authenticates with basic and names no credential_ref (nor user_env and password_env); "
                "the request cannot be made without a named credential")
    return ""


def credential_env_values(credential_refs: Any) -> set[str]:
    """Every string the named credential variables hold, and each half of a
    ``user:password`` one. Used to keep a credential out of the recorded
    configuration -- the halves count because the password half is the one
    that would be pasted into a property by mistake."""
    out: set[str] = set()
    for ref in (credential_refs or []):
        raw = os.environ.get(str(ref), "")
        if not raw:
            continue
        out.add(raw)
        if CREDENTIAL_SEPARATOR in raw:
            user, _, password = raw.partition(CREDENTIAL_SEPARATOR)
            out.update(x for x in (user, password) if x)
    return out


def credential_conflicts(source_config: dict[str, str], credential_refs: Any) -> list[str]:
    """The configuration KEYS whose value is a credential the environment
    holds under one of the named references.

    ``source_config`` is recorded verbatim on the capture receipt -- that is
    what makes the mode reproducible -- so a credential passed as
    configuration would be written into the evidence. Naming the key (never
    the value) is enough to fix it."""
    values = credential_env_values(credential_refs)
    return sorted(k for k, v in (source_config or {}).items() if str(v) in values)


def parse_assignments(items: Any, what: str = "--source-config") -> dict[str, str]:
    """``KEY=VALUE`` repetitions as a mapping. The harness never knows the KEY:
    which switch turns the source's security on is an argument it records, not
    a name it carries."""
    out: dict[str, str] = {}
    for item in (items or []):
        text = str(item)
        key, sep, value = text.partition("=")
        if not sep or not key.strip():
            raise CorpusError("%s %r is not KEY=VALUE" % (what, text))
        if key.strip() in out:
            raise CorpusError("%s names %s twice" % (what, key.strip()))
        out[key.strip()] = value
    return out


def auth_headers_for(identity: dict[str, Any], credential_refs: Any = None) -> tuple[dict[str, str], str]:
    """(headers, gap) for one identity, with the credential read at request
    time from the environment.

    ``credential_refs`` is the allow-list the caller declared (None = no
    restriction, the historical behaviour). A scenario naming a reference the
    caller did not declare is a GAP, not a quiet anonymous request: the
    capture reads only variables it was told to read, so what a capture may
    touch is on its own command line and on its receipt."""
    ident = identity or {}
    kind = str(ident.get("kind") or "none")
    if kind in ("", "none"):
        return {}, ""
    if kind != "basic":
        return {}, "identity kind %r is not supported; the corpus must describe how the request authenticates" % kind
    ref = str(ident.get("credential_ref") or "")
    if ref:
        if credential_refs is not None and ref not in {str(r) for r in credential_refs}:
            return {}, ("identity names credential_ref %s, which this capture was not given (pass --credential-ref %s); "
                        "a credential is never read from an undeclared variable" % (ref, ref))
        raw = os.environ.get(ref, "")
        if not raw:
            return {}, "identity needs %s in the environment (it holds user%spassword)" % (ref, CREDENTIAL_SEPARATOR)
        user, sep, password = raw.partition(CREDENTIAL_SEPARATOR)
        if not sep or not user or not password:
            return {}, "the credential %s does not hold user%spassword" % (ref, CREDENTIAL_SEPARATOR)
    else:
        user = os.environ.get(str(ident.get("user_env") or ""), "")
        password = os.environ.get(str(ident.get("password_env") or ""), "")
        if not user or not password:
            return {}, "identity needs %s and %s in the environment" % (ident.get("user_env"), ident.get("password_env"))
    token = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic %s" % token}, ""


# ---------------------------------------------------------------------------
# the source's own authorization policies (ADR-014)
# ---------------------------------------------------------------------------
_AUTHZ_ANNOTATIONS = ("PreAuthorize", "RolesAllowed", "Secured")


def _authz_expression(simple: str, values: Any) -> str:
    """The policy a single annotation states, as one comparable expression.

    ``@PreAuthorize`` carries an expression; ``@RolesAllowed`` and
    ``@Secured`` carry a role SET, so their roles are sorted -- two handlers
    that list the same roles in another order state one policy, not two."""
    vals = values if isinstance(values, dict) else {}
    raw = vals.get("value")
    if raw is None and len(vals) == 1:
        raw = list(vals.values())[0]
    items = raw if isinstance(raw, list) else ([] if raw in (None, "") else [raw])
    texts = [str(x) for x in items if str(x).strip()]
    if simple == "PreAuthorize":
        return " ".join(texts).strip()
    return ", ".join(sorted(texts))


def _authz_of(annotations: Any) -> list[tuple[str, str]]:
    """[(annotation simple name, expression)] for one member or type."""
    out: list[tuple[str, str]] = []
    for a in (annotations or []):
        if not isinstance(a, dict):
            continue
        fqn = str(a.get("fqn") or a.get("name") or "")
        simple = fqn.rsplit(".", 1)[-1]
        if simple not in _AUTHZ_ANNOTATIONS:
            continue
        values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
        out.append((simple, _authz_expression(simple, values)))
    return sorted(set(out))


def source_authorization_policy_map(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """({policy id: {"annotation", "expression", "entry_points", "types",
    "members"}}, why-unknown) -- the DISTINCT authorization policies the frozen
    source states, and which entry points each one guards.

    Read from M1's structure model (``@PreAuthorize``, ``@RolesAllowed``,
    ``@Secured``) and joined to the evidence bundle's entry points, never from
    text and never from a specimen's own role names: the id is the digest of
    the annotation and its expression, so the same policy on six handlers is
    one policy and a renamed controller states the same set. A member's own
    annotation overrides its type's, the way the platform resolves it.

    Enabled-mode scenario derivation (allowed identity / anonymous / invalid
    credentials / authenticated without the role) is a later change; it
    consumes this map, so the policies it must cover are named here rather
    than inferred from a controller's text. An unreadable model or a missing
    bundle is a REASON: "no policies" and "not read" must not look alike."""
    sp = Path(root) / STRUCTURE
    if not sp.is_file():
        return {}, "M1's structural model %s is not in this tree, so the source's authorization policies are unknown" % STRUCTURE
    try:
        model = load_json(sp)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (STRUCTURE, exc)
    bp = Path(root) / EVIDENCE_BUNDLE
    if not bp.is_file():
        return {}, ("%s is not in this tree, so which entry points the source's authorization policies guard is unknown"
                    % EVIDENCE_BUNDLE)
    try:
        bundle = load_json(bp)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (EVIDENCE_BUNDLE, exc)
    by_member: dict[tuple[str, str], list[str]] = {}
    by_type: dict[str, list[str]] = {}
    for e in (bundle.get("entry_points") or []):
        if not isinstance(e, dict):
            continue
        eid, etype, member = str(e.get("id") or ""), str(e.get("type") or ""), str(e.get("member") or "")
        if not eid or not etype:
            continue
        by_member.setdefault((etype, member), []).append(eid)
        by_type.setdefault(etype, []).append(eid)
    out: dict[str, dict[str, Any]] = {}

    def add(simple: str, expression: str, fqn: str, member: str, eids: list[str]) -> None:
        pid = "authz:%s" % sha256_bytes(canonical_bytes({"annotation": simple, "expression": expression}))[:12]
        row = out.setdefault(pid, {"annotation": simple, "expression": expression,
                                   "entry_points": [], "types": [], "members": []})
        for eid in eids:
            if eid not in row["entry_points"]:
                row["entry_points"].append(eid)
        if fqn and fqn not in row["types"]:
            row["types"].append(fqn)
        label = "%s#%s" % (fqn, member) if member else fqn
        if label not in row["members"]:
            row["members"].append(label)

    for t in (model.get("types") or []):
        if not isinstance(t, dict):
            continue
        fqn = str(t.get("fqn") or "")
        type_policies = _authz_of(t.get("annotations"))
        covered: set[str] = set()
        for m in (t.get("methods") or []):
            if not isinstance(m, dict):
                continue
            sig = str(m.get("signature") or m.get("name") or "")
            eids = by_member.get((fqn, sig)) or by_member.get((fqn, str(m.get("name") or ""))) or []
            own = _authz_of(m.get("annotations"))
            for simple, expression in (own or type_policies):
                add(simple, expression, fqn, sig, eids)
            covered.update(eids)
        # a type-level policy guards whatever the type answers that no member
        # of the model claimed (a supertype or marker entry point)
        rest = [eid for eid in (by_type.get(fqn) or []) if eid not in covered]
        for simple, expression in type_policies:
            add(simple, expression, fqn, "", rest)
    for row in out.values():
        row["entry_points"].sort()
        row["types"].sort()
        row["members"].sort()
    return dict(sorted(out.items())), ""


def source_authorization_policies(root: Path) -> tuple[list[str], str]:
    """(the authorization policy ids the FROZEN source states, why-unknown);
    see source_authorization_policy_map."""
    policies, why = source_authorization_policy_map(root)
    return sorted(policies), why


# ---------------------------------------------------------------------------
# what a policy ACCEPTS: the supported expression grammar (ADR-014)
# ---------------------------------------------------------------------------
# The enabled-mode derivation needs one thing from each policy: which roles it
# lets through. Everything else about an authorization expression -- a method
# argument, a bean call, a boolean combination -- is a question this grammar
# does not answer, and an expression it cannot read is a typed GAP with no
# scenarios rather than a guess: deriving "authenticated without the role"
# from an expression nobody parsed would name an identity the source may well
# accept, and the negative scenario would be a false expectation.
#
# Supported: hasRole(<role>), hasAnyRole(<role>, ...), and the role LIST of
# @RolesAllowed / @Secured, where <role> is a quoted literal or a constant
# reference that resolves through M1's structure model (@roles.OWNER_ADMIN,
# #roles.OWNER_ADMIN, Roles.OWNER_ADMIN, T(a.b.Roles).OWNER_ADMIN). The
# constant is read from the model's own field values, never from a specimen's
# role names: the harness does not know what a role is called.
#
# `@roles` and `#roles` are SpEL BEAN references, and a bean is not a type: the
# name belongs to a type carrying a component stereotype, and is that type's
# decapitalized simple name unless the stereotype states one. Resolving the
# reference as though it were a type name would accept any class that happens
# to lower-case to it.
ROLE_PREFIX = "ROLE_"
# a field's recorded constant value; M1's model carries the literal under
# whichever of these keys its extractor writes
_CONSTANT_VALUE_KEYS = ("constant", "constant_value", "value", "literal", "initializer")
_ROLE_CALLS = ("hasRole", "hasAnyRole")
_ROLE_SET_ANNOTATIONS = ("RolesAllowed", "Secured")
# what makes a type a bean, and so makes its name a bean name
_COMPONENT_STEREOTYPES = ("Component", "Named", "Service")
# where a resolved constant's VALUE came from. The sealed model is preferred;
# a run whose sealed structure predates the constant key falls back to the
# frozen source's own tree, and the scenario says which one answered.
SEALED_STRUCTURE = "sealed structure"
FROZEN_SOURCE_MODEL = "frozen-source model"
_NO_CONSTANT = "the constant %s resolves to no string field of a type the structure model records"
_NOT_A_REFERENCE = "%s is neither a quoted role nor a constant this model resolves"
# the challenge a source sends with an unauthenticated refusal; asserted on
# the FIRST response of the scenarios that provoke it (redirects are never
# followed, so there is no second one to read)
CHALLENGE_HEADER = "WWW-Authenticate"


def _unquote(text: str) -> str:
    t = str(text).strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return t[1:-1]
    return t


def _decapitalize(simple: str) -> str:
    """A stereotyped type's default bean name (java.beans.Introspector's rule:
    two leading capitals are left alone, so ``URLRoles`` is ``URLRoles``)."""
    s = str(simple)
    if not s:
        return ""
    if len(s) > 1 and s[0].isupper() and s[1].isupper():
        return s
    return s[0].lower() + s[1:]


def _annotation_simple(a: Any) -> str:
    """An annotation row's simple name, from either model's shape (the dest
    model records ``simple`` beside the fqn; the structure model the fqn)."""
    if not isinstance(a, dict):
        return ""
    for key in ("simple", "fqn", "name"):
        text = str(a.get(key) or "").strip()
        if text:
            return text.rsplit(".", 1)[-1]
    return ""


def _annotation_values(a: Any) -> list[str]:
    """The string literals an annotation states for its ``value`` attribute.

    The structure model keys its values by attribute; the dest model keys the
    literal ones under ``named`` and flattens the rest. Either way an
    attribute nobody wrote is absent, never guessed."""
    if not isinstance(a, dict):
        return []
    named = a.get("named")
    raw: Any = None
    if isinstance(named, dict) and named:
        raw = named.get("value")
    if raw is None:
        values = a.get("values")
        raw = values.get("value") if isinstance(values, dict) else values
    items = raw if isinstance(raw, list) else ([] if raw in (None, "") else [raw])
    return [_unquote(str(x)) for x in items if str(x).strip()]


def _stereotype_of(annotations: Any) -> tuple[str, list[str]]:
    """(the component stereotype a type carries, the bean names it states).

    The first stereotype in name order, so two of them decide the same way
    every run. A stereotype that names the bean replaces the default: Spring
    registers ``@Component("theRoles")`` under that name and no other."""
    rows = [a for a in (annotations or []) if isinstance(a, dict)]
    for a in sorted(rows, key=_annotation_simple):
        simple = _annotation_simple(a)
        if simple in _COMPONENT_STEREOTYPES:
            return simple, [v for v in _annotation_values(a) if v]
    return "", []


def _field_constant(f: Any) -> str:
    """The literal a field row records, under whichever key wrote it."""
    if not isinstance(f, dict):
        return ""
    for key in _CONSTANT_VALUE_KEYS:
        raw = f.get(key)
        if isinstance(raw, str) and _unquote(raw):
            return _unquote(raw)
    return ""


def _index_role_constants(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The two indexes a reference is resolved through: by TYPE name (lowered,
    as a ``Roles.X`` reference is read) and by BEAN name (exact, as ``@roles``
    is). A name two different types answer to resolves to neither: an
    ambiguous reference is not a role."""
    by_type: dict[str, dict[str, Any]] = {}
    by_bean: dict[str, dict[str, Any]] = {}
    ambiguous_type: set[str] = set()
    ambiguous_bean: set[str] = set()
    for row in rows:
        key = str(row.get("simple") or "").lower()
        if key:
            prev = by_type.get(key)
            if prev is not None and (prev["fqn"] != row["fqn"] or prev["fields"] != row["fields"]):
                ambiguous_type.add(key)
            by_type[key] = row
        for bean in row.get("beans") or []:
            prev = by_bean.get(bean)
            if prev is not None and (prev["fqn"] != row["fqn"] or prev["fields"] != row["fields"]):
                ambiguous_bean.add(bean)
            by_bean[bean] = row
    for key in ambiguous_type:
        by_type.pop(key, None)
    for key in ambiguous_bean:
        by_bean.pop(key, None)
    return {
        "rows": sorted((dict(r) for r in rows), key=lambda r: str(r.get("fqn") or "")),
        "by_type": dict(sorted(by_type.items())),
        "by_bean": dict(sorted(by_bean.items())),
    }


def role_constants_from_model(model: Any, source: str = SEALED_STRUCTURE) -> dict[str, Any]:
    """The constants catalog of one structural model (M1's sealed model, or
    the dest-model extractor's reading of another tree).

    A row is kept when the type records a string constant OR carries a
    component stereotype: the stereotype alone is what makes ``@roles`` a name
    for it, and a constants type nothing records a value for must be reported
    as a missing CONSTANT rather than a missing bean."""
    types = model.get("types") if isinstance(model, dict) else model
    rows: list[dict[str, Any]] = []
    for t in (types or []):
        if not isinstance(t, dict):
            continue
        fqn = str(t.get("fqn") or "").strip()
        simple = fqn.rsplit(".", 1)[-1].strip()
        if not simple:
            continue
        fields: dict[str, str] = {}
        for f in (t.get("fields") or []):
            name = str(f.get("name") or "") if isinstance(f, dict) else ""
            value = _field_constant(f)
            if name and value:
                fields[name] = value
        stereotype, declared = _stereotype_of(t.get("annotations"))
        beans = sorted(dict.fromkeys(declared)) if declared else ([_decapitalize(simple)] if stereotype else [])
        if not fields and not stereotype:
            continue
        rows.append({"fqn": fqn, "simple": simple, "fields": fields,
                     "sources": {name: source for name in fields},
                     "stereotype": stereotype, "beans": beans})
    return _index_role_constants(rows)


def _merge_constant_rows(preferred: dict[str, Any] | None, fallback: dict[str, Any] | None) -> dict[str, Any]:
    if preferred is None:
        return dict(fallback or {})
    if fallback is None:
        return dict(preferred)
    row = dict(preferred)
    fields = dict(fallback.get("fields") or {})
    fields.update(preferred.get("fields") or {})
    sources = dict(fallback.get("sources") or {})
    sources.update(preferred.get("sources") or {})
    row["fields"] = fields
    row["sources"] = sources
    row["stereotype"] = str(preferred.get("stereotype") or fallback.get("stereotype") or "")
    row["beans"] = sorted(dict.fromkeys(list(preferred.get("beans") or []) + list(fallback.get("beans") or [])))
    return row


def merge_role_constants(preferred: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """One catalog from two, by type, the PREFERRED model's value winning
    wherever it has one. The sealed model is the preferred one: what M1 sealed
    is the claim of record, and the other tree is only read for what it does
    not carry."""
    rows: dict[str, dict[str, Any]] = {str(r.get("fqn") or ""): dict(r) for r in (fallback.get("rows") or [])}
    for r in (preferred.get("rows") or []):
        fqn = str(r.get("fqn") or "")
        rows[fqn] = _merge_constant_rows(r, rows.get(fqn))
    return _index_role_constants(list(rows.values()))


def source_role_constants(root: Path) -> tuple[dict[str, Any], str]:
    """(the constants catalog M1's sealed structure model states, why-unknown).

    A source that spells its roles once in a constants type and refers to them
    from every ``@PreAuthorize`` (``hasRole(@roles.OWNER_ADMIN)``) has put the
    role NAME in the model's field values; the expression alone carries only a
    reference."""
    p = Path(root) / STRUCTURE
    empty = _index_role_constants([])
    if not p.is_file():
        return empty, "M1's structural model %s is not in this tree, so a role constant cannot be resolved" % STRUCTURE
    try:
        model = load_json(p)
    except (OSError, ValueError) as exc:
        return empty, "%s could not be read: %s" % (STRUCTURE, exc)
    return role_constants_from_model(model, SEALED_STRUCTURE), ""


def _is_constant_reference(token: str) -> bool:
    """Whether a token is a REFERENCE rather than a role name written out."""
    tok = str(token).strip()
    return bool(tok) and (tok.startswith("T(") or tok[0] in ("@", "#") or "." in tok)


def resolve_role_constant(token: str, constants: dict[str, Any]) -> tuple[str, str, str]:
    """(the role a constant reference names, why-not, the resolution evidence).

    ``@roles.X`` / ``#roles.X`` is a SpEL bean reference: ``roles`` names a
    type that carries a component stereotype, by the name that stereotype
    states or by its decapitalized simple name. ``Roles.X`` and
    ``T(a.b.Roles).X`` name the type itself. Both end at a field whose
    recorded constant IS the role -- the harness never knows what a role is
    called, so an unrecorded constant is a gap and never a guess."""
    tok = str(token).strip()
    ref = tok
    if ref.startswith("T(") and ")" in ref:
        ref = ref[ref.index(")") + 1:].lstrip(".")
        ref = "%s.%s" % (tok[2:tok.index(")")].rsplit(".", 1)[-1], ref) if ref else ""
    bean_ref = bool(ref) and ref[0] in ("@", "#")
    ref = ref.lstrip("@#")
    if "." not in ref:
        return "", _NOT_A_REFERENCE % tok, ""
    owner, _, field = ref.rpartition(".")
    owner = owner.rsplit(".", 1)[-1].strip()
    if bean_ref:
        row = (constants.get("by_bean") or {}).get(owner)
        if row is None:
            return "", ("the bean reference %s names no component-stereotyped type (@%s) the structure model records"
                        % (tok, ", @".join(_COMPONENT_STEREOTYPES))), ""
    else:
        row = (constants.get("by_type") or {}).get(owner.lower())
        if row is None:
            return "", _NO_CONSTANT % tok, ""
    value = str((row.get("fields") or {}).get(field) or "")
    if not value:
        return "", _NO_CONSTANT % tok, ""
    detail = '%s.%s = "%s" (constant from %s)' % (row.get("simple"), field, value,
                                                  (row.get("sources") or {}).get(field) or SEALED_STRUCTURE)
    evidence = ("structure:%s @%s → bean %s; %s" % (row.get("simple"), row.get("stereotype"), owner, detail)
                if bean_ref else "structure:%s" % detail)
    return value, "", evidence


def _role_token(token: str, constants: dict[str, Any], *, literal_ok: bool) -> tuple[str, str, str]:
    """(the role a single argument names, why-not, the resolution evidence).

    ``literal_ok`` says whether a bare word is a role NAME: it is in a
    ``@RolesAllowed`` value list (the model records those as strings) and it
    is not inside a SpEL call, where a bare word is a reference to something
    this grammar has not read."""
    tok = str(token).strip()
    if not tok:
        return "", "an empty role", ""
    if tok[0] in ("'", '"'):
        role = _unquote(tok)
        return (role, "", "") if role else ("", "the empty string is not a role", "")
    if _is_constant_reference(tok):
        return resolve_role_constant(tok, constants or {})
    if literal_ok:
        return tok, "", ""
    return "", _NOT_A_REFERENCE % tok, ""


def _balanced(text: str) -> bool:
    """Whether every parenthesis in ``text`` closes inside it."""
    depth = 0
    for ch in str(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _split_args(text: str) -> list[str]:
    """The top-level comma-separated arguments of a call; a comma inside
    ``T(a.b.C)`` is not an argument separator."""
    out: list[str] = []
    depth, current = 0, ""
    for ch in str(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth <= 0:
            out.append(current)
            current = ""
            continue
        current += ch
    out.append(current)
    return [a.strip() for a in out if a.strip()]


def _role_arguments(annotation: str, expression: str) -> tuple[list[str], bool, str]:
    """(the arguments naming this policy's roles, whether a bare word is one
    of them, why-unsupported) -- the grammar, read once."""
    text = str(expression or "").strip()
    if not text:
        return [], False, "the policy states no expression"
    if str(annotation) in _ROLE_SET_ANNOTATIONS:
        return _split_args(text), True, ""
    call = re.fullmatch(r"([A-Za-z]\w*)\s*\((.*)\)", text, re.DOTALL)
    # the call has to BE the whole expression: ``hasRole('A') or hasRole('B')``
    # matches that pattern too, and reading it as one call would derive a
    # "lacks the role" identity the source in fact lets through
    if call is not None and not _balanced(call.group(2)):
        return [], False, "the expression combines terms (%s); a combination is not one role test" % text
    if call is None or call.group(1) not in _ROLE_CALLS:
        return [], False, "only %s and the role lists of %s are read" % (
            ", ".join("%s(...)" % c for c in _ROLE_CALLS), ", ".join("@%s" % a for a in _ROLE_SET_ANNOTATIONS))
    args = _split_args(call.group(2))
    if not args or (call.group(1) == "hasRole" and len(args) != 1):
        return [], False, "%s takes %s" % (call.group(1), "exactly one role" if call.group(1) == "hasRole" else "at least one role")
    return args, False, ""


def role_reference_tokens(annotation: str, expression: str) -> list[str]:
    """The constant REFERENCES this policy's role arguments name.

    What a derivation needs before it decides whether another model has to be
    read: which constants this expression depends on, without deciding yet
    whether any of them resolve."""
    args, _literal_ok, why = _role_arguments(annotation, expression)
    if why:
        return []
    return [t for t in args if t and t[0] not in ("'", '"') and _is_constant_reference(t)]


def authorization_roles(annotation: str, expression: str, constants: dict[str, Any] | None = None,
                        evidence: list[str] | None = None) -> tuple[list[str], str]:
    """(the roles this policy ACCEPTS, why-unsupported).

    "" for the reason and a non-empty list is the only readable answer; an
    expression outside the grammar returns ([], reason) and the caller records
    a typed gap rather than deriving anything for it. ``evidence``, when a
    list is passed, receives one line per constant resolved -- which type,
    which stereotype made it a bean, the field, its value and which model
    carried it -- so a scenario derived from a constant can say where the role
    name came from."""
    consts = constants or {}
    args, literal_ok, why = _role_arguments(annotation, expression)
    if why:
        return [], why
    roles: list[str] = []
    lines: list[str] = []
    for tok in args:
        role, why, line = _role_token(tok, consts, literal_ok=literal_ok)
        if why:
            return [], why
        roles.append(role)
        if line:
            lines.append(line)
    if evidence is not None:
        for line in lines:
            if line not in evidence:
                evidence.append(line)
    return sorted(dict.fromkeys(roles)), ""


def role_matches(held: Any, accepted: Any) -> bool:
    """Whether an identity holding ``held`` satisfies a policy accepting
    ``accepted``. A platform that prefixes authorities (Spring's ``hasRole``
    prepends ``ROLE_``) makes ``ADMIN`` and ``ROLE_ADMIN`` the same role, and
    a seeded row may be stored either way; nothing else is folded."""
    def forms(role: Any) -> set[str]:
        r = str(role or "").strip()
        if not r:
            return set()
        return {r, r[len(ROLE_PREFIX):] if r.startswith(ROLE_PREFIX) else ROLE_PREFIX + r}
    return bool(forms(held) & forms(accepted))
