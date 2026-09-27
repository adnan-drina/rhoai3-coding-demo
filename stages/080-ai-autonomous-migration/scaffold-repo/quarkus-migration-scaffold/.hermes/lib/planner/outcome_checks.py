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


def _oracles(root: Path) -> dict[str, list[str]] | None:
    from planner.worklist import _iter_corpus_docs
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
                    "entry_point_inventory_sha256": sha256_file(root / EP_INVENTORY)}, **extra)


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


def _covers(node: dict[str, Any], m: dict[str, Any]) -> bool:
    cls = node.get("class")
    have = set(m.get("classes") or [])
    # plan semantics v1: an outcome owning source requirements is covered only
    # by a measurement that records each of their named checks; an empty live
    # work list or a vanished diagnostic never discharges them
    req = set(((node.get("acceptance") or {}).get("requirement_checks")) or [])
    if req and not req <= set(m.get("checks") or []):
        return False
    if cls in ("build", "config"):
        return "build" in have
    if cls == "source":
        return {"compile", "tests"} <= have
    if cls == "runtime":
        return "runtime" in have
    if cls == "behavior":
        return "parity" in have and set(node.get("scenarios") or []) <= set(m.get("scenarios") or [])
    return False


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
