#!/usr/bin/env python3
"""Persistence behaviour the destination's provider changes (compat-mapping persistence_behaviour_translations and
repository_behaviour.crud_defaults), as the planner matches it against a source method's ORDERED calls.

H-21 (v31): the flush-order row binds a port to the effects the source RECORDED -- a refused delete stays refused.
H-22 (v31): a merge of an entity the source did not load (a request's id) inserted on Hibernate 5 and throws on 6.6+;
the single-call row matches a save-like merge and never the re-attaching merge of a delete.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/persistence_translations.test.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner.source_requirements import persistence_translations  # noqa: E402

CATALOG = json.loads((HERE.parent.parent / "planning" / "catalogs" / "compat-mapping.json").read_text())


def m(*calls):
    return {"calls": [{"owner": o, "name": n} for o, n in calls]}


class Rows(unittest.TestCase):
    def ids(self, method, catalog=CATALOG):
        return [t["id"] for t in persistence_translations(method, catalog)]

    def test_a_save_like_merge_carries_the_hibernate66_row(self):
        for em in ("javax.persistence.EntityManager", "jakarta.persistence.EntityManager"):
            self.assertEqual(self.ids(m((em, "merge"))), ["hibernate66-merge-detached-without-row"])
            self.assertEqual(self.ids(m((em, "persist"), (em, "merge"))), ["hibernate66-merge-detached-without-row"])

    def test_a_reattaching_merge_before_a_remove_is_not_a_save(self):
        em, q = "javax.persistence.EntityManager", "javax.persistence.Query"
        got = self.ids(m((em, "remove"), (em, "contains"), (em, "merge"), (q, "executeUpdate")))
        self.assertEqual(got, ["hibernate6-flush-before-query"])

    def test_no_merge_no_row(self):
        em = "jakarta.persistence.EntityManager"
        self.assertEqual(self.ids(m((em, "persist"))), [])
        self.assertEqual(self.ids(m((em, "find"), (em, "createQuery"))), [])
        self.assertEqual(self.ids(m(("com.acme.Other", "merge"))), [])     # another owner's merge is not the JPA API

    def test_a_two_call_row_still_needs_its_later_call(self):
        em = "jakarta.persistence.EntityManager"
        self.assertEqual(self.ids(m((em, "remove"))), [])                   # remove alone: no flush-order difference

    def test_the_rows_say_what_the_source_did(self):
        rows = CATALOG["persistence_behaviour_translations"]
        flush = rows["hibernate6-flush-before-query"]["obligation"]
        self.assertIn("REFUSED", flush)
        self.assertIn("never delete or detach the dependents first to make a refused delete succeed", flush)
        merge = rows["hibernate66-merge-detached-without-row"]
        self.assertIn("persist the entity as new", merge["obligation"])
        self.assertIn("merge-versioned-deleted", merge["source"])
        save = CATALOG["repository_behaviour"]["crud_defaults"]["save/1"]
        self.assertIn("id is set but no row exists, persist it as new", save["semantics"])
        self.assertIn("docs.hibernate.org/orm/6.6", save["source"])


if __name__ == "__main__":
    unittest.main()
