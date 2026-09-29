#!/usr/bin/env python3
"""The Servlet redirect recipe's retained-field check (architect review 2026-09-29, G3).

v28 t_25819d9c translated the redirect and kept @Value("#{servletContext.contextPath}"), which compiles and fails
the package gate (SpEL expressions are not supported). The early check refuses exactly that: a field that
INJECTS the servlet context through Spring's @Value, resolved the way handler-parameter annotations are (a
qualified name as written, else the import that binds the simple name). The same text as a literal in another
annotation is data, an annotation no import binds is unknown attribution (never a demonstrated violation), and
the rule is read from the catalog row -- every case is repeated on a renamed type and field.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERMES = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERMES / "lib"))
from planner import worklist  # noqa: E402

CATALOG = HERMES / "planning" / "catalogs" / "compat-mapping.json"
VALUE = "org.springframework.beans.factory.annotation.Value"
JSON_PROPERTY = "com.fasterxml.jackson.annotation.JsonProperty"
HANDLER = {"type_refs": ["org.springframework.http.ResponseEntity<java.lang.Void>"], "call_names": ["location"]}
NAMES = (("org.springframework.samples.petclinic.rest.RootRestController", "servletContextPath", "redirectToSwagger"),
         ("z.gateway.PortalResource", "basePath", "go"))


def spec(fqn: str) -> dict:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))["handler_parameters"]["undocumented"]
    return rows[fqn]["response_translation"]


def typ(field: str, annotation: dict, imports: list[str]) -> dict:
    return {"imports": imports, "fields": [{"name": field, "annotations": [annotation]}]}


def ann(fqn: str, value: str, *, qualified: bool = True) -> dict:
    simple = fqn.rsplit(".", 1)[-1]
    return {"fqn": fqn if qualified else simple, "simple": simple, "resolution": "full" if qualified else "none",
            "values": [value]}


class RetainedServletContextField(unittest.TestCase):

    def verdict(self, t, fqn="jakarta.servlet.http.HttpServletResponse", type_fqn="a.T", member="m"):
        return worklist._response_verdict(type_fqn, member, [HANDLER], spec(fqn), t)

    def test_the_catalog_names_the_annotation_not_a_bare_text(self):
        for fqn in ("jakarta.servlet.http.HttpServletResponse", "javax.servlet.http.HttpServletResponse"):
            inj = spec(fqn)["forbidden_field_injection"]
            self.assertEqual((inj["annotation"], inj["value_prefixes"]), (VALUE, ["#{servletContext"]))
            self.assertNotIn("forbidden_field_values", spec(fqn))

    def test_a_value_injection_is_refused_early_under_any_name(self):
        for type_fqn, field, member in NAMES:
            for a, imports in ((ann(VALUE, "#{servletContext.contextPath}"), []),
                               (ann(VALUE, "#{servletContext.contextPath}", qualified=False), [VALUE]),
                               (ann(VALUE, "#{ servletContext.contextPath }"), [])):
                v = self.verdict(typ(field, a, imports), type_fqn=type_fqn, member=member)
                self.assertEqual((v or {}).get("verdict"), "violates", (type_fqn, a))
                self.assertIn("%s.%s still injects" % (type_fqn, field), v["detail"])
                self.assertIn("through @Value", v["detail"])
            # the pre-Jakarta row carries the same rule
            v = self.verdict(typ(field, ann(VALUE, "#{servletContext.contextPath}"), []),
                             fqn="javax.servlet.http.HttpServletResponse", type_fqn=type_fqn, member=member)
            self.assertEqual((v or {}).get("verdict"), "violates")

    def test_a_literal_in_another_annotation_is_data(self):
        for _type_fqn, field, _member in NAMES:
            for a, imports in ((ann(JSON_PROPERTY, "#{servletContext.contextPath}"), []),
                               (ann(JSON_PROPERTY, "#{servletContext.contextPath}", qualified=False), [JSON_PROPERTY])):
                self.assertIsNone(self.verdict(typ(field, a, imports)), a)

    def test_unknown_attribution_is_not_a_demonstrated_violation(self):
        # a simple @Value no import binds (a wildcard import binds nothing): the package gate still decides
        a = ann(VALUE, "#{servletContext.contextPath}", qualified=False)
        self.assertIsNone(self.verdict(typ("servletContextPath", a, ["org.springframework.beans.factory.annotation.*"])))
        self.assertIsNone(self.verdict(typ("servletContextPath", a, [])))
        # another project's annotation spelled Value is not Spring's
        self.assertIsNone(self.verdict(typ("servletContextPath", a, ["com.example.config.Value"])))

    def test_other_value_expressions_are_not_this_rule(self):
        for value in ("${server.servlet.context-path}", "#{systemProperties['user.home']}", "/petclinic"):
            self.assertIsNone(self.verdict(typ("servletContextPath", ann(VALUE, value), [])), value)

    def test_the_handler_shape_is_still_judged_first(self):
        void = {"type_refs": ["void"], "call_names": []}
        v = worklist._response_verdict("a.T", "m", [void], spec("jakarta.servlet.http.HttpServletResponse"), typ("f", ann(JSON_PROPERTY, "x"), []))
        self.assertEqual(v["verdict"], "violates")
        self.assertIn("must return org.springframework.http.ResponseEntity", v["detail"])
        self.assertIsNone(worklist._response_verdict("a.T", "m", [HANDLER], spec("jakarta.servlet.http.HttpServletResponse"),
                                                     {"imports": [], "fields": []}))


if __name__ == "__main__":
    unittest.main()
