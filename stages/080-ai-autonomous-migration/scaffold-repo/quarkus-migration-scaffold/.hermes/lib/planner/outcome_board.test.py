#!/usr/bin/env python3
"""Outcome board: derivation, publication, authority, lifecycle, continuations,
serialization. SYNTHETIC evidence: an in-memory FakeNative board with the
pinned semantics, real SQLite, real git and real processes. Native behaviour
on the exact runtime is qualified separately
(stages/080-ai-autonomous-migration/hermes-runtime/tests/rhoai3_outcome_board).

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/outcome_board.test.py
"""
from __future__ import annotations

import copy
import json
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
KERNEL = LIB.parent / "kernel"
for p in (LIB, KERNEL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import k4_graph as G  # noqa: E402
import outcome_reconcile as R  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import outcome_protocol as P  # noqa: E402
from planner import outcome_hook as HK  # noqa: E402
from planner.outcome_native import MARKER, FakeNative  # noqa: E402
from planner.outcome_store import Crash, Store, StoreError, canonical, sha  # noqa: E402

FIX = HERE / "fixtures"
SHOP = json.loads((FIX / "outcome-initial-shop.json").read_text())
LEDGER = json.loads((FIX / "outcome-initial-ledger.json").read_text())


def derive(fx=SHOP, **kw):
    return OG.derive_initial_graph(run_id=kw.pop("run_id", "r1"), worklist=kw.pop("worklist", fx["worklist"]),
                                   entry_points=kw.pop("entry_points", fx["entry_points"]),
                                   oracles=kw.pop("oracles", fx["oracles"]), references=kw.pop("references", fx["references"]),
                                   provenance=kw.pop("provenance", fx["provenance"]), **kw)


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()


def dead_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def mirror_layout(root: Path) -> None:
    """The destination's harness layout (.hermes/lib, kernel, planning, skills) as the deployed hook and tools see it."""
    for name in ("lib", "kernel", "planning", "skills"):
        os.symlink(LIB.parent / name, Path(root) / ".hermes" / name)


class Run:
    """A disposable destination root in qualification mode, a FakeNative board
    and the published shop graph."""

    def __init__(self, fx=SHOP, execution="qualification", publish=True):
        self.tmp = Path(tempfile.mkdtemp(prefix="ob-"))
        self.root = self.tmp / "dest"
        self.root.mkdir()
        (self.root / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                                 "configuration": {"board_protocol": P.OUTCOME}}))
        (self.root / ".hermes").mkdir()
        (self.root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": execution}}}}))
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        for c in fx["worklist"]["clusters"]:
            for p in c["write_set"]:
                f = self.root / p
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("// %s v0\n" % p)
        self.worklist = copy.deepcopy(fx["worklist"])
        self.save_worklist()
        shutil.copy(LIB.parents[1] / "decisions.yaml", self.root / "decisions.yaml")  # the golden's decisions
        (self.root / ".gitignore").write_text("verification/\nevidence/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "baseline")
        self.native = FakeNative(self.tmp)
        self.m2 = self.native.create(title="M2 PLAN", body="plan", assignee="implementer", parents=[], key="m2-plan",
                                     skills=["paved-road-m2"], workspace="", max_retries=1)
        self.m2_run, self.m2_lock = self.native.claim(self.m2)
        self.plan = derive(fx)
        self.store = None
        if publish:
            self.publish()

    def ctx(self, native=None):
        return L.Ctx(self.root, Store(self.root), native or self.native)

    def publish(self):
        self.store = G.init_store(self.root, run_id="r1", m2_task=self.m2, native_db=self.native.db_path, protocol=P.OUTCOME)
        G.persist_plan(self.store, self.plan)
        G.publish_plan(self.root, self.store, self.native, self.plan, m2_task=self.m2)
        return G.complete_generation(self.store, self.native)

    def save_worklist(self):
        p = self.root / L.WORKLIST
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.worklist))

    def drop(self, *ids):
        self.worklist["items"] = [i for i in self.worklist["items"] if i["id"] not in ids]
        for c in self.worklist["clusters"]:
            c["items"] = [i for i in c["items"] if i not in ids]
        self.worklist["clusters"] = [c for c in self.worklist["clusters"] if c["items"]]
        self.save_worklist()

    def tid(self, oid):
        return self.store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (oid,)).fetchone()[0]

    def release(self):
        out = L.check_complete(self.ctx(), task_id=self.m2, run_id=self.m2_run, profile="reviewer", audit_green=True)
        self.native.complete(self.m2)
        R.tick(self.root, self.native)
        return out

    def claim(self, oid, pid=None):
        tid = self.tid(oid)
        run, lock = self.native.claim(tid, pid=pid or dead_pid())
        return tid, run, lock

    def issue(self, oid, pid=None):
        tid, run, lock = self.claim(oid, pid)
        iss = L.issue(self.ctx(), task_id=tid, run_id=run, claim_lock=lock, pid=pid or dead_pid(), pgid=0)
        return tid, run, iss

    def edit(self, rel, text):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def accept(self, oid, *, classes=("compile", "tests"), scenarios=(), edit=True, attempt="1", complete=True):
        """Drive one outcome through its issued cluster to acceptance."""
        tid, run, iss = self.issue(oid)
        ctx = self.ctx()
        node = L._node(self.store.current_revision(), oid)
        if edit and iss["allowed_paths"]:
            self.edit(iss["allowed_paths"][0], "// %s accepted by %s\n" % (iss["allowed_paths"][0], oid))
        L.check_write(ctx, task_id=tid, run_id=run, rel_paths=list(iss["allowed_paths"]))
        L.record_verdict(ctx, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=ctx.product_tree(), attempt=attempt)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "accept %s" % oid, "--allow-empty")
        self.drop(*node["obligations"])
        out = L.accept_commit(ctx, task_id=tid, run_id=run, attempt=attempt, commit=git(self.root, "rev-parse", "HEAD"),
                              measurement={"classes": list(classes), "scenarios": list(scenarios)})
        if complete and out["outcome_accepted"]:
            L.check_complete(ctx, task_id=tid, run_id=run, profile="implementer", audit_green=False)
            self.native.complete(tid)
        return tid, run, out

    def accept_all_repairs(self):
        plan = self.store.current_revision()
        for n in OG.topo_order(plan["nodes"]):
            if n["role"] != "repair":
                continue
            # every acceptance measurement is a full compile/test/build measurement (run-verify
            # acceptance mode); runtime and parity are measured only where the class needs them
            cls = ("build", "compile", "tests") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
            self.accept(n["outcome_id"], classes=cls, scenarios=n.get("scenarios") or ())

    def assess(self, oid, verdict, *, new_items=(), new_clusters=()):
        tid, run, iss = self.issue(oid)
        for it in new_items:
            self.worklist["items"].append(it)
        for c in new_clusters:
            self.worklist["clusters"].append(c)
        self.save_worklist()
        v = self.root / L.VERDICT
        v.parent.mkdir(parents=True, exist_ok=True)
        v.write_text(json.dumps({"card_id": tid, "verdict": verdict, "parity_scenarios": ["items-list", "items-get-1", "items-get-missing", "orders-create"],
                                 "qualifications": [{"id": "g1-kill-ratio", "class": "deferred", "satisfied": False}]}))
        L.record_assessment(self.ctx(), task_id=tid, run_id=run, verdict_doc=json.loads(v.read_text()))
        self.native.tasks[tid]["status"] = "review"
        L.check_complete(self.ctx(), task_id=tid, run_id=run, profile="reviewer", audit_green=True)
        self.native.complete(tid)
        return tid

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ===========================================================================
class Derivation(unittest.TestCase):
    """C5/F5: initial graph from admission-time evidence (A1, A6, A14)."""

    def test_conservation_scope_and_order_shop(self):
        plan = derive()
        repair = [n for n in plan["nodes"] if n["role"] == "repair"]
        owned = sorted(ob for n in repair for ob in n["obligations"])
        mandatory = sorted(i["id"] for i in SHOP["worklist"]["items"] if i["category"] == "mandatory" and i["id"] != "inc:unlocatable:jndi")
        verify = sorted("verify:" + e for e in SHOP["oracles"])
        self.assertEqual(owned, sorted(mandatory + verify))                     # every obligation exactly once
        self.assertEqual(len(owned), len(set(owned)))
        classes = {n["class"] for n in repair}
        self.assertEqual(classes, {"build", "config", "source", "runtime", "behavior"})
        by = {n["outcome_id"]: n for n in plan["nodes"]}
        self.assertTrue(by["source:u:dto-mapper"]["shared_prerequisite"])
        self.assertIn("source:u:dto-mapper", by["source:rk:item"]["parents"])  # support before what it supports
        self.assertNotIn("source:rk:item", by["source:u:dto-mapper"]["parents"])
        rt = by["runtime:package:rk:package:spel"]
        self.assertTrue({"source:rk:item", "source:rk:order", "source:u:dto-mapper"} <= set(rt["parents"]))
        self.assertEqual(rt["acceptance"]["checks"], ["worklist-absent", "gate:runtime"])  # compile alone never discharges
        for n in plan["nodes"]:
            if n["role"] != "deliver":
                self.assertIn(OG.CONTROL_M2, n["parents"], n["outcome_id"])  # nothing escapes the open-M2 hold
        self.assertEqual([n["assignee"] for n in plan["nodes"] if n["role"] == "deliver"], [None, None, None])
        self.assertEqual({d["obligation_id"]: d["disposition"] for d in plan["dispositions"]},
                         {"inc:superseded:resteasy": "superseded", "inc:web:optional-logging": "optional"})
        ids = [u["id"] for u in plan["unresolved"]]
        self.assertIn("unresolved:verification:http:com.acme.shop.web.AdminController", ids)  # named, not a generic outcome
        self.assertIn("unresolved:unlocatable:inc:unlocatable:jndi", ids)
        self.assertEqual(plan["counts"]["baseline_outcomes"], 8)
        self.assertEqual((plan["counts"]["additions"], plan["counts"]["accepted"], plan["counts"]["unfinished"]), (0, 0, 8))
        # a grant is one cluster, never the union: item's plan paths are one file
        self.assertEqual(by["source:u:dto-mapper"]["plan_paths"], sorted(SHOP["worklist"]["clusters"][2]["write_set"]))

    def test_descriptions_carry_no_machine_authority(self):
        for n in derive()["nodes"]:
            d = n["description"]
            self.assertNotIn("```", d)
            self.assertNotIn("{", d)
            self.assertNotIn("files_writable", d)
            self.assertNotIn(".java", d.replace(n.get("subject", ""), "")) if n["class"] != "source" else None
            self.assertLessEqual(d.count(". "), 4)
            if n["role"] == "assess":
                for token in ("ACCEPT", "REFUSE", "PROVISIONAL"):
                    self.assertNotIn(token, d)                                   # no prescribed verdict

    def test_structurally_different_non_http_application(self):
        plan = derive(LEDGER)
        by = {n["outcome_id"]: n for n in plan["nodes"]}
        self.assertIn("behavior:scheduled:org.example.ledger.jobs.NightlyReconcile", by)
        self.assertIn("behavior:messaging:org.example.ledger.msg.PaymentListener", by)
        self.assertFalse(any(k.startswith("behavior:http") for k in by))
        self.assertIn("parity:reconcile-run", by["behavior:scheduled:org.example.ledger.jobs.NightlyReconcile"]["obligations"])
        # the shared repository sorts AFTER one consumer in the work list, and is still its prerequisite
        self.assertIn("source:rk:repo", by["source:rk:jobs"]["parents"])
        self.assertTrue(by["source:rk:repo"]["shared_prerequisite"])
        self.assertEqual([u["id"] for u in plan["unresolved"]], ["unresolved:verification:main:org.example.ledger.Main"])
        OG._acyclic(plan["nodes"])

    def test_refusals_never_return_a_partial_plan(self):
        wl = SHOP["worklist"]
        cases = {
            "ADMISSION_EVIDENCE_INCOMPLETE": dict(entry_points=None),
            "ADMISSION_INPUT": dict(worklist=dict(wl, items=wl["items"] + [wl["items"][0]])),
        }
        for code, kw in cases.items():
            with self.assertRaises(OG.PlanError) as cm:
                derive(**kw)
            self.assertEqual(cm.exception.code, code)
        unknown = copy.deepcopy(wl)
        unknown["measure"]["known"] = False
        with self.assertRaises(OG.PlanError) as cm:
            derive(worklist=unknown)
        self.assertEqual(cm.exception.code, "ADMISSION_EVIDENCE_INCOMPLETE")   # missing evidence is not an empty list
        orphan = copy.deepcopy(wl)
        orphan["clusters"] = orphan["clusters"][1:]
        with self.assertRaises(OG.PlanError) as cm:
            derive(worklist=orphan)
        self.assertEqual(cm.exception.code, "OBLIGATION_ORPHAN")
        big = copy.deepcopy(wl)
        big["clusters"][3]["write_set"] = ["src/main/java/F%d.java" % i for i in range(21)]
        with self.assertRaises(OG.PlanError) as cm:
            derive(worklist=big)
        self.assertEqual(cm.exception.code, "SCOPE_BOUND")
        tests = copy.deepcopy(wl)
        tests["clusters"][3]["write_set"].append("src/test/java/X.java")
        with self.assertRaises(OG.PlanError) as cm:
            derive(worklist=tests)
        self.assertEqual(cm.exception.code, "SCOPE_BOUND")
        mixed = copy.deepcopy(LEDGER["worklist"])
        mixed["items"].append(dict(mixed["items"][-1], id="parity:other", entry_point="ep:org.example.Other#x():scheduled"))
        mixed["clusters"][-1]["items"].append("parity:other")
        with self.assertRaises(OG.PlanError) as cm:
            derive(LEDGER, worklist=mixed)
        self.assertEqual(cm.exception.code, "ADMISSION_UNSUPPORTED")

    def test_deterministic_under_permutation(self):
        a = derive()
        wl = copy.deepcopy(SHOP["worklist"])
        wl["items"].reverse()
        wl["clusters"].reverse()
        b = derive(worklist=wl, entry_points=list(reversed(SHOP["entry_points"])))
        self.assertEqual(a["digest"], b["digest"])

    def test_identity_frozen_across_rename_and_regrouping(self):
        plan = derive()
        frozen = {n["outcome_id"]: {"obligations": n["obligations"], "natural_key": n.get("natural_key")}
                  for n in plan["nodes"] if n["role"] == "repair"}
        renamed = copy.deepcopy(SHOP)
        for e in renamed["entry_points"]:
            e["entry_point_id"] = e["entry_point_id"].replace("ItemController", "CatalogResource")
        # the obligation ids of the verification responsibilities change with the entry point...
        again = derive(renamed, oracles={k.replace("ItemController", "CatalogResource"): v for k, v in SHOP["oracles"].items()})
        groups = [n for n in again["nodes"] if n["role"] == "repair"]
        # ...so the renamed behavior group is NEW unless lineage says otherwise; the untouched ones resolve to themselves
        res = OG.resolve_identities(frozen, groups)
        self.assertEqual(res["source:rk:item"]["outcome_id"], "source:rk:item")
        self.assertEqual(res["behavior:http:com.acme.shop.web.CatalogResource"]["resolution"], "new")
        # with an alias recorded (an explicit rename), the frozen identity and its budget are kept
        frozen["behavior:http:com.acme.shop.web.ItemController"]["aliases"] = ["http:com.acme.shop.web.CatalogResource"]
        res = OG.resolve_identities(frozen, groups)
        self.assertEqual(res["behavior:http:com.acme.shop.web.CatalogResource"]["outcome_id"], "behavior:http:com.acme.shop.web.ItemController")
        # regrouping two frozen outcomes' obligations into one group is ambiguous
        merged = {"outcome_id": "source:merged", "natural_key": "x", "obligations": ["err:web:item-uricomponents", "err:web:order-uricomponents"]}
        with self.assertRaises(OG.PlanError) as cm:
            OG.resolve_identities(frozen, [merged])
        self.assertEqual(cm.exception.code, "IDENTITY_AMBIGUOUS")
        # a regrouped cluster keeping an owned obligation resolves to its frozen owner (no fresh budget)
        regroup = {"outcome_id": "source:rk:item-v2", "natural_key": "rk:item-v2", "obligations": ["err:web:item-uricomponents", "err:new"]}
        self.assertEqual(OG.resolve_identities(frozen, [regroup])["source:rk:item-v2"]["outcome_id"], "source:rk:item")


# ===========================================================================
class Protocol(unittest.TestCase):
    """A13 and the execution gate."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ob-proto-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self, protocol=None, execution=None, declaration=False):
        r = self.tmp / ("r%d" % len(list(self.tmp.iterdir())))
        (r / ".hermes").mkdir(parents=True)
        conf = {"board_protocol": protocol} if protocol else {}
        (r / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "configuration": conf}))
        planner = {"outcome_board": {"execution": execution}} if execution else {}
        (r / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": planner}}))
        if declaration:
            (r / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": "x"}))
        return r

    def test_default_is_serial_and_golden_is_unchanged(self):
        r = self.root()
        sel = P.select_protocol(r)
        self.assertEqual((sel.protocol, sel.execution), (P.SERIAL, P.DISABLED))
        self.assertEqual(P.execution_gate(r)[0][0], "PROTOCOL_NOT_OUTCOME")
        golden = LIB.parents[1] / "run-defaults.json"
        self.assertNotIn("board_protocol", json.loads(golden.read_text())["configuration"])
        pins = json.loads((LIB.parent / "pins.json").read_text())
        self.assertNotIn("outcome_board", pins["pins"]["planner"])
        self.assertIsNone(HK.terminator(str(r), kind="complete", profile="implementer", env={}, audit_green=lambda: True))

    def test_execution_modes(self):
        self.assertEqual(P.execution_gate(self.root(P.OUTCOME))[0][0], "OUTCOME_EXECUTION_DISABLED")
        self.assertEqual(P.execution_gate(self.root(P.OUTCOME, "qualification")), [])
        # any factory declaration present takes qualification away: an unverifiable one is unbound,
        # a valid one refuses qualification
        self.assertIn(P.execution_gate(self.root(P.OUTCOME, "qualification", declaration=True))[0][0],
                      ("PROTOCOL_UNBOUND", "OUTCOME_QUALIFICATION_REFUSED"))
        r = self.root(P.OUTCOME, "qualification")
        sel = P.Selection(P.OUTCOME, P.QUALIFICATION, "run-defaults+pins", False, "OK")
        self.assertEqual(P.execution_gate(r, sel)[0][0], "OUTCOME_QUALIFICATION_REFUSED")
        sel = P.Selection(P.OUTCOME, P.QUALIFICATION, "run-control", True, "governed")
        self.assertEqual(P.execution_gate(r, sel)[0][0], "OUTCOME_QUALIFICATION_REFUSED")
        r = self.root(P.OUTCOME, "enabled")
        (r / P.STORE_DIR).mkdir(parents=True)
        code, why = P.execution_gate(r)[0]
        self.assertEqual(code, "AUTHORITY_UNPROTECTED")                     # F1: no protected writer exists
        self.assertIn("owned by the calling uid", why)
        self.assertEqual(P.execution_gate(self.root("board/v9", "qualification"))[0][0], "PROTOCOL_UNKNOWN")

    def test_mixed_state_refuses_both_ways(self):
        r = self.root(P.OUTCOME, "qualification")
        (r / "verification" / "loop").mkdir(parents=True)
        (r / "verification" / "loop" / "issued.json").write_text(json.dumps({"idempotency_key": "k4:c:1:abcd"}))
        self.assertEqual(P.execution_gate(r)[0][0], "PROTOCOL_MIXED")
        s = self.root()
        (s / P.STORE_DIR).mkdir(parents=True)
        (s / P.STORE_FILE).write_bytes(b"")
        self.assertEqual(P.mixed_state(s)[0][0], "PROTOCOL_MIXED")
        out = HK.terminator(str(s), kind="complete", profile="implementer", env={}, audit_green=lambda: True)
        self.assertEqual(out["code"], "PROTOCOL_MIXED")


# ===========================================================================
class Publication(unittest.TestCase):
    """A2/A3: interrupted publication converges; archived/duplicate identity stops."""

    def tearDown(self):
        for r in getattr(self, "runs", []):
            r.close()

    def mk(self, **kw):
        self.runs = getattr(self, "runs", [])
        r = Run(**kw)
        self.runs.append(r)
        return r

    def test_complete_graph_before_release_and_readback(self):
        r = self.mk()
        self.assertEqual(G.readback(r.store, r.native), [])
        self.assertEqual(r.store.meta("publication_state"), "complete")
        # M3/M4 assigned under the open M2; M5 unassigned
        for n in r.plan["nodes"]:
            t = r.native.task(r.tid(n["outcome_id"]))
            self.assertEqual(t["assignee"], None if n["role"] == "deliver" else "implementer")
            self.assertEqual(t["status"], "todo")                          # held by the open M2 parent
            self.assertNotIn("```", t["body"])
        # an issue before M2 release refuses
        with self.assertRaises(L.Refusal) as cm:
            r.issue("build:rk:pom")
        self.assertEqual(cm.exception.code, "ISSUE_BEFORE_RELEASE")
        r.native.end_run(r.tid("build:rk:pom"), "todo")

    def test_interruption_after_each_durable_step_converges(self):
        for point in ("after-create", "after-attach"):
            r = self.mk(publish=False)
            store = G.init_store(r.root, run_id="r1", m2_task=r.m2, native_db=r.native.db_path, protocol=P.OUTCOME)
            G.persist_plan(store, r.plan)
            for crash_at in range(3):
                os.environ.update(OB_FAULT=point, OB_FAULT_MODE="raise")
                try:
                    G.publish_plan(r.root, store, r.native, r.plan, m2_task=r.m2)
                except Crash:
                    pass
                finally:
                    os.environ.pop("OB_FAULT", None)
                    os.environ.pop("OB_FAULT_MODE", None)
            G.publish_plan(r.root, store, r.native, r.plan, m2_task=r.m2)
            self.assertEqual(G.complete_generation(store, r.native), [], point)
            r.store = store
            for n in r.plan["nodes"]:
                live = [x for x in r.native.by_key(G.native_key("r1", n)) if x["status"] != "archived"]
                self.assertEqual(len(live), 1, (point, n["outcome_id"]))
                self.assertEqual(len(r.native.attachments(live[0]["id"])), 1, (point, n["outcome_id"]))
            # a partial generation never released M2: before completion the M2 check refused
            self.assertEqual(store.meta("publication_state"), "complete")

    def test_partial_publication_cannot_release(self):
        r = self.mk(publish=False)
        store = G.init_store(r.root, run_id="r1", m2_task=r.m2, native_db=r.native.db_path, protocol=P.OUTCOME)
        G.persist_plan(store, r.plan)
        os.environ.update(OB_FAULT="after-create", OB_FAULT_MODE="raise")
        try:
            G.publish_plan(r.root, store, r.native, r.plan, m2_task=r.m2)
        except Crash:
            pass
        finally:
            os.environ.pop("OB_FAULT")
            os.environ.pop("OB_FAULT_MODE")
        with self.assertRaises(L.Refusal) as cm:
            L.check_complete(r.ctx(), task_id=r.m2, run_id=r.m2_run, profile="reviewer", audit_green=True)
        self.assertEqual(cm.exception.code, "M2_PUBLICATION_INCOMPLETE")

    def test_archived_and_duplicate_identity_stop(self):
        r = self.mk()
        tid = r.tid("config:rk:cfg")
        r.native.archive(tid)
        self.assertTrue(any("archived" in g for g in G.readback(r.store, r.native)))
        with self.assertRaises(G.PublishError) as cm:
            G.publish_plan(r.root, r.store, r.native, r.plan, m2_task=r.m2)
        self.assertEqual(cm.exception.code, "PUBLICATION_ARCHIVED")          # never re-created
        r2 = self.mk(publish=False)
        key = G.native_key("r1", r2.plan["nodes"][0])
        for _ in range(2):   # two live rows with one key (e.g. a racing creator)
            r2.native.n += 1
            t = "t_dup%04d" % r2.native.n
            r2.native.tasks[t] = {"id": t, "status": "ready", "idempotency_key": key, "assignee": None, "title": "x",
                                  "body": "", "skills": []}
        store = G.init_store(r2.root, run_id="r1", m2_task=r2.m2, native_db=r2.native.db_path, protocol=P.OUTCOME)
        G.persist_plan(store, r2.plan)
        with self.assertRaises(G.PublishError) as cm:
            G.publish_plan(r2.root, store, r2.native, r2.plan, m2_task=r2.m2)
        self.assertEqual(cm.exception.code, "PUBLICATION_DUPLICATE")

    def test_attachment_bytes_and_caller_identity(self):
        r = self.mk()
        pub = dict(r.store.conn.execute("SELECT * FROM publication WHERE outcome_id='build:rk:pom'").fetchone())
        att = [a for a in r.native.attachments(pub["task_id"]) if a["id"] == pub["attachment_id"]][0]
        Path(att["stored_path"]).write_text("tampered")
        self.assertTrue(any("bytes differ" in g for g in G.readback(r.store, r.native)))
        with self.assertRaises(G.PublishError) as cm:
            G.init_store(r.root, run_id="r1", m2_task="t_other", native_db=r.native.db_path, protocol=P.OUTCOME)
        self.assertEqual(cm.exception.code, "PUBLICATION_FOREIGN")
        with self.assertRaises(G.PublishError) as cm:
            G.init_store(r.root, run_id="r1", m2_task=r.m2, native_db="/elsewhere/kanban.db", protocol=P.OUTCOME)
        self.assertEqual(cm.exception.code, "NATIVE_REDIRECTED")
        other = derive(run_id="r1", max_attempts=5)
        with self.assertRaises(G.PublishError) as cm:
            G.persist_plan(r.store, other)
        self.assertEqual(cm.exception.code, "PUBLICATION_REPLAN")          # identity frozen at publication


# ===========================================================================
class Authority(unittest.TestCase):
    """F1/A5/A10: missing, tampered, redirected, stale, foreign, unadmitted."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def test_valid_path_and_write_scope(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        self.assertEqual(iss["allowed_paths"], ["pom.xml"])
        ctx = r.ctx()
        L.check_write(ctx, task_id=tid, run_id=run, rel_paths=["pom.xml"])
        for bad, code in (("src/main/java/com/acme/shop/web/ItemController.java", "WRITE_OUTSIDE_ISSUE"),
                          ("verification/outcome-board/authority.sqlite3", "STORE_WRITE_REFUSED"),
                          (".hermes/pins.json", "STORE_WRITE_REFUSED")):
            with self.assertRaises(L.Refusal) as cm:
                L.check_write(ctx, task_id=tid, run_id=run, rel_paths=[bad])
            self.assertEqual(cm.exception.code, code)
        # a body that claims a wider write set changes nothing
        r.native.tasks[tid]["body"] += '\n```json\n{"files_writable": ["src/"]}\n```'
        with self.assertRaises(L.Refusal):
            L.check_write(ctx, task_id=tid, run_id=run, rel_paths=["src/main/java/com/acme/shop/web/ItemController.java"])
        self.assertTrue(any("body differs" in g for g in G.readback(r.store, r.native)))

    def test_missing_tampered_redirected_stale(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        # stale native run: a reclaim gives a new run; the old run's issue no longer acts
        r.native.end_run(tid, "ready")
        run2, lock2 = r.native.claim(tid, pid=dead_pid())
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=tid, run_id=run, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "ISSUE_STALE_RUN")
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=tid, run_id=run2, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "ISSUE_STALE_RUN")               # new run needs its own issue
        L.issue(r.ctx(), task_id=tid, run_id=run2, claim_lock=lock2, pid=dead_pid(), pgid=0)
        L.check_write(r.ctx(), task_id=tid, run_id=run2, rel_paths=["pom.xml"])
        # redirected native board
        other = FakeNative(r.tmp / "other")
        other.db_path = str(r.tmp / "other.db")
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(other), task_id=tid, run_id=run2, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "NATIVE_REDIRECTED")
        # inconsistent widening of the issue record
        con = sqlite3.connect(str(r.root / P.STORE_FILE))
        con.execute("UPDATE issues SET allowed_paths=? WHERE task_id=? AND state='active'", (json.dumps(["pom.xml", "src/x.java"]), tid))
        con.commit()
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=tid, run_id=run2, rel_paths=["src/x.java"])
        self.assertEqual(cm.exception.code, "STORE_TAMPERED")
        # a ledger row edited in place
        con.execute("UPDATE ledger SET doc=? WHERE seq=1", (json.dumps({"forged": True}),))
        con.commit()
        con.close()
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=tid, run_id=run2, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "STORE_TAMPERED")
        # redirected store (a symlink to a copy) and a deleted store
        store_dir = r.root / P.STORE_DIR
        shutil.copytree(store_dir, r.tmp / "copy")
        shutil.rmtree(store_dir)
        os.symlink(r.tmp / "copy", store_dir)
        with self.assertRaises(StoreError) as cm:
            r.ctx()
        self.assertEqual(cm.exception.code, "STORE_REDIRECTED")
        os.unlink(store_dir)
        with self.assertRaises(StoreError) as cm:
            r.ctx()
        self.assertEqual(cm.exception.code, "STORE_MISSING")

    def test_consistent_restamp_is_the_documented_cooperative_limit(self):
        """F1: a same-UID consistent rewrite of the issue AND its sealed ledger
        row is not detectable by this store. That is why 'enabled' refuses
        AUTHORITY_UNPROTECTED; the claim is recorded, not hidden."""
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        store = Store(r.root)
        widened = ["pom.xml", "src/anything.java"]
        con = sqlite3.connect(str(r.root / P.STORE_FILE))
        con.execute("UPDATE issues SET allowed_paths=? WHERE task_id=?", (json.dumps(widened), tid))
        rows = con.execute("SELECT seq, outcome_id, kind, budget_key, attempt_key, doc FROM ledger ORDER BY seq").fetchall()
        prev = "0" * 64
        for seq, oid, kind, bk, ak, doc in rows:
            d = json.loads(doc)
            if kind == "issue" and d.get("task_id") == tid:
                d["allowed_paths"] = sorted(widened)
                doc = canonical(d)
            h = sha(prev + canonical([oid, kind, bk, ak, doc]))
            con.execute("UPDATE ledger SET doc=?, prev=?, hash=? WHERE seq=?", (doc, prev, h, seq))
            prev = h
        con.execute("UPDATE meta SET value=? WHERE key='ledger_head'", (prev,))
        con.commit()
        con.close()
        L.check_write(r.ctx(), task_id=tid, run_id=run, rel_paths=["src/anything.java"])  # accepted: cooperative store
        (r.root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "enabled"}}}}))
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=tid, run_id=run, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "AUTHORITY_UNPROTECTED")
        del store

    def test_older_budget_restore_is_detected_from_the_board(self):
        r = self.r
        snap = r.tmp / "old.sqlite3"
        shutil.copy(r.root / P.STORE_FILE, snap)
        tid, run, iss = r.issue("build:rk:pom")
        ctx = r.ctx()
        for i in (1, 2):
            L.record_verdict(ctx, task_id=tid, run_id=run, verdict="REVERTED", candidate="x%d" % i, attempt=str(i), reason="measure rose")
        self.assertEqual(sum(1 for c in r.native.comments(tid) if c.startswith(MARKER + " rejected")), 2)
        r.native.end_run(tid, "ready")
        shutil.copy(snap, r.root / P.STORE_FILE)                               # an older, internally valid store
        run2, lock2 = r.native.claim(tid, pid=dead_pid())
        with self.assertRaises(L.Refusal) as cm:
            L.issue(r.ctx(), task_id=tid, run_id=run2, claim_lock=lock2, pid=dead_pid(), pgid=0)
        self.assertEqual(cm.exception.code, "STORE_ROLLBACK")

    def test_manual_claims_and_unaccepted_parents_grant_nothing(self):
        r = self.r
        # a manually claimed, unadmitted M5 stage
        prep = r.tid("deliver:prepare:c1")
        r.native.tasks[prep]["assignee"] = "implementer"
        run, lock = r.native.claim(prep, pid=dead_pid())
        with self.assertRaises(L.Refusal) as cm:
            L.issue(r.ctx(), task_id=prep, run_id=run, claim_lock=lock, pid=dead_pid(), pgid=0)
        self.assertEqual(cm.exception.code, "ISSUE_UNGRANTED")
        with self.assertRaises(L.Refusal) as cm:
            L.check_write(r.ctx(), task_id=prep, run_id=run, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "ISSUE_MISSING")
        with self.assertRaises(L.Refusal) as cm:
            L.check_complete(r.ctx(), task_id=prep, run_id=run, profile="implementer", audit_green=True)
        self.assertEqual(cm.exception.code, "DELIVER_UNGRANTED")
        r.native.end_run(prep, "todo")
        # a parent completed natively without domain acceptance
        pom = r.tid("build:rk:pom")
        r.native.complete(pom)
        r.native.complete(r.tid("config:rk:cfg"))
        with self.assertRaises(L.Refusal) as cm:
            r.issue("source:u:dto-mapper")
        self.assertEqual(cm.exception.code, "ISSUE_PARENT_UNACCEPTED")
        # a manual completion of an unaccepted outcome is refused
        tid, run, iss = r.claim("source:rk:item")
        with self.assertRaises(L.Refusal) as cm:
            L.check_complete(r.ctx(), task_id=tid, run_id=run, profile="implementer", audit_green=True)
        self.assertEqual(cm.exception.code, "OUTCOME_NOT_ACCEPTED")
        # an archived parent is not a prerequisite
        r.native.end_run(tid, "todo")
        r.native.archive(r.tid("source:u:dto-mapper"))
        with self.assertRaises(L.Refusal) as cm:
            r.issue("source:rk:item")
        self.assertEqual(cm.exception.code, "ISSUE_PARENT_ARCHIVED")

    def test_writer_ownership_requires_quiescence(self):
        r = self.r
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            tid, run, lock = r.claim("build:rk:pom", pid=sleeper.pid)
            L.issue(r.ctx(), task_id=tid, run_id=run, claim_lock=lock, pid=sleeper.pid, pgid=os.getpgid(sleeper.pid))
            r.native.end_run(tid, "ready")                                    # the run ended, its process did not
            tid2, run2, lock2 = r.claim("config:rk:cfg")
            with self.assertRaises(L.Refusal) as cm:
                L.issue(r.ctx(), task_id=tid2, run_id=run2, claim_lock=lock2, pid=dead_pid(), pgid=0)
            self.assertEqual(cm.exception.code, "WRITER_BUSY")
        finally:
            sleeper.kill()
            sleeper.wait()
        iss = L.issue(r.ctx(), task_id=tid2, run_id=run2, claim_lock=lock2, pid=dead_pid(), pgid=0)
        self.assertGreater(iss["generation"], 1)
        # the fenced former writer can no longer act even if it holds a run
        with self.assertRaises(L.Refusal):
            L.check_write(r.ctx(), task_id=tid, run_id=run, rel_paths=["pom.xml"])


# ===========================================================================
class K2HookBranch(unittest.TestCase):
    """The real kernel/pre_tool_call.sh, as a separate process, on an outcome
    run: decisions come from the authority record, never the body or K2_*."""

    HOOK = KERNEL / "pre_tool_call.sh"

    def setUp(self):
        self.r = Run()
        # the destination layout the deployed hook imports from (.hermes/lib, .hermes/kernel)
        mirror_layout(self.r.root)
        self.r.release()
        self.tid, self.run, self.iss = self.r.issue("build:rk:pom")
        self.r.native.sync()

    def tearDown(self):
        self.r.close()

    def hook(self, tool, inp, **env):
        e = dict(os.environ, HERMES_WRITE_SAFE_ROOT=str(self.r.root), K2_ALLOW_ROOT=str(self.r.root),
                 HERMES_PROFILE="implementer", HERMES_KANBAN_TASK=self.tid, HERMES_KANBAN_RUN_ID=str(self.run),
                 HERMES_HOME=str(self.r.tmp / "home"), PYTHONDONTWRITEBYTECODE="1")
        e.update(env)
        payload = {"hook_event_name": "pre_tool_call", "tool_name": tool, "tool_input": inp, "cwd": str(self.r.root)}
        p = subprocess.run(["bash", str(self.HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=e,
                           cwd=str(self.r.root))
        return json.loads(p.stdout or "{}")

    def test_decisions(self):
        root = self.r.root
        self.assertEqual(self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"}), {})
        out = self.hook("write_file", {"path": str(root / "src/main/java/com/acme/shop/web/ItemController.java"), "content": "x"})
        self.assertIn("WRITE_OUTSIDE_ISSUE", out.get("message", ""))
        # neither the body nor K2_* widens the write set
        out = self.hook("write_file", {"path": str(root / "src/main/java/com/acme/shop/web/ItemController.java"), "content": "x"},
                        K2_FILES_WRITABLE="src/main/java/com/acme/shop/web/ItemController.java", K2_CARD_PHASE="M3")
        self.assertIn("WRITE_OUTSIDE_ISSUE", out.get("message", ""))
        # K2 reads path spans (/, ./, ~/): a guardrail on the command text, not a syscall fence (AD-020)
        out = self.hook("terminal", {"command": "cp /dev/null ./verification/outcome-board/authority.sqlite3"})
        self.assertIn("STORE_WRITE_REFUSED", out.get("message", ""))
        out = self.hook("kanban_complete", {"summary": "done"})
        self.assertIn("OUTCOME_NOT_ACCEPTED", out.get("message", ""))
        self.assertEqual(self.hook("kanban_block", {"reason": "x"}), {})
        out = self.hook("kanban_request_review", {"reviewer": "reviewer"})
        self.assertIn("OUTCOME_NO_REVIEW_LANE", out.get("message", ""))
        # a stale run id (another run of the same card) acts under nothing
        out = self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"}, HERMES_KANBAN_RUN_ID=str(self.run + 99))
        self.assertIn("ISSUE_STALE_RUN", out.get("message", ""))
        # execution disabled: every product write refuses by name
        (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "disabled"}}}}))
        out = self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"})
        self.assertIn("OUTCOME_EXECUTION_DISABLED", out.get("message", ""))
        breadcrumbs = (root / "evidence" / "receipts" / "hook" / "complete-invocations.jsonl").read_text()
        self.assertIn("outcome_outcome_not_accepted", breadcrumbs)


# ===========================================================================
class AdvanceBridge(unittest.TestCase):
    """advance.py's outcome-mode hooks (_outcome_bridge): same card, ledger
    verdicts, accept-begin before the commit, re-issue instead of re-mint."""

    def setUp(self):
        sys.path.insert(0, str(LIB.parent / "skills" / "migration" / "fix-until-green" / "scripts"))
        import _outcome_bridge
        self.B = _outcome_bridge
        self.r = Run()
        mirror_layout(self.r.root)
        self.r.release()
        self.tid, self.run, self.iss = self.r.issue("build:rk:pom")
        self.r.native.sync()
        self.env = {k: os.environ.get(k) for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID")}
        os.environ.update(HERMES_KANBAN_TASK=self.tid, HERMES_KANBAN_RUN_ID=str(self.run))

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.r.close()

    def test_reject_reissue_accept_on_one_card(self):
        r, B = self.r, self.B
        self.assertTrue(B.active(r.root))
        self.assertEqual(B.record(r.root, "REVERTED", "cand-1" + "0" * 58, "measure rose"), 0)
        self.assertEqual(Store(r.root).spent(self.iss["budget"]["key"]), 1)
        self.assertEqual(B.reissue(r.root), 0)                               # never a new card
        issued = json.loads((r.root / "verification" / "loop" / "issued.json").read_text())
        self.assertEqual((issued["cluster"], issued["task_id"]), ("c:pom", self.tid))
        self.assertTrue(issued["idempotency_key"].startswith("outcome:v1:r1:build:rk:pom:c:pom:issue"))
        self.assertEqual(P.mixed_state(r.root), [])                          # an outcome-keyed record is not serial
        r.edit("pom.xml", "<fixed/>")
        cand = r.ctx().product_tree()
        self.assertEqual(B.record(r.root, "ACCEPTED", cand), 0)              # accept-begin BEFORE the commit
        git(r.root, "commit", "-qam", "accept")
        r.drop("inc:pom:quarkus-bom")
        self.assertEqual(B.after_accept(r.root, git(r.root, "rev-parse", "HEAD"), cand, {"runtime": {}}, {}), 0)
        self.assertEqual(L._outcome(Store(r.root), "build:rk:pom")["status"], "accepted")
        self.assertEqual(len([t for t in r.native.tasks.values() if t.get("idempotency_key", "").startswith("outcome:")]),
                         len([n for n in r.plan["nodes"] if n["role"] == "repair"]))  # no card was minted per attempt

    def test_serial_only_continuations_refuse_on_an_outcome_run(self):
        r = self.r
        script = LIB.parent / "skills" / "migration" / "fix-until-green" / "scripts" / "resume-after-m4.py"
        p = subprocess.run([sys.executable, str(script), "--root", str(r.root)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("PROTOCOL_NOT_SERIAL", p.stderr)
        import m5_delivery
        out = m5_delivery.start_delivery(r.root, runner=lambda argv: (1, "", "not called"))
        self.assertTrue(out["blocked"])
        self.assertIn("PROTOCOL_NOT_SERIAL", out["reason"])
        self.assertEqual(out["created"], [])

    def test_serial_root_is_untouched(self):
        tmp = Path(tempfile.mkdtemp(prefix="ob-serial-"))
        try:
            self.assertFalse(self.B.active(tmp))
            self.assertIsNone(self.B.record(tmp, "REVERTED", "x"))
            self.assertIsNone(self.B.reissue(tmp))
            self.assertIsNone(self.B.after_accept(tmp, "sha", "x", {}, {}))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
class SameOutcomeRepair(unittest.TestCase):
    """A7/A8: rejection stays on the outcome; budgets survive restart; pending candidates."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def test_reject_restart_pending_accept(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        ctx = r.ctx()
        r.edit("pom.xml", "<bad/>")
        out = L.record_verdict(ctx, task_id=tid, run_id=run, verdict="REVERTED", candidate=ctx.product_tree(), attempt="1",
                               reason="new mandatory obligation")
        self.assertEqual((out["spent"], out["card"]), (1, "stays open (same outcome)"))
        git(r.root, "checkout", "--", "pom.xml")
        # replaying the same rejection does not spend twice
        L.record_verdict(ctx, task_id=tid, run_id=run, verdict="REVERTED", candidate="x", attempt="1")
        self.assertEqual(Store(r.root).spent(iss["budget"]["key"]), 1)
        # restart: a new native run, same outcome, same budget
        r.native.end_run(tid, "ready")
        run2, lock2 = r.native.claim(tid, pid=dead_pid())
        iss2 = L.issue(r.ctx(), task_id=tid, run_id=run2, claim_lock=lock2, pid=dead_pid(), pgid=0)
        self.assertEqual((iss2["outcome_id"], iss2["budget"]["spent"]), ("build:rk:pom", 1))
        # pending candidate retained across a restart
        r.edit("pom.xml", "<candidate/>")
        cand = r.ctx().product_tree()
        L.record_verdict(r.ctx(), task_id=tid, run_id=run2, verdict="VERIFICATION_PENDING", candidate=cand, attempt="2",
                         retained={"paths": ["pom.xml"]})
        r.native.end_run(tid, "ready")
        run3, lock3 = r.native.claim(tid, pid=dead_pid())
        iss3 = L.issue(r.ctx(), task_id=tid, run_id=run3, claim_lock=lock3, pid=dead_pid(), pgid=0)   # candidate tree accepted as the retained one
        self.assertTrue(iss3["retained_candidate"])
        rp = L.restore_pending(r.ctx(), task_id=tid, run_id=run3, candidate_now=r.ctx().product_tree())
        self.assertEqual((rp["baseline_moved"], rp["spent"]), (False, 1))
        # an unexplained edit is not blessed as the next baseline
        r.native.end_run(tid, "ready")
        r.edit("pom.xml", "<something-else/>")
        run4, lock4 = r.native.claim(tid, pid=dead_pid())
        with self.assertRaises(L.Refusal) as cm:
            L.issue(r.ctx(), task_id=tid, run_id=run4, claim_lock=lock4, pid=dead_pid(), pgid=0)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        r.edit("pom.xml", "<candidate/>")
        L.issue(r.ctx(), task_id=tid, run_id=run4, claim_lock=lock4, pid=dead_pid(), pgid=0)
        # acceptance: completion only after the domain says accepted
        with self.assertRaises(L.Refusal):
            L.check_complete(r.ctx(), task_id=tid, run_id=run4, profile="implementer", audit_green=False)
        L.record_verdict(r.ctx(), task_id=tid, run_id=run4, verdict="ACCEPTED", candidate=r.ctx().product_tree(), attempt="3")
        git(r.root, "commit", "-qam", "accept")
        r.drop("inc:pom:quarkus-bom")
        out = L.accept_commit(r.ctx(), task_id=tid, run_id=run4, attempt="3", commit=git(r.root, "rev-parse", "HEAD"),
                              measurement={"classes": ["build"]})
        self.assertTrue(out["outcome_accepted"])
        L.check_complete(r.ctx(), task_id=tid, run_id=run4, profile="implementer", audit_green=False)
        acc = L.progress_account(Store(r.root), r.ctx().product_tree())
        self.assertEqual((acc["accepted_historically"], acc["unfinished"]), (1, 7))   # rejects never raised it

    def test_budget_exhaustion_and_split_successors_share_one_allowance(self):
        r = self.r
        store = Store(r.root)
        plan = store.current_revision()
        limit = L._outcome(store, "source:rk:item")["budget_limit"]
        split = L.plan_split(store, plan, "source:rk:item", {"a": ["err:web:item-uricomponents"]}, evidence="x")
        self.assertEqual(split["counts"]["replaced_or_removed"], 1)
        with self.assertRaises(L.Refusal) as cm:
            L.plan_split(store, plan, "source:rk:item", {"a": []}, evidence="x")
        self.assertEqual(cm.exception.code, "SPLIT_NOT_CONSERVING")
        two = copy.deepcopy(plan)
        n = next(x for x in two["nodes"] if x["outcome_id"] == "source:rk:item")
        n["obligations"] = ["err:a", "err:b"]
        two["digest"] = OG.plan_digest(two)
        doc = L.plan_split(store, two, "source:rk:item", {"a": ["err:a"], "b": ["err:b"]}, evidence="evidence")
        succ = [x for x in doc["nodes"] if "/split:" in x["outcome_id"]]
        self.assertEqual({s["budget"]["key"] for s in succ}, {L._outcome(store, "source:rk:item")["budget_key"]})
        # both successors spend the ONE remaining allowance
        key = succ[0]["budget"]["key"]
        with store.txn() as c:
            for i in range(limit):
                store.append(c, succ[i % 2]["outcome_id"], "reject", {"i": i}, budget_key=key, attempt_key="s%d" % i)
        self.assertEqual(store.spent(key), limit)
        # the pom outcome: exhaustion is visible and further issue refuses
        tid, run, iss = r.issue("build:rk:pom")
        for i in range(iss["budget"]["limit"]):
            out = L.record_verdict(r.ctx(), task_id=tid, run_id=run, verdict="REVERTED", candidate="c%d" % i, attempt="e%d" % i)
        self.assertTrue(out["exhausted"])
        r.native.end_run(tid, "ready")
        with self.assertRaises(L.Refusal) as cm:
            r.issue("build:rk:pom")
        self.assertIn(cm.exception.code, ("ISSUE_ALREADY_DONE", "ISSUE_BUDGET_EXHAUSTED"))

    def test_crash_between_accept_begin_and_commit_recovers_that_transaction(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        r.edit("pom.xml", "<ok/>")
        cand = r.ctx().product_tree()
        base = git(r.root, "rev-parse", "HEAD")
        L.record_verdict(r.ctx(), task_id=tid, run_id=run, verdict="ACCEPTED", candidate=cand, attempt="1")
        git(r.root, "commit", "-qam", "accepted")                              # crash here: no accept-commit row
        sha1 = git(r.root, "rev-parse", "HEAD")

        def commits(baseline):
            return [(sha1, base, cand)]
        out = L.recover_accept(r.ctx(), oid="build:rk:pom", commits=commits)
        self.assertEqual(out, [{"attempt": "%s:1" % run, "recovered_commit": sha1}])
        self.assertEqual(L.recover_accept(r.ctx(), oid="build:rk:pom", commits=commits), [])   # never twice
        self.assertEqual(Store(r.root).meta("accepted_commit"), sha1)
        self.assertEqual(Store(r.root).spent(iss["budget"]["key"]), 0)


# ===========================================================================
class Continuations(unittest.TestCase):
    """F2/C3: durable intents; REFUSE -> repair -> successor assessment -> M5."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def parity_regression(self):
        J = "src/main/java/com/acme/shop/"
        item = {"id": "parity:items-list:body", "source": "parity", "kind": "parity", "category": "mandatory",
                "path": J + "web/ItemController.java", "line": 0, "rule_id": "",
                "entry_point": "ep:com.acme.shop.web.ItemController#list():http", "scenario": "items-list"}
        cl = {"id": "c:p-items", "kind": "parity", "items": [item["id"]], "path": item["path"], "write_set": [item["path"]],
              "order_key": [5, 0, item["path"]], "status": "open", "gate": "parity"}
        return [item], [cl]

    def test_m2_release_intent_and_crash_before_reconcile(self):
        r = Run()
        try:
            L.check_complete(r.ctx(), task_id=r.m2, run_id=r.m2_run, profile="reviewer", audit_green=True)
            self.assertEqual(Store(r.root).meta("release_in_progress"), "1")
            with self.assertRaises(StoreError) as cm:   # no revision can slip in during release
                s = Store(r.root)
                s.commit_revision(dict(r.plan, revision=2), kind="x", parent=1)
            self.assertEqual(cm.exception.code, "REVISION_BLOCKED_BY_RELEASE")
            self.assertEqual(R.tick(r.root, r.native), [{"intent": "m2-release", "state": "pending"}])  # M2 not done yet
            r.native.complete(r.m2)                                           # process dies here: nothing else ran
            self.assertEqual(R.tick(r.root, r.native), [{"intent": "m2-release", "state": "done"}])
            self.assertEqual(Store(r.root).meta("publication_state"), "released")
        finally:
            r.close()

    def test_refuse_repair_reassess_then_delivery_without_operator(self):
        r = self.r
        r.accept_all_repairs()
        items, clusters = self.parity_regression()
        a1 = r.assess("assess:m4:g1", "REFUSE", new_items=items, new_clusters=clusters)
        # crash after native completion, before and during the continuation
        for point in ("reconcile-after-revision", "reconcile-after-publish", "reconcile-after-assign"):
            os.environ.update(OB_FAULT=point, OB_FAULT_MODE="raise")
            try:
                R.tick(r.root, r.native)
            except Crash:
                pass
            finally:
                os.environ.pop("OB_FAULT")
                os.environ.pop("OB_FAULT_MODE")
        R.tick(r.root, r.native)
        store = Store(r.root)
        intent = dict(store.conn.execute("SELECT * FROM intents WHERE intent_id='m4-assessed:assess:m4:g1'").fetchone())
        self.assertEqual(intent["state"], "done")
        plan = store.current_revision()
        self.assertEqual(plan["revision"], 2)
        follow = "followup:behavior:http:com.acme.shop.web.ItemController:g2"
        by = {n["outcome_id"]: n for n in plan["nodes"]}
        self.assertIn(follow, by)
        self.assertEqual(by["assess:m4:g2"]["parents"], sorted([follow, "assess:m4:g1"]))
        self.assertEqual(by["deliver:prepare:c1"]["binding"], {"assessment": "assess:m4:g2"})
        # the original assessment is preserved, not reopened
        self.assertEqual(r.native.task(a1)["status"], "done")
        self.assertEqual(L._outcome(store, "assess:m4:g1")["status"], "assessed")
        # no duplicate identity; follow-up shares its owner's budget
        for oid in (follow, "assess:m4:g2"):
            self.assertEqual(len([x for x in r.native.by_key(store.conn.execute(
                "SELECT native_key FROM publication WHERE outcome_id=?", (oid,)).fetchone()[0]) if x["status"] != "archived"]), 1)
            self.assertEqual(r.native.task(r.tid(oid))["assignee"], "implementer")
        self.assertEqual(L._outcome(store, follow)["budget_key"], L._outcome(store, "behavior:http:com.acme.shop.web.ItemController")["budget_key"])
        self.assertEqual(G.readback(store, r.native), [])
        acc = L.progress_account(store, r.ctx().product_tree())
        self.assertEqual((acc["baseline"], acc["additions"], acc["active"], acc["unfinished"]), (8, 1, 9, 1))
        # M5 is still held: prepare is not admitted on a REFUSE
        self.assertIsNone(r.native.task(r.tid("deliver:prepare:c1"))["assignee"])
        # repair the follow-up, reassess, and delivery is granted by the continuation alone
        r.native.complete(a1)
        r.accept(follow, classes=("build", "compile", "tests", "runtime", "parity"), scenarios=("items-list",))
        r.drop("inc:unlocatable:jndi")                                         # the unlocatable obligation resolved
        r.assess("assess:m4:g2", "PROVISIONAL_ACCEPT")
        R.tick(r.root, r.native)
        R.tick(r.root, r.native)                                               # idempotent: one grant
        prep = r.tid("deliver:prepare:c1")
        self.assertEqual(r.native.task(prep)["assignee"], "implementer")
        self.assertEqual([c for c in r.native.calls if c == ("assign", prep)], [("assign", prep)])
        # M5 stage runs, records its result, completes; the next stage is granted, a later one is not
        tid, run, iss = r.issue("deliver:prepare:c1")
        L.record_stage_result(r.ctx(), task_id=tid, run_id=run, result={"accepted": True, "build_authorized": True})
        L.check_complete(r.ctx(), task_id=tid, run_id=run, profile="implementer", audit_green=True)
        r.native.complete(tid)
        R.tick(r.root, r.native)
        self.assertEqual(r.native.task(r.tid("deliver:push:c1"))["assignee"], "implementer")
        self.assertIsNone(r.native.task(r.tid("deliver:accept:c1"))["assignee"])
        # a completed delivery stage is never reused for another candidate
        again = L.plan_after_refuse(Store(r.root), Store(r.root).current_revision(),
                                    {"outcome_id": "assess:m4:g2", "assessment_seq": 1, "verdict": "REFUSE"})
        self.assertIsInstance(again, L.Refusal)

    def test_refuse_with_nothing_repairable_stops_visibly(self):
        r = self.r
        r.accept_all_repairs()
        blocked = {"id": "dec:security", "source": "parity", "kind": "parity", "category": "mandatory", "path": "",
                   "line": 0, "rule_id": "", "entry_point": "ep:com.acme.shop.web.ItemController#list():http"}
        r.worklist["unlocatable"] = [{"id": "dec:security"}]
        r.assess("assess:m4:g1", "REFUSE", new_items=[blocked])
        R.tick(r.root, r.native)
        row = Store(r.root).conn.execute("SELECT state, result FROM intents WHERE intent_id='m4-assessed:assess:m4:g1'").fetchone()
        self.assertEqual(row[0], "stopped")
        self.assertIn("REFUSE_NOTHING_REPAIRABLE", row[1])


# ===========================================================================
class Applicability(unittest.TestCase):
    """F3: historical acceptance vs proof applicable to the current candidate."""

    def test_shared_change_invalidates_behavior_proof_until_measured(self):
        r = Run()
        r.release()
        try:
            r.accept_all_repairs()
            store = Store(r.root)
            tree = r.ctx().product_tree()
            acc = L.progress_account(store, tree)
            self.assertEqual((acc["accepted_historically"], acc["proof_applicable"]), (8, 8))
            # outcome B (a follow-up edit to the shared mapper) changes the product tree with a compile/test measurement
            r.edit("src/main/java/com/acme/shop/dto/ItemDto.java", "// shared change\n")
            git(r.root, "commit", "-qam", "shared change")
            t2 = r.ctx().product_tree()
            L.record_measurement(r.ctx(), tree=t2, classes=["compile", "tests", "build", "runtime"], scenarios=[], open_ids=[],
                                 source="accept:other")
            acc = L.progress_account(Store(r.root), t2)
            self.assertEqual(acc["accepted_historically"], 8)                   # history is retained
            self.assertEqual(acc["awaiting_revalidation"], 2)                   # the two behavior outcomes
            self.assertFalse(acc["complete_claim_allowed"])
            # the M4 parity measurement on the final artifact restores current proof
            L.record_measurement(r.ctx(), tree=t2, classes=["parity"], scenarios=["items-list", "items-get-1", "items-get-missing", "orders-create"],
                                 open_ids=[], source="assessment:g1")
            acc = L.progress_account(Store(r.root), t2)
            self.assertEqual((acc["proof_applicable"], acc["awaiting_revalidation"]), (8, 0))
        finally:
            r.close()


# ===========================================================================
def _racer(root: str, who: str, start, out):
    sys.path.insert(0, str(LIB))
    from planner import outcome_lifecycle as LL
    from planner.outcome_store import Store as S, StoreError as SE
    start.wait()
    s = S(Path(root))
    try:
        if who == "effect":
            LL.admit_effect(s, kind="push", candidate="c", operation_id="op-%d" % os.getpid(), expected_rev=1)
        else:
            plan = s.current_revision()
            s.commit_revision(dict(plan, revision=2), kind="revision", parent=1)
        out.put((who, "ok"))
    except (LL.Refusal, SE) as exc:
        out.put((who, exc.code))


class Serialization(unittest.TestCase):
    """F4/C4: revision vs effect admission; uncertain effects are never repeated."""

    def test_revision_racing_effect_admission(self):
        seen = set()
        for i in range(12):
            r = Run()
            try:
                r.release()
                ctx = mp.get_context("fork")
                start, out = ctx.Event(), ctx.Queue()
                procs = [ctx.Process(target=_racer, args=(str(r.root), w, start, out)) for w in ("effect", "revision")]
                for p in procs:
                    p.start()
                start.set()
                for p in procs:
                    p.join(30)
                res = dict(out.get(timeout=5) for _ in procs)
                seen.add((res["effect"], res["revision"]))
                # never both: an admitted effect blocks the revision, a committed revision stales the effect
                self.assertNotEqual((res["effect"], res["revision"]), ("ok", "ok"), res)
                self.assertIn(res, ({"effect": "ok", "revision": "REVISION_BLOCKED_BY_EFFECT"},
                                    {"effect": "EFFECT_STALE_REVISION", "revision": "ok"}))
            finally:
                r.close()
        self.assertTrue(seen)

    def test_effect_crash_recovery_by_identity(self):
        r = Run()
        r.release()
        try:
            s = Store(r.root)
            eid = L.admit_effect(s, kind="push", candidate="c1", operation_id="refs/heads/main@c1", expected_rev=1)
            L.record_effect(s, eid, "sent")
            # crash before the result is recorded; recovery asks the remote by identity
            out = L.recover_effects(s, lambda e: "landed" if e["operation_id"] == "refs/heads/main@c1" else None)
            self.assertEqual(out, [{"effect_id": eid, "state": "landed"}])
            eid2 = L.admit_effect(s, kind="deploy", candidate="c1", operation_id="pr-123", expected_rev=1)
            out = L.recover_effects(s, lambda e: None)                         # unknown stays visible
            self.assertEqual(out, [{"effect_id": eid2, "state": "uncertain"}])
            with self.assertRaises(L.Refusal) as cm:                            # never repeated automatically
                L.admit_effect(s, kind="deploy", candidate="c1", operation_id="pr-123", expected_rev=1)
            self.assertEqual(cm.exception.code, "EFFECT_EXISTS")
            with self.assertRaises(L.Refusal) as cm:                            # nor a different effect while it is unknown
                L.admit_effect(s, kind="push", candidate="c1", operation_id="other", expected_rev=1)
            self.assertEqual(cm.exception.code, "EFFECT_IN_FLIGHT")
            with self.assertRaises(StoreError) as cm:
                s.commit_revision(dict(s.current_revision(), revision=2), kind="x", parent=1)
            self.assertEqual(cm.exception.code, "REVISION_BLOCKED_BY_EFFECT")
            L.record_effect(s, eid2, "failed", {"resolved_by": "operator reading the pipeline run"})
            s.commit_revision(dict(s.current_revision(), revision=2), kind="x", parent=1)
        finally:
            r.close()


# ===========================================================================
class StagePredicates(unittest.TestCase):
    """F5: M5 stage admission from facts at that point only."""

    def good(self):
        return {"candidate": "T", "assessment": {"bound": True, "verdict": "PROVISIONAL_ACCEPT", "candidate": "T"},
                "worklist": {"state": "present", "open_mandatory": 0}, "open_repairs": [], "unresolved_ownership": [],
                "qualifications": [{"id": "g1-kill-ratio", "class": "deferred", "satisfied": False}]}

    def test_prepare(self):
        ok = L.stage_admission("prepare", self.good())
        self.assertTrue(ok["admit"])
        self.assertEqual(ok["deferred_qualifications"], ["g1-kill-ratio"])     # allowed to remain recorded
        self.assertEqual(ok["permissions"], {"deploy_for_validation": False, "ship": False})
        for mut, reason in ((lambda f: f["assessment"].update(verdict="REFUSE"), "ASSESSMENT_REFUSE"),
                            (lambda f: f.update(worklist={"state": "missing"}), "WORKLIST_MISSING"),
                            (lambda f: f.update(worklist={"state": "corrupt"}), "WORKLIST_CORRUPT"),
                            (lambda f: f.update(candidate="T2"), "CANDIDATE_STALE"),
                            (lambda f: f.update(open_repairs=["source:x"]), "OPEN_MANDATORY_REPAIR"),
                            (lambda f: f.update(unresolved_ownership=["unresolved:x"]), "UNRESOLVED_OWNERSHIP"),
                            (lambda f: f["qualifications"].append({"id": "sec", "class": "blocking", "satisfied": False}), "QUALIFICATION_SEC")):
            f = self.good()
            mut(f)
            v = L.stage_admission("prepare", f)
            self.assertFalse(v["admit"])
            self.assertIn(reason, v["reasons"])

    def test_no_circular_requirement_and_deploy_is_not_ship(self):
        push = {"candidate": "T", "preflight": {"accepted": True, "candidate": "T"}, "plan_coherent": True, "build_authorized": True}
        v = L.stage_admission("push", push)
        self.assertTrue(v["admit"])                                            # no live check required before deploy produces it
        self.assertEqual(v["permissions"], {"deploy_for_validation": True, "ship": False})
        acc = {"candidate": "T", "deploy": {"result": "ok", "candidate": "T", "image_digest": "sha256:x"}, "live_inputs": True}
        self.assertTrue(L.stage_admission("accept", acc)["admit"])
        self.assertFalse(L.stage_admission("accept", acc)["permissions"]["ship"])
        self.assertTrue(L.stage_admission("accept", dict(acc, shipping_evidence_complete=True))["permissions"]["ship"])
        self.assertIn("DEPLOYMENT_UNBOUND", L.stage_admission("accept", dict(acc, deploy={"result": "ok", "candidate": "OTHER"}))["reasons"])

    def test_facts_from_disk_treat_corrupt_worklist_as_refusal(self):
        r = Run()
        r.release()
        try:
            (r.root / L.WORKLIST).write_text("{not json")
            f = L.delivery_facts(r.ctx(), "deliver:prepare:c1")
            self.assertEqual(f["worklist"]["state"], "corrupt")
            self.assertIn("WORKLIST_CORRUPT", L.stage_admission("prepare", f)["reasons"])
            (r.root / L.WORKLIST).unlink()
            f = L.delivery_facts(r.ctx(), "deliver:prepare:c1")
            self.assertIn("WORKLIST_MISSING", L.stage_admission("prepare", f)["reasons"])
        finally:
            r.close()


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore", ResourceWarning)  # short-lived Store handles in tests
    warnings.simplefilter("ignore", DeprecationWarning)
    unittest.main(verbosity=1)
