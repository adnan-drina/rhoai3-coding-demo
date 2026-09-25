#!/usr/bin/env python3
"""Serial roadmap after M2: one executable task; planned M4/M5 have no candidate."""
from __future__ import annotations

import copy
import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.canonical import digest, write_canonical  # noqa: E402
from planner.cards import TITLE_DASH, card_title  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, DECIDED_REPAIRS_RECEIPT, SERIAL_ROADMAP, WORKLIST  # noqa: E402
from planner.roadmap import CLAIM_KEYS, compose_serial_roadmap, derive_outcome_accounts  # noqa: E402


def _cluster(cid: str, kind: str, path: str, n: int = 1, status: str = "open") -> dict:
    items = ["%s:%d" % (cid, i) for i in range(n)]
    return {
        "id": cid,
        "path": path,
        "kind": kind,
        "items": items,
        "order_key": kind,
        "status": status,
        "write_set": [path],
    }


def _worklist(*clusters: dict, head: str = "", deferred: list | None = None, runtime_ready: bool = False,
              tuple_=(3, 2, 0, 0)) -> dict:
    clusters_l = list(clusters)
    if not head:
        open_c = [c for c in clusters_l if c.get("status") == "open"]
        head = open_c[0]["id"] if open_c else ""
    return {
        "schema": "rhoai3.worklist/v1",
        "evidence_bundle_sha256": "b" * 64,
        "candidate_sha256": "c" * 64,
        "sources": {},
        "items": [],
        "clusters": clusters_l,
        "deferred": list(deferred or []),
        "blocked_clusters": [c["id"] for c in clusters_l if c.get("status") == "blocked"],
        "head": head,
        "measure": {
            "mandatory_incidents": tuple_[0],
            "compile_errors": tuple_[1],
            "failing_tests": tuple_[2],
            "parity_mismatches": tuple_[3],
            "tuple": list(tuple_),
            "known": True,
            "blocked": 0,
        },
        "order_policy": "build → config → compile → incident → test → parity",
        "runtime": {"ready": runtime_ready},
    }


def _admission(status: str = "ADMITTED") -> dict:
    doc = {
        "schema": "rhoai3.admission-receipt/v2",
        "status": status,
        "planning_only": status != "ADMITTED",
        "reasons": [] if status == "ADMITTED" else ["BLOCK"],
        "blocks": [] if status == "ADMITTED" else [{"class": "TOOL_PIN", "subject": "mta_cli", "detail": "unpinned"}],
        "seals": {},
        "activation": {"mode": "activated"},
        "measure": {"tuple": [3, 2, 0, 0], "known": True},
        "head": "c:pom",
        "counts": {"open_clusters": 2, "deferred": 0, "open_blocks": 0 if status == "ADMITTED" else 1},
        "loop_complete": False,
    }
    doc["receipt_digest"] = digest({k: v for k, v in doc.items() if k != "receipt_digest"})
    return doc


def _root_with(worklist: dict, admission: dict, *, repairs: dict | None = None) -> tuple[Path, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    write_canonical(root / WORKLIST, worklist)
    write_canonical(root / ADMISSION_RECEIPT, admission)
    if repairs is not None:
        write_canonical(root / DECIDED_REPAIRS_RECEIPT, repairs)
    return root, tmp


class SerialRoadmap(unittest.TestCase):
    def _compose(self, worklist: dict, admission: dict, **kwargs) -> dict:
        self.root, tmp = _root_with(worklist, admission, **kwargs)
        self.addCleanup(tmp.cleanup)
        return compose_serial_roadmap(self.root)

    def test_one_executable_m3_and_planned_m4_m5_without_claims(self) -> None:
        pom = _cluster("c:pom", "build", "pom.xml", 2)
        owner = _cluster("c:owner", "compile", "src/Owner.java", 3)
        doc = self._compose(_worklist(pom, owner, head="c:pom"), _admission())
        self.assertEqual(doc["schema"], "rhoai3.serial-roadmap/v1")
        self.assertEqual(doc["parallel_execution"], "deferred")
        self.assertEqual(len(doc["executable"]), 1)
        exe = doc["executable"][0]
        self.assertEqual(exe["class"], "executable")
        self.assertEqual(exe["role"], "M3")
        self.assertEqual(exe["cluster_id"], "c:pom")
        self.assertTrue(exe["admitted"])
        self.assertEqual(exe["title"], card_title(pom, 1))
        self.assertIn(TITLE_DASH, exe["title"])
        planned_roles = [p["role"] for p in doc["planned"]]
        self.assertEqual(planned_roles, ["M3", "M4", "M5", "M5", "M5"])
        self.assertEqual(doc["planned"][0]["cluster_id"], "c:owner")
        self.assertFalse(doc["planned"][0]["admitted"])
        self.assertEqual([p["title"] for p in doc["planned"][1:]], [
            "M4 VERIFY", "M5 PREFLIGHT", "M5 DEPLOY", "M5 VALIDATE",
        ])
        for row in doc["planned"]:
            for key in CLAIM_KEYS:
                self.assertNotIn(key, row)
            self.assertFalse(row["admitted"])
        self.assertEqual(doc["known_work"]["open_clusters"], 2)
        self.assertEqual(doc["known_work"]["head"], "c:pom")
        written = json.loads((self.root / SERIAL_ROADMAP).read_text(encoding="utf-8"))
        self.assertEqual(written["planned"][0]["title"], doc["planned"][0]["title"])
        self.assertNotIn("candidate_sha256", json.dumps(written["planned"]))

    def test_inconclusive_admission_has_no_executable_task(self) -> None:
        pom = _cluster("c:pom", "build", "pom.xml")
        doc = self._compose(_worklist(pom, head="c:pom"), _admission("INCONCLUSIVE"))
        self.assertEqual(doc["executable"], [])
        self.assertEqual(doc["admission_status"], "INCONCLUSIVE")
        self.assertEqual(doc["planned"][0]["cluster_id"], "c:pom")
        self.assertFalse(doc["planned"][0]["admitted"])
        self.assertTrue(any(u["class"] == "ADMISSION" for u in doc["unresolved"]))

    def test_empty_ready_worklist_executes_m4_and_plans_only_m5(self) -> None:
        doc = self._compose(
            _worklist(head="", runtime_ready=True, tuple_=(0, 0, 0, 0)),
            _admission(),
        )
        self.assertEqual(len(doc["executable"]), 1)
        self.assertEqual(doc["executable"][0]["role"], "M4")
        self.assertEqual(doc["executable"][0]["title"], "M4 VERIFY")
        self.assertEqual([p["title"] for p in doc["planned"]], [
            "M5 PREFLIGHT", "M5 DEPLOY", "M5 VALIDATE",
        ])
        for row in doc["planned"]:
            for key in CLAIM_KEYS:
                self.assertNotIn(key, row)

    def test_reconciles_applied_repairs_and_ignores_refused(self) -> None:
        pom = _cluster("c:pom", "build", "pom.xml")
        repairs = {
            "schema": "rhoai3.decided-repairs-receipt/v1",
            "rows": [
                {"id": "r-applied", "adr": "ADR-019", "status": "applied"},
                {"id": "r-already", "adr": "ADR-008", "status": "already-applied"},
                {"id": "r-no", "adr": "ADR-011", "status": "refused"},
            ],
        }
        doc = self._compose(_worklist(pom, head="c:pom"), _admission(), repairs=repairs)
        self.assertEqual([r["id"] for r in doc["reconciled"]], ["r-applied", "r-already"])


_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "remainder-v12-late.json"
_SOURCE_SHA256 = "14369b1433b1d899bd4dd472ff2cc64a1b34231aa1936eea8326917c0974f9aa"
_OUTCOME_KEYS = {"outcome_id", "obligation_ids", "cluster_ids", "plan_paths", "parents", "assignee"}
_MILESTONE_KEYS = {"milestone_id", "parents", "assignee"}
_TOP_KEYS = {
    "schema", "planning_only", "coverage_scope", "outcomes", "counts",
    "unresolved", "milestones", "lineage", "provenance",
}
_EXPECTED = (
    (
        "http-type:org.springframework.samples.petclinic.rest.PetRestController",
        ("parity:2c8c0206f70fc504", "parity:f55ae9ac55731703"),
        ("c:67bfc8d7483e",),
        ("src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java",),
    ),
    (
        "http-type:org.springframework.samples.petclinic.rest.PetTypeRestController",
        ("parity:87ef093c5a26a264",),
        ("c:b0afd88b763b",),
        ("src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java",),
    ),
    (
        "http-type:org.springframework.samples.petclinic.rest.RootRestController",
        ("parity:fd0b32ed739b54b5",),
        ("c:488e7e2d2ac4",),
        ("src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java",),
    ),
    (
        "http-type:org.springframework.samples.petclinic.rest.SpecialtyRestController",
        ("parity:fad5dafbf8f70b85",),
        ("c:90f0b647d099",),
        ("src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java",),
    ),
    (
        "http-type:org.springframework.samples.petclinic.rest.VisitRestController",
        ("parity:89dd7f8e4ba620f1",),
        ("c:996178ac5ebe",),
        ("src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java",),
    ),
)


def _envelope() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _call(env: dict, **overrides) -> dict:
    return derive_outcome_accounts(
        overrides.get("worklist", env["worklist"]),
        overrides.get("unresolved", env["unresolved"]),
        provenance=overrides.get("provenance", env["provenance"]),
        lineage=overrides.get("lineage", env["lineage"]),
    )


def _parity_item(item_id: str, declaring: str = "com.example.Widget", member: str = "get()",
          path: str = "src/Widget.java", **overrides) -> dict:
    row = {
        "id": item_id,
        "entry_point": "ep:%s#%s:http" % (declaring, member),
        "path": path,
        "kind": "parity",
        "category": "mandatory",
        "scenario": "",
        "security_mode": "disabled",
    }
    row.update(overrides)
    return row


def _parity_cluster(cluster_id: str, item_ids: list, path: str = "src/Widget.java",
             write_set: list | None = None, **overrides) -> dict:
    row = {
        "id": cluster_id,
        "status": "open",
        "items": list(item_ids),
        "path": path,
        "write_set": [path] if write_set is None else list(write_set),
        "kind": "parity",
    }
    row.update(overrides)
    return row


def _synthetic(**extra) -> dict:
    row = {
        "snapshot_kind": "synthetic",
        "scope_note": "Synthetic unit input. Not an observed migration event.",
        "construction": "Built in the unit test.",
        "observed_migration_event": False,
    }
    row.update(extra)
    return row


def _derive_min(items: list, clusters: list, unresolved: list | None = None,
                lineage: list | None = None, provenance: dict | None = None) -> dict:
    return derive_outcome_accounts(
        {"items": items, "clusters": clusters},
        [] if unresolved is None else unresolved,
        provenance=_synthetic() if provenance is None else provenance,
        lineage=[] if lineage is None else lineage,
    )


def _assert_account_shape(test: unittest.TestCase, doc: dict) -> None:
    test.assertEqual(set(doc), _TOP_KEYS)
    test.assertEqual(doc["schema"], "rhoai3.outcome-accounts-preview/v1")
    test.assertIs(doc["planning_only"], True)
    test.assertEqual(doc["coverage_scope"], "provided-obligations-only")
    test.assertEqual(doc["counts"], {
        "baseline_behavior_outcomes": len(doc["outcomes"]),
        "measured_additions": 0,
        "accepted_current_outcomes": 0,
        "remaining_behavior_outcomes": len(doc["outcomes"]),
    })
    outcome_ids = []
    for row in doc["outcomes"]:
        test.assertEqual(set(row), _OUTCOME_KEYS)
        test.assertEqual(row["parents"], ["control:m2"])
        test.assertEqual(row["assignee"], "implementer")
        test.assertEqual(row["obligation_ids"], sorted(set(row["obligation_ids"])))
        test.assertEqual(row["cluster_ids"], sorted(set(row["cluster_ids"])))
        test.assertEqual(row["plan_paths"], sorted(set(row["plan_paths"])))
        outcome_ids.append(row["outcome_id"])
    test.assertEqual(outcome_ids, sorted(outcome_ids))
    test.assertEqual([row["milestone_id"] for row in doc["milestones"]], [
        "assess:m4", "deliver:prepare", "deliver:push", "deliver:accept",
    ])
    test.assertEqual(doc["milestones"][0]["parents"], outcome_ids)
    test.assertEqual(doc["milestones"][0]["assignee"], "implementer")
    test.assertEqual(doc["milestones"][1]["parents"], ["assess:m4"])
    test.assertIsNone(doc["milestones"][1]["assignee"])
    test.assertEqual(doc["milestones"][2]["parents"], ["deliver:prepare"])
    test.assertIsNone(doc["milestones"][2]["assignee"])
    test.assertEqual(doc["milestones"][3]["parents"], ["deliver:push"])
    test.assertIsNone(doc["milestones"][3]["assignee"])
    for row in doc["milestones"]:
        test.assertEqual(set(row), _MILESTONE_KEYS)
    node_ids = outcome_ids + [row["milestone_id"] for row in doc["milestones"]]
    test.assertNotIn("control:m2", node_ids)
    parents = [parent for row in doc["milestones"] for parent in row["parents"]]
    for row in doc["unresolved"]:
        test.assertNotIn(row["id"], parents)
        test.assertNotIn(row["id"], node_ids)
    roundtrip = json.loads(json.dumps(doc))
    test.assertIsNone(roundtrip["milestones"][1]["assignee"])
    test.assertNotIn("complete", doc)
    test.assertNotIn("admitted", doc)
    test.assertNotIn("pipeline_eligible", doc)


class OutcomeAccountPreview(unittest.TestCase):
    def test_late_remainder_covers_six_obligations_as_five_outcomes(self) -> None:
        env = _envelope()
        self.assertEqual(env["provenance"]["source_sha256"], _SOURCE_SHA256)
        self.assertEqual(env["provenance"]["source_path"], "tmp/v12-run-20260924/freeze/worklist.json")
        self.assertEqual(env["provenance"]["snapshot_kind"], "late-remainder")
        listing = next(item for item in env["worklist"]["items"] if item["id"] == "parity:2c8c0206f70fc504")
        self.assertEqual(listing["scenario"], "")
        self.assertEqual(listing["security_mode"], "disabled")
        for item in env["worklist"]["items"]:
            self.assertEqual(list(item), env["provenance"]["field_projection"]["item_fields"])
            self.assertEqual(item["security_mode"], "disabled")
        for cluster in env["worklist"]["clusters"]:
            self.assertEqual(list(cluster), env["provenance"]["field_projection"]["cluster_fields"])
        self.assertEqual(
            [row["id"] for row in env["provenance"]["excluded_not_counted"]],
            [
                "inc:jakarta-jaxrs-to-quarkus-00010:2a3cac51b5769b79",
                "inc:springboot-web-to-quarkus-00010:0adc8f1f7b42e3ca",
            ],
        )
        doc = _call(env)
        _assert_account_shape(self, doc)
        self.assertEqual(doc["counts"], {
            "baseline_behavior_outcomes": 5,
            "measured_additions": 0,
            "accepted_current_outcomes": 0,
            "remaining_behavior_outcomes": 5,
        })
        self.assertEqual(
            [(row["outcome_id"], tuple(row["obligation_ids"]), tuple(row["cluster_ids"]), tuple(row["plan_paths"]))
             for row in doc["outcomes"]],
            list(_EXPECTED),
        )
        covered = [item_id for row in doc["outcomes"] for item_id in row["obligation_ids"]]
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(len(covered), 6)
        pets = doc["outcomes"][0]
        self.assertEqual(pets["obligation_ids"], ["parity:2c8c0206f70fc504", "parity:f55ae9ac55731703"])
        self.assertEqual(doc["lineage"], [{
            "outcome_id": "http-type:org.springframework.samples.petclinic.rest.RootRestController",
            "cluster_id": "c:488e7e2d2ac4",
            "card_ids": ["t_b2510378", "t_9a001ded"],
            "counts_as_addition": False,
        }])
        self.assertIs(doc["lineage"][0]["counts_as_addition"], False)
        without_lineage = _call(env, lineage=[])
        self.assertEqual(without_lineage["counts"], doc["counts"])
        self.assertEqual(without_lineage["outcomes"], doc["outcomes"])
        self.assertEqual(without_lineage["milestones"], doc["milestones"])
        self.assertEqual(without_lineage["lineage"], [])
        planned = json.dumps({"outcomes": doc["outcomes"], "milestones": doc["milestones"]})
        self.assertNotIn("t_b2510378", planned)
        self.assertNotIn("t_9a001ded", planned)
        self.assertNotIn("inc:jakarta-jaxrs-to-quarkus-00010:2a3cac51b5769b79", json.dumps(doc["outcomes"]))
        self.assertEqual(doc["unresolved"], env["unresolved"])
        self.assertEqual(doc["provenance"], env["provenance"])
        bogus = copy.deepcopy(env["provenance"])
        bogus["source_sha256"] = "0" * 64
        passed = _call(env, provenance=bogus)
        self.assertEqual(passed["provenance"]["source_sha256"], "0" * 64)
        self.assertEqual(passed["counts"]["baseline_behavior_outcomes"], 5)

    def test_order_permutations_repeat_and_detach_inputs(self) -> None:
        env = _envelope()
        original = copy.deepcopy(env)
        first = _call(env)
        second = _call(env)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["unresolved"], env["unresolved"])
        self.assertIsNot(first["unresolved"][0], env["unresolved"][0])
        self.assertIsNot(first["lineage"][0], env["lineage"][0])
        self.assertIsNot(first["lineage"][0]["card_ids"], env["lineage"][0]["card_ids"])
        self.assertIsNot(first["provenance"], env["provenance"])
        self.assertIsNot(first["provenance"]["excluded_not_counted"], env["provenance"]["excluded_not_counted"])
        items = env["worklist"]["items"]
        clusters = env["worklist"]["clusters"]
        for ordered in itertools.permutations(items):
            worklist = {"items": list(ordered), "clusters": clusters}
            self.assertEqual(_call(env, worklist=worklist), second)
        for ordered in itertools.permutations(clusters):
            worklist = {"items": items, "clusters": list(ordered)}
            self.assertEqual(_call(env, worklist=worklist), second)
        reversed_members = []
        for cluster in clusters:
            copied = copy.deepcopy(cluster)
            copied["items"] = list(reversed(cluster["items"]))
            copied["write_set"] = list(reversed(cluster["write_set"]))
            reversed_members.append(copied)
        reversed_worklist = {"items": list(reversed(items)), "clusters": list(reversed(reversed_members))}
        self.assertEqual(_call(env, worklist=reversed_worklist), second)
        first["unresolved"][0]["reason"] += " mutated"
        first["lineage"][0]["card_ids"].append("t_mutated")
        first["provenance"]["excluded_not_counted"][0]["id"] = "mutated"
        first["outcomes"][0]["parents"].append("mutated")
        self.assertEqual(env, original)
        self.assertEqual(second["outcomes"][0]["parents"], ["control:m2"])
        self.assertEqual(second["counts"]["measured_additions"], 0)

    def test_malformed_inputs_raise(self) -> None:
        sibling = _parity_item("o:keep")
        sibling_cluster = _parity_cluster("c:keep", ["o:keep"])
        other = _parity_item("o:2", declaring="com.example.Other", member="delete()", path="src/Other.java")

        def derive_bad(items, clusters, **kwargs) -> dict:
            return _derive_min(items, clusters, **kwargs)

        cases = [
            ("missing items", {"clusters": []}, [], "worklist.items"),
            ("missing clusters", {"items": []}, [], "worklist.clusters"),
            ("items not a list", {"items": None, "clusters": []}, [], "worklist.items"),
            ("clusters not a list", {"items": [], "clusters": {}}, [], "worklist.clusters"),
            ("worklist not an object", [], [], "worklist must be an object"),
        ]
        for name, worklist, unresolved, pattern in cases:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, pattern):
                    derive_outcome_accounts(worklist, unresolved, provenance=_synthetic(), lineage=[])

        with self.subTest(name="unresolved not a list"):
            with self.assertRaisesRegex(ValueError, "unresolved must be a list"):
                derive_outcome_accounts(
                    {"items": [], "clusters": []}, None, provenance=_synthetic(), lineage=[],
                )
        with self.subTest(name="lineage not a list"):
            with self.assertRaisesRegex(ValueError, "lineage must be a list"):
                derive_outcome_accounts(
                    {"items": [], "clusters": []}, [], provenance=_synthetic(), lineage=None,
                )
        with self.subTest(name="provenance not an object"):
            with self.assertRaisesRegex(ValueError, "provenance must be an object"):
                derive_outcome_accounts({"items": [], "clusters": []}, [], provenance=[], lineage=[])

        bad_entries = (
            "",
            "get()",
            "ep:#get():http",
            "ep:com.example.Widget#:http",
            "ep:com.example.Widget#get():grpc",
            "ep:com.example.Widget#get()",
            "ep: com.example.Widget#get():http",
            "ep:com.example.Widget#get():http ",
            None,
        )
        for entry in bad_entries:
            with self.subTest(entry_point=entry):
                with self.assertRaisesRegex(ValueError, "entry point"):
                    derive_bad([_parity_item("o:1", entry_point=entry)], [_parity_cluster("c:1", ["o:1"])])

        structural = {
            "duplicate item id": (
                [_parity_item("o:1"), _parity_item("o:1", member="other()", path="src/Other.java")],
                [_parity_cluster("c:1", ["o:1"])],
                "duplicate item id",
            ),
            "duplicate cluster id": (
                [_parity_item("o:1"), other],
                [_parity_cluster("c:1", ["o:1"]), _parity_cluster("c:1", ["o:2"], path="src/Other.java")],
                "duplicate cluster id",
            ),
            "duplicate membership inside a cluster": (
                [_parity_item("o:1"), sibling],
                [_parity_cluster("c:1", ["o:1", "o:1"]), sibling_cluster],
                "duplicate membership",
            ),
            "duplicate membership across clusters": (
                [_parity_item("o:1")],
                [_parity_cluster("c:1", ["o:1"]), _parity_cluster("c:2", ["o:1"], path="src/Other.java")],
                "duplicate membership",
            ),
            "orphan obligation": (
                [_parity_item("o:1"), other],
                [_parity_cluster("c:1", ["o:1"])],
                "orphan obligation",
            ),
            "unknown reference": (
                [_parity_item("o:1")],
                [_parity_cluster("c:1", ["o:1", "o:missing"])],
                "unknown obligation",
            ),
            "unsupported item kind": (
                [_parity_item("o:1", kind="compile"), sibling],
                [_parity_cluster("c:1", ["o:1"]), sibling_cluster],
                "not supported",
            ),
            "non-mandatory category": (
                [_parity_item("o:1", category="optional")],
                [_parity_cluster("c:1", ["o:1"])],
                "not mandatory",
            ),
            "unsupported cluster kind": (
                [sibling, other],
                [sibling_cluster, _parity_cluster("c:bad", ["o:2"], path="src/Other.java", kind="build")],
                "not supported",
            ),
            "non-open cluster": (
                [sibling, other],
                [sibling_cluster, _parity_cluster("c:done", ["o:2"], path="src/Other.java", status="done")],
                "not open",
            ),
            "empty cluster": (
                [sibling],
                [sibling_cluster, _parity_cluster("c:empty", [])],
                "no member obligations",
            ),
            "mixed declaring types": (
                [_parity_item("o:1", declaring="com.example.A", path="src/A.java"),
                 _parity_item("o:2", declaring="com.example.B", path="src/B.java"),
                 sibling],
                [_parity_cluster("c:mix", ["o:1", "o:2"], path="src/A.java"), sibling_cluster],
                "refusing to divide",
            ),
            "missing scenario": (
                [_parity_item("o:drop")],
                [_parity_cluster("c:1", ["o:drop"])],
                "missing scenario",
            ),
        }
        for name, (items, clusters, pattern) in structural.items():
            with self.subTest(name=name):
                if name == "missing scenario":
                    del items[0]["scenario"]
                with self.assertRaisesRegex(ValueError, pattern):
                    derive_bad(items, clusters)

        with self.subTest(name="duplicate unresolved id"):
            with self.assertRaisesRegex(ValueError, "duplicate unresolved id"):
                derive_bad([], [], unresolved=[
                    {"id": "unresolved:a", "reason": "one"},
                    {"id": "unresolved:a", "reason": "two"},
                ])
        with self.subTest(name="blank unresolved reason"):
            with self.assertRaisesRegex(ValueError, "nonempty reason"):
                derive_bad([], [], unresolved=[{"id": "unresolved:a", "reason": "  "}])
        with self.subTest(name="lineage cannot invent an outcome"):
            env = _envelope()
            with self.assertRaisesRegex(ValueError, "not a derived outcome"):
                derive_bad([], [], lineage=env["lineage"])
        with self.subTest(name="lineage cluster must belong to the outcome"):
            env = _envelope()
            row = copy.deepcopy(env["lineage"][0])
            row["cluster_id"] = "c:67bfc8d7483e"
            with self.assertRaisesRegex(ValueError, "not a cluster"):
                _call(env, lineage=[row])
        with self.subTest(name="lineage cannot record an addition"):
            env = _envelope()
            row = copy.deepcopy(env["lineage"][0])
            row["counts_as_addition"] = True
            with self.assertRaisesRegex(ValueError, "counts_as_addition"):
                _call(env, lineage=[row])
        with self.subTest(name="bad snapshot kind"):
            with self.assertRaisesRegex(ValueError, "snapshot_kind"):
                derive_bad([_parity_item("o:1")], [_parity_cluster("c:1", ["o:1"])], provenance={
                    "snapshot_kind": "initial", "scope_note": "no",
                })
        with self.subTest(name="synthetic without construction"):
            with self.assertRaisesRegex(ValueError, "construction"):
                derive_bad([], [], provenance={
                    "snapshot_kind": "synthetic",
                    "scope_note": "synthetic",
                    "observed_migration_event": False,
                })
        with self.subTest(name="synthetic observed event"):
            with self.assertRaisesRegex(ValueError, "observed_migration_event"):
                derive_bad([], [], provenance={
                    "snapshot_kind": "synthetic",
                    "scope_note": "synthetic",
                    "construction": "made up",
                    "observed_migration_event": True,
                })

    def test_unresolved_rows_stay_outside_counts_and_empty_is_not_completion(self) -> None:
        env = _envelope()
        swapped = list(reversed(env["unresolved"]))
        doc = _call(env, unresolved=swapped)
        self.assertEqual([row["id"] for row in doc["unresolved"]], [row["id"] for row in swapped])
        self.assertEqual(doc["counts"]["remaining_behavior_outcomes"], 5)
        self.assertEqual(len(doc["unresolved"]), 2)
        parents = [parent for row in doc["milestones"] for parent in row["parents"]]
        for row in doc["unresolved"]:
            self.assertNotIn(row["id"], parents)
        empty = derive_outcome_accounts(
            {"items": [], "clusters": []},
            env["unresolved"],
            provenance={
                "snapshot_kind": "synthetic",
                "scope_note": "Synthetic empty snapshot. Not a completed migration.",
                "construction": "No obligations were supplied.",
                "observed_migration_event": False,
            },
            lineage=[],
        )
        _assert_account_shape(self, empty)
        self.assertEqual(empty["outcomes"], [])
        self.assertEqual(empty["counts"], {
            "baseline_behavior_outcomes": 0,
            "measured_additions": 0,
            "accepted_current_outcomes": 0,
            "remaining_behavior_outcomes": 0,
        })
        self.assertEqual(empty["unresolved"], env["unresolved"])
        self.assertEqual(empty["milestones"][0]["parents"], [])
        self.assertEqual(empty["coverage_scope"], "provided-obligations-only")
        self.assertIs(empty["planning_only"], True)
        self.assertNotEqual(empty["counts"]["remaining_behavior_outcomes"], len(empty["unresolved"]))

    def test_logical_dependencies_have_no_execution_identity(self) -> None:
        doc = _call(_envelope())
        _assert_account_shape(self, doc)
        self.assertEqual(len(doc["milestones"]), 4)
        self.assertEqual(len(doc["outcomes"]), 5)
        self.assertNotEqual(doc["counts"]["remaining_behavior_outcomes"], len(doc["milestones"]))
        for row in doc["outcomes"] + doc["milestones"]:
            self.assertFalse({"task_id", "card_id", "run_id", "idempotency_key", "candidate_sha256",
                              "admitted", "status", "executable"} & set(row))

    def test_renamed_declaring_type_changes_outcome_id(self) -> None:
        env = _envelope()
        old = "org.springframework.samples.petclinic.rest.PetRestController"
        new = "com.example.catalog.ItemController"
        for item in env["worklist"]["items"]:
            item["entry_point"] = item["entry_point"].replace(old, new, 1)
        doc = _call(env)
        ids = [row["outcome_id"] for row in doc["outcomes"]]
        self.assertIn("http-type:" + new, ids)
        self.assertNotIn("http-type:" + old, ids)
        renamed = next(row for row in doc["outcomes"] if row["outcome_id"] == "http-type:" + new)
        self.assertEqual(renamed["obligation_ids"], ["parity:2c8c0206f70fc504", "parity:f55ae9ac55731703"])
        self.assertEqual(doc["counts"]["baseline_behavior_outcomes"], 5)
        self.assertEqual(doc["counts"]["measured_additions"], 0)
        enabled = _derive_min([_parity_item("o:1", security_mode="enabled")], [_parity_cluster("c:1", ["o:1"])])
        self.assertEqual(enabled["outcomes"][0]["outcome_id"], "http-type:com.example.Widget")

    def test_multiple_clusters_of_one_type_are_one_outcome(self) -> None:
        declaring = "com.example.catalog.ItemController"
        first = _parity_item("o:1", declaring, "list()", "src/A.java", attempt=1)
        second = _parity_item("o:2", declaring, "delete()", "src/B.java", attempt=2)
        doc = _derive_min(
            [second, first],
            [
                _parity_cluster("c:2", ["o:2"], "src/B.java", write_set=["src/B.java"]),
                _parity_cluster("c:1", ["o:1"], "src/A.java", write_set=["src/Model.java", "src/A.java"]),
            ],
        )
        _assert_account_shape(self, doc)
        self.assertEqual(len(doc["outcomes"]), 1)
        row = doc["outcomes"][0]
        self.assertEqual(row["outcome_id"], "http-type:" + declaring)
        self.assertEqual(row["obligation_ids"], ["o:1", "o:2"])
        self.assertEqual(row["cluster_ids"], ["c:1", "c:2"])
        self.assertEqual(row["plan_paths"], ["src/A.java", "src/B.java", "src/Model.java"])
        self.assertNotIn("attempt", row)

    def test_synthetic_four_then_five_keeps_additions_at_zero(self) -> None:
        env = _envelope()
        root_item = "parity:fd0b32ed739b54b5"
        root_cluster = "c:488e7e2d2ac4"
        root_outcome = "http-type:org.springframework.samples.petclinic.rest.RootRestController"
        omitted_items = [item for item in env["worklist"]["items"] if item["id"] != root_item]
        omitted_clusters = [cluster for cluster in env["worklist"]["clusters"] if cluster["id"] != root_cluster]
        omitted = derive_outcome_accounts(
            {"items": omitted_items, "clusters": omitted_clusters},
            env["unresolved"],
            provenance={
                "snapshot_kind": "synthetic",
                "scope_note": "Synthetic copy of the late remainder with the root obligation removed.",
                "construction": "Removed the root obligation, its cluster, and its lineage from a copy of the fixture.",
                "observed_migration_event": False,
            },
            lineage=[],
        )
        restored = derive_outcome_accounts(
            env["worklist"],
            env["unresolved"],
            provenance={
                "snapshot_kind": "synthetic",
                "scope_note": "Synthetic copy of the late remainder with the root obligation present.",
                "construction": "Restored the root obligation, its cluster, and its lineage on a synthetic copy.",
                "observed_migration_event": False,
            },
            lineage=env["lineage"],
        )
        _assert_account_shape(self, omitted)
        _assert_account_shape(self, restored)
        self.assertEqual(omitted["counts"]["baseline_behavior_outcomes"], 4)
        self.assertEqual(restored["counts"]["baseline_behavior_outcomes"], 5)
        self.assertEqual(omitted["counts"]["measured_additions"], 0)
        self.assertEqual(restored["counts"]["measured_additions"], 0)
        self.assertEqual(omitted["provenance"]["snapshot_kind"], "synthetic")
        self.assertEqual(restored["provenance"]["snapshot_kind"], "synthetic")
        self.assertIs(omitted["provenance"]["observed_migration_event"], False)
        self.assertIs(restored["provenance"]["observed_migration_event"], False)
        omitted_ids = {row["outcome_id"] for row in omitted["outcomes"]}
        restored_ids = {row["outcome_id"] for row in restored["outcomes"]}
        self.assertEqual(restored_ids - omitted_ids, {root_outcome})
        self.assertEqual(omitted_ids - restored_ids, set())
        self.assertNotIn(root_outcome, omitted_ids)

    def test_derivation_performs_no_io(self) -> None:
        env = _envelope()

        def _blocked(*_args, **_kwargs):
            raise AssertionError("outcome derivation attempted I/O")

        with patch("builtins.open", _blocked), patch("subprocess.run", _blocked), patch("socket.socket", _blocked):
            before = set(sys.modules)
            doc = _call(env)
            added = set(sys.modules) - before
        self.assertEqual(doc["counts"]["baseline_behavior_outcomes"], 5)
        leaked = [name for name in added if "k4" in name or "m5_delivery" in name]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
