"""Native cooperative control for the outcome board (outcome-board/v2).

Hermes Kanban is the ONE task lifecycle authority: task identity and state,
run history, dependencies, claims, review and rework, dispatch and crash
recovery are the pinned runtime's own (tasks, task_runs, task_links, the
gateway dispatcher, request_review / request_changes / block / complete).
This module is the small migration-specific adapter the architect review of
2026-09-27 retains (tmp/native-hermes-review-20260927/NATIVE-SOLUTION-REVIEW.md):

  1. deterministic publication and read-back of the plan's nodes and bounded
     revisions through native operations (planner/native_publish.py);
  2. validation of a requested native action against the task's attached
     contract, its current native run, the baseline and candidate, scope,
     evidence and the semantic repair budget (the pre_tool_call hook,
     kernel/native_gate.py and advance.py through _outcome_bridge);
  3. domain verdicts and evidence recorded ON THE BOARD: native comments
     (``[native-control] {json}`` records), attachments (plan revisions, task
     contracts, held candidates, assessments) and native run metadata; a
     read-only progress projection.

There is no second store, no service, no reconciler and no intent table. A
record is keyed; a replayed step finds its key and does not repeat an effect.

Trust boundary (stated with every claim): native Kanban uses a cooperative
local-user model. The worker's own user can alter kanban.db, the attachments
and these records; nothing here is tamper-resistant against worker code
(the earlier protected-writer requirement F1 is amended for v2 runs by the
user's decision of 2026-09-27). Worker-produced build/test/parity receipts
are trusted subject to binding and consistency checks (measurement trust
``cooperative-receipts``). The migration acceptance criteria are unchanged.

Semantics that differ from outcome-board/v1 on purpose:

  M3   one native task per outcome; a rejected attempt or a reviewer's
       request_changes is another native RUN of the same task. The
       implementer hands an accepted outcome to review; the reviewer completes
       it (the domain gate below) or requests changes.
  M4   means "verification ACCEPTED". A measured REFUSE is kept as evidence
       on its run; the same M4 task gains the necessary repairs as
       prerequisites (repair -> M4) and waits (kanban_block kind=dependency);
       native promotion resumes it. Only an accepted, candidate-bound M4
       releases M5, whose stages depend on it natively.
  M5   PREFLIGHT -> DEPLOY -> VALIDATE are native tasks created at M2 under
       M4; a push is recovered by read-back of the remote, never repeated.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from planner.outcome_checks import (AMEND_LIMIT, AMEND_MAX_FILES, CAUSE_CLASSES, DELIVERY_OK_VERDICTS, HOLD_MAX_BYTES,
                                    MAX_ASSESSMENT_GENERATIONS, OWNER_DEFECT, VERDICT, Refusal, _covers, _git,
                                    _is_product, _read_json, _unit_kind, changed_product_paths, commit_product_tree,
                                    git_commits_after, load_worklist, norm_rel, open_obligations, owner_repair_id,
                                    owner_repair_revision, planned_cluster_id, refuse_revision, repair_evidence_gaps,
                                    requirement_measurement, stage_evidence_facts)
from planner.outcome_graph import CONTROL_M2, IMPL, brief_document, plan_digest

KEY_VERSION = "v2"
ROLE_PREFIX = {"repair": "outcome", "assess": "assess", "deliver": "deliver"}
PREFIX_ROLE = {v: k for k, v in ROLE_PREFIX.items()}
M2_KEY = "m2-plan"
RECORD = "[native-control]"
CONTRACT = "contract.json"
CONTRACT_SCHEMA = "rhoai3.native-contract/v1"
PLAN_SCHEMA = "rhoai3.native-plan/v1"
PLAN_NAME = re.compile(r"^plan\.r(\d+)\.json$")
REVIEWER = "reviewer"
PROTECTED_DIRS = ("verification/outcome-board/", "verification/native-board/", ".hermes/", ".git/")
REFUSALS = Path("verification") / "native-board" / "refusals"
REPEAT_LIMIT = 3
LOCK = Path("verification") / "native-board" / "publish.lock"
MAX_RETRIES = 2
WORKSPACE = "dir:/projects/modernized"


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def native_key(run_id: str, node: dict[str, Any]) -> str:
    return "%s:%s:%s:%s" % (ROLE_PREFIX[node["role"]], KEY_VERSION, run_id, node["outcome_id"])


def parse_key(key: str | None) -> tuple[str, str, str] | None:
    """(role, run id, outcome id) of a v2 node key; None for anything else
    (M1/M2 control cards, serial-loop cards, outcome-board/v1 keys)."""
    parts = str(key or "").split(":", 3)
    if len(parts) != 4 or parts[1] != KEY_VERSION or parts[0] not in PREFIX_ROLE or not parts[2] or not parts[3]:
        return None
    return PREFIX_ROLE[parts[0]], parts[2], parts[3]


def canonical_bytes(doc: Any) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contract_doc(plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """The task's attached contract: the brief (membership, checks, lineage),
    its native identity, budget family and the paths an owner repair may
    reach. Descriptive and immutable once attached; ownership that a later
    revision moves is read from the latest plan revision, never from here."""
    doc = brief_document(plan, node)
    doc.update({
        "schema": CONTRACT_SCHEMA,
        "native_key": native_key(plan["run_id"], node),
        "stage": node.get("stage") or "",
        "budget": dict(node.get("budget") or {}),
        "repair_paths": list(node.get("repair_paths") or []),
        "repair_scenarios": list(node.get("repair_scenarios") or []),
        "control": "native-cooperative",
        "note": "Descriptive. Product edits are granted per issued cluster (native_gate.py issue), never by this file.",
    })
    return doc


STAGE_TEXT = {
    "prepare": ("Prepare the accepted candidate for delivery: confirm it is exactly the candidate M4 accepted and "
                "that it is eligible for the delivery pipeline.",
                "the release-candidate and eligibility receipts are bound to the current commit and name the "
                "accepted M4, and the reviewer approves."),
    "push": ("Deliver the accepted candidate: push exactly that commit once, let the pipeline build its image, and "
             "deploy it.",
             "the pipeline succeeded with an image digest, the deployment runs that image behind an HTTPS route, the "
             "push is recorded as landed, and the reviewer approves."),
    "accept": ("Validate the deployed application live against the source's recorded behavior.",
               "the live checks pass and the M5 verdict (ACCEPT, or INCONCLUSIVE with its reasons) is recorded for the "
               "deployed commit, and the reviewer approves."),
}


DONE_WHEN = {
    "build": "every owned obligation is gone from the measured work list, the build classpath resolves, and the reviewer approves "
             "(compile is judged on the COMPILE cards).",
    "config": "every owned obligation is gone from the measured work list, the owned configuration checks hold, and the reviewer "
              "approves (compile is judged on the COMPILE cards).",
    "source": "every owned obligation is gone from the measured work list for the current candidate, and the reviewer "
              "approves; tests run at M4.",
    "runtime": "the package and startup gate passes on the packaged candidate (compiling alone is not enough), and the "
               "reviewer approves.",
    "behavior": "the assigned parity checks pass for the current candidate with no owned obligation open, and the "
                "reviewer approves.",
}


def _plural(text: str) -> str:
    """'1 owned obligation(s)' -> '1 owned obligation'; 'n obligation(s)' -> 'n obligations'."""
    import re as _re
    return _re.sub(r"\b(\d+)( [a-z ]*?)obligation\(s\)",
                   lambda m: "%s%sobligation%s" % (m.group(1), m.group(2), "" if m.group(1) == "1" else "s"), text)


def native_description(node: dict[str, Any]) -> str:
    """The human-facing card body of a v2 task: what it delivers, how it is
    done, where the detail is and which procedure applies. No commands, no
    machine contract, no retry policy (those live in the pinned skill and the
    attached contract.json)."""
    role = node.get("role")
    if role == "assess":
        return ("Verify the combined migrated application on its packaged candidate.\n\n"
                "Done when: the M4 verdict is ACCEPT or PROVISIONAL_ACCEPT for the current candidate and the reviewer "
                "approves. A REFUSE keeps this card open: the repairs it needs become its prerequisites, and it runs "
                "again after them. Delivery (M5) starts only after this card is done.\n\n"
                "Details: the attached contract.json lists the prerequisite outcomes and the checks.\n"
                "Procedure: paved-road-m4 (outcome-board/v2).")
    if role == "deliver":
        what, done = STAGE_TEXT.get(str(node.get("stage") or ""), ("Run this delivery stage.", "its receipts pass."))
        return ("%s\n\nDone when: %s\n\n"
                "Details: the attached contract.json names the accepted verification this stage is bound to.\n"
                "Procedure: paved-road-m5 (outcome-board/v2)." % (what, done))
    if node.get("repair_paths"):
        # an owner repair: its revision wrote the one plain paragraph that explains it
        what, done = str(node.get("description") or "").split(" Complete when ", 1)[0], (
            "the failing scenarios pass on the repaired candidate and the reviewer approves; the waiting card then "
            "resumes on this repair.")
        if not what.endswith("."):
            what += "."
    else:
        from planner.outcome_graph import outcome_summary
        what = _plural(outcome_summary(node)[0])
        done = DONE_WHEN.get(str(node.get("class") or ""), "every owned obligation is closed, and the reviewer approves.")
    return ("%s\n\nDone when: %s\n\n"
            "Details: the attached contract.json lists the owned obligations, checks and evidence.\n"
            "Procedure: paved-road-m3 (outcome-board/v2). A rejected attempt or a review change request comes back "
            "to this same card." % (what, done))


def native_body(node: dict[str, Any]) -> str:
    """The task body as published (deterministic; the read-back compares exactly this)."""
    return native_description(node)


# checks a requirement can only pass once the application runs: they gate M4,
# never an outcome that runs before the application can start (v20
# build:c:9c5fb3d1b7e3 owned parity:request-body-positive-negative and could
# not be accepted while ~233 compile errors remained)
RUNTIME_CHECK_PREFIXES = ("parity:", "behavior:", "gate:package", "gate:augmentation", "gate:startup")
MEASURES_RUNTIME = {"runtime": ("gate:package", "gate:augmentation", "gate:startup"),
                    "behavior": RUNTIME_CHECK_PREFIXES}
M3_ACTION = {"build": "BUILD", "config": "CONFIGURE", "source": "COMPILE", "runtime": "RUNTIME", "behavior": "BEHAVIOR"}
DASH = "\u2014"


def _deferred(node: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(kept, deferred) requirement checks of a repair node: a runtime check
    its class cannot measure is deferred to M4."""
    checks = list(((node.get("acceptance") or {}).get("requirement_checks")) or [])
    can = MEASURES_RUNTIME.get(str(node.get("class") or ""), ())
    kept, deferred = [], []
    for c in checks:
        (deferred if c.startswith(RUNTIME_CHECK_PREFIXES) and not c.startswith(can) else kept).append(c)
    return kept, deferred


def _m3_title(node: dict[str, Any]) -> str:
    title = str(node.get("title") or node["outcome_id"])
    if title.startswith("M3 "):
        return title
    for prefix in ("Build: ", "Configuration: ", "Source compatibility: ", "Behavior: ", "Application ", "Follow-up: ", "Repair "):
        if title.startswith(prefix):
            subject = title[len(prefix):]
            break
    else:
        subject = title
    if node.get("repair_paths"):
        action = "REPAIR"
    elif node["outcome_id"].startswith("followup:"):
        action = "FOLLOW-UP"
    else:
        action = M3_ACTION.get(str(node.get("class") or ""), "REPAIR")
    return "M3 %s %s %s" % (action, DASH, subject)


def native_titles(plan: dict[str, Any]) -> dict[str, Any]:
    """Every repair outcome is titled ``M3 <ACTION> — <subject>`` (the serial
    loop's vocabulary) and no two cards share a title: equal titles become
    "part i of n" in outcome-id order (v20 had two outcomes both titled
    "Configuration: application.properties"). A title already published
    (it starts with "M3 ") is never rewritten."""
    nodes = [dict(n) for n in plan["nodes"]]
    fresh = [n for n in nodes if n.get("role") == "repair" and not str(n.get("title") or "").startswith("M3 ")]
    taken = [str(n.get("title")) for n in nodes if n not in fresh]
    groups: dict[str, list[dict[str, Any]]] = {}
    for n in sorted(fresh, key=lambda n: n["outcome_id"]):
        groups.setdefault(_m3_title(n), []).append(n)
    for base, members in groups.items():
        clash = sum(1 for t in taken if t == base or t.startswith(base + " (part "))
        total = len(members) + clash
        for i, n in enumerate(members, start=clash + 1):
            n["title"] = base if total == 1 else "%s (part %d of %d)" % (base, i, total)
    out = dict(plan, nodes=nodes)
    out.pop("digest", None)
    out["digest"] = plan_digest(out)
    return out


TEST_EXECUTION_CHECK = "measure:tests"


def defer_runtime_checks(plan: dict[str, Any]) -> dict[str, Any]:
    """Move each runtime check an early outcome cannot measure to the M4
    node's acceptance (``deferred_requirement_checks``: outcome, requirement
    ids, check), and record it on the outcome (``deferred_checks``). The check
    still gates delivery; it no longer blocks a card that runs before the
    application can start. Idempotent.

    The same for a source outcome's ``measure:tests`` (v24): the full test
    suite cannot run while the application does not compile, so an early
    compile card cannot measure it. Its scoped compile/structural checks stay
    immediate; the suite is an explicit M4 obligation naming this outcome and
    its requirements, measured on M4's candidate (``deferred_checks_status``).
    A verification that CAN run the tests still runs them at every step, and
    an introduced failing test is still vetoed there. An owner repair (a node
    with ``lineage``) runs after the application compiles and keeps it."""
    nodes = [dict(n) for n in plan["nodes"]]
    moved: list[dict[str, Any]] = []
    for n in nodes:
        if n.get("role") != "repair":
            continue
        kept, deferred = _deferred(n)
        acc = dict(n.get("acceptance") or {})
        tests_later = (str(n.get("class") or "") == "source" and not n.get("lineage")
                       and TEST_EXECUTION_CHECK in (acc.get("checks") or []))
        if not deferred and not tests_later:
            continue
        if deferred:
            acc["requirement_checks"] = kept
        if tests_later:
            acc["checks"] = [c for c in acc.get("checks") or [] if c != TEST_EXECUTION_CHECK]
            deferred = deferred + [TEST_EXECUTION_CHECK]
        n["acceptance"] = acc
        n["deferred_checks"] = sorted(set(list(n.get("deferred_checks") or []) + deferred))
        moved += [{"outcome": n["outcome_id"], "requirements": sorted(n.get("requirements") or []), "check": c}
                  for c in deferred]
    if moved:
        for n in nodes:
            if n.get("role") == "assess":
                acc = dict(n.get("acceptance") or {})
                have = {(d["outcome"], d["check"]) for d in acc.get("deferred_requirement_checks") or []}
                acc["deferred_requirement_checks"] = sorted(
                    list(acc.get("deferred_requirement_checks") or []) + [d for d in moved if (d["outcome"], d["check"]) not in have],
                    key=lambda d: (d["outcome"], d["check"]))
                n["acceptance"] = acc
    out = dict(plan, nodes=nodes)
    out.pop("digest", None)
    out["digest"] = plan_digest(out)
    return out


def native_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """The initial revision as native control publishes it: the M5 stages are
    ASSIGNED at creation (their native parent, the accepted M4, holds them;
    there are no stage grants), runtime checks of early outcomes gate M4,
    and every repair outcome carries a unique ``M3 <ACTION>`` title.
    Deterministic; the digest is recomputed."""
    out = dict(plan)
    out["nodes"] = [dict(n, assignee=IMPL) if n.get("role") == "deliver" else dict(n) for n in plan["nodes"]]
    out["control"] = "native-cooperative"
    return native_titles(defer_runtime_checks(out))


def native_revision(plan: dict[str, Any]) -> dict[str, Any]:
    """A later revision (owner repair, REFUSE repairs) as native control
    publishes it: the same titling and check placement for its new nodes."""
    return native_titles(defer_runtime_checks(plan))


def plan_attachment(plan: dict[str, Any], added: list[str]) -> dict[str, Any]:
    """The revision document attached to the board: the plan and the digest
    of the contract of every node this revision introduces."""
    nodes = {n["outcome_id"]: n for n in plan["nodes"]}
    return {"schema": PLAN_SCHEMA, "revision": int(plan["revision"]), "plan": plan,
            "contracts": {oid: sha256(canonical_bytes(contract_doc(plan, nodes[oid]))) for oid in sorted(added)}}


# ---------------------------------------------------------------------------
# the board as the adapter reads it
# ---------------------------------------------------------------------------

class Board:
    """Read side over one native board (KanbanNative or FakeNative), plus the
    keyed record writer. Everything here is derived from native state."""

    def __init__(self, native: Any, *, author: str | None = None):
        self.native = native
        self.author = author if author is not None else (os.environ.get("HERMES_PROFILE") or "").strip()

    # -- tasks -----------------------------------------------------------------
    def task(self, task_id: str) -> dict[str, Any] | None:
        return self.native.task(task_id) if task_id else None

    def node_of(self, task_id: str) -> tuple[str, str, str] | None:
        t = self.task(task_id)
        return parse_key(t.get("idempotency_key")) if t else None

    def is_m2(self, task_id: str) -> bool:
        t = self.task(task_id)
        return bool(t and t.get("idempotency_key") == M2_KEY)

    def m2_task(self) -> str:
        rows = [r for r in self.native.by_key(M2_KEY) if r["status"] != "archived"]
        return rows[0]["id"] if len(rows) == 1 else ""

    def run_tasks(self, run_id: str) -> dict[str, dict[str, Any]]:
        """outcome id -> native row, every v2 node of this run (archived included)."""
        out: dict[str, dict[str, Any]] = {}
        for prefix in ROLE_PREFIX.values():
            for r in self.native.tasks_with_key_prefix("%s:%s:%s:" % (prefix, KEY_VERSION, run_id)):
                parsed = parse_key(r["idempotency_key"])
                if parsed:
                    out.setdefault(parsed[2], r)
        return out

    def task_of(self, run_id: str, node: dict[str, Any]) -> str:
        live = [r for r in self.native.by_key(native_key(run_id, node)) if r["status"] != "archived"]
        return live[0]["id"] if len(live) == 1 else ""

    # -- attachments -------------------------------------------------------------
    def attachment(self, task_id: str, name: str) -> tuple[bytes, dict[str, Any]] | None:
        rows = [a for a in self.native.attachments(task_id) if a["filename"] == name]
        if not rows:
            return None
        if len(rows) > 1:
            raise Refusal("ATTACHMENT_AMBIGUOUS", "%s carries %d attachments named %s" % (task_id, len(rows), name))
        try:
            return Path(rows[0]["stored_path"]).read_bytes(), rows[0]
        except OSError as exc:
            raise Refusal("ATTACHMENT_UNREADABLE", "%s %s: %s" % (task_id, name, exc)) from exc

    def contract(self, task_id: str) -> dict[str, Any]:
        got = self.attachment(task_id, CONTRACT)
        if got is None:
            raise Refusal("CONTRACT_MISSING", "%s carries no %s" % (task_id, CONTRACT))
        try:
            doc = json.loads(got[0])
        except ValueError as exc:
            raise Refusal("CONTRACT_CORRUPT", "%s %s: %s" % (task_id, CONTRACT, exc)) from exc
        t = self.task(task_id) or {}
        if doc.get("schema") != CONTRACT_SCHEMA or doc.get("native_key") != t.get("idempotency_key"):
            raise Refusal("CONTRACT_FOREIGN", "%s's contract names %r" % (task_id, doc.get("native_key")))
        return doc

    # -- plan revisions ------------------------------------------------------------
    def revisions(self, run_id: str) -> dict[int, tuple[str, dict[str, Any]]]:
        """revision -> (task that carries it, document). Two different
        documents for one revision refuse PLAN_FORKED."""
        holders = [self.m2_task()] + [r["id"] for r in self.run_tasks(run_id).values()]
        out: dict[int, tuple[str, dict[str, Any]]] = {}
        for tid in [h for h in holders if h]:
            for a in self.native.attachments(tid):
                m = PLAN_NAME.match(str(a["filename"]))
                if not m:
                    continue
                try:
                    doc = json.loads(Path(a["stored_path"]).read_bytes())
                except (OSError, ValueError) as exc:
                    raise Refusal("PLAN_CORRUPT", "%s %s: %s" % (tid, a["filename"], exc)) from exc
                if not isinstance(doc, dict) or doc.get("schema") != PLAN_SCHEMA or not isinstance(doc.get("plan"), dict):
                    raise Refusal("PLAN_CORRUPT", "%s %s is not a native plan revision" % (tid, a["filename"]))
                if doc["plan"].get("run_id") != run_id:
                    continue
                n = int(m.group(1))
                if n in out and out[n][1]["plan"].get("digest") != doc["plan"].get("digest"):
                    raise Refusal("PLAN_FORKED", "revision %d exists twice with different digests (%s, %s)" % (n, out[n][0], tid))
                out.setdefault(n, (tid, doc))
        return out

    def plan(self, run_id: str) -> dict[str, Any]:
        revs = self.revisions(run_id)
        if not revs:
            raise Refusal("PLAN_MISSING", "no native plan revision is attached for run %s" % run_id)
        top = max(revs)
        if sorted(revs) != list(range(1, top + 1)):
            raise Refusal("PLAN_GAP", "revisions %s are not a contiguous chain" % sorted(revs))
        for n in range(2, top + 1):
            if int(revs[n][1]["plan"].get("parent_revision") or 0) != n - 1:
                raise Refusal("PLAN_GAP", "revision %d does not follow %d" % (n, n - 1))
        plan = revs[top][1]["plan"]
        if plan_digest(plan) != plan.get("digest"):
            raise Refusal("PLAN_DIGEST", "revision %d digest does not cover its content" % top)
        return plan

    def contract_digests(self, run_id: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for _n, (_tid, doc) in sorted(self.revisions(run_id).items()):
            for oid, digest in (doc.get("contracts") or {}).items():
                out.setdefault(oid, digest)
        return out

    # -- records -------------------------------------------------------------------
    def records(self, task_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        """The domain records on a task, oldest first; a key is recorded once
        (the first occurrence wins). Each carries its board-wide comment id."""
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for c in self.native.comment_rows(task_id):
            body = str(c.get("body") or "")
            if not body.startswith(RECORD + " "):
                continue
            try:
                doc = json.loads(body[len(RECORD) + 1:])
            except ValueError:
                continue
            if not isinstance(doc, dict) or not doc.get("key") or doc["key"] in seen:
                continue
            seen.add(doc["key"])
            doc["_id"] = int(c["id"])
            if kind is None or doc.get("kind") == kind:
                out.append(doc)
        return out

    def record(self, task_id: str, kind: str, key: str, **doc: Any) -> dict[str, Any]:
        """Write one keyed record; an existing key is returned unchanged."""
        for r in self.records(task_id):
            if r["key"] == key:
                return r
        body = dict(doc, kind=kind, key=key, v=1)
        self.native.comment(task_id, "%s %s" % (RECORD, json.dumps(body, sort_keys=True, separators=(",", ":"))),
                            self.author)
        got = next((r for r in self.records(task_id) if r["key"] == key), None)
        if got is None:
            raise Refusal("RECORD_LOST", "the record %s on %s did not read back" % (key, task_id))
        return got


def board_for(root: Path, native: Any = None) -> Board:
    if native is None:
        from planner.outcome_native import KanbanNative, default_db_path
        db = default_db_path()
        native = KanbanNative(db, hermes=(os.environ.get("HERMES_BIN") or "hermes").split(),
                              env=dict(os.environ, HERMES_KANBAN_DB=db) if db else None)
    return Board(native)


# ---------------------------------------------------------------------------
# run identity and the plan node of a task
# ---------------------------------------------------------------------------

def _gate(root: Path) -> None:
    from planner.outcome_protocol import execution_gate, select_protocol
    sel = select_protocol(root)
    if not sel.native:
        raise Refusal("PROTOCOL_NOT_NATIVE", "this run selects %s" % sel.protocol)
    g = execution_gate(root, sel)
    if g:
        raise Refusal(g[0][0], g[0][1])


def _node(plan: dict[str, Any], oid: str) -> dict[str, Any] | None:
    return next((n for n in plan.get("nodes") or [] if n["outcome_id"] == oid), None)


def node_context(board: Board, task_id: str) -> tuple[str, str, str, dict[str, Any], dict[str, Any]]:
    """(role, run id, outcome id, latest plan, node) of a published task."""
    parsed = board.node_of(task_id)
    if parsed is None:
        raise Refusal("NOT_A_NODE", "%s is not an outcome-board/v2 node" % task_id)
    role, run_id, oid = parsed
    plan = board.plan(run_id)
    node = _node(plan, oid)
    if node is None or node.get("role") != role:
        raise Refusal("NODE_UNKNOWN", "%s (%s) is not in the current plan revision" % (task_id, oid))
    return role, run_id, oid, plan, node


def live_run(board: Board, task_id: str, run_id: int) -> dict[str, Any]:
    t = board.task(task_id)
    if t is None:
        raise Refusal("RUN_FOREIGN_TASK", "%s is not on the board" % task_id)
    if t.get("status") != "running" or int(t.get("current_run_id") or 0) != int(run_id) or not run_id:
        raise Refusal("RUN_STALE", "%s is %s with run %s; the caller holds run %s"
                      % (task_id, t.get("status"), t.get("current_run_id"), run_id))
    return t


def owned(plan: dict[str, Any], node: dict[str, Any]) -> set[str]:
    oid = node["outcome_id"]
    return set(node.get("obligations") or []) | {ob for ob, o in (plan.get("ownership") or {}).items() if o == oid}


def _product_tree(root: Path) -> str:
    from planner.canonical import product_tree_sha256
    return product_tree_sha256(root)


def _head(root: Path) -> str:
    p = _git(root, "rev-parse", "HEAD")
    return p.stdout.strip() if p.returncode == 0 else ""


# ---------------------------------------------------------------------------
# the semantic repair budget (native runs + domain records, per family)
# ---------------------------------------------------------------------------

def family_spent(board: Board, run_id: str, plan: dict[str, Any], key: str) -> int:
    """Rejected attempts plus reviewer change requests across every task of
    one budget family (an owner, its follow-ups and its owner repairs share
    one key). Quota waits, crashes, timeouts and dependency waits spend
    nothing: they are neither reject records nor changes_requested runs."""
    if not key:
        return 0
    tasks = board.run_tasks(run_id)
    spent = 0
    for n in plan.get("nodes") or []:
        if n.get("role") != "repair" or str((n.get("budget") or {}).get("key") or "") != key:
            continue
        row = tasks.get(n["outcome_id"])
        if not row:
            continue
        voided = {str(v.get("reject") or "") for v in board.records(row["id"], "reject-voided")}
        spent += sum(1 for r in board.records(row["id"], "reject") if r["key"] not in voided)
        spent += sum(1 for r in board.native.runs(row["id"]) if r.get("outcome") == "changes_requested")
    return spent


def void_rejects(board: Board, *, task_id: str, keys: list[str], reason: str, by: str) -> list[str]:
    """The Operator's disposition that named rejections were caused by a HARNESS
    defect, not by the candidate (v21 t_0bc6319b: a planned unit refused "measure
    did not decrease" by a gate that could not measure it). Each stays on the
    record; a `reject-voided` record beside it takes it out of the family budget.
    Only the Operator records this; a rejection of a broken candidate is never voided."""
    if by != "operator":
        raise Refusal("VOID_NOT_OPERATOR", "only the Operator voids a rejection (profile %r)" % by)
    if not reason.strip():
        raise Refusal("VOID_REASON_MISSING", "name the harness defect that caused the rejection")
    rejects = {r["key"]: r for r in board.records(task_id, "reject")}
    voided = {str(v.get("reject") or "") for v in board.records(task_id, "reject-voided")}
    unknown = [k for k in keys if k not in rejects]
    if unknown:
        raise Refusal("VOID_UNKNOWN_REJECT", "%s: no such rejection on %s (%s)" % (", ".join(unknown), task_id,
                                                                                    ", ".join(sorted(rejects)) or "none"))
    done = []
    for k in keys:
        if k in voided:
            continue
        board.record(task_id, "reject-voided", "reject-voided:%s" % k, reject=k, reason=reason[:500],
                     cluster=rejects[k].get("cluster") or "", original_reason=str(rejects[k].get("reason") or "")[:300])
        done.append(k)
    return done


def budget_state(board: Board, run_id: str, plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    b = node.get("budget") or {}
    key, limit = str(b.get("key") or ""), int(b.get("limit") or 0)
    spent = family_spent(board, run_id, plan, key)
    return {"key": key, "limit": limit, "spent": spent, "exhausted": bool(limit) and spent >= limit}


# ---------------------------------------------------------------------------
# issue: the run-bound scope of THIS native run
# ---------------------------------------------------------------------------

def _allowed_paths(node: dict[str, Any], worklist: dict[str, Any] | None, own: set[str]) -> tuple[str, list[str]]:
    """The ONE open cluster this outcome may edit now, and its write set."""
    if node.get("role") != "repair" or worklist is None:
        return "", []
    for c in worklist.get("clusters") or []:
        if not isinstance(c, dict) or c.get("status") != "open":
            continue
        if own & set(c.get("items") or []) or c.get("id") in set(node.get("clusters") or []):
            return str(c["id"]), sorted(str(p) for p in c.get("write_set") or [])
    return "", []


def objective_open(descriptor: dict[str, Any], worklist: dict[str, Any] | None) -> bool:
    """Is any admitted obligation of an objective still reported? Asked of the
    line-free identity (a moved site is the same site) and, for an obligation
    without one (an MTA incident), of its id."""
    if not worklist:
        return False
    want = set((descriptor.get("identities") or {}).values())
    for it in worklist.get("items") or []:
        if not isinstance(it, dict) or str(it.get("category") or "") != "mandatory":
            continue
        if str(it.get("identity") or "") in want or str(it.get("id") or "") in want:
            return True
    return False


def _open_pending(board: Board, task_id: str) -> dict[str, Any] | None:
    pend = None
    for r in board.records(task_id):
        if r["kind"] == "pending":
            pend = r
        elif r["kind"] in ("reject", "accept-commit", "accept-aborted") and pend is not None:
            pend = None
        elif r["kind"] == "restore" and pend is not None and r.get("closes_pending"):
            pend = None
    return pend


def _accept_records(board: Board, task_id: str) -> list[dict[str, Any]]:
    return [r for r in board.records(task_id) if r["kind"] in ("accept-commit", "accept-evaluated")]


def _rework_paths(root: Path, board: Board, task_id: str) -> list[str]:
    """After a reviewer's request_changes: the product paths this task's own
    accepted commits changed (git diff-tree), bounded."""
    paths: set[str] = set()
    for r in board.records(task_id, "accept-commit"):
        commit = str(r.get("commit") or "")
        got = changed_product_paths(root, commit + "^1", commit) if commit else None
        paths |= set(got or [])
    return sorted(paths)[:AMEND_MAX_FILES]


def _changes_requested_since_accept(board: Board, task_id: str) -> bool:
    runs = board.native.runs(task_id)
    last_change = max((int(r["id"]) for r in runs if r.get("outcome") == "changes_requested"), default=0)
    if not last_change:
        return False
    last_accept_run = max((int(r.get("run") or 0) for r in _accept_records(board, task_id)), default=0)
    return last_change > last_accept_run


def _owner_hold_pending(root: Path, board: Board, run_id: str, plan: dict[str, Any], task_id: str) -> str:
    """The owner repair a held candidate of this task still waits on ('' when
    none). Recovers an interrupted publication of that repair first."""
    for h in board.records(task_id, "owner-hold"):
        fid = str(h.get("repair") or "")
        node = _node(plan, fid)
        if node is None:
            # the hold was recorded, the revision not yet attached: finish it
            _publish_owner_repair(root, board, run_id, plan, h)
            plan = board.plan(run_id)
            node = _node(plan, fid)
        tid = board.task_of(run_id, node) if node else ""
        t = board.task(tid) if tid else None
        if not t or t.get("status") != "done":
            # finish an interrupted publication (task, contract, links); every step is looked up first
            from planner.native_publish import publish_revision
            publish_revision(root, board, plan, added=[fid], holder=task_id)
            return fid
    return ""


def repair_waiting(board: Board, run_id: str, plan: dict[str, Any], task_id: str) -> str:
    """The owner repair a held candidate of this task waits on and that is
    not done yet ('' when none). Read-only."""
    for h in board.records(task_id, "owner-hold"):
        node = _node(plan, str(h.get("repair") or ""))
        tid = board.task_of(run_id, node) if node else ""
        if not tid or (board.task(tid) or {}).get("status") != "done":
            return str(h.get("repair") or "")
    return ""


def _baseline_evidence(root: Path, tree: str, head: str) -> dict[str, Any] | None:
    """The loop's recorded M2 baseline as the measurement of THIS tree, or None:
    only when the baseline step's commit is HEAD, its candidate digest is this
    tree (the same product_tree_sha256) and its measure was fully known. Its
    classes are what that verification EXECUTED on this tree (the step's
    recorded execution, planner.measurement), exactly the evidence an ordinary
    acceptance needs: a known tuple does not show the tests ran (v23's
    baseline read [4, 233, 0] and no test could run), and a step recorded
    before executions were kept proves no class at all."""
    from planner.measurement import classes
    from planner.paths import LOOP_STEPS
    try:
        steps = json.loads((Path(root) / LOOP_STEPS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    base = next((s for s in steps.get("steps") or [] if isinstance(s, dict) and s.get("verdict") == "baseline"), None)
    if not base or not head or str(base.get("commit") or "") != head or str(base.get("candidate_sha256") or "") != tree \
            or not (base.get("measure") or {}).get("known"):
        return None
    ex = base.get("execution") if isinstance(base.get("execution"), dict) else None
    if ex is not None and str(ex.get("tree") or "") != tree:
        ex = None
    return {"key": "baseline:%s" % head[:12], "task": "M2 baseline", "outcome": CONTROL_M2, "commit": head,
            "measurement": {"classes": classes(ex), "scenarios": [], "execution": ex}}


def _satisfied(root: Path, board: Board, run: str, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any],
               tree: str, head: str) -> tuple[dict[str, Any] | None, list[str]]:
    """An outcome with nothing left to issue whose owned obligations are
    already absent (another outcome's accepted commit discharged them -- v21
    t_23612034: the package unit u:0e0fee12e896 fixed PropertyComparator):
    measured on THIS tree from the acceptance another card recorded on it.
    (evidence, []) when it is satisfied; (None, reasons) otherwise."""
    if changed_product_paths(root, head):
        return None, ["the product tree differs from HEAD %s" % head[:12]]
    still = sorted(open_obligations(worklist) & owned(plan, node))
    if still:
        return None, ["open obligation %s" % o for o in still[:6]]
    evidence = None
    for oid, row in (board.run_tasks(run) or {}).items():
        for r in _accept_records(board, row["id"]):
            if r.get("kind") == "accept-commit" and r.get("outcome_accepted") and r.get("tree") == tree \
                    and not r.get("satisfied_by"):
                evidence = dict(r, task=row["id"], outcome=oid)
    if evidence is None and node.get("check_plan"):
        # compatibility-objectives/v1: before any outcome is accepted, the tree M2 measured and
        # admitted IS a measured tree -- a requirement whose checks already hold there (v23: the
        # decided security switch rendered by bootstrap) is satisfied, never handed an empty unit
        evidence = _baseline_evidence(root, tree, head)
    if evidence is None:
        return None, ["no outcome was accepted on this tree %s: nothing measured it" % tree[:12]]
    em = evidence.get("measurement") or {}
    m = _measure(root, plan, node, worklist, tree, {"classes": em.get("classes") or [], "scenarios": em.get("scenarios") or [],
                                                    "execution": em.get("execution")})
    m["classes_asserted_by"] = "%s %s (%s)" % ("baseline step" if evidence["outcome"] == CONTROL_M2 else "accept-commit",
                                              evidence["key"], evidence["task"])
    gaps = repair_evidence_gaps(root, node, tree)
    reasons = not_accepted_reasons({"measurement": m, "repair_evidence_gaps": gaps})
    if not _covers(node, m) and not reasons:
        reasons = ["the check class of %s was not measured on this tree" % node["outcome_id"]]
    if reasons or m["open_owned"]:
        return None, reasons
    # the record whose measurement of THIS tree is the evidence: a witness, never
    # the cause (v23 t_dddc1862 named the unrelated Vet repository commit as the
    # one that "discharged" a Visit source file it never touched). File overlap
    # proves neither, so no causal claim is made at all.
    return {"measurement": m, "by": {"task": evidence["task"], "outcome": evidence["outcome"], "commit": evidence.get("commit"),
                                     "record": evidence["key"], "relation": "witness"}}, []


def issue(root: Path, board: Board, *, task_id: str, run_id: int, claim_lock: str = "",
          replay_unchanged: bool = False) -> dict[str, Any]:
    """The scope of this native run: the one open cluster (or planned unit,
    owner repair unit, rework unit) of the task's outcome, the baseline it is
    measured against and the budget it spends from. Recorded as an ``issue``
    record on the task; loop tools read its projection (issued.json).

    ``replay_unchanged`` (the worker's own ``native_gate.py issue``): a repeat
    that would record exactly this run's latest issue again returns it instead
    of a duplicate record. A re-issue the loop makes after a verdict (the
    bridge's CONTINUE) is a new attempt and always records a new issue."""
    root = Path(root)
    _gate(root)
    t = live_run(board, task_id, run_id)
    if claim_lock and t.get("claim_lock") and t["claim_lock"] != claim_lock:
        raise Refusal("RUN_STALE", "the claim lock does not match the native claim")
    role, run, oid, plan, node = node_context(board, task_id)
    if t.get("assignee") != IMPL:
        raise Refusal("ISSUE_UNASSIGNED", "%s is assigned %r; only the implementer's run is issued" % (task_id, t.get("assignee")))
    board.contract(task_id)                                     # the attached contract is this task's
    undone = [p for p in t.get("parents") or [] if (board.task(p) or {}).get("status") != "done"]
    if undone:
        raise Refusal("ISSUE_PARENT_UNDONE", "%s runs before its prerequisites %s are done" % (task_id, ", ".join(undone[:4])))
    tree, head = _product_tree(root), _head(root)
    if role == "deliver":
        m4 = m4_acceptance(root, board, run, plan)
        if not m4["accepted"]:
            raise Refusal("ISSUE_M4_NOT_ACCEPTED", "M5 runs only on an accepted verification: %s" % m4["why"])
        if m4["candidate"] != tree:
            raise Refusal("ISSUE_STALE_CANDIDATE", "M4 accepted candidate %s; the tree is now %s (candidate drift)"
                          % (m4["candidate"][:12], tree[:12]))
    budget = budget_state(board, run, plan, node) if role == "repair" else {"key": "", "limit": 0, "spent": 0, "exhausted": False}
    if role == "repair":
        waiting = _owner_hold_pending(root, board, run, plan, task_id)
        if waiting:
            raise Refusal("OWNER_REPAIR_PENDING", "%s waits on the repair %s of its owner; end this run with "
                                                  "kanban_block kind=dependency" % (oid, waiting))
        # v24 (architect decision 2026-09-28): the M2-published family budget is the ONE limit of a
        # governed repair card; a card without a published key and limit refuses instead of falling
        # back to decisions.max_attempts (that stays an input to the initial budget calculation only)
        if not budget["key"] or int(budget["limit"] or 0) <= 0:
            raise Refusal("ISSUE_BUDGET_UNPUBLISHED", "%s carries no published family budget (key %r, limit %r): the "
                          "plan revision is incomplete; kanban_block kind=needs_input" % (oid, budget["key"], budget["limit"]))
        if budget["exhausted"]:
            raise Refusal("ISSUE_BUDGET_EXHAUSTED", "%s spent %d of %d (rejected attempts and change requests, cumulative "
                          "across runs); kanban_block kind=needs_input naming the outcome" % (budget["key"], budget["spent"], budget["limit"]))
        # a commit made by a worker that died before recording it is recovered from git history first
        recover_accept(root, board, task_id=task_id, skip_run=run_id)
    pending = _open_pending(board, task_id)
    committed = commit_product_tree(root, head) if head else ""
    if committed and tree != committed and not (pending and pending.get("candidate") == tree):
        raise Refusal("ISSUE_BASELINE_DRIFT", "the product tree differs from HEAD %s and is not the retained candidate of %s; "
                      "unexplained edits are not blessed" % (head[:12], oid))
    worklist, why = load_worklist(root)
    if role == "repair" and worklist is None:
        raise Refusal("ISSUE_" + why, "an outcome is issued against the measured work list")
    cluster, allowed, unit = "", [], None
    satisfied, unsatisfied = None, []
    objective = None
    if role == "repair":
        own = owned(plan, node)
        eu = node.get("execution_unit") if isinstance(node.get("execution_unit"), dict) else None
        if eu and objective_open(eu, worklist):
            # compatibility-objectives/v1: the admitted objective is ONE bounded
            # scope, issued whole -- never its first open unit
            # the grant is the envelope the shared scope validator admits, recomputed here from the
            # descriptor and its digest-bound child seals -- never the stored bounds
            from planner.worklist import ObjectiveScopeError, build_objective_scope
            try:
                env = build_objective_scope(root, oid, eu, worklist)
            except ObjectiveScopeError as exc:
                raise Refusal("ISSUE_OBJECTIVE_SCOPE", str(exc)[:400])
            cluster, allowed, objective = "objective:%s" % oid, sorted(env["writable_paths"]), eu
        else:
            cluster, allowed = _allowed_paths(node, worklist, own)
        if not cluster and node.get("repair_paths"):
            cluster = planned_cluster_id(oid)
            allowed = sorted(node["repair_paths"])[:AMEND_MAX_FILES]
            unit = {"refusal": "", "paths": allowed, "basis": "owner repair"}
        elif not cluster and (node.get("planned_units") or node.get("requirements")):
            # compatibility-objectives/v1: a requirement outcome whose planned checks already hold
            # on an accepted tree is satisfied, not handed a unit with nothing to repair
            if node.get("check_plan") and not _changes_requested_since_accept(board, task_id):
                satisfied, unsatisfied = _satisfied(root, board, run, plan, node, worklist, tree, head)
            if satisfied is None:
                from planner.outcome_graph import planned_unit_grant
                g = planned_unit_grant(node, plan.get("requirements") or [], exists=lambda rel: (root / rel).exists(),
                                       cluster_open=False)
                unit = dict(g)
                if not g.get("refusal"):
                    cluster = planned_cluster_id(oid)
                    allowed = sorted(g.get("paths") or [])
        if not cluster and _changes_requested_since_accept(board, task_id):
            paths = _rework_paths(root, board, task_id)
            if paths:
                cluster = "rework:%s:%d" % (oid, run_id)
                allowed = paths
                unit = {"refusal": "", "paths": paths, "basis": "reviewer requested changes"}
        if cluster:
            allowed = sorted(set(allowed) | amended_paths(board, task_id, cluster))
        elif satisfied is None and not (unit and unit.get("refusal")):
            satisfied, unsatisfied = _satisfied(root, board, run, plan, node, worklist, tree, head)
    fields = dict(outcome_id=oid, role=role, cluster=cluster, allowed_paths=allowed, baseline_commit=head, baseline_tree=tree,
                  budget_key=budget["key"], revision=int(plan["revision"]))
    rec = _unchanged_issue(board, task_id, run_id, fields) if replay_unchanged else None
    replayed = rec is not None
    if rec is None:
        seq = len([r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]) + 1
        rec = board.record(task_id, "issue", "issue:%d:%d" % (run_id, seq), run=int(run_id), seq=seq, **fields)
    seq = int(rec.get("seq") or 0)
    nxt = ""
    if satisfied is not None:
        # recorded once per native run (a replayed issue finds the key); judged later exactly like any
        # acceptance: outcome_acceptance re-measures it on the then-current tree
        board.record(task_id, "accept-commit", "accept-commit:%d:satisfied" % int(run_id), run=int(run_id), commit=head,
                     tree=tree, cluster="", outcome_accepted=True, measurement=satisfied["measurement"],
                     repair_evidence_gaps=[], satisfied_by=satisfied["by"])
        nxt = ("SATISFIED: %s is already satisfied on this measured tree %s: it owns no open obligation and its "
               "checks hold. Witness: the measurement recorded by %s (%s) at commit %s -- the record that measured this "
               "tree, not the change that satisfied it. Nothing to edit: run python3 .hermes/kernel/native_gate.py "
               "--root . handoff, then kanban_request_review reviewer=reviewer with its summary and metadata. Do not run "
               "brief.py or advance.py." % (
                   oid, tree[:12], satisfied["by"]["task"], satisfied["by"]["outcome"], str(satisfied["by"]["commit"] or "")[:12]))
    elif role == "repair" and not cluster:
        nxt = ("NOTHING ISSUED: %s has no open scope and is not satisfied (%s). kanban_block kind=needs_input naming "
               "these reasons." % (oid, "; ".join(([("planned unit refused: %s" % unit["refusal"])] if unit and unit.get("refusal") else [])
                                         + unsatisfied[:3]) or "no reason measured"))
    if replayed:
        nxt = ("ALREADY ISSUED: issue %d of this run is unchanged (same scope, baseline, budget and plan revision; nothing "
               "recorded since), so nothing new was recorded. To inspect it, read verification/loop/issued.json or run "
               "brief.py; issuing again changes nothing. %s" % (seq, nxt)).strip()
    return {"issue_id": seq, "replayed": replayed, "next": nxt, "satisfied": satisfied, "task_id": task_id, "run_id": int(run_id), "outcome_id": oid, "role": role,
            "cluster": cluster, "allowed_paths": allowed, "budget": budget, "retained_candidate": bool(pending),
            "objective": objective,
            "planned_unit": (dict(unit, owed=unit.get("owed") or [], bounds=unit.get("bounds") or {},
                                  kind=_unit_kind(node)) if unit else None),
            "held_candidate": bool(board.records(task_id, "owner-hold")) and not board.records(task_id, "restore-held"),
            "parked_candidate": bool(parked_pending(board, task_id)),
            "run": run, "baseline_commit": head, "baseline_tree": tree, "claimed_control": False,
            "control": "native-cooperative", "record": rec["key"],
            "amendments": [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {}}
                           for a in board.records(task_id, "amend") if a.get("cluster") == cluster] if cluster else []}


def _unchanged_issue(board: Board, task_id: str, run_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    """This run's latest issue record when a repeated issue would record the same thing again: the same
    outcome, role, scope, baseline, budget key and plan revision, and no domain record of any kind written
    on the task since it (a verdict, an acceptance, an amendment, a park all make the next issue a new one).
    v26 t_7c356ade issued seven times in forty seconds while reading the output: seven identical records,
    each with its own key, for one unchanged authority."""
    recs = board.records(task_id)
    mine = [r for r in recs if r.get("kind") == "issue" and int(r.get("run") or 0) == int(run_id)]
    if not mine:
        return None
    last = mine[-1]
    if any(int(r.get("_id") or 0) > int(last.get("_id") or 0) for r in recs):
        return None
    if any(last.get(k) != v for k, v in fields.items()):
        return None
    return last


def active_issue(board: Board, task_id: str, run_id: int) -> dict[str, Any]:
    """The latest issue of THIS native run, revalidated against the board."""
    live_run(board, task_id, run_id)
    rows = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]
    if not rows:
        raise Refusal("ISSUE_MISSING", "no issue for %s run %s; run python3 .hermes/kernel/native_gate.py --root . issue "
                                       "after the claim" % (task_id, run_id))
    return rows[-1]


def amended_paths(board: Board, task_id: str, cluster: str) -> set[str]:
    return {str(a["path"]) for a in board.records(task_id, "amend") if a.get("cluster") == cluster}


def amend(root: Path, board: Board, *, task_id: str, run_id: int, cluster: str, rel: str, row: dict[str, Any]) -> dict[str, Any]:
    """Scope amendment (amend-scope.py validated evidence and locus): the same
    bounds as before, then a keyed ``amend`` record and a fresh issue."""
    iss = active_issue(board, task_id, run_id)
    rel = norm_rel(rel)
    if str(iss.get("cluster") or "") != cluster:
        raise Refusal("AMEND_FOREIGN_CLUSTER", "the issue for this run is cluster %r, not %r" % (iss.get("cluster"), cluster))
    if rel in set(iss.get("allowed_paths") or []):
        return {"path": rel, "already": True, "allowed_paths": iss["allowed_paths"]}
    if not _is_product(rel) or rel == "pom.xml" or (rel.startswith("src/test/") and not rel.endswith((".properties", ".yaml", ".yml"))):
        raise Refusal("AMEND_PATH", "%s is not a path an amendment may reach" % rel)
    if len(str(row.get("reason") or "").strip()) < 12 or not str(row.get("locus") or "").strip():
        raise Refusal("AMEND_UNEVIDENCED", "an amendment carries a reason and the locus the validator established")
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""), only=[rel])
    if changed is None or changed:
        raise Refusal("AMEND_ALREADY_EDITED", "%s has already been edited; an amendment authorizes a change before it happens" % rel)
    prior = [a for a in board.records(task_id, "amend") if a.get("cluster") == cluster]
    if len(prior) >= AMEND_LIMIT:
        raise Refusal("AMEND_LIMIT", "cluster %s already carries %d amendment(s) (limit %d)" % (cluster, len(prior), AMEND_LIMIT))
    allowed = sorted(set(iss.get("allowed_paths") or []) | {rel})
    if len(allowed) > AMEND_MAX_FILES:
        raise Refusal("AMEND_OVERSIZE", "%d files exceed the unit bound %d" % (len(allowed), AMEND_MAX_FILES))
    board.record(task_id, "amend", "amend:%s:%s" % (cluster, rel), cluster=cluster, path=rel, run=int(run_id),
                 reason=str(row.get("reason") or "")[:500], locus=str(row.get("locus") or "")[:500], evidence=row.get("evidence") or {})
    seq = int(iss.get("seq") or 1) + len(prior) + 1
    board.record(task_id, "issue", "issue:%d:%d:amend:%s" % (run_id, seq, sha256(rel.encode())[:12]),
                 **{k: v for k, v in iss.items() if k not in ("kind", "key", "v", "_id", "allowed_paths", "seq")},
                 seq=seq, allowed_paths=allowed)
    return {"path": rel, "already": False, "allowed_paths": allowed, "issue_id": seq, "amendments": len(prior) + 1}


# ---------------------------------------------------------------------------
# hook checks
# ---------------------------------------------------------------------------

def check_write(board: Board, *, task_id: str, run_id: int, rel_paths: list[str]) -> None:
    """A product write outside this run's issued scope refuses; harness state
    is never tool-written."""
    for rel in rel_paths:
        r = norm_rel(rel)
        if any(r == d.rstrip("/") or r.startswith(d) for d in PROTECTED_DIRS):
            raise Refusal("STORE_WRITE_REFUSED", "%s is harness state; only its own entry points write it" % r)
    product = [r for r in (norm_rel(x) for x in rel_paths) if _is_product(r)]
    if not product:
        return
    iss = active_issue(board, task_id, run_id)
    allowed = set(iss.get("allowed_paths") or [])
    for r in product:
        if r not in allowed:
            raise Refusal("WRITE_OUTSIDE_ISSUE", "%s is not in the issued scope %s (%s)"
                          % (r, iss.get("cluster") or "(none)", ", ".join(sorted(allowed)) or "no product edits"))


def outcome_acceptance(root: Path, board: Board, task_id: str, plan: dict[str, Any], node: dict[str, Any]) -> tuple[bool, str]:
    """Is this repair outcome accepted ON THE CURRENT TREE? The latest
    acceptance record says so, it was measured on exactly this product tree,
    and no obligation the outcome owns is open in the measured work list."""
    recs = _accept_records(board, task_id)
    if not recs or not recs[-1].get("outcome_accepted"):
        return False, "no accepted measurement is recorded for %s" % node["outcome_id"]
    tree = _product_tree(root)
    if recs[-1].get("tree") != tree:
        return False, "%s was accepted on tree %s; the tree is now %s" % (node["outcome_id"], str(recs[-1].get("tree"))[:12], tree[:12])
    wl, why = load_worklist(root)
    if wl is None:
        return False, "completion is judged against the measured work list (%s)" % why
    still = sorted(open_obligations(wl) & owned(plan, node))
    if still:
        return False, "%s still owns open %s" % (node["outcome_id"], ", ".join(still[:5]))
    return True, "accepted on %s" % tree[:12]


def m4_acceptance(root: Path, board: Board, run_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    """The M4 the delivery stages are bound to: its task, its latest
    assessment, and whether that assessment is an accepted verdict."""
    bind = ""
    for n in plan.get("nodes") or []:
        if n.get("role") == "deliver" and n.get("stage") == "prepare":
            bind = str((n.get("binding") or {}).get("assessment") or "")
    node = _node(plan, bind) if bind else None
    tid = board.task_of(run_id, node) if node else ""
    rec = latest_assessment(board, tid) if tid else None
    verdict = str((rec or {}).get("verdict") or "")
    ok = verdict in DELIVERY_OK_VERDICTS
    return {"task": tid, "assessment": bind, "verdict": verdict, "candidate": str((rec or {}).get("candidate") or ""),
            "accepted": ok, "done": bool(tid and (board.task(tid) or {}).get("status") == "done"),
            "why": "" if ok else ("verdict %s" % (verdict or "unrecorded"))}


def m4_closure(root: Path, native: Any = None) -> dict[str, Any] | None:
    """The M4 closure an outcome-board/v2 run delivers from (m5_delivery):
    the M4 task done on an accepted verdict."""
    board = board_for(Path(root), native)
    run_id = run_id_of(Path(root), board)
    try:
        plan = board.plan(run_id)
    except Refusal:
        return None
    m4 = m4_acceptance(Path(root), board, run_id, plan)
    if not m4["done"] or not m4["accepted"]:
        return None
    return {"closed": True, "card": m4["task"], "verdict": m4["verdict"], "assessment": m4["assessment"]}


def run_id_of(root: Path, board: Board) -> str:
    """The run of this destination: the factory declaration's run id, else
    the key of the M2 plan revision."""
    decl = _read_json(Path(root) / "run-budget.json")
    rid = str((decl or {}).get("run_id") or "") if isinstance(decl, dict) else ""
    if rid:
        return rid
    m2 = board.m2_task()
    for a in board.native.attachments(m2) if m2 else []:
        if PLAN_NAME.match(str(a["filename"])):
            try:
                return str(json.loads(Path(a["stored_path"]).read_bytes())["plan"]["run_id"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return ""


def check_terminator(root: Path, board: Board, *, task_id: str, run_id: int, kind: str, profile: str,
                     audit_green: Callable[[], bool]) -> dict[str, Any] | None:
    """The domain decision on a native terminator of a v2 task. None: this
    task is neither the M2 control card nor a v2 node (the serial rules
    apply). kind: complete | request_review | block."""
    root = Path(root)
    if board.is_m2(task_id):
        if kind == "block":
            return {"action": "allow", "code": "BLOCK_ALLOWED"}
        _gate(root)
        run = run_id_of(root, board)
        from planner.native_publish import readback
        try:
            plan = board.plan(run)
        except Refusal as exc:
            raise Refusal("M2_PUBLICATION_INCOMPLETE", "%s: %s" % (exc.code, exc.detail)) from exc
        gaps = readback(board, plan)
        if gaps:
            raise Refusal("M2_READBACK", "; ".join(gaps[:4]))
        if kind == "complete":
            if profile != REVIEWER:
                raise Refusal("M2_TERMINATOR", "M2 ends with kanban_request_review reviewer=reviewer; the reviewer completes it")
            if not audit_green():
                raise Refusal("M2_AUDIT_RED", "the paved-road M2 audit has not exited 0 in this run")
            return {"action": "allow", "code": "M2_RELEASE"}
        return {"action": "allow", "code": "M2_REVIEW_ALLOWED"}
    if board.node_of(task_id) is None:
        return None
    if kind == "block":
        # a legal result: dependency waits, exhausted budgets, external blockers -- but a card
        # whose issued run leaves product edits in the shared tree parks them first
        issued = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id or 0)]
        live = int((board.task(task_id) or {}).get("current_run_id") or 0) == int(run_id or 0)
        if issued and live and board.node_of(task_id)[0] == "repair" and not refusal_stop(root, task_id, run_id):
            # only this run's own candidate counts: another card's edit in the shared tree is never
            # this card's to park (v21 t_051c4490: an ended session saw the next card's edit)
            head = _head(root)
            changed = _issued_changes(root, board, task_id, run_id, head) if head else None
            if changed:
                raise Refusal("BLOCK_LEAVES_CANDIDATE", "this run leaves product edits in the shared tree (%s): run "
                              "python3 .hermes/kernel/native_gate.py --root . park (it holds them on this card and restores "
                              "HEAD), then kanban_block" % ", ".join(changed[:4]))
        return {"action": "allow", "code": "BLOCK_ALLOWED"}
    _gate(root)
    role, run, oid, plan, node = node_context(board, task_id)
    if kind == "complete" and profile != REVIEWER:
        raise Refusal("NATIVE_TERMINATOR", "%s ends its implementation run with kanban_request_review reviewer=reviewer; "
                                           "the reviewer completes it after the domain gate" % oid)
    if role == "repair":
        waiting = repair_waiting(board, run, plan, task_id)
        if waiting:
            raise Refusal("OWNER_REPAIR_PENDING", "%s holds a candidate for the repair %s: end this run with "
                                                  "kanban_block kind=dependency" % (oid, waiting))
        ok, why = outcome_acceptance(root, board, task_id, plan, node)
        if not ok:
            raise Refusal("OUTCOME_NOT_ACCEPTED", "%s: a rejected or unfinished attempt keeps the outcome open" % why)
        if kind == "complete" and not audit_green():
            raise Refusal("OUTCOME_AUDIT_RED", "the paved-road M3 audit has not exited 0 in this reviewer run")
        return {"action": "allow", "code": "OUTCOME_%s_ALLOWED" % ("COMPLETE" if kind == "complete" else "REVIEW")}
    if role == "assess":
        rec = latest_assessment(board, task_id)
        if rec is None:
            raise Refusal("ASSESS_UNRECORDED", "no assessment record on %s (native_gate.py assessment-record)" % task_id)
        if rec.get("verdict") not in DELIVERY_OK_VERDICTS:
            raise Refusal("ASSESS_NOT_ACCEPTED", "the latest assessment is %s: M4 means verification ACCEPTED. Run "
                          "native_gate.py m4-repair and end this run with kanban_block kind=dependency" % rec.get("verdict"))
        if rec.get("candidate") != _product_tree(root):
            raise Refusal("ASSESS_STALE", "the assessment measured another candidate")
        unmet = unmet_deferred(root, board, plan, node, task_id)
        tests = [u for u in unmet if u.split(": ", 1)[0].endswith("|" + TEST_EXECUTION_CHECK)]
        runtime = [u for u in unmet if u not in tests]
        if runtime:
            raise Refusal("ASSESS_DEFERRED_CHECKS", "runtime checks deferred to M4 are not met: %s. Run native_gate.py "
                          "m4-repair (each becomes a follow-up of its owning outcome) and end this run with kanban_block "
                          "kind=dependency" % "; ".join(runtime[:4]))
        if tests:
            raise Refusal("ASSESS_TESTS_UNMEASURED", "the full test suite owed to M4 by %d outcome(s) has not passed on "
                          "this candidate (%s). Run run-verify.sh --mode acceptance on the candidate and record the "
                          "assessment again; a failing test becomes a work-list obligation of this candidate"
                          % (len(tests), tests[0][:220]))
        if kind == "complete" and not audit_green():
            raise Refusal("ASSESS_AUDIT_RED", "the paved-road M4 audit has not exited 0 in this reviewer run")
        return {"action": "allow", "code": "ASSESS_%s_ALLOWED" % ("COMPLETE" if kind == "complete" else "REVIEW")}
    # deliver
    m4 = m4_acceptance(root, board, run, plan)
    if not m4["accepted"] or m4["candidate"] != _product_tree(root):
        raise Refusal("DELIVER_STALE_CANDIDATE", "the delivery candidate is not the accepted M4 candidate (%s)" % (m4["why"] or "drift"))
    if kind == "request_review":
        active_issue(board, task_id, run_id)
        return {"action": "allow", "code": "DELIVER_REVIEW_ALLOWED"}
    if not audit_green():
        raise Refusal("DELIVER_AUDIT_RED", "the paved-road M5 audit has not exited 0 in this reviewer run")
    ok, facts, reasons = stage_evidence(root, board, run, plan, str(node.get("stage") or ""))
    if not ok:
        code = "STAGE_EVIDENCE_MISSING" if any(r.startswith("STAGE_EVIDENCE_MISSING") for r in reasons) else "STAGE_EVIDENCE_REFUSED"
        raise Refusal(code, "; ".join(reasons[:4]))
    return {"action": "allow", "code": "DELIVER_COMPLETE_ALLOWED"}


# ---------------------------------------------------------------------------
# attempts on the SAME outcome task
# ---------------------------------------------------------------------------

def _scope_gaps(root: Path, iss: dict[str, Any], commit: str = "") -> list[str]:
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""), commit)
    if changed is None:
        return ["the changed paths since baseline %s could not be measured" % str(iss.get("baseline_commit") or "none")[:12]]
    allowed = set(iss.get("allowed_paths") or [])
    return ["%s is outside the issued scope" % c for c in changed if c not in allowed]


def record_verdict(root: Path, board: Board, *, task_id: str, run_id: int, verdict: str, candidate: str, attempt: str,
                   reason: str = "", retained: dict[str, Any] | None = None) -> dict[str, Any]:
    """REVERTED / VERIFICATION_PENDING / ACCEPTED (accept-begin) of the issued scope."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    key = "%s:%s" % (run_id, attempt)
    if verdict == "REVERTED":
        recovered = owner_recovery(root, board, iss, task_id=task_id, run_id=run_id, candidate=candidate, key=key)
        if recovered is not None:
            return recovered
        rec = board.record(task_id, "reject", "reject:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                           candidate=candidate, reason=reason[:300])
        b = budget_state(board, run, plan, node)
        return {"verdict": verdict, "outcome_id": oid, "spent": b["spent"], "limit": b["limit"], "exhausted": b["exhausted"],
                "card": "stays open (same outcome task)", "record": rec["key"]}
    if verdict == "VERIFICATION_PENDING":
        board.record(task_id, "pending", "pending:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                     candidate=candidate, baseline_commit=iss.get("baseline_commit"), baseline_tree=iss.get("baseline_tree"),
                     retained=retained or {}, reason=reason[:300])
        return {"verdict": verdict, "outcome_id": oid, "spent": budget_state(board, run, plan, node)["spent"]}
    if verdict == "ACCEPTED":
        gaps = _scope_gaps(root, iss)
        if gaps:
            raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(gaps[:4]))
        board.record(task_id, "accept-begin", "accept-begin:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                     candidate=candidate, baseline_commit=iss.get("baseline_commit"))
        return {"verdict": verdict, "outcome_id": oid, "next": "commit, then accept-commit"}
    raise Refusal("VERDICT_UNKNOWN", verdict)


def _measure(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any], tree: str,
             measurement: dict[str, Any]) -> dict[str, Any]:
    from planner.requirement_checks import passed
    scenarios = [str(s) for s in measurement.get("scenarios") or []]
    open_now = open_obligations(worklist)
    ex = measurement.get("execution") if isinstance(measurement.get("execution"), dict) else None
    m = {"tree": tree, "classes": sorted(set(measurement.get("classes") or [])), "scenarios": sorted(set(scenarios)),
         "open_owned": sorted(open_now & owned(plan, node)), "open_count": len(open_now),
         "classes_asserted_by": "verification execution" if ex is not None else "worker-receipts"}
    if ex is not None:
        m["execution"] = {k: {"state": v.get("state"), "detail": v.get("detail")} for k, v in (ex.get("stages") or {}).items()}
        m["execution_tree"] = str(ex.get("tree") or "")
        m["execution_bound"] = bool(ex.get("bound"))
    checks = requirement_measurement(root, plan, node, worklist, scenarios, tree)
    if checks and node.get("check_plan"):
        # compatibility-objectives/v1: judged per (requirement, check); a check
        # name passes only when it passes for every requirement that uses it
        from planner.outcome_checks import requirement_matrix
        matrix = requirement_matrix(root, plan, node, worklist, scenarios, tree)
        m["check_matrix"] = {rq: {c: v.get("status") for c, v in cs.items()} for rq, cs in matrix.items()}
        names = {c for cs in matrix.values() for c in cs}
        m["checks"] = sorted(c for c in names if all(cs[c].get("status") == "pass" for cs in matrix.values() if c in cs))
        m["unmet_checks"] = {"%s|%s" % (rq, c): {"status": v.get("status"), "detail": str(v.get("detail") or "")[:200]}
                             for rq, cs in sorted(matrix.items()) for c, v in sorted(cs.items()) if v.get("status") != "pass"}
        checks = None
    if checks:
        m["checks"] = passed(checks)
        # only the checks THIS outcome is judged by; a check deferred to M4 (a runtime check an early
        # outcome cannot measure) is named apart, never as a reason this card is not accepted
        kept = set(((node.get("acceptance") or {}).get("requirement_checks")) or [])
        m["unmet_checks"] = {k: {"status": v.get("status"), "detail": str(v.get("detail") or "")[:200]}
                             for k, v in sorted(checks.items()) if v.get("status") != "pass" and k in kept}
        deferred = sorted(k for k, v in checks.items() if k not in kept and v.get("status") != "pass")
        if deferred:
            m["deferred_to_m4"] = deferred
    # the classes the node's DECLARED acceptance still requires (a measure:tests
    # deferred to M4 at publication is not required here; see defer_runtime_checks)
    from planner.measurement import needed_classes
    need = needed_classes(node)
    missing = sorted(need - set(m["classes"]))
    if str(node.get("class") or "") == "behavior":
        missing += ["scenario %s" % x for x in sorted(set(node.get("scenarios") or []) - set(m["scenarios"]))]
    if missing:
        m["missing_classes"] = missing
    return m


def not_accepted_reasons(acc: dict[str, Any]) -> list[str]:
    """Why an acceptance record did not accept its outcome, each reason named:
    open owned obligations, unmet requirement checks with their measured
    detail, missing measurement classes, owner-repair evidence gaps."""
    m = acc.get("measurement") or {}
    out = ["open obligation %s" % o for o in (m.get("open_owned") or [])[:6]]
    out += ["check %s is %s: %s" % (k, v.get("status"), v.get("detail")) for k, v in (m.get("unmet_checks") or {}).items()]
    out += ["not measured: %s" % c for c in m.get("missing_classes") or []]
    out += ["repair evidence: %s" % g for g in acc.get("repair_evidence_gaps") or []]
    return out


UNRESOLVED_DETAIL = "could not fully resolve"


def _unmeasurable_yet(m: dict[str, Any]) -> list[str]:
    """This outcome's own checks that could not be measured ONLY because the
    file they judge does not fully resolve -- when every owned obligation is
    already gone, the unresolved diagnostics belong to OTHER outcomes (v21
    t_0bc6319b: SpringDataVisitRepositoryImpl could not resolve
    org.springframework.dao.DataAccessException, owned by the dao unit that
    waits on this card). Empty unless EVERY unmet check is of that kind."""
    if m.get("open_owned"):
        return []
    unmet = m.get("unmet_checks") or {}
    late = [k for k, v in unmet.items() if v.get("status") == "unknown" and UNRESOLVED_DETAIL in str(v.get("detail") or "")]
    return sorted(late) if late and len(late) == len(unmet) else []


def _covers_or_defers(board: Board, run: str, plan: dict[str, Any], node: dict[str, Any], m: dict[str, Any],
                      *, record: bool) -> bool:
    """_covers, where a check this outcome cannot measure YET (_unmeasurable_yet)
    is judged at M4 instead: recorded on every M4 task as a `defer-check`, read
    back by unmet_deferred, refused there (ASSESS_DEFERRED_CHECKS) until it passes."""
    if _covers(node, m):
        return True
    if node.get("check_plan") is not None:
        # compatibility-objectives/v1: prerequisites were planned at M2; an
        # immediate check that cannot pass yet stays pending, never moved to
        # M4 by what the worker happened to encounter
        return False
    late = _unmeasurable_yet(m)
    if not late or not _covers(node, dict(m, checks=sorted(set(m.get("checks") or []) | set(late)))):
        return False
    m["deferred_unresolved"] = late
    if record:
        oid = node["outcome_id"]
        for n in plan.get("nodes") or []:
            if n.get("role") != "assess":
                continue
            m4 = board.task_of(run, n)
            if not m4:
                continue
            for chk in late:
                board.record(m4, "defer-check", "defer-check:%s:%s" % (oid, chk), outcome=oid, check=chk,
                             requirements=sorted(node.get("requirements") or []),
                             reason=str(((m.get("unmet_checks") or {}).get(chk) or {}).get("detail") or "")[:300])
    return True


def accept_commit(root: Path, board: Board, *, task_id: str, run_id: int, attempt: str, commit: str,
                  measurement: dict[str, Any]) -> dict[str, Any]:
    """Record the committed acceptance of the issued scope and decide whether
    the OUTCOME is accepted: every owned obligation absent from the rebuilt
    work list and the outcome's check class measured on this tree."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    key = "%s:%s" % (run_id, attempt)
    begin = [r for r in board.records(task_id, "accept-begin") if r["key"] == "accept-begin:%s" % key]
    if not begin:
        raise Refusal("ACCEPT_UNBEGUN", "no accept-begin for attempt %s" % attempt)
    tree = _product_tree(root)
    if tree != begin[-1]["candidate"]:
        raise Refusal("ACCEPT_TREE_DRIFT", "the committed tree is not the verified candidate")
    if _head(root) != commit:
        raise Refusal("ACCEPT_COMMIT_MISMATCH", "HEAD is not the named commit %s" % commit[:12])
    parent = _git(root, "rev-parse", "--verify", "-q", "%s^1" % commit).stdout.strip()
    if not iss.get("baseline_commit") or parent != iss["baseline_commit"]:
        raise Refusal("ACCEPT_BASELINE_ANCESTRY", "commit %s is not a child of the issued baseline %s"
                      % (commit[:12], str(iss.get("baseline_commit") or "none")[:12]))
    gaps = _scope_gaps(root, iss, commit)
    if gaps:
        raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(gaps[:4]))
    wl, why = load_worklist(root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    m = _measure(root, plan, node, wl, tree, measurement)
    evidence_gaps = repair_evidence_gaps(root, node, tree)
    covered = _covers_or_defers(board, run, plan, node, m, record=not evidence_gaps)
    done = not m["open_owned"] and covered and not evidence_gaps
    board.record(task_id, "accept-commit", "accept-commit:%s" % key, run=int(run_id), commit=commit, tree=tree,
                 cluster=iss.get("cluster") or "", outcome_accepted=done, measurement=m, repair_evidence_gaps=evidence_gaps)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"],
            "covered": covered, "repair_evidence_gaps": evidence_gaps,
            "not_accepted_because": [] if done else not_accepted_reasons({"measurement": m, "repair_evidence_gaps": evidence_gaps})}


def recover_accept(root: Path, board: Board, *, task_id: str, skip_run: int | None = None,
                   commits: Callable[[str], list[tuple[str, str, str]]] | None = None) -> list[dict[str, Any]]:
    """After a crash between accept-begin and accept-commit: the commit whose
    parent is the recorded baseline and whose product tree is the candidate is
    recorded (recovered); none aborts to a retained candidate. Never spends,
    never commits again."""
    commits = commits or git_commits_after(Path(root))
    closed = {r["key"].split(":", 1)[1] for r in board.records(task_id) if r["kind"] in ("accept-commit", "accept-aborted")}
    out = []
    for r in board.records(task_id, "accept-begin"):
        attempt_key = r["key"].split(":", 1)[1]
        if attempt_key in closed or (skip_run is not None and int(r.get("run") or 0) == int(skip_run)):
            continue
        hits = [s for s, parent, tree in commits(str(r.get("baseline_commit") or ""))
                if parent == r.get("baseline_commit") and tree == r.get("candidate")]
        if len(hits) > 1:
            raise Refusal("ACCEPT_RECOVERY_AMBIGUOUS", "%d commits carry candidate %s; the acceptance of attempt %s is not guessed"
                          % (len(hits), str(r.get("candidate"))[:12], attempt_key))
        if len(hits) == 1:
            board.record(task_id, "accept-commit", "accept-commit:%s" % attempt_key, run=int(r.get("run") or 0),
                         commit=hits[0], tree=r.get("candidate"), cluster=r.get("cluster") or "", recovered=True,
                         outcome_accepted=False)
            out.append({"attempt": attempt_key, "recovered_commit": hits[0]})
        else:
            board.record(task_id, "accept-aborted", "accept-aborted:%s" % attempt_key, run=int(r.get("run") or 0),
                         why="no commit carries the candidate")
            board.record(task_id, "pending", "pending:%s:aborted" % attempt_key, run=int(r.get("run") or 0),
                         candidate=r.get("candidate"), baseline_commit=r.get("baseline_commit"),
                         reason="acceptance interrupted before commit; candidate retained")
            out.append({"attempt": attempt_key, "aborted": True})
    return out


def evaluate_unchanged_rework(root: Path, board: Board, *, task_id: str, run_id: int,
                              measurement: dict[str, Any]) -> dict[str, Any] | None:
    """A reviewer's change request answered with NO product change (v24 run
    t_e2932aa0: the request was procedural -- a missing skill_view line -- and
    the product was already accepted). The outcome is judged again ON THE
    CURRENT TREE, exactly as an acceptance is judged, and recorded as
    accept-evaluated: nothing is committed, no attempt is spent, and the old
    tree's acceptance is never carried over to a tree other cards have moved.

    None unless: the issued unit is a rework unit, changes were requested since
    the task's last accepted outcome, and none of the paths that task's own
    accepted commits changed differs from the last accepted commit (committed
    or in the working tree). A changed candidate takes the normal path."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    if not str(iss.get("cluster") or "").startswith("rework:") or not _changes_requested_since_accept(board, task_id):
        return None
    rows = _accept_records(board, task_id)
    accepted = [r for r in rows if r.get("outcome_accepted") and r.get("commit")]
    if not accepted:
        return None
    base = str(accepted[-1]["commit"])
    paths = _rework_paths(root, board, task_id)
    if not paths:
        return None
    if _git(root, "diff", "--quiet", base, "--", *paths).returncode != 0:
        return None          # committed or uncommitted change to the task's own paths: judged normally
    role, run, oid, plan, node = node_context(board, task_id)
    tree = _product_tree(root)
    wl, why = load_worklist(root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    m = _measure(root, plan, node, wl, tree, measurement)
    gaps = repair_evidence_gaps(root, node, tree)
    covered = _covers_or_defers(board, run, plan, node, m, record=not gaps)
    done = not m["open_owned"] and covered and not gaps
    board.record(task_id, "accept-evaluated", "accept-evaluated:rework:%d:%d" % (int(run_id), len(rows)),
                 run=int(run_id), commit=base, tree=tree, outcome_accepted=done, measurement=m,
                 basis="rework-unchanged", accepted_commit=base, repair_evidence_gaps=gaps)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"], "covered": covered,
            "commit": base,
            "not_accepted_because": [] if done else not_accepted_reasons({"measurement": m, "repair_evidence_gaps": gaps})}


def evaluate_recovered(root: Path, board: Board, *, task_id: str, run_id: int, measurement: dict[str, Any]) -> dict[str, Any] | None:
    """Finish an acceptance that recovery recorded: the recovered commit is
    the current tree, re-measured, judged exactly as accept_commit judges.
    None when there is nothing to finish."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    rows = _accept_records(board, task_id)
    if not rows or rows[-1].get("outcome_accepted"):
        return None
    last = rows[-1]
    tree = _product_tree(root)
    if not last.get("recovered"):
        # the latest acceptance did not accept the outcome and the tree has not moved since:
        # it is judged again under the current rules (v21 t_0bc6319b: a check that could not
        # be measured became decidable after an Operator correction) -- no commit, no attempt
        if tree != last.get("tree"):
            return None
    elif tree != last.get("tree"):
        raise Refusal("ACCEPT_TREE_DRIFT", "the tree is not the recovered commit's tree")
    wl, why = load_worklist(root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    m = _measure(root, plan, node, wl, tree, measurement)
    gaps = repair_evidence_gaps(root, node, tree)
    covered = _covers_or_defers(board, run, plan, node, m, record=not gaps)
    done = not m["open_owned"] and covered and not gaps
    # one record per evaluation: a later evaluation under corrected rules is a new verdict, not a replay
    board.record(task_id, "accept-evaluated", "accept-evaluated:%s:%d" % (last["key"].split(":", 1)[1], len(rows)),
                 run=int(run_id),
                 commit=last.get("commit"), tree=tree, outcome_accepted=done, measurement=m)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"], "covered": covered,
            "commit": last.get("commit"),
            "not_accepted_because": [] if done else not_accepted_reasons({"measurement": m, "repair_evidence_gaps": gaps})}


def restore_pending(root: Path, board: Board, *, task_id: str, run_id: int, candidate_now: str) -> dict[str, Any]:
    iss = active_issue(board, task_id, run_id)
    pend = _open_pending(board, task_id)
    if pend is None:
        raise Refusal("RESTORE_NO_PENDING", "no retained candidate on %s" % task_id)
    if candidate_now != pend.get("candidate"):
        raise Refusal("RESTORE_DIGEST", "the restored tree is not the retained candidate")
    moved = str(iss.get("baseline_commit") or "") != str(pend.get("baseline_commit") or "")
    board.record(task_id, "restore", "restore:%s:%s" % (run_id, pend["key"]), run=int(run_id), candidate=candidate_now,
                 original_baseline=pend.get("baseline_commit"), current_baseline=iss.get("baseline_commit"),
                 baseline_moved=moved, closes_pending=False)
    return {"outcome_id": iss.get("outcome_id"), "baseline_moved": moved}


# ---------------------------------------------------------------------------
# automatic owner recovery on native tasks
# ---------------------------------------------------------------------------

def accepted_steps(root: Path, board: Board, run_id: str) -> list[dict[str, Any]]:
    """Every committed acceptance on the board, oldest first (board-wide
    comment order), with the paths each commit changed."""
    rows = []
    for oid, t in board.run_tasks(run_id).items():
        for r in board.records(t["id"], "accept-commit"):
            if r.get("commit"):
                rows.append((r["_id"], oid, t["id"], r))
    out = []
    for _id, oid, tid, r in sorted(rows):
        commit = str(r["commit"])
        out.append({"cluster": str(r.get("cluster") or oid), "card": tid, "commit": commit, "verdict": "accepted",
                    "outcome_id": oid, "changed": changed_product_paths(root, commit + "^1", commit) or []})
    return out


def _classify(root: Path, board: Board, run_id: str, plan: dict[str, Any], iss: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from planner import runtime_cause as RC
    except ImportError:
        return None
    from planner.paths import LOOP_ACCEPTED, PARITY_DIR
    wl, _why = load_worklist(root)
    wl = wl or {"items": [], "clusters": []}
    row = next((c for c in wl.get("clusters") or [] if isinstance(c, dict) and c.get("id") == iss.get("cluster")), {})
    node = _node(plan, str(iss.get("outcome_id") or "")) or {}
    issued = {"cluster": iss.get("cluster") or "", "task_id": "", "items": list(row.get("items") or []), "gate_items": [],
              "scenarios": list(node.get("scenarios") or []), "entry_points": list(node.get("entry_points") or []),
              "write_set": list(iss.get("allowed_paths") or []), "amendments": []}
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or "")) or []
    cur = {"failures": RC.failures_of(wl, issued, RC.scenario_records(root / PARITY_DIR)), "changed": changed}
    if not cur["failures"]:
        return None
    baseline = {"tree": str(iss.get("baseline_tree") or ""), "records": RC.scenario_records(root / LOOP_ACCEPTED / "parity")}
    try:
        out = RC.classify(root, issued, cur, accepted_steps(root, board, run_id), baseline)
    except Exception as exc:  # a classifier failure is no evidence of anything
        return {"class": "ambiguous", "owner": None, "evidence": [], "reason": "classifier failed: %s" % type(exc).__name__}
    if isinstance(out, dict):
        out = dict(out, failing_scenarios=sorted({str(f.get("scenario") or "") for f in cur["failures"]} - {""}),
                   baseline_tree=baseline["tree"])
    return out if isinstance(out, dict) else None


def _hold_files(root: Path, iss: dict[str, Any]) -> dict[str, str] | None:
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""))
    if changed is None or not set(changed) <= set(iss.get("allowed_paths") or []):
        return None
    out: dict[str, str] = {}
    size = 0
    for rel in changed:
        p = root / rel
        data = p.read_bytes() if p.is_file() and not p.is_symlink() else b""
        size += len(data)
        out[rel] = base64.b64encode(data).decode("ascii") if p.exists() else ""
    return out if size <= HOLD_MAX_BYTES else None


def owner_recovery(root: Path, board: Board, iss: dict[str, Any], *, task_id: str, run_id: int, candidate: str,
                   key: str) -> dict[str, Any] | None:
    """None = the ordinary rejection applies. A validated owner defect: the
    candidate is HELD (a versioned attachment on this task, no attempt spent),
    ONE bounded repair of the owner is published as a native task, linked as a
    prerequisite of this task (and of the open M4), and this run ends with
    kanban_block kind=dependency. Native promotion resumes it."""
    role, run, oid, plan, node = node_context(board, task_id)
    res = _classify(root, board, run, plan, iss)
    if res is None:
        return None
    cls = str(res.get("class") or "")
    why = ""
    if cls not in CAUSE_CLASSES:
        why = "classifier answered %r" % cls
    elif cls != OWNER_DEFECT:
        why = "%s: %s" % (cls, str(res.get("reason") or "")[:200])
    owner_doc = res.get("owner") if isinstance(res.get("owner"), dict) else {}
    owner = str(owner_doc.get("outcome_id") or "")
    evidence = res.get("evidence") if isinstance(res.get("evidence"), list) else []
    onode = _node(plan, owner) if owner else None
    fid = owner_repair_id(owner, oid) if owner else ""
    if not why:
        otask = board.task_of(run, onode) if onode else ""
        base_rows = [e for e in evidence if isinstance(e, dict) and e.get("kind") == "baseline-record"]
        if not onode or owner == oid or onode.get("role") != "repair" or (board.task(otask) or {}).get("status") != "done":
            why = "owner %r is not another accepted (done) repair outcome" % owner
        elif not base_rows or not any(e.get("kind") == "baseline-failure" for e in evidence):
            why = "no evidence names the failure on the baseline"
        elif any(e.get("baseline_tree") != iss.get("baseline_tree") or e.get("bound_to") != iss.get("baseline_tree")
                 for e in base_rows):
            why = "the evidence names another baseline than the issued one"
        elif not res.get("failing_scenarios"):
            why = "no failing scenario to re-measure after the repair"
        elif budget_state(board, run, plan, onode)["exhausted"]:
            why = "the owner's budget %s is exhausted" % (onode.get("budget") or {}).get("key")
        elif _node(plan, fid) is not None or any(h.get("repair") == fid for h in board.records(task_id, "owner-hold")):
            why = "the one bounded repair of %s for %s was already scheduled" % (owner, oid)
    held = _hold_files(root, iss) if not why else None
    if not why and held is None:
        why = "the candidate cannot be held (outside the issue, unmeasurable or too large)"
    if why:
        if cls in CAUSE_CLASSES and cls != "candidate-regression":
            board.record(task_id, "cause-report", "cause:%s" % key, run=int(run_id), cls=cls, owner=owner, why=why[:300])
        return None
    # the held candidate: an attachment (the bytes), then the keyed record naming it
    name = "held.%s.json" % sha256(key.encode())[:12]
    data = canonical_bytes({"schema": "rhoai3.native-held/v1", "task": task_id, "run": int(run_id), "candidate": candidate,
                            "baseline_commit": iss.get("baseline_commit"), "files": held})
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-held-") as td:
            p = Path(td) / name
            p.write_bytes(data)
            board.native.attach(task_id, str(p), name)
    owner_task = board.task_of(run, onode)
    last_issue = next((r for r in reversed(board.records(owner_task, "issue")) if r.get("allowed_paths")), None)
    repair_paths = sorted(set((last_issue or {}).get("allowed_paths") or []) | set(owner_doc.get("paths") or []))[:AMEND_MAX_FILES]
    hold = board.record(task_id, "owner-hold", "owner-hold:%s" % key, run=int(run_id), owner=owner, repair=fid,
                        candidate=candidate, attachment=name, sha256=sha256(data), baseline_commit=iss.get("baseline_commit"),
                        repair_paths=repair_paths, repair_scenarios=list(res.get("failing_scenarios") or []),
                        budget={"key": (onode.get("budget") or {}).get("key"), "limit": (onode.get("budget") or {}).get("limit")},
                        reason=str(res.get("reason") or "")[:300], evidence=evidence[:6])
    _publish_owner_repair(root, board, run, plan, hold)
    return {"verdict": "OWNER_RECOVERY", "outcome_id": oid, "owner": owner, "repair": fid, "spent": budget_state(board, run, plan, node)["spent"],
            "limit": int((node.get("budget") or {}).get("limit") or 0), "exhausted": False, "held_paths": sorted(held),
            "card": "stays open; revert the tree and end this run with kanban_block kind=dependency"}


def _publish_owner_repair(root: Path, board: Board, run_id: str, plan: dict[str, Any], hold: dict[str, Any]) -> None:
    """The revision adding the owner repair, attached to the dependent, then
    the repair task and its links (repair -> dependent, repair -> open M4).
    Every step is looked up before it is repeated."""
    from planner.native_publish import publish_revision
    dep_task = ""
    for oid, row in board.run_tasks(run_id).items():
        if any(h["key"] == hold["key"] for h in board.records(row["id"], "owner-hold")):
            dep_task = row["id"]
            dep = oid
            break
    if not dep_task:
        raise Refusal("OWNER_HOLD_LOST", "the owner-hold record %s is on no task of run %s" % (hold["key"], run_id))
    doc = {"owner": hold["owner"], "dependent": dep, "evidence": hold.get("evidence") or [], "reason": hold.get("reason") or "",
           "repair_paths": hold.get("repair_paths") or [], "repair_scenarios": hold.get("repair_scenarios") or [],
           "budget": hold.get("budget") or {}}
    tasks = board.run_tasks(run_id)
    open_assess = {n["outcome_id"] for n in plan["nodes"] if n.get("role") == "assess"
                   and (board.task(tasks.get(n["outcome_id"], {}).get("id", "")) or {}).get("status") != "done"}
    nxt = owner_repair_revision(plan, doc, open_assessments=open_assess)
    if isinstance(nxt, Refusal):
        raise nxt
    if nxt is not None:
        nxt = native_revision(nxt)
    if nxt is None:                      # replay: the revision already carries it; finish its publication
        publish_revision(root, board, plan, added=[hold["repair"]], holder=dep_task)
        return
    publish_revision(root, board, nxt, added=[hold["repair"]], holder=dep_task)


def restore_held(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """The held candidate (after its owner's repair), for the caller to write
    back and re-verify on the repaired baseline: only paths the CURRENT issue
    allows. No acceptance is carried over."""
    iss = active_issue(board, task_id, run_id)
    holds = board.records(task_id, "owner-hold")
    if not holds:
        raise Refusal("RESTORE_NO_HOLD", "no held candidate on %s" % task_id)
    h = holds[-1]
    got = board.attachment(task_id, str(h.get("attachment") or ""))
    if got is None or sha256(got[0]) != h.get("sha256"):
        raise Refusal("RESTORE_HELD_CORRUPT", "the held candidate %s is missing or differs from its record" % h.get("attachment"))
    files = json.loads(got[0]).get("files") or {}
    outside = sorted(set(files) - set(iss.get("allowed_paths") or []))
    if outside:
        raise Refusal("RESTORE_OUTSIDE_ISSUE", "held paths %s are outside the current issue" % ", ".join(outside[:3]))
    board.record(task_id, "restore-held", "restore-held:%s" % h["key"], run=int(run_id), files=sorted(files))
    return {"outcome_id": iss.get("outcome_id"), "files": files, "owner": h.get("owner"),
            "baseline_then": h.get("baseline_commit"), "baseline_now": iss.get("baseline_commit")}


# ---------------------------------------------------------------------------
# park: a card's unjudged candidate never stays in the shared tree
# ---------------------------------------------------------------------------

def _changed_vs_head(root: Path) -> tuple[str, list[str]]:
    head = _head(root)
    changed = changed_product_paths(root, head) if head else None
    if changed is None:
        raise Refusal("PARK_UNMEASURABLE", "the product changes against HEAD could not be measured")
    return head, changed


def _issued_changes(root: Path, board: Board, task_id: str, run_id: int, head: str) -> list[str] | None:
    """Product paths changed against HEAD that THIS native run was issued (the
    union of its issue records' allowed_paths). None when unmeasurable."""
    mine = {p for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)
            for p in (r.get("allowed_paths") or [])}
    changed = changed_product_paths(root, head)
    return None if changed is None else [c for c in changed if c in mine]


def park(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """Hold this card's uncommitted product candidate as a versioned
    attachment on the card and restore the product tree to HEAD, so the next
    card starts from the accepted state (v20: a verified-but-unjudged pom.xml
    left in the tree made every later card refuse ISSUE_BASELINE_DRIFT).
    The candidate is restored by ``restore-parked`` when this card resumes."""
    root = Path(root)
    live_run(board, task_id, run_id)
    node_context(board, task_id)
    head, _all = _changed_vs_head(root)
    changed = [c for c in _all if c in set(_issued_changes(root, board, task_id, run_id, head) or [])]
    if not changed:
        return {"parked": [], "note": "no edit of a path this run was issued differs from HEAD %s" % head[:12]}
    files: dict[str, str] = {}
    for rel in changed:
        p = root / rel
        files[rel] = base64.b64encode(p.read_bytes()).decode("ascii") if p.is_file() and not p.is_symlink() else ""
    data = canonical_bytes({"schema": "rhoai3.native-parked/v1", "task": task_id, "run": int(run_id), "head": head,
                            "candidate": _product_tree(root), "files": files})
    digest = sha256(data)
    name = "parked.%d.%s.json" % (int(run_id), digest[:12])
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-park-") as td:
            f = Path(td) / name
            f.write_bytes(data)
            board.native.attach(task_id, str(f), name)
    rec = board.record(task_id, "park", "park:%d:%s" % (int(run_id), digest[:16]), run=int(run_id), head=head,
                       attachment=name, sha256=digest, paths=sorted(files))
    for rel in changed:
        tracked = _git(root, "cat-file", "-e", "%s:%s" % (head, rel)).returncode == 0
        if tracked:
            _git(root, "checkout", head, "--", rel)
        elif (root / rel).exists():
            (root / rel).unlink()
    left = [c for c in (_changed_vs_head(root)[1]) if c in set(changed)]
    if left:
        raise Refusal("PARK_INCOMPLETE", "the tree still differs from HEAD at %s" % ", ".join(left[:4]))
    return {"parked": sorted(files), "attachment": name, "record": rec["key"], "head": head}


def parked_pending(board: Board, task_id: str) -> dict[str, Any] | None:
    restored = {r.get("park") for r in board.records(task_id, "restore-parked")}
    rows = [r for r in board.records(task_id, "park") if r["key"] not in restored]
    return rows[-1] if rows else None


def restore_parked(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """Put this card's parked candidate back (paths of the current issue
    only); it is re-verified, never carried over as accepted."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    rec = parked_pending(board, task_id)
    if rec is None:
        raise Refusal("RESTORE_NO_PARK", "no parked candidate on %s" % task_id)
    got = board.attachment(task_id, str(rec.get("attachment") or ""))
    if got is None or sha256(got[0]) != rec.get("sha256"):
        raise Refusal("RESTORE_PARK_CORRUPT", "the parked candidate %s is missing or differs from its record" % rec.get("attachment"))
    files = json.loads(got[0]).get("files") or {}
    outside = sorted(set(files) - set(iss.get("allowed_paths") or []))
    if outside:
        raise Refusal("RESTORE_OUTSIDE_ISSUE", "parked paths %s are outside the current issue" % ", ".join(outside[:3]))
    for rel, b64 in sorted(files.items()):
        p = root / rel
        if b64:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(base64.b64decode(b64))
        elif p.exists():
            p.unlink()
    board.record(task_id, "restore-parked", "restore-parked:%s" % rec["key"], run=int(run_id), park=rec["key"],
                 files=sorted(files))
    return {"restored": sorted(files), "from": rec["key"], "head_then": rec.get("head"), "head_now": _head(root)}


# ---------------------------------------------------------------------------
# repeated refusals: the third identical refusal in a run names the terminator
# ---------------------------------------------------------------------------

def note_refusal(root: Path, task_id: str, run_id: int, code: str) -> int:
    """Count identical refusals of this task's current run (v20 t_686c715b ran
    the same refused command 181 times). Returns the count."""
    if not task_id:
        return 0
    p = Path(root) / REFUSALS / ("%s.json" % task_id)
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError):
        doc = {}
    if doc.get("run") != int(run_id) or doc.get("code") != code:
        doc = {"run": int(run_id), "code": code, "count": 0}
    doc["count"] = int(doc.get("count") or 0) + 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))
    return doc["count"]


def refusal_stop(root: Path, task_id: str, run_id: int) -> dict[str, Any] | None:
    """The recorded stop for this run, when its last refusal repeated REPEAT_LIMIT times."""
    try:
        doc = json.loads((Path(root) / REFUSALS / ("%s.json" % task_id)).read_text())
    except (OSError, ValueError):
        return None
    return doc if doc.get("run") == int(run_id) and int(doc.get("count") or 0) >= REPEAT_LIMIT else None


# ---------------------------------------------------------------------------
# M4: verification ACCEPTED, or repairs as prerequisites of the same task
# ---------------------------------------------------------------------------

def deferred_checks_status(root: Path, plan: dict[str, Any], node: dict[str, Any], scenarios: list[str],
                           tree: str, extra: list[dict[str, Any]] | None = None) -> dict[str, dict[str, str]]:
    """The runtime checks deferred to this M4 (defer_runtime_checks), measured
    on the current tree exactly as the owning outcome's checks are
    (requirement_measurement): '<outcome>|<check>' -> {status, detail}."""
    rows = list(((node.get("acceptance") or {}).get("deferred_requirement_checks")) or []) + list(extra or [])
    if not rows:
        return {}
    wl, why = load_worklist(root)
    out: dict[str, dict[str, str]] = {}
    tests: tuple[str, str] | None = None
    for d in rows:
        key = "%s|%s" % (d.get("outcome"), d.get("check"))
        if wl is None:
            out[key] = {"status": "unknown", "detail": "no measured work list (%s)" % why}
            continue
        if d.get("check") == TEST_EXECUTION_CHECK:
            # the full suite, executed on THIS candidate by the verification
            # that produced the work list (planner.measurement); a tuple's 0
            # on a tree that did not compile is not a passing suite
            if tests is None:
                from planner.measurement import execution, tests_status
                from planner.paths import VERIFY_RUN
                try:
                    run_doc = json.loads((Path(root) / VERIFY_RUN).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    run_doc = {}
                tests = tests_status(execution(wl, run_doc, tree, root))
            out[key] = {"status": tests[0], "detail": tests[1]}
            continue
        pseudo = {"outcome_id": d.get("outcome"), "requirements": list(d.get("requirements") or []),
                  "acceptance": {"requirement_checks": [d.get("check")]}}
        got = requirement_measurement(root, plan, pseudo, wl, scenarios, tree) or {}
        out[key] = dict(got.get(d.get("check")) or {"status": "unknown", "detail": "not measured"})
    return out


def unmet_deferred(root: Path, board: Board, plan: dict[str, Any], node: dict[str, Any], task_id: str) -> list[str]:
    rec = latest_assessment(board, task_id)
    scen = []
    if rec:
        try:
            scen = list(_assessment_doc(board, task_id, rec).get("parity_scenarios") or [])
        except Refusal:
            scen = []
    extra = [{"outcome": r.get("outcome"), "requirements": list(r.get("requirements") or []), "check": r.get("check")}
             for r in board.records(task_id, "defer-check")]
    st = deferred_checks_status(root, plan, node, scen, _product_tree(root), extra=extra)
    return ["%s: %s (%s)" % (k, v.get("status"), str(v.get("detail") or "")[:160]) for k, v in sorted(st.items())
            if v.get("status") != "pass"]


def latest_assessment(board: Board, task_id: str) -> dict[str, Any] | None:
    rows = board.records(task_id, "assessment")
    return rows[-1] if rows else None


def record_assessment(root: Path, board: Board, *, task_id: str, run_id: int, verdict_doc: dict[str, Any]) -> dict[str, Any]:
    """The M4 measurement of this run: the verdict (bound to this task), the
    candidate tree and the open obligations the rebuilt work list names, as
    a versioned attachment plus a keyed record."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "assess":
        raise Refusal("ASSESS_FOREIGN", "%s is not an assessment" % oid)
    if str(verdict_doc.get("card_id") or "") != task_id:
        raise Refusal("ASSESS_UNBOUND", "the verdict names card %r, not %s" % (verdict_doc.get("card_id"), task_id))
    token = str(verdict_doc.get("verdict") or verdict_doc.get("token") or "").upper()
    if not token:
        raise Refusal("ASSESS_UNBOUND", "the verdict carries no token")
    wl, why = load_worklist(root)
    tree = _product_tree(root)
    obligations = []
    if wl is not None:
        clusters = {str(i): c for c in wl.get("clusters") or [] for i in c.get("items") or []}
        for it in wl.get("items") or []:
            if it.get("category") == "mandatory":
                c = clusters.get(str(it["id"])) or {}
                obligations.append({"id": it["id"], "kind": it.get("kind"), "entry_point": it.get("entry_point", ""),
                                    "scenario": it.get("scenario", ""), "cluster": c.get("id", ""), "status": c.get("status", ""),
                                    "write_set": list(c.get("write_set") or []), "gate": it.get("gate", ""),
                                    "key": (c.get("unit") or {}).get("unit_id") or c.get("retry_key") or c.get("id", ""),
                                    "path": it.get("path", "")})
    doc = {"schema": "rhoai3.native-assessment/v1", "task": task_id, "run": int(run_id), "verdict": token, "candidate": tree,
           "worklist": why or "present", "obligations": obligations,
           "failed_floors": list(verdict_doc.get("failed_floors") or []),
           "release_blockers": list(verdict_doc.get("release_blockers") or []),
           "qualifications": list(verdict_doc.get("qualifications") or []),
           "parity_scenarios": [str(s) for s in verdict_doc.get("parity_scenarios") or []],
           # the plan's unresolved responsibilities, owned by this assessment and carried to M5 (v24 WP3):
           # a verdict never discharges one; only a resolution bound to its id, evidence and candidate does
           "unresolved_responsibilities": [{"id": str(u.get("id")), "blocks": str(u.get("blocks") or "delivery"),
                                            "entry_points": len(u.get("entry_points") or []),
                                            "consequence": "ship: false until resolved (M5 release obligation)"}
                                           for u in plan.get("unresolved") or [] if isinstance(u, dict)],
           "classes_asserted_by": "worker-receipts"}
    data = canonical_bytes(doc)
    digest = sha256(data)
    name = "assessment.%d.%s.json" % (int(run_id), digest[:12])
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-assess-") as td:
            p = Path(td) / name
            p.write_bytes(data)
            board.native.attach(task_id, str(p), name)
    rec = board.record(task_id, "assessment", "assessment:%d:%s" % (int(run_id), digest[:16]), run=int(run_id),
                       verdict=token, candidate=tree, attachment=name, sha256=digest, open_obligations=len(obligations),
                       worklist=why or "present")
    return {"verdict": token, "candidate": tree, "open_obligations": len(obligations), "record": rec["key"],
            "accepted": token in DELIVERY_OK_VERDICTS}


def _assessment_doc(board: Board, task_id: str, rec: dict[str, Any]) -> dict[str, Any]:
    got = board.attachment(task_id, str(rec.get("attachment") or ""))
    if got is None or sha256(got[0]) != rec.get("sha256"):
        raise Refusal("ASSESS_CORRUPT", "assessment %s is missing or differs from its record" % rec.get("attachment"))
    return json.loads(got[0])


def m4_repair(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """After a measured REFUSE on this M4 run: the repairs the verdict needs,
    published as native tasks and linked as prerequisites of THIS task
    (repair -> M4). The caller then ends the run with kanban_block
    kind=dependency; native promotion resumes M4 when they are done."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "assess":
        raise Refusal("ASSESS_FOREIGN", "%s is not an assessment" % oid)
    rec = latest_assessment(board, task_id)
    if rec is None or int(rec.get("run") or 0) != int(run_id):
        raise Refusal("REFUSE_UNRECORDED", "record this run's assessment first (native_gate.py assessment-record)")
    unmet_all = unmet_deferred(root, board, plan, node, task_id)
    # the full test suite is measured on THIS candidate, not repaired by its early owners: a failing
    # test is already a surefire obligation of the assessed work list, and a suite that never ran
    # is this M4's own missing measurement (run-verify.sh --mode acceptance), never a follow-up card
    unmet_def = [u for u in unmet_all if u.split(": ", 1)[0].split("|", 1)[-1] != TEST_EXECUTION_CHECK]
    tests_unmet = [u for u in unmet_all if u not in unmet_def]
    if rec["verdict"] in DELIVERY_OK_VERDICTS and not unmet_def:
        if tests_unmet:
            raise Refusal("M4_TESTS_UNMEASURED", "the full test suite owed by %d outcome(s) is not passing on this "
                          "candidate (%s): run run-verify.sh --mode acceptance on it; failing tests arrive as work-list "
                          "obligations" % (len(tests_unmet), tests_unmet[0][:200]))
        raise Refusal("REFUSE_NOT_REFUSED", "the assessment is %s: hand it to review" % rec["verdict"])
    tasks = board.run_tasks(run)
    ran = [n["outcome_id"] for n in plan["nodes"] if n.get("role") == "deliver"
           and (board.task(tasks.get(n["outcome_id"], {}).get("id", "")) or {}).get("status") in ("running", "review", "done")]
    if ran:
        raise Refusal("DELIVERY_CYCLE_UNSUPPORTED", "delivery stage %s already ran for a candidate; a second cycle is an explicit stop" % ran[0])
    if rec.get("worklist") != "present":
        raise Refusal("REFUSE_" + str(rec.get("worklist")), "the assessment has no measured work list")
    refused_runs = sorted({int(r.get("run") or 0) for r in board.records(task_id, "assessment")
                           if r.get("verdict") not in DELIVERY_OK_VERDICTS})
    gen = len(refused_runs)
    doc = _assessment_doc(board, task_id, rec)

    def status_of(o: str) -> str:
        row = tasks.get(o)
        return "done" if row and (board.task(row["id"]) or {}).get("status") == "done" else "open"

    def budget_of(o: str) -> dict[str, Any]:
        return dict((_node(plan, o) or {}).get("budget") or {})

    prior = [r for r in board.records(task_id, "m4-repair") if int(r.get("run") or 0) == int(run_id)]
    if prior:
        nxt_rev = int(prior[-1]["revision"])
        cur = board.plan(run)
        if int(cur["revision"]) < nxt_rev:
            raise Refusal("REFUSE_REVISION_LOST", "revision %d recorded for this run is not on the board" % nxt_rev)
        added = list(prior[-1].get("added") or [])
        from planner.native_publish import publish_revision
        publish_revision(root, board, cur, added=added, holder=task_id)
        return {"verdict": rec["verdict"], "revision": nxt_rev, "added": added, "replayed": True,
                "terminator": "kanban_block kind=dependency"}
    # an unmet deferred runtime check becomes an obligation of its owning outcome
    # (a follow-up sharing the owner's budget when the owner is done)
    obligations = list(doc.get("obligations") or [])
    base_plan = dict(plan, ownership=dict(plan.get("ownership") or {}))
    extra_checks: dict[str, tuple[str, list[str]]] = {}
    for line in unmet_def:
        key = line.split(": ", 1)[0]          # "<owner>|<check>: <status> (<detail>)"
        owner, chk = key.split("|", 1)
        onode = _node(plan, owner) or {}
        ob_id = "deferred-check:%s:%s" % (owner, chk)
        base_plan["ownership"][ob_id] = owner
        extra_checks[ob_id] = (chk, list(onode.get("requirements") or []))
        obligations.append({"id": ob_id, "kind": "requirement-check", "write_set": list(onode.get("plan_paths") or []),
                            "key": owner, "cluster": "", "status": "open", "path": ""})
    gen = max(gen, 1)
    nxt = refuse_revision(base_plan, obligations, gen=gen, trigger=oid, verdict=rec["verdict"],
                          status_of=status_of, budget_of=budget_of, successor=False)
    if isinstance(nxt, Refusal):
        raise nxt
    for n in nxt["nodes"]:
        if n.get("role") != "repair" or n["outcome_id"] not in (nxt.get("additions") or []):
            continue
        own_checks = [extra_checks[o] for o in n.get("obligations") or [] if o in extra_checks]
        if own_checks:
            acc = dict(n.get("acceptance") or {})
            acc["requirement_checks"] = sorted({c for c, _r in own_checks})
            n["acceptance"] = acc
            n["requirements"] = sorted({r for _c, rs in own_checks for r in rs})
            n["class"] = "behavior"          # a runtime check is measured on the running application
    nxt.pop("digest", None)
    nxt["digest"] = plan_digest(nxt)
    nxt = native_revision(nxt)
    added = list(nxt.get("additions") or [])
    # the targets that are existing open owners already are M4's prerequisites (every repair is)
    board.record(task_id, "m4-repair", "m4-repair:%d" % int(run_id), run=int(run_id), revision=int(nxt["revision"]),
                 added=added, verdict=rec["verdict"])
    from planner.native_publish import publish_revision
    publish_revision(root, board, nxt, added=added, holder=task_id)
    return {"verdict": rec["verdict"], "revision": int(nxt["revision"]), "added": added, "replayed": False,
            "unresolved": [u["id"] for u in nxt.get("unresolved") or []], "terminator": "kanban_block kind=dependency"}


# ---------------------------------------------------------------------------
# M5: stage evidence and the push effect, recovered by read-back
# ---------------------------------------------------------------------------

def _stage_task(board: Board, run_id: str, plan: dict[str, Any], stage: str) -> str:
    node = next((n for n in plan["nodes"] if n.get("role") == "deliver" and n.get("stage") == stage), None)
    return board.task_of(run_id, node) if node else ""


def stage_evidence(root: Path, board: Board, run_id: str, plan: dict[str, Any], stage: str) -> tuple[bool, dict[str, Any], list[str]]:
    m4 = m4_acceptance(root, board, run_id, plan)
    push_task = _stage_task(board, run_id, plan, "push")

    def landed(head: str) -> bool:
        return bool(head and push_task and any(r.get("state") == "landed" and r.get("head") == head
                                               for r in board.records(push_task, "push")))
    return stage_evidence_facts(root, stage, m4_task=m4["task"], push_landed=landed)


def push_probe(root: Path, remote: str, ref: str, want: str) -> str | None:
    """'landed' when the remote ref is exactly ``want``, 'failed' when it
    answers another value, None when the remote cannot be read (uncertain)."""
    p = subprocess.run(["git", "-C", str(root), "ls-remote", remote, ref], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        return None
    got = (p.stdout.split() or [""])[0]
    return "landed" if got == want else "failed"


def push(root: Path, board: Board, *, task_id: str, run_id: int, remote: str = "origin", ref: str = "refs/heads/main",
         pusher: Callable[[list[str]], subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    """The M5 DEPLOY publication step: exactly the accepted candidate, once.
    The remote is read back FIRST: a push that already landed (a crashed
    earlier run) is recorded, never repeated."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "deliver" or node.get("stage") != "push":
        raise Refusal("EFFECT_STAGE", "%s may not push; only the M5 DEPLOY stage may" % oid)
    ok, _facts, reasons = stage_evidence(root, board, run, plan, "prepare")
    head = _head(root)
    if not ok:
        raise Refusal("EFFECT_INELIGIBLE", "preflight evidence does not admit %s (%s)" % (head[:12], "; ".join(reasons[:2])))
    op = "%s:%s@%s" % (remote, ref, head)
    done = [r for r in board.records(task_id, "push") if r.get("op") == op and r.get("state") in ("landed", "failed")]
    if done:
        return {"op": op, "state": done[-1]["state"], "already": True}
    seen = push_probe(root, remote, ref, head)
    if seen == "landed":
        board.record(task_id, "push", "push:%s:landed" % op, run=int(run_id), op=op, head=head, state="landed", recovered=True)
        return {"op": op, "state": "landed", "already": True}
    board.record(task_id, "push", "push:%s:sent:%d" % (op, int(run_id)), run=int(run_id), op=op, head=head, state="sent")
    run_push = pusher or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=600))
    p = run_push(["git", "-C", str(root), "push", remote, "%s:%s" % (head, ref)])
    state = push_probe(root, remote, ref, head) or "uncertain"
    board.record(task_id, "push", "push:%s:%s" % (op, state if state != "uncertain" else "uncertain:%d" % int(run_id)),
                 run=int(run_id), op=op, head=head, state=state, rc=int(getattr(p, "returncode", -1)))
    return {"op": op, "state": state, "already": False}


# ---------------------------------------------------------------------------
# review handoff: a task-specific summary and structured metadata
# ---------------------------------------------------------------------------

def handoff(root: Path, board: Board, *, task_id: str) -> dict[str, Any]:
    """What the implementer passes to kanban_request_review (summary and
    metadata), built from this task's own records and attachments on the
    board. Read-only; it decides nothing (the K2 gate and the reviewer do)."""
    root = Path(root)
    if board.is_m2(task_id):
        run = run_id_of(root, board)
        plan = board.plan(run)
        from planner.native_publish import readback
        gaps = readback(board, plan)
        tasks = board.run_tasks(run)
        created = [tasks[n["outcome_id"]]["id"] for n in plan["nodes"] if n["outcome_id"] in tasks]
        # v26 M2 review: "34 children" were cited, but only the cards linked to M2 itself are its
        # children (Hermes's completion guard rejects the chained M5 ids as not children); name both
        direct = [tasks[n["outcome_id"]]["id"] for n in plan["nodes"]
                  if n["outcome_id"] in tasks and CONTROL_M2 in (n.get("parents") or [])]
        chained = [t for t in created if t not in set(direct)]
        roles = {r: sum(1 for n in plan["nodes"] if n.get("role") == r) for r in ("repair", "assess", "deliver")}
        unresolved = [u["id"] for u in plan.get("unresolved") or []]
        receipt = _read_json(root / "evidence" / "planning" / "admission-receipt.json") or {}
        summary = ("Plan %s: published %d cards (%d repair outcomes, M4, %d M5 stages): %d are this card's direct "
                   "children, %d are chained below them; read-back %s. %s"
                   % (receipt.get("status") or "admitted", len(created), roles["repair"], roles["deliver"],
                      len(direct), len(chained), "equal" if not gaps else "has %d gap(s)" % len(gaps),
                      ("Unresolved: %s." % ", ".join(unresolved[:5])) if unresolved else "No unresolved responsibility."))
        return {"summary": summary, "metadata": {
            "created_cards": created, "direct_children": direct, "chained_descendants": chained,
            "plan_revision": int(plan["revision"]), "plan_digest": plan["digest"],
            "attachments": ["plan.r%d.json" % int(plan["revision"])], "read_back": gaps,
            "admission": {"path": "evidence/planning/admission-receipt.json", "status": receipt.get("status")},
            "unresolved": unresolved, "limitations": ["worker-produced receipts are trusted subject to binding (cooperative-receipts)"]}}
    role, run, oid, plan, node = node_context(board, task_id)
    tree = _product_tree(root)
    if role == "repair":
        recs = _accept_records(board, task_id)
        last = recs[-1] if recs else {}
        m = last.get("measurement") or {}
        rejects = len(board.records(task_id, "reject"))
        b = budget_state(board, run, plan, node)
        ok = bool(last.get("outcome_accepted")) and last.get("tree") == tree
        summary = ("%s: %s on commit %s; %d owned obligation(s) open; checks %s. %d rejected attempt(s) on this card; "
                   "budget %d of %d." % (node.get("title") or oid, "accepted" if ok else "NOT accepted on the current tree",
                                         str(last.get("commit") or "none")[:12], len(m.get("open_owned") or []),
                                         ", ".join(m.get("classes") or []) or "none", rejects, b["spent"], b["limit"]))
        limits = ["classes are asserted by worker receipts (cooperative-receipts)"]
        if last.get("repair_evidence_gaps"):
            limits.append("repair evidence gaps: %s" % "; ".join(last["repair_evidence_gaps"][:3]))
        return {"summary": summary, "metadata": {
            "outcome_id": oid, "commit": last.get("commit"), "tree": last.get("tree"), "accepted_on_current_tree": ok,
            "measurement": {k: m.get(k) for k in ("classes", "scenarios", "checks", "open_owned", "open_count") if k in m},
            "attempts_rejected": rejects, "budget": b, "attachments": [CONTRACT],
            "records": [r["key"] for r in recs[-2:]], "limitations": limits}}
    if role == "assess":
        rec = latest_assessment(board, task_id) or {}
        doc = _assessment_doc(board, task_id, rec) if rec else {}
        deferred = [q.get("id") for q in doc.get("qualifications") or [] if not q.get("satisfied")]
        summary = ("M4 verdict %s on candidate %s; %d open obligation(s); %s."
                   % (rec.get("verdict") or "unrecorded", str(rec.get("candidate") or "")[:12], int(rec.get("open_obligations") or 0),
                      ("deferred qualifications: %s" % ", ".join(deferred)) if deferred else "no deferred qualification"))
        return {"summary": summary, "metadata": {
            "verdict": rec.get("verdict"), "candidate": rec.get("candidate"), "candidate_is_current": rec.get("candidate") == tree,
            "attachments": [CONTRACT] + ([rec["attachment"]] if rec.get("attachment") else []),
            "failed_floors": doc.get("failed_floors") or [], "release_blockers": doc.get("release_blockers") or [],
            "deferred_qualifications": deferred, "limitations": ["measurements are worker receipts (cooperative-receipts)"]}}
    stage = str(node.get("stage") or "")
    ok, facts, reasons = stage_evidence(root, board, run, plan, stage)
    summary = ("%s: stage evidence %s for commit %s%s." % (node.get("title") or oid, "complete" if ok else "INCOMPLETE",
                                                         str(facts.get("candidate_sha") or "")[:12],
                                                         "" if ok else " (%s)" % "; ".join(reasons[:2])))
    return {"summary": summary, "metadata": {
        "stage": stage, "candidate_sha": facts.get("candidate_sha"), "receipts": facts.get("receipts") or {},
        "facts": {k: v for k, v in facts.items() if k not in ("receipts",)}, "reasons": reasons,
        "attachments": [CONTRACT], "limitations": ["stage receipts are produced by the worker (cooperative-receipts)"]}}


# ---------------------------------------------------------------------------
# progress: a read-only projection of the board
# ---------------------------------------------------------------------------

def progress_account(root: Path, board: Board, run_id: str) -> dict[str, Any]:
    """active = baseline + additions = accepted + unfinished; accepted splits
    into proof_applicable (accepted on the current tree, or covered by an
    accepted M4 of the current tree) and awaiting_revalidation. Derived from
    native tasks and their records only; never read back as a decision."""
    plan = board.plan(run_id)
    tasks = board.run_tasks(run_id)
    tree = _product_tree(root)
    revs = board.revisions(run_id)
    base_ids = {n["outcome_id"] for n in revs[min(revs)][1]["plan"]["nodes"] if n.get("role") == "repair"} if revs else set()
    repair = [n for n in plan["nodes"] if n.get("role") == "repair"]
    now_ids = {n["outcome_id"] for n in repair}
    m4 = m4_acceptance(Path(root), board, run_id, plan)
    accepted, applicable = [], []
    for n in repair:
        row = tasks.get(n["outcome_id"])
        if not row or (board.task(row["id"]) or {}).get("status") != "done":
            continue
        accepted.append(n["outcome_id"])
        recs = _accept_records(board, row["id"])
        if (recs and recs[-1].get("tree") == tree) or (m4["accepted"] and m4["candidate"] == tree):
            applicable.append(n["outcome_id"])
    statuses = {oid: (board.task(r["id"]) or {}).get("status") for oid, r in tasks.items()}
    return {
        "control": "native-cooperative", "revision": int(plan["revision"]),
        "baseline": len(base_ids), "additions": len(now_ids - base_ids), "active": len(now_ids),
        "accepted_historically": len(accepted), "proof_applicable": len(applicable),
        "awaiting_revalidation": len(accepted) - len(applicable), "unfinished": len(now_ids) - len(accepted),
        "unresolved": [u["id"] for u in plan.get("unresolved") or []],
        "milestones": {n["outcome_id"]: statuses.get(n["outcome_id"], "unpublished") for n in plan["nodes"]
                       if n.get("role") in ("assess", "deliver")},
        "m4": {k: m4[k] for k in ("verdict", "accepted", "done")},
        "complete_claim_allowed": not plan.get("unresolved") and len(accepted) == len(now_ids) and len(applicable) == len(accepted),
        "claimed_control": False,
    }


# ---------------------------------------------------------------------------
# the one serialization point for publication (a lock file, not state)
# ---------------------------------------------------------------------------

@contextmanager
def publication_lock(root: Path, timeout: float = 120.0) -> Iterator[None]:
    """The pinned create_task checks idempotency outside its write
    transaction: concurrent creates can duplicate. Every native graph
    mutation of this adapter runs under this exclusive lock."""
    p = Path(root) / LOCK
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise Refusal("PUBLICATION_BUSY", "another publisher holds %s" % LOCK)
                time.sleep(0.2)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


__all__ = ["Board", "board_for", "native_key", "parse_key", "contract_doc", "native_plan", "plan_attachment", "issue",
           "active_issue", "amend", "check_write", "check_terminator", "record_verdict", "accept_commit", "recover_accept",
           "evaluate_recovered", "restore_pending", "restore_held", "owner_recovery", "record_assessment", "m4_repair",
           "m4_acceptance", "m4_closure", "stage_evidence", "push", "progress_account", "publication_lock", "Refusal",
           "CONTROL_M2", "VERDICT"]
