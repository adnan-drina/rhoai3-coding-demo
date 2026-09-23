#!/usr/bin/env python3
"""Serial roadmap after M2: one executable task; planned M4/M5 have no candidate."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.canonical import digest, write_canonical  # noqa: E402
from planner.cards import TITLE_DASH, card_title  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, DECIDED_REPAIRS_RECEIPT, SERIAL_ROADMAP, WORKLIST  # noqa: E402
from planner.roadmap import CLAIM_KEYS, compose_serial_roadmap  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
