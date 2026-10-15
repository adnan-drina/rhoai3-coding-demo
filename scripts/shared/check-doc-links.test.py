#!/usr/bin/env python3
"""Unit tests for check-doc-links.py. Run: python3 scripts/shared/check-doc-links.test.py"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_doc_links", HERE / "check-doc-links.py")
cdl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdl)

MAP = """\
schema_version: 2
converted_families: [odf]
skill_reference_ignore: [odf-operator]
products:
  odf:
    skill_prefix: odf-
    docs_slug: red_hat_openshift_data_foundation
    docs_version: "4.22"
    pin:
      file: gitops/stages/010-x/odf/subscription.yaml
      field: spec.channel
      pattern: 'stable-(\\d+\\.\\d+)'
    categories:
      object:
        routes:
          - book: managing_hybrid_and_multicloud_resources
            status: active
            skill: odf-object-bucket-claims
          - book: planned_book
            status: planned
            skill: odf-future
  rhcl:
    skill_prefix: rhcl-
    docs_slug: red_hat_connectivity_link
    docs_version: "1.4"
    pin:
      file: scripts/policy.py
      pattern: "'rhcl-operator':'(\\\\d+\\\\.\\\\d+)\\\\.\\\\d+'"
    categories:
      about:
        routes:
          - book: red_hat_connectivity_link
            skill: rhcl-about
cited_products:
  keycloak:
    docs_slug: red_hat_build_of_keycloak
    docs_version: "26.4"
    pin:
      none: not in Git
"""

ODF_URL = "https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim"


def skill(name: str, product: str, version: str, body: str = "") -> str:
    return textwrap.dedent(f"""\
        ---
        name: {name}
        metadata:
          product: {product}
          docs-version: "{version}"
        description: test skill
        ---

        # {name}

        """) + body


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write(".agents/references/red-hat-doc-map.yaml", MAP)
        self.write("gitops/stages/010-x/odf/subscription.yaml",
                   "apiVersion: operators.coreos.com/v1alpha1\nkind: Subscription\nspec:\n  channel: stable-4.22\n")
        self.write("scripts/policy.py", "minimum={'rhcl-operator':'1.4.3'}\n")
        self.write(".agents/skills/odf-object-bucket-claims/SKILL.md",
                   skill("odf-object-bucket-claims", "odf", "4.22", f"See [OBC]({ODF_URL}).\n"))
        self.write(".agents/skills/rhcl-about/SKILL.md", skill("rhcl-about", "rhcl", "1.4"))
        self.write("AGENTS.md", "Use the `odf-object-bucket-claims` skill.\n")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cdl.main(["--root", str(self.root), *args])
        return code, out.getvalue()

    def codes(self) -> list[tuple[str, str]]:
        checker = cdl.Checker(self.root)
        checker.check_pins()
        checker.check_skills()
        checker.check_links()
        checker.check_references()
        return sorted((code, family) for code, family, _, _ in checker.findings)


class CheckDocLinksTest(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.tmp.cleanup()

    def test_clean_fixture_only_reports_unpinned(self):
        self.assertEqual(self.fx.codes(), [("UNPINNED", "keycloak")])
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)

    def test_unpinned_converted_family_does_not_fail(self):
        self.fx.write(".agents/references/red-hat-doc-map.yaml",
                      MAP.replace("converted_families: [odf]", "converted_families: [odf, keycloak]"))
        self.assertIn(("UNPINNED", "keycloak"), self.fx.codes())
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertIn("failing=0", out)

    def test_stale_skill_version_fails_converted_family(self):
        self.fx.write(".agents/skills/odf-object-bucket-claims/SKILL.md",
                      skill("odf-object-bucket-claims", "odf", "4.20"))
        self.assertIn(("STALE", "odf"), self.fx.codes())
        self.assertEqual(self.fx.run()[0], 1)
        self.assertEqual(self.fx.run("--report")[0], 0)

    def test_missing_frontmatter(self):
        self.fx.write(".agents/skills/odf-object-bucket-claims/SKILL.md",
                      "---\nname: odf-object-bucket-claims\ndescription: x\n---\n")
        self.assertIn(("FRONTMATTER", "odf"), self.fx.codes())

    def test_link_version_and_unknown_slug(self):
        self.fx.write(".agents/skills/odf-object-bucket-claims/references/notes.md",
                      ODF_URL.replace("/4.22/", "/4.20/") + "\n"
                      "https://docs.redhat.com/en/documentation/no_such_product/1.0/html/x\n")
        codes = self.fx.codes()
        self.assertIn(("LINK-VERSION", "odf"), codes)
        self.assertIn(("LINK-UNKNOWN", "odf"), codes)

    def test_readme_link_attributed_to_cited_product(self):
        self.fx.write("gitops/stages/010-x/odf/README.md",
                      "https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/x\n")
        self.assertIn(("LINK-VERSION", "rhcl"), self.fx.codes())

    def test_stage_readme_and_docs_links_are_checked(self):
        old = "https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/x\n"
        self.fx.write("stages/010-x/README.md", old)
        self.fx.write("docs/OPERATIONS.md", old)
        self.fx.write("README.md", old)
        findings = [(c, f, w) for c, f, w in self._findings() if c == "LINK-VERSION"]
        self.assertEqual(sorted(w.split(":")[0] for _, _, w in findings),
                         ["README.md", "docs/OPERATIONS.md", "stages/010-x/README.md"])
        self.assertTrue(all(f == "odf" for _, f, _ in findings))
        self.assertEqual(self.fx.run()[0], 1)  # odf is a converted family

    def test_docs_links_of_unconverted_product_report_only(self):
        self.fx.write("docs/TROUBLESHOOTING.md",
                      "https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/x\n")
        self.assertIn(("LINK-VERSION", "rhcl"), self.fx.codes())
        self.assertEqual(self.fx.run()[0], 0)

    def test_docs_migration_and_nested_stage_files_are_skipped(self):
        old = "https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/x\n"
        self.fx.write("docs/migration/old-plan.md", old)
        self.fx.write("stages/010-x/notes/README.md", old)
        self.assertNotIn("LINK-VERSION", [c for c, _ in self.fx.codes()])

    def _findings(self):
        checker = cdl.Checker(self.fx.root)
        checker.check_links()
        return [(code, family, where) for code, family, where, _ in checker.findings]

    def test_placeholder_links_are_ignored(self):
        self.fx.write(".agents/skills/odf-object-bucket-claims/references/t.md",
                      "https://docs.redhat.com/en/documentation/<slug>/<version>/\n")
        self.assertNotIn("LINK-UNKNOWN", [c for c, _ in self.fx.codes()])

    def test_pin_mismatch_yaml_field_and_regex(self):
        self.fx.write("gitops/stages/010-x/odf/subscription.yaml", "spec:\n  channel: stable-4.20\n")
        self.fx.write("scripts/policy.py", "minimum={'rhcl-operator':'1.3.4'}\n")
        codes = self.fx.codes()
        self.assertIn(("PIN-MISMATCH", "odf"), codes)
        self.assertIn(("PIN-MISMATCH", "rhcl"), codes)

    def test_pin_unreadable(self):
        self.fx.write("gitops/stages/010-x/odf/subscription.yaml", "spec:\n  name: odf\n")
        self.assertIn(("PIN-UNREADABLE", "odf"), self.fx.codes())

    def test_unconverted_family_reports_without_failing(self):
        self.fx.write(".agents/skills/rhcl-about/references/official-doc-extraction.md", "copied\n")
        self.fx.write(".agents/skills/rhcl-about/references/source-capture.md", "ledger\n")
        codes = self.fx.codes()
        self.assertIn(("EXTRACTION", "rhcl"), codes)
        self.assertIn(("SOURCE-CAPTURE", "rhcl"), codes)
        self.assertEqual(self.fx.run()[0], 0)

    def test_extraction_in_converted_family_fails(self):
        self.fx.write(".agents/skills/odf-object-bucket-claims/references/official-doc-extraction.md", "x\n")
        self.assertEqual(self.fx.run()[0], 1)

    def test_missing_skill_references(self):
        self.fx.write("AGENTS.md", "Use the `odf-nope` skill and the `odf-operator` skill.\n"
                                   "Read .agents/skills/odf-gone/SKILL.md.\n")
        self.fx.write(".agents/references/red-hat-doc-map.yaml",
                      MAP.replace("skill: odf-object-bucket-claims", "skill: odf-renamed"))
        found = [(c, f) for c, f in self.fx.codes() if c in ("MISSING-SKILL", "UNROUTED")]
        self.assertEqual(found, [("MISSING-SKILL", "odf")] * 3 + [("UNROUTED", "odf")])

    def test_skill_size(self):
        self.fx.write(".agents/skills/rhcl-about/SKILL.md", skill("rhcl-about", "rhcl", "1.4", "line\n" * 200))
        self.assertIn(("SKILL-SIZE", "rhcl"), self.fx.codes())

    def test_brief_hides_unconverted_lines(self):
        self.fx.write(".agents/skills/rhcl-about/references/source-capture.md", "x\n")
        _, out = self.fx.run("--brief")
        self.assertNotIn("SOURCE-CAPTURE rhcl", out)
        self.assertIn("rhcl (report-only): 1", out)

    def convert_skills(self, *names: str) -> None:
        self.fx.write(".agents/references/red-hat-doc-map.yaml",
                      MAP.replace("converted_families: [odf]",
                                  "converted_families: [odf]\nconverted_skills: [" + ", ".join(names) + "]"))
        self.fx.write(".agents/skills/rhcl-other/SKILL.md", skill("rhcl-other", "rhcl", "1.4"))
        self.fx.write(".agents/references/red-hat-doc-map.yaml",
                      (self.fx.root / ".agents/references/red-hat-doc-map.yaml").read_text().replace(
                          "            skill: rhcl-about\n",
                          "            skill: rhcl-about\n          - book: other\n            skill: rhcl-other\n"))

    def test_converted_skill_fails_only_for_listed_skill(self):
        self.convert_skills("rhcl-about")
        self.fx.write(".agents/skills/rhcl-other/references/source-capture.md", "x\n")
        code, out = self.fx.run("--brief")
        self.assertEqual(code, 0, out)
        self.assertIn("rhcl (partial, 1 skills converted): 1", out)
        self.fx.write(".agents/skills/rhcl-about/references/source-capture.md", "x\n")
        code, out = self.fx.run("--brief")
        self.assertEqual(code, 1, out)
        self.assertIn("SOURCE-CAPTURE rhcl .agents/skills/rhcl-about/", out)
        self.assertNotIn("rhcl-other/references", out)

    def test_converted_skill_link_version_fails(self):
        self.convert_skills("rhcl-about")
        self.fx.write(".agents/skills/rhcl-about/SKILL.md", skill(
            "rhcl-about", "rhcl", "1.4",
            "https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/x\n"))
        self.assertEqual(self.fx.run()[0], 1)

    def test_partial_family_pin_mismatch_fails(self):
        self.convert_skills("rhcl-about")
        self.fx.write("scripts/policy.py", "minimum={'rhcl-operator':'1.3.4'}\n")
        self.assertEqual(self.fx.run()[0], 1)

    def test_converted_skill_must_exist(self):
        self.convert_skills("rhcl-gone")
        self.assertIn(("MISSING-SKILL", "rhcl"), self.fx.codes())
        self.assertEqual(self.fx.run()[0], 1)

    def test_live_classification(self):
        answers = {
            ODF_URL: (200, '<h2 id="object-bucket-claim">'),
            "https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/gone": (404, ""),
            "https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/blocked": (403, ""),
        }
        self.fx.write(".agents/skills/odf-object-bucket-claims/references/links.md",
                      f"{ODF_URL}#object-bucket-claim\n{ODF_URL}#missing-anchor\n"
                      + "\n".join(u for u in answers if u != ODF_URL) + "\n")
        original = cdl.fetch
        cdl.fetch = lambda url: answers[url]
        try:
            code, out = self.fx.run("--live", "--delay", "0")
        finally:
            cdl.fetch = original
        self.assertEqual(code, 1)
        self.assertIn("LIVE-BROKEN odf", out)
        self.assertIn("HTTP 404", out)
        self.assertIn("anchor #missing-anchor", out)
        self.assertIn("INCONCLUSIVE odf", out)
        self.assertNotIn("anchor #object-bucket-claim not found", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
