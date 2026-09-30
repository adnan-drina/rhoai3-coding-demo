"""The outcome board's pure domain checks, shared by both control models.

Moved unchanged out of outcome_lifecycle.py (2026-09-27) when native
cooperative control (outcome-board/v2, planner/native_control.py) replaced the
protected authority for new runs. Nothing here holds or writes a lifecycle
record: each function reads its arguments, the destination tree, git objects
or the measured work list and returns a fact. outcome_lifecycle (v1, the
protected-authority protocol kept for runs that selected it) and
native_control (v2) both decide from these same predicates:

  plan         initial_plan_from_root (revision 1 from admission evidence)
  work list    load_worklist, open_obligations
  scope        changed_product_paths (raw blob comparison, no worktree git),
               norm_rel, _is_product
  acceptance   requirement_measurement, _covers, repair_evidence_gaps
  recovery     git_commits_after, commit_product_tree
  delivery     stage_admission, DELIVERY_RECEIPTS
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from planner.outcome_graph import derive_initial_graph


WORKLIST = Path("evidence") / "planning" / "worklist.json"


EP_INVENTORY = Path("evidence") / "entry-point-inventory.json"


STRUCTURE = Path("evidence") / "structure" / "structure.json"


VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"


DELIVERY_OK_VERDICTS = ("ACCEPT", "PROVISIONAL_ACCEPT")


EXEMPT_DIRS = ("evidence/", "verification/", ".derived/", "target/")


class Refusal(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def corpus_binding_gaps(root: Path) -> list[str]:
    """Why this tree's scenario corpora cannot bind oracles to ITS entry points
    ([] when they can). Entry-point ids depend on how fully M1 resolved the
    source (v21: a classpath fix turned 14 of 34 simple-name signatures into
    qualified ones), so a corpus derived against another evidence bundle, or a
    scenario naming an entry point this inventory does not hold, is a stale
    binding: planning from it would report covered entry points as having no
    oracle. The capture tools refuse such a corpus the same way
    (capture-source-oracles/_scenarios.py); planning must not read around it."""
    from planner.canonical import digest
    from planner.paths import EVIDENCE_BUNDLE
    from planner.worklist import SCENARIO_CORPORA
    root = Path(root)
    corpora = [rel for rel in SCENARIO_CORPORA if (root / rel).is_file()]
    if not corpora:
        return []
    bundle = _read_json(root / EVIDENCE_BUNDLE)
    # the entry points of the bundle the corpus is bound to (M1's inventory,
    # as the bundle carries it -- the same reference capture qualification uses)
    have = {str(r.get("id")) for r in (bundle or {}).get("entry_points") or [] if isinstance(r, dict)}
    gaps: list[str] = []
    for rel in corpora:
        doc = _read_json(root / rel)
        if not isinstance(doc, dict):
            gaps.append("%s is unreadable" % rel)
            continue
        receipt = _read_json(root / rel.parent / "_derive.json")
        if isinstance(doc.get("derived_from"), dict):
            bound = str((receipt or {}).get("evidence_bundle_sha256") or "") if isinstance(receipt, dict) else ""
            if not isinstance(bundle, dict) or bound != digest(bundle):
                gaps.append("%s was derived against evidence bundle %s, not this tree's bundle: derive the corpus (and "
                            "capture it) again" % (rel, bound[:12] or "<none>"))
                continue
        stale = sorted({str(sc.get("entry_point")) for sc in doc.get("scenarios") or []
                        if isinstance(sc, dict) and sc.get("entry_point") and str(sc.get("entry_point")) not in have})
        if stale:
            gaps.append("%s binds %d entry point(s) this tree's evidence bundle does not hold (stale binding), e.g. %s"
                        % (rel, len(stale), stale[0]))
    return gaps


def objective_inputs(root: Path, worklist: dict[str, Any]) -> dict[str, Any] | None:
    """The inputs of policy compatibility-objectives/v1 for this root, or None
    when decisions.yaml does not select it. Read here so the composition stays
    pure: the catalog, every admitted unit's sealed inventory, the qualified
    symbol of each unsealed compile item (resolved through the declaring file's
    imports in the destination model -- unresolved stays absent, never guessed)
    and the frozen structural model. A selected policy whose catalog is missing
    refuses (OBJECTIVES_CATALOG) instead of planning without it."""
    from planner.decisions import compatibility_objectives, load_decisions
    from planner.paths import CATALOGS_DIR
    try:
        doc = load_decisions(root)
    except (OSError, ValueError):
        doc = {}
    if compatibility_objectives(doc) != "v1":
        return None
    root = Path(root)
    catalog = _read_json(root / CATALOGS_DIR / "compat-mapping.json")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("objective_families"), dict):
        from planner.outcome_graph import PlanError
        raise PlanError("OBJECTIVES_CATALOG", "decisions select compatibility-objectives/v1 and the catalog has no objective_families")
    seals: dict[str, Any] = {}
    unsealed: list[dict[str, Any]] = []
    items = {str(i.get("id")): i for i in (worklist or {}).get("items") or [] if isinstance(i, dict)}
    for c in (worklist or {}).get("clusters") or []:
        ref = c.get("batch_scope") or {}
        doc_ = _read_json(root / str(ref.get("path") or "")) if ref.get("path") else None
        if isinstance(doc_, dict):
            seals[str(c["id"])] = doc_
        else:
            unsealed.extend(items[m] for m in c.get("items") or [] if m in items and str(items[m].get("kind")) == "compile")
    item_symbols: dict[str, str] = {}
    if unsealed:
        try:
            from planner.dest_model import dest_model
            from planner.worklist import _annotation_simples, resolve_compile_symbol
            model = dest_model(root)
            ann = _annotation_simples(model)
            for it in unsealed:
                key, _kind = resolve_compile_symbol(model, it, ann)
                if key and "." in key:
                    item_symbols[str(it["id"])] = key
        except Exception:  # noqa: BLE001 -- no model: nothing resolves, nothing is guessed
            item_symbols = {}
    st = _read_json(root / STRUCTURE)
    return {"catalog": catalog, "seals": seals, "item_symbols": item_symbols,
            "structure_types": (st or {}).get("types") or [] if isinstance(st, dict) else []}


def _oracles(root: Path) -> dict[str, list[str]] | None:
    """entry point -> captured scenario ids, or None when no corpus exists OR
    the corpora are not bound to this tree (corpus_binding_gaps): unknown,
    never a partial map that silently drops coverage."""
    from planner.worklist import _iter_corpus_docs
    if corpus_binding_gaps(root):
        return None
    out: dict[str, list[str]] = {}
    seen = False
    for doc in _iter_corpus_docs(root):
        seen = True
        for sc in doc.get("scenarios") or []:
            if isinstance(sc, dict) and sc.get("id") and sc.get("entry_point"):
                out.setdefault(str(sc["entry_point"]), []).append(str(sc["id"]))
    return out if seen else None


def _references(root: Path) -> dict[str, list[str]]:
    doc = _read_json(Path(root) / STRUCTURE)
    if not isinstance(doc, dict):
        return {}
    path_of = {str(t.get("fqn")): str(t.get("path") or "") for t in doc.get("types") or [] if isinstance(t, dict)}
    out: dict[str, set[str]] = {}
    for t in doc.get("types") or []:
        if not isinstance(t, dict) or not t.get("path"):
            continue
        for ref in list(t.get("type_refs") or []) + list(t.get("supertypes") or []):
            q = path_of.get(str(ref))
            if q and q != t["path"]:
                out.setdefault(str(t["path"]), set()).add(q)
    return {k: sorted(v) for k, v in out.items()}


def initial_plan_from_root(root: Path) -> dict[str, Any]:
    """Revision 1 from the ADMITTED work list and the M1 inventories. Missing
    admission evidence refuses (PlanError ADMISSION_EVIDENCE_INCOMPLETE)."""
    from planner.admission import verify_receipt
    from planner.decisions import load_decisions, max_attempts
    from planner.outcome_graph import PlanError
    root = Path(root)
    receipt, gaps = verify_receipt(root, require_admitted=True)
    if gaps or receipt is None:
        raise PlanError("ADMISSION_NOT_ADMITTED", "; ".join(gaps or ["no admission receipt"]))
    worklist = _read_json(root / WORKLIST)
    inv = _read_json(root / EP_INVENTORY)
    if not isinstance(inv, dict) or not isinstance(inv.get("entry_points"), list):
        raise PlanError("ADMISSION_EVIDENCE_INCOMPLETE", "%s is missing or malformed" % EP_INVENTORY)
    decl = _read_json(root / "run-budget.json") or {}
    run_id = str(decl.get("run_id") or "") if isinstance(decl, dict) else ""
    if not run_id:
        mig = root / "migration.yaml"
        from planner.yamlite import load_yaml
        doc = load_yaml(mig) if mig.is_file() else {}
        run_id = str(((doc or {}).get("resources") or {}).get("run") or "")
    from planner.canonical import sha256_file
    # plan semantics v1 (decisions.loop.plan_semantics, sealed by the receipt
    # just verified): the source-derived requirements enter revision 1; absent
    # keeps the revision exactly as before
    from planner.decisions import plan_semantics
    oracles = _oracles(root)
    extra: dict[str, Any] = {}
    if plan_semantics(load_decisions(root)) == "v1":
        from planner import source_requirements
        extra["requirements"] = source_requirements.for_root(root, oracles=oracles)["requirements"]
    return derive_initial_graph(
        run_id=run_id or "local", worklist=worklist, entry_points=inv["entry_points"], oracles=oracles,
        references=_references(root), max_attempts=max_attempts(load_decisions(root)),
        provenance={"snapshot_kind": "admission", "scope_note": "admission-time work list and M1 inventories of this run",
                    "receipt_sha256": receipt.get("receipt_digest"), "worklist_sha256": sha256_file(root / WORKLIST),
                    "entry_point_inventory_sha256": sha256_file(root / EP_INVENTORY)},
        objectives=objective_inputs(root, worklist), **extra)


def load_worklist(root: Path) -> tuple[dict[str, Any] | None, str]:
    """(work list, '') or (None, why). Missing or corrupt is never empty."""
    p = Path(root) / WORKLIST
    if not p.is_file():
        return None, "WORKLIST_MISSING"
    doc = _read_json(p)
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list) or not isinstance(doc.get("clusters"), list):
        return None, "WORKLIST_CORRUPT"
    if not isinstance(doc.get("measure"), dict) or doc["measure"].get("known") is not True:
        return None, "WORKLIST_UNKNOWN"
    return doc, ""


def open_obligations(worklist: dict[str, Any]) -> set[str]:
    return {str(i["id"]) for i in worklist.get("items") or []
            if isinstance(i, dict) and i.get("category") == "mandatory" and i.get("id")}


def _git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=not binary)


def _tree_blobs(root: Path, commit: str) -> dict[str, tuple[str, str]] | None:
    """{rel: (mode, blob id)} of a committed tree's product paths (ls-tree: object
    data only; no working tree, no filter)."""
    from planner.paths import is_product_path
    ls = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit, binary=True)
    if ls.returncode != 0:
        return None
    out: dict[str, tuple[str, str]] = {}
    for rec in ls.stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode, kind, oid = meta.split()
        rel = name.decode("utf-8", "surrogateescape")
        if kind == b"blob" and is_product_path(rel):
            out[rel] = (mode.decode(), oid.decode())
    return out


def _blob_id(data: bytes, algo: str) -> str:
    import hashlib
    h = hashlib.new(algo)
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def changed_product_paths(root: Path, base: str, commit: str = "", only: list[str] | None = None) -> list[str] | None:
    """Product paths that differ between the baseline commit and ``commit``, or
    the working tree (untracked, not ignored, included) when ``commit`` is
    empty. The working tree is compared IN PYTHON against the baseline's raw
    blob ids: git never reads a worktree file here, so no repository-configured
    clean filter, fsmonitor or diff driver can run (in the authority's
    principal). None when git cannot answer: unknown is never 'nothing changed'."""
    from planner.paths import is_product_path
    if not base:
        return None
    if commit:
        p = _git(root, "diff-tree", "-r", "--no-renames", "--name-only", "-z", base, commit)
        if p.returncode != 0:
            return None
        return sorted({n for n in p.stdout.split("\0") if n and is_product_path(n)})
    fmt = _git(root, "rev-parse", "--show-object-format").stdout.strip() or "sha1"
    blobs = _tree_blobs(root, base)
    ign = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    if blobs is None or ign.returncode != 0 or fmt not in ("sha1", "sha256"):
        return None
    ignored = [n for n in ign.stdout.split("\0") if n]
    root = Path(root)
    changed: set[str] = set()
    seen: set[str] = set()
    names = list(only) if only is not None else None
    if names is None:
        names = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for fn in filenames:
                names.append(os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/"))
    for rel in names:
        if not is_product_path(rel) or any(rel == i.rstrip("/") or (i.endswith("/") and rel.startswith(i)) for i in ignored):
            continue
        p = root / rel
        if p.is_symlink():
            data, mode = os.readlink(p).encode("utf-8", "surrogateescape"), "120000"
        elif p.is_file():
            data, mode = p.read_bytes(), "100755" if os.access(p, os.X_OK) else "100644"
        else:
            continue
        seen.add(rel)
        want = blobs.get(rel)
        if want is None or want[1] != _blob_id(data, fmt) or (want[0] == "120000") != (mode == "120000"):
            changed.add(rel)
    for rel in blobs:
        if (only is None or rel in only) and rel not in seen:
            changed.add(rel)          # deleted since the baseline
    return sorted(changed)


def planned_cluster_id(oid: str) -> str:
    return "planned:%s:1" % oid


def _unit_kind(node: dict[str, Any]) -> str:
    """The loop card kind a synthetic unit is projected as (issued.json)."""
    return {"build": "build", "config": "config", "source": "compile", "runtime": "incident",
            "behavior": "parity"}.get(str(node.get("class") or ""), "compile")


AMEND_LIMIT = 4


AMEND_MAX_FILES = 20


def norm_rel(rel: str) -> str:
    """Destination-relative POSIX path: backslashes folded, leading './'
    segments removed (never a leading '.' of a name such as .hermes)."""
    r = str(rel or "").replace("\\", "/")
    while r.startswith("./"):
        r = r[2:]
    return r.lstrip("/")


def _is_product(rel: str) -> bool:
    from planner.paths import is_product_path
    return is_product_path(rel)


OWNER_DEFECT = "pre-existing-owner-defect"


CAUSE_CLASSES = (OWNER_DEFECT, "candidate-regression", "ambiguous")


HOLD_MAX_BYTES = 2 << 20


def repair_evidence_gaps(root: Path, node: dict[str, Any], tree: str) -> list[str]:
    """An owner repair is accepted only when every scenario the classifier saw
    fail now PASSES, in a live scenario record bound to this very tree
    (worker-produced receipts: the declared measurement trust)."""
    sids = list(node.get("repair_scenarios") or [])
    if not sids:
        return []
    from planner import runtime_cause as RC
    from planner.paths import PARITY_DIR
    recs = RC.scenario_records(Path(root) / PARITY_DIR)
    out = []
    for sid in sids:
        r = recs.get(sid) or {}
        bound = str(((r.get("binding") or {}) if isinstance(r.get("binding"), dict) else {}).get("candidate_sha256") or "")
        if r.get("verdict") != "PASS" or bound != tree:
            out.append("%s is %s on %s" % (sid, r.get("verdict") or "unmeasured", (bound or "no tree")[:12]))
    return out


def git_commits_after(root: Path) -> Callable[[str], list[tuple[str, str, str]]]:
    """commits(baseline) -> [(sha, first parent, product tree digest)] for every
    commit between the baseline and HEAD. The digest is the product-tree identity
    of the committed tree (the same algorithm as the working tree's)."""
    def commits(baseline: str) -> list[tuple[str, str, str]]:
        if not baseline:
            return []
        p = subprocess.run(["git", "-C", str(root), "rev-list", "--parents", "%s..HEAD" % baseline],
                           capture_output=True, text=True)
        if p.returncode != 0:
            return []
        out = []
        for line in p.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] != baseline:
                continue
            digest = commit_product_tree(root, parts[0])
            if digest:
                out.append((parts[0], parts[1], digest))
        return out
    return commits


def commit_product_tree(root: Path, commit: str) -> str:
    """The product-tree digest (canonical.product_tree_sha256's algorithm) of a
    COMMITTED tree, from raw blobs: ls-tree and cat-file only, so no checkout,
    archive conversion or repository-configured filter runs. '' when git
    cannot answer."""
    import hashlib
    tree = _tree_blobs(root, commit)
    if tree is None:
        return ""
    entries = [(rel, oid) for rel, (_mode, oid) in tree.items()]
    h = hashlib.sha256()
    if entries:
        batch = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"], input=b"".join(e[1].encode() + b"\n" for e in sorted(entries)),
                               capture_output=True)
        if batch.returncode != 0:
            return ""
        data, pos = batch.stdout, 0
        blobs = {}
        for rel, oid in sorted(entries):
            eol = data.index(b"\n", pos)
            size = int(data[pos:eol].split()[2])
            blobs[rel] = data[eol + 1:eol + 1 + size]
            pos = eol + 1 + size + 1
        # the working-tree digest walks sorted Paths: component-wise order, not string order
        for rel in sorted(blobs, key=lambda r: tuple(r.split("/"))):
            h.update(rel.encode("utf-8", "surrogateescape"))
            h.update(b"\0")
            h.update(blobs[rel])
            h.update(b"\0")
    return h.hexdigest()


def requirement_measurement(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any],
                            scenarios: list[str], tree: str = "") -> dict[str, dict[str, str]] | None:
    """The requirement checks of `node` measured on the tree `worklist`
    describes (plan semantics v1); None for an outcome that owns none. The
    mode receipts and the compiler document are this root's own records;
    requirement_checks trusts a receipt only when it is bound to `tree`."""
    if not ((node.get("acceptance") or {}).get("requirement_checks")):
        return None
    from planner.paths import VERIFY_DIAGNOSTICS
    from planner.requirement_checks import measure
    from planner.worklist import parity_receipt_file
    owned = set(node.get("requirements") or [])
    reqs = [r for r in plan.get("requirements") or [] if isinstance(r, dict) and r.get("id") in owned]
    receipts = {m: _read_json(Path(root) / parity_receipt_file(m)) for m in ("disabled", "enabled")}
    diags = _read_json(Path(root) / VERIFY_DIAGNOSTICS)
    return measure(root, reqs, worklist=worklist, scenarios=scenarios, tree=tree,
                   receipts={m: r for m, r in receipts.items() if isinstance(r, dict)},
                   diagnostics=diags if isinstance(diags, dict) else None)


def requirement_matrix(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any],
                       scenarios: list[str], tree: str = "") -> dict[str, dict[str, dict[str, str]]]:
    """compatibility-objectives/v1: every IMMEDIATE (requirement, check) of the
    node's check plan measured for THAT requirement alone -- two requirements
    using gate:compile keep their own results, and one passing cannot stand
    for another's unknown. {requirement: {check: {status, detail}}}."""
    from planner.paths import VERIFY_DIAGNOSTICS
    from planner.requirement_checks import measure
    from planner.worklist import parity_receipt_file
    rows = {str(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
    want: dict[str, set[str]] = {}
    for row in node.get("check_plan") or []:
        if row.get("stage") == "immediate":
            want.setdefault(str(row["requirement"]), set()).add(str(row["check"]))
    receipts = {m: _read_json(Path(root) / parity_receipt_file(m)) for m in ("disabled", "enabled")}
    receipts = {m: r for m, r in receipts.items() if isinstance(r, dict)}
    diags = _read_json(Path(root) / VERIFY_DIAGNOSTICS)
    out: dict[str, dict[str, dict[str, str]]] = {}
    for rq, checks in sorted(want.items()):
        r = rows.get(rq)
        if r is None:
            out[rq] = {c: {"status": "unknown", "detail": "the requirement is not in the plan"} for c in sorted(checks)}
            continue
        one = dict(r, acceptance=[c for c in r.get("acceptance") or [] if c in checks])
        got = measure(root, [one], worklist=worklist, scenarios=scenarios, tree=tree, receipts=receipts,
                      diagnostics=diags if isinstance(diags, dict) else None)
        out[rq] = {c: dict(got.get(c) or {"status": "unknown", "detail": "not measured"}) for c in sorted(checks)}
    return out


def _covers(node: dict[str, Any], m: dict[str, Any]) -> bool:
    cls = node.get("class")
    have = set(m.get("classes") or [])
    from planner.measurement import needed_classes
    # plan semantics v1: an outcome owning source requirements is covered only
    # by a measurement that records each of their named checks; an empty live
    # work list or a vanished diagnostic never discharges them
    req = set(((node.get("acceptance") or {}).get("requirement_checks")) or [])
    if req and not req <= set(m.get("checks") or []):
        return False
    if cls not in ("build", "config", "source", "runtime", "behavior"):
        return False
    # the node's declared measure:/gate:/parity: checks, as published: a
    # measure:tests moved to M4 at publication is M4's to discharge
    # (native_control.defer_runtime_checks), never assumed here
    if not needed_classes(node) <= have:
        return False
    if cls == "behavior":
        return set(node.get("scenarios") or []) <= set(m.get("scenarios") or [])
    return True


def owner_repair_id(owner: str, dependent: str) -> str:
    return "repair:%s:for:%s" % (owner, dependent)


def stage_admission(stage: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Admit one M5 stage from facts known at that point, and only those.

    A later stage's own output is never required before it can start. A
    deferred release qualification may remain recorded; a delivery-blocking one
    refuses. deploy_for_validation is never ship."""
    reasons: list[str] = []
    a = facts.get("assessment") or {}
    wl = facts.get("worklist") or {}
    cand = facts.get("candidate") or ""
    if stage == "prepare":
        if not a.get("bound"):
            reasons.append("ASSESSMENT_UNBOUND")
        if str(a.get("verdict") or "").upper() not in DELIVERY_OK_VERDICTS:
            reasons.append("ASSESSMENT_%s" % (str(a.get("verdict") or "MISSING").upper()))
        if a.get("candidate") != cand:
            reasons.append("CANDIDATE_STALE")
        if wl.get("state") != "present":
            reasons.append("WORKLIST_%s" % str(wl.get("state") or "MISSING").upper())
        elif int(wl.get("open_mandatory") or 0):
            reasons.append("OPEN_MANDATORY_OBLIGATIONS")
        if facts.get("open_repairs"):
            reasons.append("OPEN_MANDATORY_REPAIR")
        if facts.get("unresolved_ownership"):
            reasons.append("UNRESOLVED_OWNERSHIP")
    elif stage == "push":
        pf = facts.get("preflight") or {}
        if not pf.get("accepted") or pf.get("candidate") != cand:
            reasons.append("PREFLIGHT_NOT_ACCEPTED_FOR_CANDIDATE")
        if not facts.get("plan_coherent", False):
            reasons.append("PLAN_INCOHERENT")
        if not facts.get("build_authorized", False):
            reasons.append("BUILD_NOT_AUTHORIZED")
    elif stage == "accept":
        dep = facts.get("deploy") or {}
        if not dep.get("result") or dep.get("candidate") != cand or not dep.get("image_digest"):
            reasons.append("DEPLOYMENT_UNBOUND")
        if not facts.get("live_inputs", False):
            reasons.append("LIVE_INPUTS_MISSING")
    else:
        reasons.append("STAGE_UNKNOWN")
    for q in facts.get("qualifications") or []:
        if q.get("class") == "blocking" and not q.get("satisfied") and q.get("before", "prepare") == stage:
            reasons.append("QUALIFICATION_%s" % str(q.get("id")).upper())
    deferred = [q["id"] for q in facts.get("qualifications") or [] if q.get("class") == "deferred" and not q.get("satisfied")]
    ship = stage == "accept" and not reasons and bool(facts.get("shipping_evidence_complete"))
    return {"stage": stage, "admit": not reasons, "reasons": reasons, "deferred_qualifications": deferred,
            "permissions": {"deploy_for_validation": stage == "push" and not reasons, "ship": ship}}


DELIVERY_RECEIPTS = {
    "prepare": (Path("verification/delivery/candidate.json"), Path("verification/delivery/eligibility.json")),
    "push": (Path("verification/delivery/pipeline.json"), Path("verification/delivery/deployment.json")),
    "accept": (Path("verification/delivery/live.json"), Path("evidence/verdicts/m5-verdict.json")),
}


def _git_head(root: Path) -> str:
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


# ---------------------------------------------------------------------------
# plan revisions after a finding (shared by v1's reconciler and v2's M4 task)
# ---------------------------------------------------------------------------

MAX_ASSESSMENT_GENERATIONS = 4


def refuse_revision(plan: dict[str, Any], obligations: list[dict[str, Any]], *, gen: int, trigger: str, verdict: str,
                    status_of: Callable[[str], str], budget_of: Callable[[str], dict[str, Any]],
                    successor: bool) -> dict[str, Any] | Refusal:
    """The revision after a measured REFUSE: every open obligation the
    assessment recorded goes to its frozen owner (still open), a follow-up of
    that owner sharing its budget (owner already accepted), or a new bounded
    outcome; ambiguous or evidence-less findings become unresolved rows. Never
    reopens an accepted outcome, never renews a budget.

    ``gen``        the assessment generation that measured the REFUSE (1-based)
    ``status_of``  outcome id -> its lifecycle status ('accepted'/'done' = accepted)
    ``budget_of``  outcome id -> {'key', 'limit'} of its budget family
    ``successor``  v1: a successor assessment node g+1 and the delivery stages
                   rebound to it. v2 (native): no successor -- the SAME M4
                   task (``trigger``) gains the new repairs as prerequisites
                   and runs again once they are done.
    """
    if gen >= MAX_ASSESSMENT_GENERATIONS:
        return Refusal("ASSESSMENT_BOUND", "generation %d reached the bound %d; escalate" % (gen, MAX_ASSESSMENT_GENERATIONS))
    from planner.outcome_graph import (ASSESS_PREFIX, ASSESS_SKILL, DELIVER_STAGES, IMPL, REPAIR_SKILL, REPAIR_SKILLS, declaring_type,
                                       owner_of_finding, plan_digest, render_description)
    run_id = plan["run_id"]
    nodes = [dict(n) for n in plan["nodes"]]
    by_id = {n["outcome_id"]: n for n in nodes}
    ownership = dict(plan.get("ownership") or {})
    unresolved = list(plan.get("unresolved") or [])
    touched: dict[str, dict[str, Any]] = {}
    additions: list[str] = []
    for ob in obligations:
        if ob.get("status") == "blocked" or not ob.get("write_set"):
            uid = "unresolved:decision:%s" % ob["id"]
            if not any(u["id"] == uid for u in unresolved):
                unresolved.append({"id": uid, "kind": "decision", "blocks": "delivery", "reason": "no card can discharge %s" % ob["id"], "obligations": [ob["id"]]})
            continue
        owner = ownership.get(ob["id"])
        if owner is None:
            # plan semantics v1: the frozen owner of a later finding, or a typed revision class
            found = owner_of_finding(plan, {"id": ob["id"], "path": ob.get("path") or "", "entry_point": ob.get("entry_point") or "",
                                            "kind": ob.get("kind") or "", "cluster": ob.get("cluster") or ""})
            if found.get("owner"):
                owner = str(found["owner"])
            elif found.get("class") in ("ambiguous-ownership", "evidence-gap") and (plan.get("requirements") or []):
                uid = "unresolved:%s:%s" % (found["class"], ob["id"])
                if not any(u["id"] == uid for u in unresolved):
                    unresolved.append({"id": uid, "kind": found["class"], "blocks": "delivery", "obligations": [ob["id"]],
                                       "reason": "a later finding has no single planned owner (%s)" % found["class"],
                                       "candidates": list(found.get("candidates") or [])})
                continue
        if owner is None:
            typ, kind = declaring_type(ob.get("entry_point") or "")
            natural = "%s:%s" % (kind, typ) if typ else str(ob.get("key") or "")
            owner = next((n["outcome_id"] for n in nodes if n.get("role") == "repair" and n.get("natural_key") == natural), None)
        known = bool(owner) and owner in by_id
        if known and status_of(owner) not in ("accepted", "done"):
            target = owner
        elif known:
            target = "followup:%s:g%d" % (owner, gen + 1)
            if target not in by_id:
                parent = by_id[owner]
                by_id[target] = {"outcome_id": target, "role": "repair", "class": parent.get("class"), "subject": parent.get("subject"),
                                 "natural_key": "", "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [],
                                 "scenarios": [], "parents": [], "assignee": IMPL, "skills": list(REPAIR_SKILLS),
                                 "lineage": [{"follows": owner, "reason": "assessment %s found new work after acceptance" % trigger}],
                                 "budget": dict(budget_of(owner))}
                additions.append(target)
        else:
            typ, kind = declaring_type(ob.get("entry_point") or "")
            cls = "behavior" if typ else ("runtime" if ob.get("gate") in ("package", "startup", "boot") else "source")
            target = ("behavior:%s:%s" % (kind, typ)) if typ else "%s:%s" % (cls, ob.get("key") or ob["id"])
            if target in by_id and status_of(target) in ("accepted", "done"):
                target = "followup:%s:g%d" % (target, gen + 1)
            if target not in by_id:
                by_id[target] = {"outcome_id": target, "role": "repair", "class": cls, "subject": typ or str(ob.get("path") or ob["id"]),
                                 "natural_key": "%s:%s" % (kind, typ) if typ else str(ob.get("key") or ""),
                                 "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [], "scenarios": [],
                                 "parents": [], "assignee": IMPL, "skills": list(REPAIR_SKILLS),
                                 "lineage": [{"discovered_by": trigger}],
                                 "budget": {"key": "rk:outcome:%s:%s" % (run_id, target), "limit": 3}}
                additions.append(target)
        n = by_id[target]
        n["obligations"] = sorted(set(n["obligations"]) | {ob["id"]})
        if ob.get("cluster"):
            n["clusters"] = sorted(set(n["clusters"]) | {ob["cluster"]})
        n["plan_paths"] = sorted(set(n["plan_paths"]) | set(ob.get("write_set") or []))
        if ob.get("entry_point"):
            n["entry_points"] = sorted(set(n["entry_points"]) | {ob["entry_point"]})
        if ob.get("scenario"):
            n["scenarios"] = sorted(set(n["scenarios"]) | {ob["scenario"]})
        ownership[ob["id"]] = target
        touched[target] = n
    if not touched:
        return Refusal("REFUSE_NOTHING_REPAIRABLE", "the REFUSE names no obligation a card can discharge; %d unresolved decision(s); "
                       "unresolved: %s" % (sum(1 for u in unresolved if u["kind"] == "decision"),
                                           ", ".join(u["id"] for u in unresolved if u["kind"] != "decision")[:400] or "none"))
    open_repairs = sorted(oid for oid, n in by_id.items() if n.get("role") == "repair"
                          and (status_of(oid) not in ("accepted", "done") or oid in additions))
    for oid in additions:
        # a published card's description is never rewritten (the pinned CLI has
        # no body edit); only new outcomes get their text here
        n = by_id[oid]
        n["title"] = "Follow-up: %s" % n["subject"] if oid.startswith("followup:") else {
            "behavior": "Behavior: %s", "runtime": "Application %s", "source": "Source compatibility: %s"}.get(
            n.get("class"), "Outcome: %s") % n["subject"]
        n["description"] = render_description(n)
        n["acceptance"] = {"checks": {"behavior": ["worklist-absent", "parity:scenarios"],
                                      "runtime": ["worklist-absent", "gate:runtime"]}.get(
            n.get("class"), ["worklist-absent", "measure:compile", "measure:tests"])}
    if successor:
        succ = "%s:g%d" % (ASSESS_PREFIX, gen + 1)
        by_id[succ] = {"outcome_id": succ, "role": "assess", "class": "assess", "generation": gen + 1, "subject": "M4 ASSESS",
                       "title": "M4 ASSESS (reassessment %d)" % (gen + 1), "parents": sorted(set(open_repairs) | {trigger}),
                       "assignee": IMPL, "skills": [ASSESS_SKILL], "obligations": [], "clusters": [], "plan_paths": [],
                       "lineage": [{"succeeds": trigger, "verdict": verdict}]}
        by_id[succ]["description"] = render_description(by_id[succ])
        for stage in DELIVER_STAGES:
            did = "deliver:%s:c1" % stage
            if did in by_id:
                d = dict(by_id[did])
                d["binding"] = {"assessment": succ}
                if stage == DELIVER_STAGES[0]:
                    d["parents"] = sorted(set(d.get("parents") or []) | {succ})
                by_id[did] = d
    else:
        # native: the same assessment waits on the new repairs (repair -> M4, never the reverse)
        m4 = dict(by_id[trigger])
        m4["parents"] = sorted(set(m4.get("parents") or []) | set(additions))
        m4["lineage"] = list(m4.get("lineage") or []) + [{"refused": gen, "verdict": verdict, "repairs": sorted(additions)}]
        by_id[trigger] = m4
    new_nodes = [by_id[k] for k in sorted(by_id)]
    counts = dict(plan.get("counts") or {})
    counts["additions"] = int(counts.get("additions") or 0) + len(additions)
    doc = {
        "schema": plan["schema"], "run_id": run_id, "revision": int(plan["revision"]) + 1,
        "parent_revision": int(plan["revision"]), "kind": "refuse-repair", "provenance": plan.get("provenance"),
        "trigger": {"intent": "m4-assessed:%s" % trigger, "verdict": verdict},
        "nodes": new_nodes, "ownership": ownership, "dispositions": list(plan.get("dispositions") or []),
        "unresolved": sorted(unresolved, key=lambda u: u["id"]), "counts": counts,
        "additions": sorted(additions), "claimed_control": False,
    }
    if not successor:
        for k in ("requirements", "requirement_ownership"):
            if k in plan:
                doc[k] = plan[k]
    doc["digest"] = plan_digest(doc)
    return doc


def orphaned_obligations(plan: dict[str, Any], worklist: dict[str, Any], status_of: Callable[[str], str],
                         holder: str = "") -> list[dict[str, Any]]:
    """Open mandatory obligations of the measured work list that no OPEN outcome
    will discharge: owned by no plan node (they appeared after M2 froze
    ownership -- v28: the package gate first ran once compilation reached zero
    errors and failed at RootRestController.java), or owned by an outcome that
    is already accepted (reopened after acceptance). Each with its work-list
    cluster and write set. Pure.

    A finding at an entry point or scenario an OPEN outcome other than
    ``holder`` claims is that outcome's, not an orphan: it takes it when it runs
    (v29 t_65445e69 was refused over the Vet, Specialty and Pet controllers'
    own parity failures, each claimed by that controller's open behavior card)."""
    owner_of: dict[str, str] = {str(k): str(v) for k, v in (plan.get("ownership") or {}).items()}
    claims: dict[str, set[str]] = {}

    def _bare(v: str) -> str:
        return v[3:] if v.startswith(("ep:", "sc:")) else v

    for n in plan.get("nodes") or []:
        oid = str(n.get("outcome_id") or "")
        for ob in n.get("obligations") or []:
            owner_of.setdefault(str(ob), oid)
        if n.get("role") == "repair" and status_of(oid) not in ("accepted", "done"):
            for k in list(n.get("entry_points") or []) + list(n.get("scenarios") or []):
                claims.setdefault(_bare(str(k)), set()).add(oid)
    cluster_of: dict[str, dict[str, Any]] = {}
    for c in worklist.get("clusters") or []:
        if isinstance(c, dict):
            for i in c.get("items") or []:
                cluster_of.setdefault(str(i), c)
    out = []
    for i in worklist.get("items") or []:
        if not isinstance(i, dict) or i.get("category") != "mandatory" or not i.get("id"):
            continue
        iid = str(i["id"])
        owner = owner_of.get(iid, "")
        if owner and status_of(owner) not in ("accepted", "done"):
            continue
        claimed = claims.get(_bare(str(i.get("entry_point") or "")), set()) | claims.get(_bare(str(i.get("scenario") or "")), set())
        if claimed and holder not in claimed:
            continue
        c = cluster_of.get(iid) or {}
        out.append({"id": iid, "path": str(i.get("path") or ""), "kind": str(i.get("kind") or ""),
                    "entry_point": str(i.get("entry_point") or ""), "scenario": str(i.get("scenario") or ""),
                    "cluster": str(c.get("id") or ""),
                    "write_set": [str(w) for w in c.get("write_set") or []],
                    "status": "blocked" if c.get("status") == "blocked" else "open",
                    "reopened_from": owner, "detail": str(i.get("message") or i.get("detail") or "")[:300]})
    return out


def orphan_revision(plan: dict[str, Any], orphans: list[dict[str, Any]], *, holder: str,
                    status_of: Callable[[str], str], budget_of: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """M3 routing of orphaned obligations (orphaned_obligations) found by a card
    that measures the running application, by the rules refuse_revision applies
    at M4: the frozen owner (owner_of_finding: the obligation, its work-list
    cluster, a planned requirement's scope), then a follow-up of that owner
    sharing its budget when the owner is accepted. Never reopens an accepted
    outcome, never renews a budget, never widens another card's scope.

    Returns {"plan": the next revision or None, "added": new follow-ups,
    "self": obligations now owned by the holder, "unresolved": [(obligation,
    reason)]}. The new follow-ups become parents of every open behavior or
    runtime outcome (the holder included) and of every open assessment: none of
    them can measure while the application does not build or start."""
    from planner.outcome_graph import REPAIR_SKILLS, owner_of_finding, plan_digest, render_description
    by_id = {n["outcome_id"]: dict(n) for n in plan["nodes"]}
    ownership = dict(plan.get("ownership") or {})
    added: list[str] = []
    mine: list[str] = []
    unresolved: list[tuple[str, str]] = []
    hnode = by_id.get(holder) or {}

    def _bare(v: str, prefix: str) -> str:
        return v[len(prefix):] if v.startswith(prefix) else v

    own_eps = {_bare(str(e), "ep:") for e in hnode.get("entry_points") or []}
    own_scs = {_bare(str(s), "sc:") for s in hnode.get("scenarios") or []}
    for ob in orphans:
        # a finding at one of the holder's OWN entry points or scenarios is the holder's: it is the card that
        # measures that behavior and can repair it (amend-scope reaches the producing file). v29 t_65445e69: its
        # own endpoints' parity failures were ambiguous between it and an accepted controller objective, and the
        # card was refused instead of issued
        if (ob.get("entry_point") and _bare(str(ob["entry_point"]), "ep:") in own_eps) \
                or (ob.get("scenario") and _bare(str(ob["scenario"]), "sc:") in own_scs):
            ownership[ob["id"]] = holder
            mine.append(ob["id"])
            continue
        if ob.get("status") == "blocked" or not ob.get("write_set"):
            unresolved.append((ob["id"], "its work-list cluster has no write set a card could be granted"))
            continue
        found = {} if ob.get("reopened_from") else owner_of_finding(plan, ob)
        owner = str(ob.get("reopened_from") or found.get("owner") or "")
        if not owner or owner not in by_id:
            unresolved.append((ob["id"], "no single planned owner (%s%s)" % (
                found.get("class") or "unowned", (": " + ", ".join(found.get("candidates") or [])) if found.get("candidates") else "")))
            continue
        if owner == holder:
            ownership[ob["id"]] = holder
            mine.append(ob["id"])
            continue
        if status_of(owner) not in ("accepted", "done"):
            unresolved.append((ob["id"], "its owner %s is still open and does not own it" % owner))
            continue
        g = 1
        while "followup:%s:m3g%d" % (owner, g) in by_id and status_of("followup:%s:m3g%d" % (owner, g)) in ("accepted", "done"):
            g += 1
        target = "followup:%s:m3g%d" % (owner, g)
        if target not in by_id:
            parent = by_id[owner]
            by_id[target] = {"outcome_id": target, "role": "repair", "class": parent.get("class"), "subject": parent.get("subject"),
                             "natural_key": "", "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [],
                             "scenarios": [], "parents": [], "assignee": parent.get("assignee"), "skills": list(REPAIR_SKILLS),
                             "lineage": [{"follows": owner, "found_by": holder,
                                          "reason": "M3 found an obligation no open outcome discharges after %s was accepted" % owner}],
                             "budget": dict(budget_of(owner))}
            added.append(target)
        n = by_id[target]
        n["obligations"] = sorted(set(n.get("obligations") or []) | {ob["id"]})
        if ob.get("cluster"):
            n["clusters"] = sorted(set(n.get("clusters") or []) | {ob["cluster"]})
        n["plan_paths"] = sorted(set(n.get("plan_paths") or []) | set(ob.get("write_set") or []))
        ownership[ob["id"]] = target
    if not added and not mine:
        return {"plan": None, "added": [], "self": [], "unresolved": unresolved}
    for oid in added:
        n = by_id[oid]
        n["title"] = "Follow-up: %s" % n["subject"]
        n["description"] = render_description(n)
        n["acceptance"] = {"checks": {"behavior": ["worklist-absent", "parity:scenarios"],
                                      "runtime": ["worklist-absent", "gate:runtime"]}.get(
            n.get("class"), ["worklist-absent", "measure:compile", "measure:tests"])}
    if added:
        for oid, n in list(by_id.items()):
            waits = (n.get("role") == "repair" and str(n.get("class") or "") in ("behavior", "runtime")
                     and status_of(oid) not in ("accepted", "done")) or oid == holder \
                or (n.get("role") == "assess" and status_of(oid) not in ("accepted", "done"))
            if waits and oid not in added:
                by_id[oid] = dict(n, parents=sorted(set(n.get("parents") or []) | set(added)))
    counts = dict(plan.get("counts") or {})
    counts["additions"] = int(counts.get("additions") or 0) + len(added)
    doc = {"schema": plan["schema"], "run_id": plan["run_id"], "revision": int(plan["revision"]) + 1,
           "parent_revision": int(plan["revision"]), "kind": "m3-orphan-route", "provenance": plan.get("provenance"),
           "trigger": {"intent": "m3-orphans:%s" % holder}, "nodes": [by_id[k] for k in sorted(by_id)],
           "ownership": ownership, "dispositions": list(plan.get("dispositions") or []),
           "unresolved": list(plan.get("unresolved") or []), "counts": counts,
           "additions": sorted(set(plan.get("additions") or []) | set(added)), "claimed_control": False}
    for k in ("requirements", "requirement_ownership", "execution"):
        if k in plan:
            doc[k] = plan[k]
    doc["digest"] = plan_digest(doc)
    return {"plan": doc, "added": added, "self": mine, "unresolved": unresolved}


def owner_repair_revision(plan: dict[str, Any], doc: dict[str, Any], *, open_assessments: set[str]) -> dict[str, Any] | Refusal | None:
    """The revision adding ONE bounded repair of an accepted owner (automatic
    owner recovery): a new outcome with lineage to the owner, the owner's budget
    key (no fresh budget) and the owner's recorded write set; it becomes a
    PARENT of the dependent (and of every open assessment), so the dependent
    waits on the repair, never the reverse. None when the revision already
    carries it (replay)."""
    from planner.outcome_graph import IMPL, REPAIR_SKILL, REPAIR_SKILLS, plan_digest
    owner, dep = doc["owner"], doc["dependent"]
    fid = owner_repair_id(owner, dep)
    by_id = {n["outcome_id"]: dict(n) for n in plan["nodes"]}
    if fid in by_id:
        return None
    on, dn = by_id.get(owner), by_id.get(dep)
    if not on or not dn:
        return Refusal("OWNER_REPAIR_FOREIGN", "%s or %s is not in the current revision" % (owner, dep))
    node = {"outcome_id": fid, "role": "repair", "class": on.get("class"), "subject": on.get("subject"), "natural_key": "",
            "obligations": [], "clusters": [], "plan_paths": sorted(doc.get("repair_paths") or []),
            "repair_paths": sorted(doc.get("repair_paths") or []), "repair_scenarios": list(doc.get("repair_scenarios") or []),
            "entry_points": [], "scenarios": [], "parents": [],
            "assignee": IMPL, "skills": list(REPAIR_SKILLS), "budget": dict(doc["budget"]),
            "lineage": [{"repairs": owner, "for": dep, "cause": OWNER_DEFECT, "reason": doc.get("reason") or "",
                         "evidence": doc.get("evidence")}],
            "acceptance": {"checks": ["measure:compile", "measure:tests"] + ["scenario:%s" % x for x in doc.get("repair_scenarios") or []]}}
    node["title"] = "Repair %s (found by %s)" % (on.get("subject") or owner, dn.get("subject") or dep)
    node["description"] = ("Repair the runtime defect in %s that the work on %s exposed: the failure is proven on the "
                           "accepted baseline and belongs to %s. Complete when the owner's checks pass again on the "
                           "repaired candidate; %s then resumes and is re-verified on this repair. The attached brief "
                           "lists the evidence." % (on.get("subject") or owner, dn.get("subject") or dep, owner, dep))
    by_id[fid] = node
    by_id[dep] = dict(dn, parents=sorted(set(dn.get("parents") or []) | {fid}))
    for oid, n in list(by_id.items()):
        if n.get("role") == "assess" and oid in open_assessments:
            by_id[oid] = dict(n, parents=sorted(set(n.get("parents") or []) | {fid}))
    counts = dict(plan.get("counts") or {})
    counts["additions"] = int(counts.get("additions") or 0) + 1
    new = {
        "schema": plan["schema"], "run_id": plan["run_id"], "revision": int(plan["revision"]) + 1,
        "parent_revision": int(plan["revision"]), "kind": "owner-repair", "provenance": plan.get("provenance"),
        "trigger": {"intent": "owner-repair:%s:%s" % (owner, dep)},
        "nodes": [by_id[k] for k in sorted(by_id)], "ownership": dict(plan.get("ownership") or {}),
        "dispositions": list(plan.get("dispositions") or []), "unresolved": list(plan.get("unresolved") or []),
        "counts": counts, "additions": sorted(set(plan.get("additions") or []) | {fid}), "claimed_control": False,
    }
    for k in ("requirements", "requirement_ownership"):
        if k in plan:
            new[k] = plan[k]
    new["digest"] = plan_digest(new)
    return new


def stage_evidence_facts(root: Path, stage: str, *, m4_task: str,
                         push_landed: Callable[[str], bool]) -> tuple[bool, dict[str, Any], list[str]]:
    """The deciding facts of one M5 stage, DERIVED from the stage producers' own
    receipts (prepare-release-candidate, observe-app-push/assert-deployed-app,
    live-acceptance/compose-m5-verdict) and the push record, all bound to the
    current Git candidate. (ok, facts, reasons). Missing, failed or
    contradictory evidence is never success. ``m4_task`` is the native task of
    the assessment the stages are bound to; ``push_landed(head)`` answers
    whether a push of exactly ``head`` is recorded as landed."""
    root = Path(root)
    head = _git_head(root)
    reasons: list[str] = []
    docs: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    import hashlib
    for rel in DELIVERY_RECEIPTS.get(stage, ()):
        doc = _read_json(root / rel)
        if not isinstance(doc, dict):
            reasons.append("STAGE_EVIDENCE_MISSING:%s" % rel)
            continue
        docs[rel.name] = doc
        digests[str(rel)] = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if stage not in DELIVERY_RECEIPTS:
        reasons.append("STAGE_UNKNOWN:%s" % stage)
    if reasons:
        return False, {"stage": stage, "candidate_sha": head}, reasons

    def bound(label: str, doc: dict[str, Any]) -> None:
        if str(doc.get("candidate_sha") or "") != head or not head:
            reasons.append("CANDIDATE_MISMATCH:%s names %s, HEAD is %s" % (label, str(doc.get("candidate_sha") or "none")[:12], head[:12]))

    facts: dict[str, Any] = {"stage": stage, "candidate_sha": head, "receipts": digests}
    if stage == "prepare":
        cand, elig = docs["candidate.json"], docs["eligibility.json"]
        bound("candidate.json", cand)
        bound("eligibility.json", elig)
        if cand.get("ok") is not True or cand.get("pipeline_eligible") is not True:
            reasons.append("PREFLIGHT_FAILED:%s" % (cand.get("reason") or "candidate not pipeline-eligible"))
        if elig.get("pipeline_eligible") is not True:
            reasons.append("PREFLIGHT_FAILED:eligibility not pipeline-eligible")
        if not m4_task or str(cand.get("m4_card") or "") != m4_task:
            reasons.append("ASSESSMENT_MISMATCH:candidate binds M4 %r, the stage binds %r" % (cand.get("m4_card"), m4_task))
        facts.update(pipeline_eligible=cand.get("pipeline_eligible") is True, release_eligible=bool(cand.get("release_eligible")),
                     m4_card=str(cand.get("m4_card") or ""), outstanding=len(cand.get("outstanding") or []))
    elif stage == "push":
        pipe, dep = docs["pipeline.json"], docs["deployment.json"]
        bound("pipeline.json", pipe)
        bound("deployment.json", dep)
        if pipe.get("ok") is not True or pipe.get("succeeded") is not True or not pipe.get("image_digest"):
            reasons.append("DEPLOY_FAILED:pipeline %s" % (pipe.get("reason") or "not a succeeded run with an image digest"))
        if dep.get("ok") is not True or dep.get("image_digest") != pipe.get("image_digest"):
            reasons.append("DEPLOY_FAILED:deployment %s" % (",".join(dep.get("issues") or []) or "image differs from the pipeline's"))
        if not str(dep.get("route_url") or "").startswith("https://"):
            reasons.append("DEPLOY_FAILED:route is not https")
        if not push_landed(head):
            reasons.append("PUSH_NOT_LANDED:no recorded, landed push effect for %s" % head[:12])
        facts.update(image_digest=str(pipe.get("image_digest") or ""), route_url=str(dep.get("route_url") or ""),
                     https=str(dep.get("route_url") or "").startswith("https://"), pipeline_run=str(pipe.get("pipeline_run") or ""))
    else:
        live, verdict = docs["live.json"], docs["m5-verdict.json"]
        bound("live.json", live)
        bound("m5-verdict.json", verdict)
        if live.get("ok") is not True:
            reasons.append("VALIDATE_FAILED:live %s" % ",".join(live.get("issues") or []))
        token = str(verdict.get("verdict") or "")
        if token not in ("ACCEPT", "INCONCLUSIVE") or verdict.get("failed_stage"):
            reasons.append("VALIDATE_FAILED:M5 verdict %s %s" % (token or "missing", verdict.get("failed_stage") or ""))
        facts.update(verdict=token, ship=bool(token == "ACCEPT" and verdict.get("ship") is True),
                     deployment_status=str(verdict.get("deployment_status") or ""))
    return not reasons, facts, reasons
