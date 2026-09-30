"""v29: a fragment implementation that answers its members through a repository
extending the fragment interface recurses at runtime (the generated Spring Data
repository routes every interface method back to the implementation). The
structural assessment refuses it; a body with its own JPQL is accepted. Each
verdict repeated on a twin that shares no identifier."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.worklist import _assess_implementations, fragment_routed_back  # noqa: E402


def specimen(pkg: str, ent: str):
    parent = "%s.repository.%sRepository" % (pkg, ent)
    impl = parent + "Impl"
    sd = "%s.repository.springdatajpa.SpringData%sRepository" % (pkg, ent)
    rel = "%s/repository/%sRepositoryImpl.java" % (pkg.replace(".", "/"), ent)

    def model(calls):
        return {"types": [
            {"fqn": parent, "path": rel.replace("Impl", ""), "supertypes": [], "declared": []},
            {"fqn": sd, "path": "x/%s.java" % sd.rsplit(".", 1)[-1],
             "supertypes": [parent, "org.springframework.data.repository.Repository<%s.model.%s,java.lang.Integer>" % (pkg, ent)],
             "declared": [{"signature": "findById(int)", "has_body": False}]},
            {"fqn": impl, "path": rel, "resolution": "full", "supertypes": [parent], "annotations": [],
             "declared": [{"signature": "findAll()", "has_body": True, "body_shape": {"kind": "substantive"}, "calls": calls[0]},
                          {"signature": "findById(int)", "has_body": True, "body_shape": {"kind": "substantive"}, "calls": calls[1]}]}]}
    return parent, impl, sd, rel, model


class RoutedBack(unittest.TestCase):
    def check(self, pkg: str, ent: str):
        parent, impl, sd, rel, model = specimen(pkg, ent)
        recursing = model([["%s.findAll()" % parent], ["%s.findById(int)" % sd]])
        own_jpql = model([["jakarta.persistence.EntityManager.createQuery(java.lang.String,java.lang.Class)",
                           "jakarta.persistence.TypedQuery.getResultList()"],
                          ["jakarta.persistence.EntityManager.find(java.lang.Class,java.lang.Object)"]])
        impl_row = lambda m: next(t for t in m["types"] if t["fqn"] == impl)
        # an inherited method counts under the type that declares it; an override under the subtype
        self.assertEqual(fragment_routed_back(recursing, impl_row(recursing), parent, ["findAll()", "findById(int)"]),
                         [("findAll()", "findAll()", parent), ("findById(int)", "findById(int)", sd)])
        self.assertEqual(fragment_routed_back(own_jpql, impl_row(own_jpql), parent, ["findAll()", "findById(int)"]), [])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "src/main/java" / rel
            p.parent.mkdir(parents=True)
            p.write_text("class X {}\n")
            row = {"path": "src/main/java/" + rel, "parent": parent, "type": impl, "members": ["findAll()", "findById(int)"]}
            for m, want in ((recursing, "violates"), (own_jpql, "ok")):
                by_path = {"src/main/java/" + rel: [impl_row(m)]}
                v = _assess_implementations(Path(d), {"implementation_obligations": [row]}, m, by_path, "r")
                self.assertEqual(v[0]["verdict"], want, v)
                if want == "violates":
                    self.assertIn("StackOverflowError", v[0]["detail"])
                    self.assertIn("EntityManager", v[0]["detail"])

    def test_a_fragment_implementation_that_calls_back_into_its_repository_is_refused(self):
        self.check("org.springframework.samples.petclinic", "Owner")

    def test_the_same_verdicts_on_a_twin_that_shares_no_identifier(self):
        self.check("com.acme.shop", "Item")


if __name__ == "__main__":
    unittest.main()
