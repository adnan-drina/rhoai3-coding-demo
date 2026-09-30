"""ADR-025: the three response equivalences, grammar and boundaries."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import response_equivalence as R  # noqa: E402

ADVICE = json.dumps({"className": "org.springframework.http.converter.HttpMessageNotReadableException",
                     "exMessage": "JSON parse error: Unexpected end-of-input"})


class Challenges(unittest.TestCase):
    def test_duplicates_are_one_and_field_lines_join(self):
        self.assertTrue(R.challenges_equal('Basic realm="Realm", Basic realm="Realm"', 'Basic realm="Realm"'))
        self.assertTrue(R.challenges_equal(['Basic realm="Realm"', 'Basic realm="Realm"'], 'Basic realm="Realm"'))
        self.assertTrue(R.challenges_equal('Basic realm="R", Bearer', ['Bearer', 'basic REALM="R"']))

    def test_quoted_realms_containing_commas(self):
        self.assertEqual(R.parse_challenges('Basic realm="a, b", charset="UTF-8"'),
                         [("basic", (("charset", "UTF-8"), ("realm", "a, b")))])
        self.assertTrue(R.challenges_equal('Basic realm="a, b", Basic realm="a, b"', 'Basic realm="a, b"'))
        self.assertFalse(R.challenges_equal('Basic realm="a, b"', 'Basic realm="a", Basic realm="b"'))
        self.assertTrue(R.challenges_equal('Basic realm="a\\"b"', 'Basic realm=\'a"b\''.replace("'", '"').replace('a"b', 'a\\"b')))

    def test_real_differences_remain(self):
        self.assertFalse(R.challenges_equal('Basic realm="Realm"', 'Basic realm="realm"'))      # realm is case-sensitive
        self.assertFalse(R.challenges_equal('Basic realm="Realm"', 'Bearer realm="Realm"'))
        self.assertFalse(R.challenges_equal('Basic realm="R", charset="UTF-8"', 'Basic realm="R"'))
        self.assertFalse(R.challenges_equal('Basic realm="R"', 'Basic realm="R", Bearer'))

    def test_token68_and_unparseable_values(self):
        self.assertEqual(R.parse_challenges("Negotiate abc=="), [("negotiate", ("token68", "abc=="))])
        self.assertIsNone(R.parse_challenges('Basic realm="unterminated'))
        self.assertFalse(R.challenges_equal('Basic realm="x', 'Basic realm="x"'))    # raw comparison then


class Advice(unittest.TestCase):
    def test_identified_from_the_source_response_only(self):
        self.assertTrue(R.deserialization_advice(400, ADVICE))
        self.assertTrue(R.deserialization_advice("400", ADVICE.encode()))
        self.assertFalse(R.deserialization_advice(500, ADVICE))
        other = json.dumps({"className": "java.lang.IllegalStateException", "exMessage": "x"})
        self.assertFalse(R.deserialization_advice(400, other))                   # the advice, but not a body-read failure
        self.assertFalse(R.deserialization_advice(400, json.dumps({"className": R.SOURCE_DESERIALIZATION_EXCEPTIONS[0]})))
        self.assertFalse(R.deserialization_advice(400, ""))

    def test_keys_enforced_values_present_and_non_empty(self):
        ok = json.dumps({"className": "com.fasterxml.jackson.core.io.JsonEOFException", "exMessage": "Unexpected end"})
        self.assertTrue(R.advice_values_equivalent(ADVICE, ok)[0])
        self.assertFalse(R.advice_values_equivalent(ADVICE, "")[0])
        self.assertFalse(R.advice_values_equivalent(ADVICE, json.dumps({"className": "x"}))[0])
        self.assertFalse(R.advice_values_equivalent(ADVICE, json.dumps({"className": "x", "exMessage": " "}))[0])
        self.assertFalse(R.advice_values_equivalent(ADVICE, json.dumps({"className": "x", "exMessage": "y", "extra": 1}))[0])
        self.assertFalse(R.advice_values_equivalent(ADVICE, json.dumps({"className": 1, "exMessage": "y"}))[0])


class Root(unittest.TestCase):
    def test_outside_the_application_root(self):
        self.assertTrue(R.outside_application_root("/api/owners", "/petclinic/"))
        self.assertFalse(R.outside_application_root("/petclinic/api/owners", "/petclinic/"))
        self.assertFalse(R.outside_application_root("/petclinic", "/petclinic"))
        self.assertTrue(R.outside_application_root("/petclinicx/api", "/petclinic"))
        self.assertFalse(R.outside_application_root("/anything", "/"))
        self.assertFalse(R.outside_application_root("/anything", ""))
        lim = R.scope_limitation(["outside-root", "outside-root"])
        self.assertEqual((lim["owner"], lim["adr"], lim["scenarios"]), ("scope-decision", "ADR-025", ["outside-root"]))

    def test_the_adr_must_be_accepted_in_the_destination(self):
        golden = Path(__file__).resolve().parents[2]
        self.assertTrue(R.adr_accepted(golden))
        self.assertFalse(R.adr_accepted(Path(tempfile.mkdtemp())))
        self.assertFalse(R.adr_accepted(None))


if __name__ == "__main__":
    unittest.main(verbosity=1)
