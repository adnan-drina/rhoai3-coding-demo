#!/usr/bin/env python3
"""ADR-025 in both comparators: the M4 scenario comparator's header rule and
the M-3 reference comparator, the latter on the REAL frozen source captures
(fixtures/reference-qualification/source-oracle) against synthetic
destination exchanges -- each rule identified from the source side only, and
every non-ruled difference still reported."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _oracle_common import header_diffs  # noqa: E402

FUG = HERE.parents[2] / "migration" / "fix-until-green" / "scripts"
sys.path.insert(0, str(FUG))
import reference_qualification as rq  # noqa: E402


class M4Headers(unittest.TestCase):
    def test_www_authenticate_is_a_challenge_set_only_under_the_ruling(self):
        want = {"WWW-Authenticate": 'Basic realm="Realm", Basic realm="Realm"'}
        have = {"WWW-Authenticate": 'Basic realm="Realm"'}
        self.assertEqual(header_diffs(want, have, challenge_sets=True), [])
        self.assertEqual(len(header_diffs(want, have)), 1)                      # without the ADR: raw
        self.assertEqual(len(header_diffs(want, {"WWW-Authenticate": 'Basic realm="Other"'}, challenge_sets=True)), 1)


def _dest(status, headers, body, path):
    return {"request": {"method": "GET", "path": path}, "response": {"status": status, "headers": headers, "body": body}}


class Reference(unittest.TestCase):
    def setUp(self):
        self.corpus = rq.load_corpus()
        self.steps = {s["id"]: s for s in self.corpus["steps"]}
        try:
            self.dis = rq.load_oracle("hsqldb", "disabled")["steps"]
            self.en = rq.load_oracle("hsqldb", "enabled")["steps"]
        except rq.Skip as exc:
            self.skipTest(str(exc))

    def cmp(self, sid, oracle, dest, adr):
        notes = []
        v, d = rq.compare(self.steps[sid], oracle[sid], dest, {}, {}, self.corpus, adr025=adr, notes=notes)
        return v, d, notes

    def test_outside_root_compares_status_only(self):
        dest = _dest(404, {"content-type": "application/json"}, '{"details":"not found"}', "/api/owners")
        self.assertEqual(self.cmp("outside-root", self.dis, dest, False)[0], "MISMATCH")
        v, d, notes = self.cmp("outside-root", self.dis, dest, True)
        self.assertEqual((v, d), ("MATCH", []))
        self.assertIn("outside-application-root", notes[0])
        self.assertEqual(self.cmp("outside-root", self.dis, dict(dest, response=dict(dest["response"], status=500)), True)[0],
                         "MISMATCH")

    def test_advice_values_present_keys_media_type_and_status_enforced(self):
        src = self.dis["owner-create-malformed"]["response"]
        good = json.dumps({"className": "com.fasterxml.jackson.core.io.JsonEOFException", "exMessage": "Unexpected end"})
        dest = _dest(400, {"content-type": "text/plain;charset=UTF-8"}, good, "/petclinic/api/owners")
        self.assertEqual(self.cmp("owner-create-malformed", self.dis, dest, False)[0], "MISMATCH")
        v, d, notes = self.cmp("owner-create-malformed", self.dis, dest, True)
        self.assertEqual((v, d), ("MATCH", []), d)
        self.assertIn("ADR-025", notes[0])
        # keys, media type and status stay enforced
        for bad in (_dest(400, {"content-type": "text/plain;charset=UTF-8"}, json.dumps({"className": "x"}), "/"),
                    _dest(400, {}, good, "/"),
                    _dest(500, {"content-type": "text/plain;charset=UTF-8"}, good, "/"),
                    _dest(400, {"content-type": "text/plain;charset=UTF-8"}, "", "/")):
            self.assertEqual(self.cmp("owner-create-malformed", self.dis, bad, True)[0], "MISMATCH")
        self.assertIn("className", src["body"])

    def test_the_advice_rule_never_applies_to_another_body(self):
        # a validation 400 is not the advice's deserialization answer: its body is compared as before
        sid = "owner-create-blank-firstname"
        dest = _dest(400, {"errors": "[]"}, '{"className":"x","exMessage":"y"}', "/")
        v, d, notes = self.cmp(sid, self.dis, dest, True)
        self.assertEqual(v, "MISMATCH")
        self.assertEqual(notes, [])

    def test_duplicate_challenges_equal_one(self):
        sid = "auth-wrong-password-read"
        src = self.en[sid]["response"]
        dest = _dest(src["status"], dict(src["headers"], **{"www-authenticate": 'Basic realm="Realm"'}), src["body"], "/")
        self.assertEqual(self.cmp(sid, self.en, dest, False)[0], "MISMATCH")
        self.assertEqual(self.cmp(sid, self.en, dest, True)[:2], ("MATCH", []))
        other = _dest(src["status"], dict(src["headers"], **{"www-authenticate": 'Basic realm="Other"'}), src["body"], "/")
        self.assertEqual(self.cmp(sid, self.en, other, True)[0], "MISMATCH")


if __name__ == "__main__":
    unittest.main(verbosity=1)
