#!/usr/bin/env python3
"""isolation_carry_forward: a receipt is carried only across changes that touch
nothing isolation-relevant (image digest re-pins in the named devfiles are the
one exception). Disposable git repositories; no cluster."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolation_carry_forward as CF  # noqa: E402

D1, D2 = "sha256:" + "1" * 64, "sha256:" + "2" * 64
DEVFILE = CF.DIGEST_ONLY[0]
RBAC = "gitops/stages/050-advanced-app-platform/base/devspaces/worker-rbac.yaml"


def git(repo: Path, *a: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *a], text=True).strip()


def commit(repo: Path, files: dict[str, str]) -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    return git(repo, "rev-parse", "HEAD")


def devfile(digest: str, extra: str = "") -> str:
    return "components:\n  - name: tools\n    container:\n      image: quay.io/x/ws@%s\n%s" % (digest, extra)


class CarryForward(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plat, self.gold = self.tmp / "platform", self.tmp / "golden"
        for r in (self.plat, self.gold):
            r.mkdir()
            git(r, "init", "-q")
        self.p0 = commit(self.plat, {DEVFILE: devfile(D1), RBAC: "kind: Role\n", "docs/x.md": "a\n"})
        self.g0 = commit(self.gold, {"devfile.yaml": devfile(D1), ".hermes/lib/x.py": "a = 1\n"})
        self.receipt = self.tmp / "receipt.json"
        self.receipt.write_text(json.dumps({"schema": "rhoai3.run-isolation/v1", "golden_commit": self.g0,
                                            "platform_commit": self.p0}))

    def record(self, p1: str, g1: str, **over) -> dict:
        rec = {"schema": CF.SCHEMA, "receipt_sha256": hashlib.sha256(self.receipt.read_bytes()).hexdigest(),
               "from": {"golden": self.g0, "platform": self.p0}, "to": {"golden": g1, "platform": p1},
               "by": "operator", "reason": "typed-repair image and harness release, no isolation change"}
        rec.update(over)
        return rec

    def gaps(self, rec: dict, p1: str, g1: str) -> list[str]:
        return CF.gaps(rec, self.receipt, self.plat, self.gold, g1, p1)

    def test_digest_repins_and_unrelated_changes_carry(self):
        p1 = commit(self.plat, {DEVFILE: devfile(D2), "docs/x.md": "b\n", "gitops/stages/040-x/gw.yaml": "mem: 2Gi\n"})
        g1 = commit(self.gold, {"devfile.yaml": devfile(D2), ".hermes/lib/x.py": "a = 2\n"})
        self.assertEqual(self.gaps(self.record(p1, g1), p1, g1), [])

    def test_an_isolation_relevant_change_refuses(self):
        p1 = commit(self.plat, {RBAC: "kind: ClusterRole\n"})
        g1 = self.g0
        self.assertTrue(any(RBAC in g for g in self.gaps(self.record(p1, g1), p1, g1)))

    def test_a_devfile_change_beyond_digests_refuses(self):
        p1 = commit(self.plat, {DEVFILE: devfile(D2, "      mountSources: true\n")})
        self.assertTrue(any(DEVFILE in g for g in self.gaps(self.record(p1, self.g0), p1, self.g0)))
        g1 = commit(self.gold, {"devfile.yaml": devfile(D1, "      env: [{name: X, value: y}]\n")})
        self.assertTrue(any("golden devfile.yaml" in g for g in self.gaps(self.record(self.p0, g1), self.p0, g1)))

    def test_the_binding_is_exact(self):
        p1, g1 = commit(self.plat, {"docs/x.md": "c\n"}), self.g0
        self.assertTrue(self.gaps(self.record(p1, g1, receipt_sha256="0" * 64), p1, g1))            # another receipt
        self.assertTrue(self.gaps(self.record(p1, g1, **{"from": {"golden": g1, "platform": p1}}), p1, g1))
        self.assertTrue(self.gaps(self.record(p1, g1), self.p0, g1))                               # carried elsewhere
        self.assertTrue(self.gaps(self.record(p1, g1, by=""), p1, g1))                              # no Operator


if __name__ == "__main__":
    unittest.main(verbosity=1)
