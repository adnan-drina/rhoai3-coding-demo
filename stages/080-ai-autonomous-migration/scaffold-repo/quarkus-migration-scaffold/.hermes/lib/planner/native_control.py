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

from planner import card_text as CT
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
# H-11 slice 2 (card/v2): the full record is a native attachment; the comment is a plain sentence and this
# one reference line. Readers accept both forms in any mix; the REFERENCING comment's id orders the record.
RECORD_REF = re.compile(r"^\[native-control\] ref=v2 attachment=(rec-[0-9a-f]{12}-[0-9a-f]{12}[.]json) "
                        r"sha256=([0-9a-f]{64})$", re.M)
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


PILOT_TEXT = ("\n\nParallel pilot (PARALLEL-M3-PILOT.md): this card runs beside %s, each in its own git worktree. Your "
              "workspace is this task's worktree -- the directory you start in -- not /projects/modernized: run every "
              "tool with --root . from it and never edit the main tree. Your accepted candidate is not yet the "
              "application's: after advance.py accepts it, run python3 .hermes/kernel/native_gate.py --root . integrate, "
              "which applies it to the main tree and verifies the combined result there; request review only after it "
              "reports INTEGRATED.")


def native_body(node: dict[str, Any]) -> str:
    """The task body as published (deterministic; the read-back compares exactly this). A card/v2 plan
    stores each node's body when the node is first published (``card_body``, planner.card_text), so a
    later revision or renderer never rewrites it; an earlier plan renders the v1 text as it always did."""
    body = node["card_body"] if isinstance(node.get("card_body"), str) else native_description(node)
    if node.get("pilot_pair"):
        body += PILOT_TEXT % ", ".join(node["pilot_pair"])
    return body


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
    v2 = plan.get("presentation") == CT.PRESENTATION_V2
    for n in sorted(fresh, key=lambda n: n["outcome_id"]):
        groups.setdefault(CT.title(plan, n) if v2 else _m3_title(n), []).append(n)
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


def native_plan(plan: dict[str, Any], *, presentation: str = "v1") -> dict[str, Any]:
    """The initial revision as native control publishes it: the M5 stages are
    ASSIGNED at creation (their native parent, the accepted M4, holds them;
    there are no stage grants), runtime checks of early outcomes gate M4,
    and every repair outcome carries a unique ``M3 <ACTION>`` title.
    ``presentation`` is the run's decisions.loop.card_presentation: "v2"
    pins planner.card_text on the plan (every later revision inherits it).
    Deterministic; the digest is recomputed."""
    out = dict(plan)
    out["nodes"] = [dict(n, assignee=IMPL) if n.get("role") == "deliver" else dict(n) for n in plan["nodes"]]
    out["control"] = "native-cooperative"
    if presentation == "v2":
        out["presentation"] = CT.PRESENTATION_V2
    return card_bodies(native_titles(defer_runtime_checks(out)))


def native_revision(plan: dict[str, Any]) -> dict[str, Any]:
    """A later revision (owner repair, REFUSE repairs) as native control
    publishes it: the same titling and check placement for its new nodes."""
    return card_bodies(native_titles(defer_runtime_checks(plan)))


def card_bodies(plan: dict[str, Any]) -> dict[str, Any]:
    """card/v2: render the body of every node that has none yet (a node is rendered once, when first
    published, from the facts of that revision); a v1 plan is returned unchanged."""
    if plan.get("presentation") != CT.PRESENTATION_V2:
        return plan
    nodes = []
    changed = False
    for n in plan["nodes"]:
        n = dict(n)
        if not isinstance(n.get("card_body"), str):
            if n.get("role") == "repair":
                n["card_body"] = CT.description(plan, n)
            elif n.get("role") == "assess":
                n["card_body"] = CT.assess_description(plan, n)
            else:
                n["card_body"] = native_description(n)
            changed = True
        nodes.append(n)
    if not changed:
        return plan
    out = dict(plan, nodes=nodes)
    out.pop("digest", None)
    out["digest"] = plan_digest(out)
    return out


def card_presentation_of(root: Path) -> str:
    """The run's decided card presentation (decisions.loop.card_presentation; "v1" when undecided)."""
    from planner.decisions import card_presentation, load_decisions
    try:
        return card_presentation(load_decisions(Path(root)))
    except Exception:  # noqa: BLE001 - an unreadable decisions file is admission's refusal, not a presentation
        return "v1"


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

    def __init__(self, native: Any, *, author: str | None = None, record_format: str = "v1"):
        self.native = native
        self.author = author if author is not None else (os.environ.get("HERMES_PROFILE") or "").strip()
        self.record_format = record_format          # "v2": attachment-backed records (card/v2 runs)
        self._ref_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

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
            ref = RECORD_REF.search(body)
            if ref is not None:
                doc = self._referenced(task_id, ref.group(1), ref.group(2))
            elif not body.startswith(RECORD + " "):
                continue
            else:
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

    def _referenced(self, task_id: str, name: str, digest: str) -> dict[str, Any]:
        """The record a v2 reference names: the attachment on THIS task, its bytes matching the digest, a
        record document. Missing or mismatched evidence refuses -- a record never silently disappears."""
        hit = self._ref_cache.get((task_id, name, digest))
        if hit is not None:
            return dict(hit)
        rows = [a for a in self.native.attachments(task_id) if a["filename"] == name]
        if not rows:
            raise Refusal("RECORD_EVIDENCE_MISSING", "%s references %s, which is not attached to it" % (task_id, name))
        try:
            data = Path(rows[0]["stored_path"]).read_bytes()
        except OSError as exc:
            raise Refusal("RECORD_EVIDENCE_MISSING", "%s %s: %s" % (task_id, name, exc)) from exc
        if sha256(data) != digest:
            raise Refusal("RECORD_EVIDENCE_MISMATCH", "%s %s does not match its reference digest" % (task_id, name))
        try:
            doc = json.loads(data)
        except ValueError as exc:
            raise Refusal("RECORD_EVIDENCE_MISMATCH", "%s %s is not a record: %s" % (task_id, name, exc)) from exc
        if not isinstance(doc, dict) or not doc.get("key") or not name.startswith("rec-%s-" % sha256(doc["key"].encode("utf-8"))[:12]):
            raise Refusal("RECORD_EVIDENCE_MISMATCH", "%s %s does not hold the record its name binds" % (task_id, name))
        self._ref_cache[(task_id, name, digest)] = doc
        return dict(doc)

    def record(self, task_id: str, kind: str, key: str, **doc: Any) -> dict[str, Any]:
        """Write one keyed record; an existing key is returned unchanged."""
        for r in self.records(task_id):
            if r["key"] == key:
                return r
        body = dict(doc, kind=kind, key=key, v=1)
        if self.record_format == "v2":
            # attachment first (no control effect alone), then the referencing comment commits the record;
            # a retry after an interruption reuses an identical attachment instead of attaching it twice
            data = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
            digest = sha256(data)
            name = "rec-%s-%s.json" % (sha256(key.encode("utf-8"))[:12], digest[:12])
            have = [a for a in self.native.attachments(task_id) if a["filename"] == name]
            if not have:
                import tempfile
                with tempfile.TemporaryDirectory(prefix="native-record-") as td:
                    f = Path(td) / name
                    f.write_bytes(data)
                    self.native.attach(task_id, str(f), name)
            from planner.card_text import record_summary
            self.native.comment(task_id, "%s\n\n%s ref=v2 attachment=%s sha256=%s"
                                % (record_summary(kind, body), RECORD, name, digest), self.author)
        else:
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
    # H-11 slice 2: a card/v2 run writes attachment-backed records (the run's pinned card presentation);
    # every run reads both forms
    return Board(native, record_format="v2" if card_presentation_of(root) == "v2" else "v1")


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

def _allowed_paths(node: dict[str, Any], worklist: dict[str, Any] | None, own: set[str],
                   order: dict[str, set[str]] | None = None) -> tuple[str, list[str]]:
    """The ONE open cluster this outcome may edit now, and its write set.

    A cluster holding an item the destination answered with a server error
    goes first: a request that throws cannot show whether a header or body
    repair of the same request is right (v29 t_65445e69 spent two CORS
    attempts on a scenario a StackOverflowError answered).

    check-schedule/v1 generalizes that rule (``order``, issue_order): a
    cluster holding a scenario of a producer this card's comparisons come
    ``after`` -- while that producer is not measured PASS -- goes first too,
    and a cluster whose every item is such a dependent comparison is held
    last. A cluster of comparisons without ``after`` (a preflight, an
    anonymous rejection) is never held. Otherwise the work list's order
    stands."""
    if node.get("role") != "repair" or worklist is None:
        return "", []
    items = {str(i.get("id")): i for i in worklist.get("items") or [] if isinstance(i, dict)}
    first = set((order or {}).get("first") or ())
    held = set((order or {}).get("held") or ())

    def _scen(x: Any) -> str:
        return _bare_scenario((items.get(str(x)) or {}).get("scenario"))

    def _producer_item(x: Any) -> bool:
        # the producer's repair: a status/body difference on one of its own scenarios, never a header-only one
        it = items.get(str(x)) or {}
        return bool(_scen(x)) and _scen(x) in first and str(it.get("cause") or "") not in HEADER_CAUSES

    def _rank(c: dict[str, Any]) -> int:
        ids = list(c.get("items") or [])
        if any(((items.get(str(x)) or {}).get("advice") or {}).get("server_error") for x in ids) \
                or any(_producer_item(x) for x in ids):
            return 0
        if held and ids and all(_scen(x) in held for x in ids):
            return 2
        return 1

    mine = [c for c in worklist.get("clusters") or []
            if isinstance(c, dict) and c.get("status") == "open"
            and (own & set(c.get("items") or []) or c.get("id") in set(node.get("clusters") or []))]
    for c in sorted(mine, key=_rank):
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
    now = {str(r.get("check")) for r in node.get("check_plan") or [] if r.get("stage") != "later"} \
        | set(((node.get("acceptance") or {}).get("requirement_checks")) or [])
    owed = [c for c in remeasure_owed(board, run, node["outcome_id"]) if c in now]
    if owed:
        # a shared producer's repair marked this path: only a measurement of THIS outcome discharges it
        # (a later row it owns is remeasured at its earliest points and at M4, not here)
        return None, ["remeasure owed after a shared producer's repair: %s" % ", ".join(owed[:4])]
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
    in_progress = None
    if committed and tree != committed and not (pending and pending.get("candidate") == tree):
        # V29-3: a REJECTED candidate whose revert was interrupted (the worker was stopped between the
        # native reject record and the restore) is exactly the judged bytes: set aside onto the card that
        # rejected it and restored, verified below -- never built upon, never read as a baseline
        if set_aside_rejected(root, board, task_id=task_id, run_id=run_id):
            tree = _product_tree(root)
    if committed and tree != committed and not (pending and pending.get("candidate") == tree):
        # V29-3: THIS run was already issued, so the edits are its own work in progress -- never a
        # stopped run's leftovers. The repeat is measured against the run's issued baseline and may
        # only replay that issue; nothing is set aside (the architect's reproduction: a repeated
        # issue parked the current worker's repair under the older run 29 and reset it).
        in_progress = _in_progress_issue(root, board, task_id=task_id, run_id=run_id, head=head)
        if in_progress is not None:
            tree = committed
        # a run the runtime stopped left its unjudged edits: set them aside as evidence (v29 run 75)
        elif park_abandoned(root, board, task_id=task_id, run_id=run_id):
            tree = _product_tree(root)
    if in_progress is None and committed and tree != committed and not (pending and pending.get("candidate") == tree):
        raise Refusal("ISSUE_BASELINE_DRIFT", "the product tree differs from HEAD %s and is not the retained candidate of %s; "
                      "unexplained edits are not blessed" % (head[:12], oid))
    worklist, why = load_worklist(root)
    if role == "repair" and worklist is None:
        raise Refusal("ISSUE_" + why, "an outcome is issued against the measured work list")
    if role == "repair" and str(node.get("class") or "") in ORPHAN_WAITERS and in_progress is None:
        routed = route_orphans(root, board, task_id=task_id, run_id=run_id, run=run, plan=plan, worklist=worklist, tree=tree)
        if routed is not None and routed.get("self"):
            plan = board.plan(run)
            node = _node(plan, oid) or node
    schedule = None
    if role == "repair" and str(node.get("class") or "") in ORPHAN_WAITERS and in_progress is None:
        # check-schedule/v1: the later checks whose earliest point is this card are measured now on the
        # measured candidate; a FAIL is routed to its owner (OWNER_REPAIR_PENDING), a pending row stays owed
        schedule = schedule_at_issue(root, board, task_id=task_id, run_id=run_id, run=run, plan=plan, holder=oid,
                                     worklist=worklist, tree=tree)
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
            order = None
            if any(r.get("after") for r in node.get("check_plan") or []):
                known = {"%s#%s" % (m["owner"], m["check"]): m["state"] for m in (schedule or {}).get("rows") or []}
                order = issue_order(plan, node, _producer_states(root, plan, node, worklist, tree, _status_fn(board, run), known))
            cluster, allowed = _allowed_paths(node, worklist, own, order)
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
                    # the unit's checks are MEASURED: its issue carries what they measure (v29 Owner: a
                    # verification-only unit was issued with no scenarios and no comparison ever ran)
                    from planner.requirement_checks import measured_check_rows
                    if any(str(r.get("check") or "").startswith(("parity:sc:", "parity:ep:", "location:"))
                           for r in measured_check_rows(plan, node)):
                        from planner.requirement_checks import verification_scope
                        scope = verification_scope(root, plan, node)
                        if scope["unresolved"]:
                            raise Refusal("VERIFICATION_SCOPE_UNRESOLVED", "%s: the planned checks name targets no bound "
                                          "corpus resolves -- %s. A harness defect: kanban_block kind=needs_input quoting "
                                          "this line" % (oid, "; ".join("%s (%s)" % (u["check"], u["why"])
                                                                          for u in scope["unresolved"][:4])))
                        unit["verification"] = scope
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
    if unit and isinstance(unit.get("verification"), dict):
        # the issued verification scope is recorded ON the native issue: acceptance judges against it
        fields["verification"] = unit["verification"]
    rec = _unchanged_issue(board, task_id, run_id, fields) if replay_unchanged else None
    if in_progress is not None:
        # architect review cf164288: a re-issue -- replayed or not -- never blesses unjudged edits as a baseline;
        # they stay in the tree, attributed to this run and to nobody else
        raise Refusal("ISSUE_BASELINE_DRIFT", "run %d of %s holds unjudged edits of its issue %s (%s); judge them first "
                      "(run-verify.sh --mode acceptance, then advance.py). Nothing was set aside and nothing was recorded"
                      % (int(run_id), oid, in_progress["key"], in_progress.get("cluster") or "no cluster"))
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
               "brief.py; issuing again changes nothing.%s %s" % (
                   seq, " Your edits in progress are kept as they are." if in_progress is not None else "", nxt)).strip()
    return {"issue_id": seq, "replayed": replayed, "in_progress": in_progress is not None, "next": nxt, "satisfied": satisfied, "task_id": task_id, "run_id": int(run_id), "outcome_id": oid, "role": role,
            "cluster": cluster, "allowed_paths": allowed, "budget": budget, "retained_candidate": bool(pending),
            "objective": objective,
            "planned_unit": (dict(unit, owed=unit.get("owed") or [], bounds=unit.get("bounds") or {},
                                  kind=_unit_kind(node)) if unit else None),
            "held_candidate": bool(board.records(task_id, "owner-hold")) and not board.records(task_id, "restore-held"),
            "parked_candidate": bool(parked_pending(board, task_id)),
            "run": run, "baseline_commit": head, "baseline_tree": tree, "claimed_control": False,
            "schedule": [{k: m.get(k) for k in ("owner", "check", "state", "missing")} for m in (schedule or {}).get("rows") or []],
            "remeasure_owed": remeasure_owed(board, run, oid) if role == "repair" else [],
            "control": "native-cooperative", "record": rec["key"],
            "amendments": [amendment_projection(root, head, a) for a in board.records(task_id, "amend")
                           if a.get("cluster") == cluster] if cluster else []}


def amendment_projection(root: Path, head: str, a: dict[str, Any]) -> dict[str, Any]:
    """An amend record as the loop's acceptance reads it, WITH its grant facts.

    v29 run 76: the projection dropped granted_before_sha256 and dirty_at_grant,
    so on every run after the granting one advance.py read the amendment as
    "without authority" and rejected a correct candidate. A native amend record
    is clean at grant by construction (amend() refuses AMEND_ALREADY_EDITED);
    a record written before it carried the digest takes the content at HEAD,
    which the issue has just proven unedited."""
    got = str(a.get("granted_before_sha256") or "")
    if not got:
        blob = _git(Path(root), "show", "%s:%s" % (head, a["path"]), binary=True) if head else None
        got = hashlib.sha256(blob.stdout).hexdigest() if blob is not None and blob.returncode == 0 else ""
    return {"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {},
            "granted_before_sha256": got, "dirty_at_grant": False}


def _in_progress_issue(root: Path, board: Board, *, task_id: str, run_id: int, head: str) -> dict[str, Any] | None:
    """The latest issue of THIS native run when the run has been issued and the
    tree carries edits (its work in progress); None when this run was never
    issued, so the edits cannot be its own. An edit outside everything the run
    was issued, or a HEAD that moved under the run's baseline, is the drift
    refusal -- and still nothing is set aside."""
    mine = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]
    if not mine:
        return None
    last = mine[-1]
    if str(last.get("baseline_commit") or "") != head:
        raise Refusal("ISSUE_BASELINE_DRIFT", "run %d was issued at %s and HEAD is now %s with uncommitted edits; nothing "
                      "was set aside" % (int(run_id), str(last.get("baseline_commit") or "none")[:12], head[:12]))
    issued = {p for r in mine for p in (r.get("allowed_paths") or [])}
    _head_now, changed = _changed_vs_head(root)
    outside = sorted(set(changed) - issued)
    if outside:
        raise Refusal("ISSUE_BASELINE_DRIFT", "%s changed outside what run %d was issued (%s); nothing was set aside"
                      % (", ".join(outside[:4]), int(run_id), ", ".join(sorted(issued)[:4]) or "no product paths"))
    return last


ORPHAN_WAITERS = ("behavior", "runtime")


def route_orphans(root: Path, board: Board, *, task_id: str, run_id: int, run: str, plan: dict[str, Any],
                  worklist: dict[str, Any], tree: str) -> dict[str, Any] | None:
    """A behavior or runtime outcome measures the RUNNING application. An open
    mandatory obligation no open outcome will discharge (orphaned_obligations:
    it appeared after M2 froze ownership, or reopened after its owner was
    accepted) keeps the application from building or starting, so no such card
    can measure anything. v28: the package gate first ran once compilation
    reached zero errors, failed on a SpEL field the RootRestController COMPILE
    card kept, and every M3 BEHAVIOR card -- issued no write set -- recorded a
    witness checkpoint, stayed PENDING and blocked asking the Operator.

    Routed here by the rules M4's refuse_revision applies (orphan_revision):
    a follow-up of the frozen owner sharing its budget, published as a
    prerequisite of this card, the other open behavior/runtime cards and the
    open assessments; this run then ends with kanban_block kind=dependency
    (OWNER_REPAIR_PENDING) and native promotion resumes the cards after it. An
    obligation this card owns is issued to it. Anything no rule can route is a
    named ISSUE_ORPHANED_OBLIGATION refusal (kanban_block kind=needs_input),
    never an empty scope. Only a work list measured on THIS product tree
    routes anything. None when nothing is orphaned."""
    if not tree or str(worklist.get("candidate_sha256") or "") != tree:
        return None
    from planner.outcome_checks import orphan_revision, orphaned_obligations
    tasks = board.run_tasks(run)

    def status_of(o: str) -> str:
        row = tasks.get(o)
        return "done" if row and (board.task(row["id"]) or {}).get("status") == "done" else "open"

    orphans = orphaned_obligations(plan, worklist, status_of, holder=str(board.node_of(task_id)[2]))
    if not orphans:
        return None
    oid = str(board.node_of(task_id)[2])
    out = orphan_revision(plan, orphans, holder=oid, status_of=status_of,
                          budget_of=lambda o: dict((_node(plan, o) or {}).get("budget") or {}))
    if out["plan"] is not None:
        nxt = native_revision(out["plan"])
        board.record(task_id, "orphan-route", "orphan-route:%d:r%d" % (int(run_id), int(nxt["revision"])), run=int(run_id),
                     revision=int(nxt["revision"]), added=out["added"], owned_here=out["self"],
                     orphans=[o["id"] for o in orphans][:20], unresolved=[u[0] for u in out["unresolved"]][:20])
        from planner.native_publish import publish_revision
        publish_revision(root, board, nxt, added=out["added"], holder=task_id)
    named = "; ".join("%s at %s" % (o["id"], o.get("path") or o.get("cluster") or "?") for o in orphans[:3])
    if out["added"]:
        raise Refusal("OWNER_REPAIR_PENDING", "%s measures the running application, which %s keeps from building or starting; "
                      "no open outcome discharged it, so %s (its owner's follow-up, sharing the owner's budget) is now a "
                      "prerequisite of this card, of the other behavior cards and of M4. End this run with kanban_block "
                      "kind=dependency; this card resumes after it" % (oid, named, ", ".join(out["added"])))
    if out["unresolved"] and not out["self"]:
        raise Refusal("ISSUE_ORPHANED_OBLIGATION", "%s cannot measure the running application: %s. No open outcome discharges "
                      "it and it cannot be routed (%s). End this run with kanban_block kind=needs_input naming it"
                      % (oid, named, "; ".join("%s: %s" % u for u in out["unresolved"][:3])))
    return out


# ---------------------------------------------------------------------------
# check-schedule/v1 executed through the lifecycle (roadmap M-2): a later check
# is measured at its earliest useful point, its failure routed to its owner
# ---------------------------------------------------------------------------

SCHEDULE_FIRST_PACKAGE = "first-package"          # compatibility_objectives.FIRST_PACKAGE
# worklist.CORS_CAUSE / REPRESENTATION_CAUSE: header-only comparisons, never a producer's repair
HEADER_CAUSES = ("cors-response", "content-type-parameter")
SCHEDULED_OBLIGATION = "scheduled-check:%s:%s"     # owner, check
SCHEDULE_STATES = ("pass", "fail", "unknown", "pending")


def _bare_scenario(s: Any) -> str:
    s = str(s or "")
    return s[3:] if s.startswith("sc:") else s


def _status_fn(board: Board, run: str) -> Callable[[str], str]:
    tasks = board.run_tasks(run)

    def status_of(o: str) -> str:
        row = tasks.get(o)
        return "done" if row and (board.task(row["id"]) or {}).get("status") == "done" else "open"
    return status_of


def scheduled_rows(plan: dict[str, Any], holder: str) -> list[dict[str, Any]]:
    """The LATER check-plan rows whose earliest measurement point is the card
    ``holder``: its own outcome id in ``earliest.at``, or ``first-package``
    when the holder measures the running application (a behavior or runtime
    card runs only after every build, configuration and source outcome is
    accepted). One row per (owner, check): the requirements that use it and
    the union of their prerequisites; the owner's own card never measures its
    later debt here. Pure; deterministic."""
    hnode = _node(plan, holder) or {}
    runs_app = hnode.get("role") == "repair" and str(hnode.get("class") or "") in ORPHAN_WAITERS
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for n in plan.get("nodes") or []:
        if n.get("role") != "repair" or n["outcome_id"] == holder:
            continue
        for r in n.get("check_plan") or []:
            if r.get("stage") != "later" or not isinstance(r.get("earliest"), dict):
                continue
            at = [str(x) for x in r["earliest"].get("at") or []]
            if holder not in at and not (runs_app and SCHEDULE_FIRST_PACKAGE in at):
                continue
            owner = str(r.get("owner") or n["outcome_id"])
            got = rows.setdefault((owner, str(r["check"])), {
                "owner": owner, "check": str(r["check"]), "requirements": set(), "requires": set(), "after": set(),
                "milestone": str(r["earliest"].get("milestone") or ""), "qualification": str(r.get("qualification") or "")})
            got["requirements"].add(str(r.get("requirement") or ""))
            got["requires"] |= {str(x) for x in r.get("requires") or []}
            got["after"] |= {str(x) for x in r.get("after") or []}
    return [dict(v, requirements=sorted(v["requirements"] - {""}), requires=sorted(v["requires"]), after=sorted(v["after"]))
            for _k, v in sorted(rows.items())]


def _receipts(root: Path) -> dict[str, dict[str, Any]]:
    from planner.worklist import parity_receipt_file
    got = {m: _read_json(Path(root) / parity_receipt_file(m)) for m in ("disabled", "enabled")}
    return {m: r for m, r in got.items() if isinstance(r, dict)}


def measured_scenarios(root: Path, tree: str) -> list[str]:
    """The parity scenarios the composed receipts measured on THIS candidate
    (a receipt bound to another tree measured nothing here)."""
    from planner.worklist import parity_state
    out: set[str] = set()
    for rec in _receipts(root).values():
        bind = rec.get("binding") if isinstance(rec.get("binding"), dict) else {}
        if tree and str(bind.get("candidate_sha256") or "") == tree:
            out |= set((parity_state(rec).get("scenarios") or {}).keys())
    return sorted(out)


def unmet_requires(root: Path, requires: list[str], worklist: dict[str, Any] | None, tree: str,
                   status_of: Callable[[str], str]) -> list[str]:
    """Each verification prerequisite of a scheduled row that does NOT hold on
    the measured candidate, named. Fail closed: an unknown prerequisite is
    unmet. application:* read the package/boot gate rows of the work list
    measured on this tree; database:working is the boot gate's start against
    the decided database with no environment blocker; mode-receipt:<m> a
    composed receipt of that mode bound to this tree; compiled:/repair:<o>
    that outcome's card is done."""
    from planner.requirement_checks import PASS, _gate
    from planner.worklist import parity_state
    if not isinstance(worklist, dict) or not tree or str(worklist.get("candidate_sha256") or "") != tree:
        return ["a work list measured on this candidate %s (measured: %s)"
                % (tree[:12], str((worklist or {}).get("candidate_sha256") or "none")[:12])]
    out: list[str] = []
    rt = worklist.get("runtime") if isinstance(worklist.get("runtime"), dict) else {}
    receipts = None
    for req in requires:
        kind, _, arg = req.partition(":")
        if req == "application:packaged":
            if _gate(worklist, "package") != PASS:
                out.append("%s (the package gate did not pass on this candidate)" % req)
        elif req == "application:started":
            if _gate(worklist, "boot") != PASS:
                out.append("%s (the packaged application did not start on this candidate)" % req)
        elif req == "database:working":
            if _gate(worklist, "boot") != PASS or rt.get("blockers"):
                out.append("%s (the application did not start against the decided database%s)"
                           % (req, ": %s" % "; ".join(str(b) for b in rt["blockers"])[:160] if rt.get("blockers") else ""))
        elif kind == "mode-receipt":
            receipts = _receipts(root) if receipts is None else receipts
            rec = receipts.get(arg) or {}
            bind = rec.get("binding") if isinstance(rec.get("binding"), dict) else {}
            if str(bind.get("candidate_sha256") or "") != tree or not parity_state(rec).get("known"):
                out.append("%s (no %s-mode receipt measured on this candidate)" % (req, arg))
        elif kind in ("compiled", "repair"):
            if status_of(arg) != "done":
                out.append("%s (%s is not accepted)" % (req, arg))
        else:
            out.append("%s (an unknown prerequisite is never met)" % req)
    return out


def measure_scheduled(root: Path, plan: dict[str, Any], row: dict[str, Any], worklist: dict[str, Any] | None, tree: str,
                      status_of: Callable[[str], str], scenarios: list[str] | None = None) -> dict[str, Any]:
    """One scheduled row on the measured candidate: ``pending`` naming each
    unmet prerequisite (never a pass, never dropped), else the owner's check
    measured exactly as M4 measures a deferred check (requirement_measurement
    of the owner's requirements): pass | fail | unknown. A repository row
    carries its focused qualification's evidence (read only; it grants
    nothing)."""
    out = {"owner": row["owner"], "check": row["check"], "requirements": list(row.get("requirements") or []),
           "milestone": row.get("milestone") or ""}
    if row.get("qualification"):
        from planner.qualification_evidence import resolve
        q = resolve(row["qualification"], Path(root), tree=tree)
        out["qualification"] = {"id": q["id"], "status": q["status"], "test": q["test"], "missing": q["missing"][:2]}
    missing = unmet_requires(root, list(row.get("requires") or []), worklist, tree, status_of)
    if missing:
        return dict(out, state="pending", missing=missing, detail="not measured: %d prerequisite(s) unmet" % len(missing))
    scen = measured_scenarios(root, tree) if scenarios is None else list(scenarios)
    pseudo = {"outcome_id": row["owner"], "requirements": list(row.get("requirements") or []),
              "acceptance": {"requirement_checks": [row["check"]]}}
    got = (requirement_measurement(root, plan, pseudo, worklist or {}, scen, tree) or {}).get(row["check"]) \
        or {"status": "unknown", "detail": "not measured"}
    state = str(got.get("status") or "unknown")
    return dict(out, state=state if state in ("pass", "fail") else "unknown", missing=[], detail=str(got.get("detail") or "")[:300])


def _producer_states(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any] | None, tree: str,
                     status_of: Callable[[str], str], known: dict[str, str]) -> dict[str, str]:
    """'<owner>#<check>' -> pass | fail | unknown | pending for every producer
    this card's own comparisons come ``after``; one measurement per producer."""
    out: dict[str, str] = {}
    for r in node.get("check_plan") or []:
        for key in r.get("after") or []:
            key = str(key)
            if key in out:
                continue
            if key in known:
                out[key] = known[key]
                continue
            owner, _, chk = key.partition("#")
            onode = _node(plan, owner) or {}
            rows = [x for x in onode.get("check_plan") or [] if str(x.get("check")) == chk]
            if not rows:
                out[key] = "unknown"
                continue
            got = measure_scheduled(root, plan, {"owner": owner, "check": chk,
                                                 "requirements": sorted({str(x.get("requirement")) for x in rows}),
                                                 "requires": sorted({str(q) for x in rows for q in x.get("requires") or []})},
                                    worklist, tree, status_of)
            out[key] = got["state"]
    return out


def issue_order(plan: dict[str, Any], node: dict[str, Any], producers: dict[str, str]) -> dict[str, set[str]]:
    """check-schedule/v1 issuance order of a card's open clusters, as the
    scenarios that go FIRST and the ones HELD. A comparison whose ``after``
    producer is not measured PASS is held behind the producer's own
    scenarios (the repository contract's read/write scenarios: its repair
    cluster: a status/body difference there, not a header-only one). A row
    without ``after`` -- a preflight, an anonymous rejection that never
    reaches the repository -- is never held behind CRUD. Pure."""
    reqs = {str(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
    first: set[str] = set()
    held: set[str] = set()
    failing = {k for k, v in producers.items() if v != "pass"}
    for key in failing:
        owner, _, chk = key.partition("#")
        for row in (_node(plan, owner) or {}).get("check_plan") or []:
            if str(row.get("check")) != chk:
                continue
            facts = (reqs.get(str(row.get("requirement"))) or {}).get("facts") or {}
            for v in facts.get("verification") or []:
                if isinstance(v, dict):
                    first |= {_bare_scenario(s) for s in v.get("scenarios") or []}
    for row in node.get("check_plan") or []:
        chk = str(row.get("check") or "")
        if chk.startswith("parity:") and "-mode:" not in chk and set(str(x) for x in row.get("after") or []) & failing:
            held.add(_bare_scenario(chk[len("parity:"):]))
    return {"first": first, "held": held}


def _row_scenarios(m: dict[str, Any], reqs: dict[str, dict[str, Any]]) -> set[str]:
    chk = str(m.get("check") or "")
    if chk.startswith("parity:") and "-mode:" not in chk:
        return {_bare_scenario(chk[len("parity:"):])}
    if chk.startswith("behavior:repository-effects:"):
        return {_bare_scenario(s) for rq in m.get("requirements") or []
                for v in ((reqs.get(rq) or {}).get("facts") or {}).get("verification") or [] if isinstance(v, dict)
                for s in v.get("scenarios") or []}
    return set()


def _producer_difference(m: dict[str, Any], reqs: dict[str, dict[str, Any]], worklist: dict[str, Any] | None) -> bool:
    """Does a FAILing scheduled row point at its owner's producer? For a
    scenario-backed row: at least one open finding on its scenarios is a
    status/body difference or a server error, not only a header (CORS,
    representation) difference the measuring card repairs itself. A row not
    backed by scenarios is its owner's by construction."""
    scen = _row_scenarios(m, reqs)
    if not scen:
        return True
    for it in (worklist or {}).get("items") or []:
        if not isinstance(it, dict):
            continue
        s = {_bare_scenario(x) for x in [it.get("scenario")] + list(it.get("scenarios") or []) if x}
        if s & scen and (str(it.get("cause") or "") not in HEADER_CAUSES or (it.get("advice") or {}).get("server_error")):
            return True
    return False


def _effect_route(root: Path, plan: dict[str, Any], m: dict[str, Any], worklist: dict[str, Any] | None, tree: str,
                  scen: list[str], status_of: Callable[[str], str]) -> dict[str, Any] | None:
    """H-13 (architect decision 2026-10-01): who repairs a FAILING repository-effects row. The row's
    structured witnesses (requirement_checks.effect_witnesses) resolved through the plan's ownership:
    {witnesses, owners: {finding: open owner}, unowned: [finding], complete}. None for any other check
    (its routing is unchanged). An owner counts only as an open repair outcome of this plan."""
    if not str(m.get("check") or "").startswith("behavior:repository-effects:"):
        return None
    from planner.requirement_checks import effect_witnesses
    reqs = [q for q in plan.get("requirements") or [] if isinstance(q, dict) and q.get("id") in set(m.get("requirements") or [])]
    w = effect_witnesses(root, reqs, m["check"], worklist=worklist or {}, scenarios=scen, tree=tree, receipts=_receipts(root))
    # the existing deterministic resolver (outcome_graph.owner_of_finding): the plan's obligation ownership, then
    # the finding's cluster, then the planned requirement whose scope holds its locus -- so a finding of an open
    # card that has not been issued yet is that card's, not "unowned"; two claimants stay unresolved, named
    from planner.outcome_graph import owner_of_finding
    items = {str(i.get("id")): i for i in (worklist or {}).get("items") or [] if isinstance(i, dict)}
    owners: dict[str, str] = {}
    unowned: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    for f in w["findings"]:
        got = owner_of_finding(plan, items.get(f["finding"]) or {"id": f["finding"], "entry_point": f.get("entry_point")})
        o = str(got.get("owner") or "")
        node = _node(plan, o) if o else None
        if node and node.get("role") == "repair" and status_of(o) != "done":
            owners[f["finding"]] = o
        else:
            unowned.append(f["finding"])
            if got.get("class") == "ambiguous-ownership":
                ambiguous[f["finding"]] = list(got.get("candidates") or [])
    return {"witnesses": w, "owners": owners, "unowned": sorted(unowned), "ambiguous": ambiguous,
            "complete": bool(w["complete"]) and not unowned}


def _waits_on(plan: dict[str, Any], node_id: str) -> set[str]:
    """Every outcome ``node_id`` waits on, transitively, through plan parents."""
    parents = {n["outcome_id"]: set(n.get("parents") or []) for n in plan.get("nodes") or []}
    seen: set[str] = set()
    stack = list(parents.get(node_id, ()))
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(parents.get(p, ()))
    return seen


def acceptance_cycles(plan: dict[str, Any], deps: list[tuple[str, str]]) -> list[str]:
    """H-13: an outcome whose acceptance needs a repair OWNED by another outcome must not be waited on by
    that owner, directly or transitively -- the native parent graph stays acyclic while the acceptance
    dependency closes the cycle (v30 t_557b0bed / t_b996bea6). ``deps``: (judged outcome, evidence
    owner). Returns each cycle, named; [] when none."""
    out = []
    for judged, owner in deps:
        if judged != owner and judged in _waits_on(plan, owner):
            out.append("%s's acceptance needs a repair owned by %s, which waits on it" % (judged, owner))
    return out


def schedule_at_issue(root: Path, board: Board, *, task_id: str, run_id: int, run: str, plan: dict[str, Any],
                      holder: str, worklist: dict[str, Any] | None, tree: str, accepted: str = "") -> dict[str, Any] | None:
    """Measure every later row scheduled at this card (scheduled_rows) on the
    measured candidate, record the result on this card (``schedule-measure``,
    keyed per run, revision and tree), and route each FAIL to the row's owner
    as an owed repair obligation by the existing M3 orphan-routing rules
    (orphan_revision): the follow-up of the accepted owner, sharing its family
    budget, becomes a prerequisite of this card, the other open behavior and
    runtime cards and M4 -- then OWNER_REPAIR_PENDING (kanban_block
    kind=dependency). Not routed (named in the row's ``route``): a check this
    card judges itself as an immediate check, one already routed, one whose
    owner is still open, and a scenario failure that is only a header
    difference. A pending or unknown row stays owed (M4 remains the backstop
    and measures it again). None when nothing is scheduled here.

    ``accepted`` (the accept-commit key; accept_commit): the same measurement
    of the candidate this card just had judged, so a row still pending when
    its last earliest-point card is accepted is not left to M4. Same
    prerequisites, same keyed record (a replay records nothing), same routing
    -- except that the accepted card itself does not wait on the follow-up and
    nothing is raised: the other open behavior/runtime cards and M4 do."""
    rows = scheduled_rows(plan, holder)
    if not rows:
        return None
    status_of = _status_fn(board, run)
    scen = measured_scenarios(root, tree)
    measured = [measure_scheduled(root, plan, r, worklist, tree, status_of, scen) for r in rows]
    hnode = _node(plan, holder) or {}
    judged_here = {str(r.get("check")) for r in hnode.get("check_plan") or [] if r.get("stage") != "later"} \
        | set(((hnode.get("acceptance") or {}).get("requirement_checks")) or [])
    reqs = {str(q.get("id")): q for q in plan.get("requirements") or [] if isinstance(q, dict)}
    ownership = plan.get("ownership") or {}
    fails = []
    for m in measured:
        if m["state"] != "fail":
            continue
        ob = SCHEDULED_OBLIGATION % (m["owner"], m["check"])
        cur = str(ownership.get(ob) or "")
        if m["check"] in judged_here:
            # the same comparison is this card's own immediate check: its finding is this card's cluster
            m["route"] = "judged by %s itself (its own immediate check); the owner still owes it at M4" % holder
        elif cur and status_of(cur) != "done":
            m["route"] = "already routed to %s" % cur
        elif status_of(m["owner"]) != "done":
            m["route"] = "its owner %s is still open: judged there and at M4" % m["owner"]
        elif not ((lambda er: (bool(er["witnesses"]["findings"]) or bool(er["witnesses"]["record_only"]))
                   if er is not None else _producer_difference(m, reqs, worklist))(
                      m.setdefault("_er", _effect_route(root, plan, m, worklist, tree, scen, status_of)))):
            er0 = m.pop("_er", None)
            if er0 is not None and (er0["witnesses"]["unknown"]):
                m["witnesses"] = er0["witnesses"]
                m["route"] = ("not attributable: no finding or comparison FAIL explains it and %d scenario(s) are unknown "
                              "on this candidate; the check stays owed (never PASS) and M4 measures it again"
                              % len(er0["witnesses"]["unknown"]))
            else:
                m["route"] = ("only header-only differences are open on its scenarios: this card's own clusters, "
                              "not a producer repair")
        else:
            # H-13: for a repository-effects row the witnesses decide: a status/body/server-error finding or a
            # comparison FAIL no finding explains (record-only) is a producer difference -- never an empty set
            er = m.pop("_er", None)
            if er is not None:
                m["witnesses"] = er["witnesses"]
                m["repair_owners"] = sorted(set(er["owners"].values()))
            if er is not None and er["complete"]:
                # H-13: every failing finding is already owned by an open outcome (the holder included):
                # the check stays FAIL and owed, its findings stay with their owners, and no follow-up
                # (which those owners would wait on) is minted for the check's original owner
                m["route"] = ("evidence owned by open outcomes: %s; the check stays FAIL and owed until measured PASS"
                              % ", ".join("%s -> %s" % (f, o) for f, o in sorted(er["owners"].items())))
            else:
                m["route"] = "owner"
                m["contributors"] = sorted(set(er["owners"].values())) if er is not None else []
                if er is not None and er.get("ambiguous"):
                    m["ambiguous_ownership"] = er["ambiguous"]      # reported, never resolved by picking one
                fails.append(m)
    rec = board.record(task_id, "schedule-measure", "schedule-measure:%d:r%d:%s" % (int(run_id), int(plan["revision"]), tree[:16]),
                       run=int(run_id), revision=int(plan["revision"]), tree=tree, holder=holder, rows=measured,
                       **({"at": "accept", "accept": accepted} if accepted else {}))
    orphans, unrouted = [], []
    for m in fails:
        ob = SCHEDULED_OBLIGATION % (m["owner"], m["check"])
        onode = _node(plan, m["owner"]) or {}
        orphans.append({"id": ob, "path": "", "kind": "requirement-check", "entry_point": "", "scenario": "",
                        "cluster": "", "write_set": sorted(set(onode.get("plan_paths") or [])
                                                           | {str(p) for q in plan.get("requirements") or [] if isinstance(q, dict)
                                                              and q.get("id") in m["requirements"] for p in q.get("paths") or []}),
                        "status": "open", "reopened_from": m["owner"], "detail": m["detail"][:300]})
    out = {"record": rec["key"], "rows": measured, "routed": [], "unrouted": unrouted}
    if not orphans:
        return out
    from planner.outcome_checks import orphan_revision
    routed = orphan_revision(plan, orphans, holder=holder, status_of=status_of,
                             budget_of=lambda o: dict((_node(plan, o) or {}).get("budget") or {}))
    if routed["plan"] is None:
        out["unrouted"] += routed["unresolved"]
        return out
    nxt = routed["plan"]
    by_ob = {SCHEDULED_OBLIGATION % (m["owner"], m["check"]): m for m in fails}
    for n in nxt["nodes"]:
        mine = [by_ob[o] for o in n.get("obligations") or [] if o in by_ob]
        if n.get("role") != "repair" or not mine or not n["outcome_id"].startswith("followup:"):
            continue
        acc = dict(n.get("acceptance") or {})
        acc["requirement_checks"] = sorted(set(acc.get("requirement_checks") or []) | {m["check"] for m in mine})
        n["acceptance"] = acc
        n["requirements"] = sorted(set(n.get("requirements") or []) | {q for m in mine for q in m["requirements"]})
        n["class"] = "behavior"          # measured on the running application, exactly like an M4 deferred-check follow-up
        n["schedule"] = [{"check": m["check"], "measured_at": holder, "milestone": m["milestone"]}
                         for m in sorted(mine, key=lambda x: x["check"])]
    if accepted:
        # the card whose acceptance measured the failure is not held by it: its own checks passed
        for n in nxt["nodes"]:
            if n["outcome_id"] == holder:
                n["parents"] = sorted(set(n.get("parents") or []) - set(routed["added"]))
    # H-13 mixed failures: a follow-up judged on a check whose other failing findings are owned by open
    # outcomes must not be waited on by those owners (directly or through anything they wait on); it waits
    # on them instead, so each contributor can repair its own finding first
    deps: list[tuple[str, str]] = []
    for n in nxt["nodes"]:
        mine = [by_ob[o] for o in n.get("obligations") or [] if o in by_ob]
        if not mine or not n["outcome_id"].startswith("followup:"):
            continue
        contributors = sorted({c for m in mine for c in m.get("contributors") or []} - {n["outcome_id"]})
        if not contributors:
            continue
        fid = n["outcome_id"]
        for c in contributors:
            for x in nxt["nodes"]:
                if x["outcome_id"] == c or x["outcome_id"] in _waits_on(nxt, c):
                    x["parents"] = sorted(set(x.get("parents") or []) - {fid})
        n["parents"] = sorted(set(n.get("parents") or []) | set(contributors))
        deps += [(fid, c) for c in contributors]
    cycles = acceptance_cycles(nxt, deps)
    if cycles:
        raise Refusal("ACCEPTANCE_CYCLE", "the revision for %s is refused before publication: %s. A harness planning defect: "
                      "kanban_block kind=needs_input quoting this line" % (holder, "; ".join(cycles[:3])))
    nxt["trigger"] = {"intent": "m3-schedule:%s" % holder}
    nxt.pop("digest", None)
    nxt["digest"] = plan_digest(nxt)
    nxt = native_revision(nxt)
    board.record(task_id, "schedule-route", "schedule-route:%d:r%d" % (int(run_id), int(nxt["revision"])), run=int(run_id),
                 revision=int(nxt["revision"]), added=routed["added"], obligations=sorted(by_ob)[:20],
                 unresolved=[u[0] for u in routed["unresolved"]][:20])
    from planner.native_publish import publish_revision
    publish_revision(root, board, nxt, added=routed["added"], holder=task_id)
    out["routed"] = routed["added"]
    if accepted:
        return out
    hparents = set((_node(nxt, holder) or {}).get("parents") or [])
    if not (hparents & set(routed["added"])):
        return out       # H-13: the holder repairs its own share first; the follow-up waits on it, not the reverse
    named = "; ".join("%s of %s (%s)" % (m["check"], m["owner"], m["detail"][:120]) for m in fails[:3])
    raise Refusal("OWNER_REPAIR_PENDING", "%s is the earliest measurement point of %s, which FAILS on this candidate; the "
                  "check is owed by its owner, so %s (the owner's follow-up, sharing the owner's budget) is now a prerequisite "
                  "of this card, of the other behavior cards and of M4. End this run with kanban_block kind=dependency; this "
                  "card resumes after it" % (holder, named, ", ".join(routed["added"]) or "its open follow-up"))


def schedule_status(board: Board, run: str, plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Read-only: '<owner>|<check>' -> the latest scheduled measurement of every
    later row (state, missing, where, tree), or ``not-reached`` when no card at
    its earliest point has been issued yet. A pending row is never reported
    as passed; M4 still measures every row."""
    latest: dict[str, dict[str, Any]] = {}
    for oid, row in sorted((board.run_tasks(run) or {}).items()):
        for rec in board.records(row["id"], "schedule-measure"):
            for m in rec.get("rows") or []:
                k = "%s|%s" % (m.get("owner"), m.get("check"))
                if k not in latest or int(rec["_id"]) > int(latest[k]["_id"]):
                    latest[k] = dict(m, at=oid, tree=rec.get("tree"), _id=int(rec["_id"]))
    out: dict[str, dict[str, Any]] = {}
    for n in plan.get("nodes") or []:
        for r in n.get("check_plan") or []:
            if r.get("stage") != "later":
                continue
            k = "%s|%s" % (r.get("owner") or n["outcome_id"], r["check"])
            out[k] = latest.get(k) or {"state": "not-reached", "at": "", "missing": [],
                                       "earliest": list((r.get("earliest") or {}).get("at") or [])}
    return out


# ---------------------------------------------------------------------------
# a shared producer's accepted repair: every affected path is remeasured
# ---------------------------------------------------------------------------

def _causal_scope(plan: dict[str, Any], node: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(producer outcome, its causal_scope) for a producer or a follow-up /
    owner repair of one (lineage), else ('', {})."""
    if isinstance(node.get("causal_scope"), dict):
        return node["outcome_id"], node["causal_scope"]
    for ln in node.get("lineage") or []:
        p = _node(plan, str((ln or {}).get("follows") or "")) or {}
        if isinstance(p.get("causal_scope"), dict):
            return p["outcome_id"], p["causal_scope"]
    return "", {}


def mark_remeasure(board: Board, run: str, plan: dict[str, Any], node: dict[str, Any], *, task_id: str, accept_key: str,
                   tree: str) -> list[str]:
    """After an accepted repair of a shared producer: every affected path of
    its causal_scope is marked for remeasurement on its own card
    (``remeasure`` record, keyed by the producer and the acceptance). The
    producer's acceptance discharges no affected path. Returns the marked
    outcomes. Replay-safe (keyed)."""
    producer, scope = _causal_scope(plan, node)
    marked = []
    for a in scope.get("affects") or []:
        target = _node(plan, str(a.get("outcome") or ""))
        tid = board.task_of(run, target) if target else ""
        if not tid:
            continue
        board.record(tid, "remeasure", "remeasure:%s:%s" % (producer, accept_key), producer=producer, repair=node["outcome_id"],
                     repair_task=task_id, accept=accept_key, tree=tree, checks=sorted(str(c) for c in a.get("checks") or []))
        marked.append(target["outcome_id"])
    return marked


def _passes_since(board: Board, run: str, oid: str, since: int) -> set[str]:
    """Checks measured PASS for outcome ``oid`` after board comment ``since``:
    its own acceptance measurements, and scheduled measurements of rows it owns."""
    out: set[str] = set()
    tasks = board.run_tasks(run) or {}
    row = tasks.get(oid)
    if row:
        for r in board.records(row["id"], "accept-commit"):
            if int(r["_id"]) <= since:
                continue
            m = r.get("measurement") or {}
            out |= set(m.get("checks") or [])
    for _o, t in tasks.items():
        for rec in board.records(t["id"], "schedule-measure"):
            if int(rec["_id"]) <= since:
                continue
            out |= {str(m.get("check")) for m in rec.get("rows") or [] if m.get("owner") == oid and m.get("state") == "pass"}
    return out


def remeasure_owed(board: Board, run: str, oid: str) -> list[str]:
    """The checks of ``oid`` marked for remeasurement after a shared
    producer's repair and not measured PASS for ``oid`` itself since. Another
    path's pass never discharges them."""
    tasks = board.run_tasks(run) or {}
    row = tasks.get(oid)
    if not row:
        return []
    owed: set[str] = set()
    for mark in board.records(row["id"], "remeasure"):
        owed |= set(mark.get("checks") or []) - _passes_since(board, run, oid, int(mark["_id"]))
    return sorted(owed)


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
                 reason=str(row.get("reason") or "")[:500], locus=str(row.get("locus") or "")[:500], evidence=row.get("evidence") or {},
                 granted_before_sha256=(hashlib.sha256((Path(root) / rel).read_bytes()).hexdigest()
                                        if (Path(root) / rel).is_file() else ""))
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
    if node.get("pilot_pair"):
        # a pair outcome is accepted by its latest INTEGRATION into the main tree: a later judgement of the same
        # candidate in its worktree (v29 t_fa95d5e7: an unchanged rework after a change request, accept-evaluated
        # on the worktree tree) never replaces it; a new worktree candidate is refused by integration_gap until
        # it is integrated too
        recs = [r for r in recs if r.get("pilot") == "integration"]
        if not recs:
            return False, "%s: its latest acceptance is a worktree candidate, not the main tree's integration" % node["outcome_id"]
    if not recs or not recs[-1].get("outcome_accepted"):
        return False, "no accepted measurement is recorded for %s" % node["outcome_id"]
    tree = _product_tree(root)
    if recs[-1].get("tree") != tree:
        # a pilot pair outcome accepted by integration stands while later commits (its sibling's
        # integration) leave everything it changed untouched (PARALLEL-M3-PILOT.md)
        from planner.pilot import sibling_tolerant
        if sibling_tolerant(root, board, task_id, node, str(recs[-1].get("tree") or "")):
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
        from planner.pilot import integration_gap
        gap = integration_gap(root, board, task_id, node)
        if gap:
            raise Refusal("PILOT_NOT_INTEGRATED", gap)
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


def issued_verification(board: Board, task_id: str, run_id: int) -> dict[str, Any] | None:
    """The verification scope of the planned unit THIS run was last issued, or None."""
    rows = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]
    ver = (rows[-1].get("verification") or (rows[-1].get("planned_unit") or {}).get("verification")) if rows else None
    return dict(ver) if isinstance(ver, dict) else None


def verification_input_gaps(root: Path, scope: dict[str, Any], ex: dict[str, Any] | None) -> list[str]:
    """What makes a measurement unfit to judge an issued verification scope (architect re-review of
    68152b24): a required mode's corpus that is missing or no longer the one issued, and a runner
    assignment that moved or dropped an issued scenario. Each is a named reason the outcome stays
    unaccepted; nothing falls back to either mode's evidence."""
    import hashlib
    from planner.worklist import SCENARIO_CORPORA, SECURITY_MODES, _sid
    gaps: list[str] = []
    issued = {m: {_sid(x) for x in sids or []} for m, sids in (scope.get("scenarios_by_mode") or {}).items() if sids}
    for m in sorted(issued):
        rel = dict(zip(SECURITY_MODES, SCENARIO_CORPORA)).get(m)
        p = Path(root) / rel if rel else None
        now = hashlib.sha256(p.read_bytes()).hexdigest() if p is not None and p.is_file() else ""
        want = str((scope.get("corpus_sha256") or {}).get(m) or "")
        if not now:
            gaps.append("the %s-mode corpus the scope was issued from is missing" % m)
        elif want and now != want:
            gaps.append("the %s-mode corpus changed since issuance (%s, issued %s)" % (m, now[:12], want[:12]))
    par = ((ex or {}).get("stages") or {}).get("parity") or {}
    ran = {m: {_sid(x) for x in sids or []} for m, sids in (par.get("assigned") or {}).items()}
    for m, want in sorted(issued.items()):
        missing = sorted(want - ran.get(m, set()))
        if missing:
            gaps.append("the runner did not compare %d issued %s-mode scenario(s) in that mode (%s)" % (
                len(missing), m, ", ".join(missing[:3])))
    return gaps


def _measure(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any], tree: str,
             measurement: dict[str, Any], issued_scope: dict[str, Any] | None = None) -> dict[str, Any]:
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
    scoped = {"issued_scope": issued_scope} if issued_scope is not None else {}
    checks = requirement_measurement(root, plan, node, worklist, scenarios, tree, **scoped)
    if checks and node.get("check_plan"):
        # compatibility-objectives/v1: judged per (requirement, check); a check
        # name passes only when it passes for every requirement that uses it
        from planner.outcome_checks import requirement_matrix
        matrix = requirement_matrix(root, plan, node, worklist, scenarios, tree, **scoped)
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
    if issued_scope is not None:
        gaps = verification_input_gaps(root, issued_scope, ex)
        if gaps:
            # a verification input is missing or moved: nothing this measurement says can discharge the scope
            m["verification_input_gaps"] = gaps
            m["checks"] = []
            m.setdefault("unmet_checks", {})["verification-input"] = {"status": "unknown", "detail": "; ".join(gaps)[:300]}
    # the classes the node's DECLARED acceptance still requires (a measure:tests
    # deferred to M4 at publication is not required here; see defer_runtime_checks)
    from planner.measurement import needed_classes
    need = needed_classes(node)
    missing = sorted(need - set(m["classes"]))
    if str(node.get("class") or "") == "behavior":
        from planner.worklist import _sid
        seen = {_sid(x) for x in m["scenarios"]}
        missing += ["scenario %s" % x for x in sorted(node.get("scenarios") or []) if _sid(x) not in seen]
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
                  measurement: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
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
    m = _measure(root, plan, node, wl, tree, measurement, issued_scope=issued_verification(board, task_id, run_id))
    evidence_gaps = repair_evidence_gaps(root, node, tree)
    covered = _covers_or_defers(board, run, plan, node, m, record=not evidence_gaps)
    done = not m["open_owned"] and covered and not evidence_gaps
    board.record(task_id, "accept-commit", "accept-commit:%s" % key, run=int(run_id), commit=commit, tree=tree,
                 cluster=iss.get("cluster") or "", outcome_accepted=done, measurement=m, repair_evidence_gaps=evidence_gaps,
                 **(extra or {}))
    # check-schedule/v1: an accepted repair of a shared producer marks every affected path for remeasurement
    marked = mark_remeasure(board, run, plan, node, task_id=task_id, accept_key="accept-commit:%s" % key, tree=tree) if done else []
    schedule = None
    if role == "repair" and str(node.get("class") or "") in ORPHAN_WAITERS:
        # check-schedule/v1: the rows scheduled at this card measured on the candidate just judged
        schedule = schedule_at_issue(root, board, task_id=task_id, run_id=run_id, run=run, plan=plan, holder=oid,
                                     worklist=wl, tree=tree, accepted="accept-commit:%s" % key)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"], "remeasure": marked,
            "schedule": [{k: x.get(k) for k in ("owner", "check", "state", "missing", "route")}
                         for x in (schedule or {}).get("rows") or []],
            "schedule_routed": list((schedule or {}).get("routed") or []),
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
    m = _measure(root, plan, node, wl, tree, measurement, issued_scope=issued_verification(board, task_id, run_id))
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
    m = _measure(root, plan, node, wl, tree, measurement, issued_scope=issued_verification(board, task_id, run_id))
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
    return _stash(root, board, task_id=task_id, run_id=run_id, head=head, changed=changed, kind="park")


def _stash(root: Path, board: Board, *, task_id: str, run_id: int, head: str, changed: list[str],
           kind: str) -> dict[str, Any]:
    """Attach `changed` (bytes, or deleted) to the card under a digest-named
    attachment, record it, and restore those paths to HEAD. The attachment and
    the record come first, so an interrupted stash re-runs to the same key."""
    files: dict[str, str] = {}
    for rel in changed:
        p = root / rel
        files[rel] = base64.b64encode(p.read_bytes()).decode("ascii") if p.is_file() and not p.is_symlink() else ""
    data = canonical_bytes({"schema": "rhoai3.native-parked/v1", "task": task_id, "run": int(run_id), "head": head,
                            "candidate": _product_tree(root), "files": files})
    digest = sha256(data)
    name = "%s.%d.%s.json" % ("parked" if kind == "park" else kind, int(run_id), digest[:12])
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-park-") as td:
            f = Path(td) / name
            f.write_bytes(data)
            board.native.attach(task_id, str(f), name)
    rec = board.record(task_id, kind, "%s:%d:%s" % (kind, int(run_id), digest[:16]), run=int(run_id), head=head,
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


ABANDONED = "abandoned-candidate"


def park_abandoned(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any] | None:
    """v29 run 75: a worker the runtime STOPPED (a loop guard's gave_up, a
    crash, a timeout) runs no terminator, so its unjudged edits stay in the
    shared tree and the next issue refuses ISSUE_BASELINE_DRIFT until someone
    cleans up by hand. The next issue of the same card sets them aside instead
    -- as evidence (an attachment and an ``abandoned-candidate`` record), never
    as a candidate to restore -- when, and only when, every changed product
    path lies inside what the card's most recent ENDED run was issued, and no
    candidate of the card is retained. Anything else stays the drift refusal:
    an edit no ended run of this card was issued is not this card's to discard.

    Ownership is proven, never inferred from path overlap (architect review of
    0dd677ba: a replacement run that edited an allowed file and asked for its
    issue again had its own work archived as its predecessor's). So this runs
    only on the TRANSITION into the current run -- before its first issue --
    and only when the native run table shows the predecessor ENDED, the
    current run started after it, and every changed file was last written
    inside the predecessor's run window. A deletion carries no time, and any
    missing fact leaves the tree untouched for the drift refusal."""
    root = Path(root)
    records = board.records(task_id, "issue")
    if any(int(r.get("run") or 0) == int(run_id) for r in records):
        return None                       # this run has been issued: the tree's edits are its own
    head, changed = _changed_vs_head(root)
    if not changed or _open_pending(board, task_id) is not None:
        return None
    runs = sorted({int(r.get("run") or 0) for r in records} - {0})
    if not runs or runs[-1] >= int(run_id):
        return None
    last = runs[-1]
    prev, cur = board.native.run(last) or {}, board.native.run(int(run_id)) or {}
    if (str(prev.get("task_id") or "") != task_id or str(prev.get("status") or "") in ("", "running")
            or not prev.get("started_at") or not prev.get("ended_at")):
        return None                       # no native proof the predecessor ended
    t0, t1 = float(prev["started_at"]), float(prev["ended_at"])
    if not cur.get("started_at") or float(cur["started_at"]) < t1:
        return None                       # the current run is not provably its successor
    issued = {p for r in records if int(r.get("run") or 0) == last for p in (r.get("allowed_paths") or [])}
    if not set(changed) <= issued:
        return None
    for rel in changed:
        p = root / rel
        if not p.is_file() or p.is_symlink():
            return None                   # a deletion carries no time: ownership unproven
        if not (t0 <= p.stat().st_mtime <= t1 + ABANDON_WINDOW_SLACK):
            return None                   # written outside the predecessor's run: not provably its own
    return dict(_stash(root, board, task_id=task_id, run_id=last, head=head, changed=sorted(changed), kind=ABANDONED),
                run=last, window=[t0, t1])


# seconds past a run's recorded end in which its own last write may still land (the runtime records the
# end after it stops the worker)
ABANDON_WINDOW_SLACK = 5.0


def _attached_state(board: Board, task_id: str, rec: dict[str, Any]) -> dict[str, str] | None:
    got = board.attachment(task_id, str(rec.get("attachment") or ""))
    if got is None:
        return None
    try:
        return dict(json.loads(got[0]).get("files") or {})
    except ValueError:
        return None


def set_aside_rejected(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any] | None:
    """V29-3 / I-11: a worker stopped between its native ``reject`` record and
    the revert (no terminator ran) leaves the REJECTED candidate in the shared
    tree. Unrecognized, it blocks every other card (ISSUE_BASELINE_DRIFT) or is
    built upon as if it were the baseline. It is recognized only by identity:
    the whole product tree is exactly the candidate a reject record names, of
    a run that has ENDED -- or of this very run, when the rejection is newer
    than its latest issue. Then those bytes are attached to the card that
    rejected them (an ``abandoned-candidate`` record naming the rejection) and
    the paths are restored and verified (_stash). An unrelated edit changes
    the digest, so it is never matched, and a retained candidate is never
    touched.

    A set-aside interrupted part-way through its restore is resumed: every
    still-changed path lies inside one set-aside record at this HEAD and its
    bytes are still the attached ones; anything else stays the drift refusal."""
    root = Path(root)
    head, changed = _changed_vs_head(root)
    if not changed:
        return None
    parsed = board.node_of(task_id)
    if parsed is None:
        return None
    tree = _product_tree(root)
    rows = board.run_tasks(parsed[1])
    # once THIS run was issued, the edits may be its own (V29-3): only its own rejection, newer than its
    # latest issue, may be set aside -- never an older run's, and no other card's
    issued_now = any(int(r.get("run") or 0) == int(run_id) for r in board.records(task_id, "issue"))
    cards = [task_id] + ([] if issued_now else sorted({r["id"] for r in rows.values()} - {task_id}))
    for t in cards:
        if _open_pending(board, t) is not None:
            continue
        recs = board.records(t)
        for rej in [r for r in recs if r.get("kind") == "reject" and r.get("candidate") == tree]:
            rrun = int(rej.get("run") or 0)
            if t == task_id and rrun == int(run_id):
                last_issue = max([int(r["_id"]) for r in recs if r.get("kind") == "issue" and int(r.get("run") or 0) == rrun]
                                 or [0])
                if int(rej["_id"]) < last_issue:
                    continue      # rejected before this run's latest issue: these bytes are not that candidate now
            elif issued_now or not run_ended(board, t, rrun):
                continue
            got = _stash(root, board, task_id=t, run_id=rrun, head=head, changed=sorted(changed), kind=ABANDONED)
            board.record(t, "rejected-set-aside", "rejected-set-aside:%s:%s" % (rej["key"], got["record"].rsplit(":", 1)[-1]),
                         reject=rej["key"], abandoned=got["record"], attachment=got["attachment"], run=rrun,
                         by_issue_of=task_id, head=head)
            return dict(got, run=rrun, task=t, reject=rej["key"])
        for ab in ([] if issued_now else [r for r in recs if r.get("kind") == ABANDONED and r.get("head") == head]):
            if not set(changed) <= set(ab.get("paths") or []):
                continue
            files = _attached_state(board, t, ab)
            if files is None:
                continue
            same = True
            for rel in changed:
                p = root / rel
                want = files.get(rel)
                have = base64.b64encode(p.read_bytes()).decode("ascii") if p.is_file() and not p.is_symlink() else ""
                same = same and want is not None and want == have
            if not same:
                continue
            for rel in changed:
                if _git(root, "cat-file", "-e", "%s:%s" % (head, rel)).returncode == 0:
                    _git(root, "checkout", head, "--", rel)
                elif (root / rel).exists():
                    (root / rel).unlink()
            left = [c for c in _changed_vs_head(root)[1] if c in set(changed)]
            if left:
                raise Refusal("PARK_INCOMPLETE", "the tree still differs from HEAD at %s" % ", ".join(left[:4]))
            return {"resumed": ab["key"], "task": t, "parked": sorted(changed)}
    return None


def run_ended(board: Board, task_id: str, run_id: int) -> bool:
    """Has native run ``run_id`` of ``task_id`` ENDED? Only when the task is not
    running it, and the native run row exists and is no longer running. A run
    the board does not know is not proven ended."""
    t = board.task(task_id) or {}
    if t.get("status") == "running" and int(t.get("current_run_id") or 0) == int(run_id):
        return False
    row = board.native.run(int(run_id)) if hasattr(board.native, "run") else None
    return bool(row) and str(row.get("task_id") or task_id) == task_id and str(row.get("status") or "") != "running"


# ---------------------------------------------------------------------------
# lifecycle reconciliation: expired issuance and budget-derived deferrals
# ---------------------------------------------------------------------------

_ISSUED_KEY_RE = re.compile(r":issue(\d+):r(\d+)$")
ISSUED_HISTORY = Path("verification") / "loop" / "issued-history"


def issuance_state(root: Path, board: Board, data: bytes | None = None) -> dict[str, Any]:
    """Is verification/loop/issued.json still an ACTIVE issuance? Asked of the
    native board, never of the file's existence (v29 I-11: a run the loop guard
    stopped left it behind, and the Operator step read it as a live card).
    ``data`` judges those exact bytes instead of re-reading the file.

      none       no projection
      retained   the card holds a retained candidate (VERIFICATION_PENDING)
      live       the card is running (its issued run, or a newer claim), or a
                 native run of the card has not ended (a surviving worker)
      expired    the card is not running, no run of it is running natively,
                 and it retains nothing
      unbound    the projection names no card on this board, or a run the
                 board does not know: nothing can be said, so a caller refuses
                 as it would for a live card"""
    from planner.paths import LOOP_ISSUED
    if data is None:
        p = Path(root) / LOOP_ISSUED
        if not p.is_file():
            return {"state": "none"}
        try:
            data = p.read_bytes()
        except OSError:
            return {"state": "unbound", "why": "the projection could not be read"}
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError:
        return {"state": "unbound", "why": "the projection could not be read"}
    if not isinstance(doc, dict):
        return {"state": "unbound", "why": "the projection is not a document"}
    return _issuance_of(board, doc, sha256(data))


def _issuance_of(board: Board, doc: dict[str, Any], digest: str) -> dict[str, Any]:
    """The state of ONE projection's identity: its task, its run, the native
    run row. A missing or malformed run identity is unbound, never expired."""
    task = str(doc.get("task_id") or "")
    m = _ISSUED_KEY_RE.search(str(doc.get("idempotency_key") or ""))
    out = {"task": task, "run": int(m.group(2)) if m else 0, "issue": int(m.group(1)) if m else 0,
           "cluster": str(doc.get("cluster") or ""), "digest": digest}
    t = board.task(task) if task else None
    if t is None:
        return dict(out, state="unbound", why="the projection names no task on this board")
    if _open_pending(board, task) is not None:
        return dict(out, state="retained")
    if t.get("status") == "running":
        cur = int(t.get("current_run_id") or 0)
        return dict(out, state="live", why=("run %d is running" % cur) if cur == out["run"] else
                    ("a newer claim (run %d) holds the card" % cur))
    alive = [int(r.get("id") or 0) for r in board.native.runs(task) if str(r.get("status") or "") == "running"]
    if alive:
        return dict(out, state="live", why="native run %s of the card has not ended" % ", ".join(map(str, alive)))
    if not m:
        return dict(out, state="unbound", why="the projection carries no run identity")
    row = board.native.run(out["run"]) or {}
    if str(row.get("task_id") or "") != task:
        return dict(out, state="unbound", why="run %d is not a run of %s on this board" % (out["run"], task))
    if str(row.get("status") or "") in ("", "running") or not row.get("ended_at"):
        return dict(out, state="unbound", why="run %d has not ended natively (%s)" % (out["run"], row.get("status")))
    return dict(out, state="expired", status=str(t.get("status") or ""), run_status=str(row.get("status") or ""),
                ended_at=row.get("ended_at"))


def retire_issuance(root: Path, board: Board, *, by: str, reason: str) -> dict[str, Any]:
    """Move an EXPIRED projection into verification/loop/issued-history/ and
    record it on the card: the history is kept, the live slot is freed. A
    projection that is live, retained or unbound is refused.

    Bound to ONE projection identity (architect review of 0dd677ba: a claim
    and a new projection that appeared between the check and the unlink were
    deleted). Under the publication lock that issue publication also takes,
    the projection is MOVED atomically to a name carrying the digest that was
    judged; the moved bytes must be those bytes, and anything else -- a newer
    projection written without the lock -- is put back and the retirement
    refused. Only then is it archived, recorded and dropped; an interrupted
    retirement finds its moved file and finishes it, to the same record."""
    from planner.paths import LOOP_ISSUED
    if by != "operator":
        raise Refusal("RETIRE_NOT_OPERATOR", "only the Operator retires an issuance (profile %r)" % by)
    src = Path(root) / LOOP_ISSUED
    with publication_lock(root):
        done = [_finish_retirement(root, board, f, reason) for f in sorted(src.parent.glob(src.name + RETIRING + "*"))]
        st = issuance_state(root, board)
        if st["state"] == "none":
            return {"retired": done[-1] if done else None, "state": "none"}
        if st["state"] != "expired":
            raise Refusal("ISSUANCE_NOT_EXPIRED", "the issuance of %s (run %s) is %s%s" % (
                st.get("task") or "?", st.get("run"), st["state"], (": " + st["why"]) if st.get("why") else ""))
        moved = src.with_name(src.name + RETIRING + st["digest"][:16])
        os.rename(src, moved)
        if sha256(moved.read_bytes()) != st["digest"]:
            if not src.exists():
                os.link(moved, src)
            moved.unlink()
            raise Refusal("ISSUANCE_CHANGED", "the projection changed while it was judged expired (a newer issuance "
                                              "was published); it is left in place")
        return {"retired": _finish_retirement(root, board, moved, reason), "state": "expired", "task": st["task"],
                "run": st["run"]}


RETIRING = ".retiring."


def _finish_retirement(root: Path, board: Board, moved: Path, reason: str) -> str:
    """Archive a moved projection, record it on its card and drop the moved
    file; idempotent in every step (history by digest, record by key)."""
    from planner.canonical import load_json
    data = moved.read_bytes()
    digest = sha256(data)
    if not moved.name.endswith(RETIRING + digest[:16]):
        raise Refusal("RETIRING_CORRUPT", "%s does not hold the bytes its name records" % moved.name)
    st = _issuance_of(board, load_json(moved), digest)
    rel = ISSUED_HISTORY / ("issued.%s.r%d.i%d.%s.json" % (st["task"], st["run"], st["issue"], digest[:12]))
    dest = Path(root) / rel
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    elif dest.read_bytes() != data:
        raise Refusal("RETIRING_CORRUPT", "%s exists with other bytes" % rel)
    board.record(st["task"], "issuance-retired", "issuance-retired:%s" % digest[:16], run=st["run"],
                 issue=st["issue"], cluster=st["cluster"], history=rel.as_posix(), status=st.get("status"),
                 run_status=st.get("run_status"), ended_at=st.get("ended_at"), reason=reason[:500])
    moved.unlink()
    return rel.as_posix()


EXHAUSTION_REASON = re.compile(r"^(\d+) of (\d+) attempt\(s\) spent against (\S+); last: ")


def effective_budget(board: Board, task_id: str) -> dict[str, Any]:
    """The family budget of a repair card as the native account holds it:
    spent excludes voided rejections; remaining is what the published limit
    still allows. Read-only; the limit is never changed here."""
    _role, run, _oid, plan, node = node_context(board, task_id)
    b = budget_state(board, run, plan, node)
    tasks = board.run_tasks(run)
    voided = sum(len(board.records(tasks[n["outcome_id"]]["id"], "reject-voided")) for n in plan.get("nodes") or []
                 if b["key"] and n.get("role") == "repair" and str((n.get("budget") or {}).get("key") or "") == b["key"]
                 and n["outcome_id"] in tasks)
    return {"key": b["key"], "limit": int(b["limit"]), "spent": int(b["spent"]), "voided": voided,
            "remaining": max(0, int(b["limit"]) - int(b["spent"])), "exhausted": bool(b["exhausted"])}


def reconcile_deferrals(root: Path, board: Board, *, task_id: str, by: str, reason: str) -> dict[str, Any]:
    """Lift a deferral this card's family BUDGET caused once that budget, as
    effectively spent (voided rejections excluded), is no longer exhausted.

    v29 I-10: voiding the three rejections a harness defect caused restored the
    allowance but left verification/loop/deferred.json holding the cluster, so
    the card was issued a cluster that could not pass. Only an EXHAUSTION
    deferral is considered -- its reason is exactly the loop's own
    "N of L attempt(s) spent against <this family's key>; last: ..." (V29-1:
    any other blocker that merely mentions the key stays) -- for a cluster a
    card of this budget family was issued; a budget still exhausted keeps it.
    The limit, the rejection records, the legacy attempt allowance (steps.json)
    and every other deferral are untouched, nothing is minted, and a second
    call finds nothing left to lift (the record key is the cluster and the
    reason's digest; the record precedes the write, so a crash in between
    re-runs to the same record). The effective spend and allowance are
    reported: a reconciliation never moves them."""
    from planner.canonical import load_json, write_canonical
    from planner.paths import LOOP_DEFERRED
    if by != "operator":
        raise Refusal("RECONCILE_NOT_OPERATOR", "only the Operator reconciles a deferral (profile %r)" % by)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "repair":
        raise Refusal("RECONCILE_ROLE", "%s is a %s card; only repair cards carry a family budget" % (task_id, role))
    before = effective_budget(board, task_id)
    b = budget_state(board, run, plan, node)
    p = Path(root) / LOOP_DEFERRED
    doc = load_json(p) if p.is_file() else {"schema": "rhoai3.loop-deferred/v1", "clusters": [], "reasons": {}}
    reasons = dict(doc.get("reasons") or {})
    tasks = board.run_tasks(run)
    family = [tasks[n["outcome_id"]]["id"] for n in plan.get("nodes") or []
              if n.get("role") == "repair" and b["key"] and str((n.get("budget") or {}).get("key") or "") == b["key"]
              and n["outcome_id"] in tasks]
    issued = {str(r.get("cluster") or "") for t in (family or [task_id]) for r in board.records(t, "issue")}
    lifted: list[str] = []
    kept: list[dict[str, str]] = []
    for c in list(doc.get("clusters") or []):
        why = str(reasons.get(c) or "")
        m = EXHAUSTION_REASON.match(why)
        if c not in issued or not b["key"] or not m or m.group(3) != b["key"]:
            if c in issued and b["key"] and b["key"] in why:
                kept.append({"cluster": c, "why": "not a budget exhaustion of %s: %s" % (b["key"], why[:160])})
            continue          # not a deferral this family's budget caused
        if b["exhausted"]:
            kept.append({"cluster": c, "why": "%s is still exhausted (%d of %d)" % (b["key"], b["spent"], b["limit"])})
            continue
        board.record(task_id, "deferral-lifted", "deferral-lifted:%s:%s" % (c, sha256(why.encode("utf-8"))[:12]),
                     cluster=c, budget_key=b["key"], spent=int(b["spent"]), limit=int(b["limit"]),
                     was_deferred_because=why[:500], reason=reason[:500])
        lifted.append(c)
    if lifted:
        doc["clusters"] = [c for c in doc.get("clusters") or [] if c not in lifted]
        doc["reasons"] = {k: v for k, v in reasons.items() if k not in lifted}
        write_canonical(p, doc)
    after = effective_budget(board, task_id)
    return {"lifted": lifted, "kept": kept, "budget": {k: b[k] for k in ("key", "spent", "limit", "exhausted")},
            "effective": {"before": before, "after": after},
            "admission": _readmit_if_stale(root, set(doc.get("clusters") or []))}


def _readmit_if_stale(root: Path, deferred: set[str]) -> str:
    """The admission seal (or the sealed work list) still naming a cluster that
    is no longer deferred is stale (v29 I-11: the lifted cluster kept
    MANUAL_CLUSTER, the parity composer refused a receipt against it, and the
    sweep wrote INCONCLUSIVE over every FAIL). Rebuild the work list and
    re-seal, as the loop does after any disposition; nothing is minted.
    Checked on every call, so an interrupted reconciliation re-seals on the
    repeat."""
    from planner.canonical import load_json
    from planner.paths import ADMISSION_RECEIPT, WORKLIST
    p = Path(root) / ADMISSION_RECEIPT
    if not p.is_file():
        return "no admission receipt"
    rec = load_json(p)
    stale = [b for b in rec.get("blocks") or [] if b.get("class") == "MANUAL_CLUSTER" and b.get("subject") not in deferred]
    wl = Path(root) / WORKLIST
    try:
        listed = set((load_json(wl).get("deferred") or []) if wl.is_file() else [])
    except (OSError, ValueError):
        listed = set()
    if not stale and not (listed - set(deferred)):
        return str(rec.get("status") or "")
    from planner import pipeline
    from planner.worklist import build_worklist
    build_worklist(Path(root))
    return str(pipeline.admit(Path(root)).get("status") or "")


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
        # H-11: the decision, each execution stage's state and each check's result -- not the check classes
        summary = CT.handoff_summary(str(node.get("title") or oid), node, last, accepted_now=ok, rejects=rejects, budget=b)
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
