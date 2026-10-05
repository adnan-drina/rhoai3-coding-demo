#!/usr/bin/env python3
"""B12 + B9 brief guidance selftest, under two package layouts.

  * an endpoint's response type is placed where its file IS: a generated
    OpenAPI type under target/generated-sources/openapi with the generator
    input a durable change goes to; a handwritten class whose name ends in
    Dto stays handwritten; a type nobody declares is RESPONSE_TYPE_UNRESOLVED
    with the roots searched
  * a mapper returning the response type is named with its annotation-
    processor implementation, and the implementation's edit owner is the
    annotated declaration, never the generated file
  * a getter matched by NAME is an unverified search hint, never a diagnosis
  * an order difference is explained in one sentence from B9's explanation
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import worklist  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


POM = """<project><build><plugins><plugin>
<groupId>org.openapitools</groupId><artifactId>openapi-generator-maven-plugin</artifactId>
<executions><execution><configuration>
<inputSpec>${project.basedir}/src/main/resources/openapi/%s.yml</inputSpec>
<modelPackage>%s</modelPackage>
</configuration></execution></executions>
</plugin></plugins></build></project>
"""


def _case(base: str) -> int:
    pkg = base.replace(".", "/")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "pom.xml").write_text(POM % ("api", base + ".dto"), encoding="utf-8")
        gen = root / "target/generated-sources/openapi/src/main/java" / pkg / "dto"
        gen.mkdir(parents=True)
        (gen / "LedgerDto.java").write_text("package %s.dto; public class LedgerDto {}\n" % base, encoding="utf-8")
        ann = root / "target/generated-sources/annotations" / pkg / "mapper"
        ann.mkdir(parents=True)
        (ann / "LedgerMapperImpl.java").write_text("package %s.mapper; class LedgerMapperImpl {}\n" % base, encoding="utf-8")
        ctrl = "src/main/java/%s/rest/LedgerController.java" % pkg
        model = {"types": [
            {"fqn": "%s.rest.LedgerController" % base, "path": ctrl, "declared": [
                {"name": "listLedgers", "type_refs": ["org.springframework.http.ResponseEntity<java.util.List<%s.dto.LedgerDto>>" % base]},
                {"name": "legacy", "type_refs": ["%s.api.LegacySummaryDto" % base]},
                {"name": "orphan", "type_refs": ["%s.gone.MissingView" % base]}]},
            {"fqn": "%s.api.LegacySummaryDto" % base, "path": "src/main/java/%s/api/LegacySummaryDto.java" % pkg, "declared": []},
            {"fqn": "%s.mapper.LedgerMapper" % base, "path": "src/main/java/%s/mapper/LedgerMapper.java" % pkg, "declared": [
                {"name": "toLedgerDtos", "type_refs": ["java.util.Collection<%s.dto.LedgerDto>" % base]}]},
            {"fqn": "%s.domain.Unrelated" % base, "path": "src/main/java/%s/domain/Unrelated.java" % pkg, "declared": [
                {"name": "getEntries", "type_refs": ["java.util.List<java.lang.String>"]}]},
        ]}
        real = worklist.dest_model
        worklist.dest_model = lambda _root, **_k: model
        try:
            ep = "ep:%s.rest.LedgerController#listLedgers():http" % base
            rp = worklist.response_path(root, ep)
            placed = {t["fqn"]: t for t in rp.get("types") or []}
            dto = placed.get("%s.dto.LedgerDto" % base) or {}
            if rp.get("status") != "resolved" or dto.get("ownership") != "generated" \
                    or dto.get("path") != "target/generated-sources/openapi/src/main/java/%s/dto/LedgerDto.java" % pkg:
                return _fail("a generated response type is found under its generated root (%s): %s" % (base, rp))
            if not any("src/main/resources/openapi/api.yml" in i for i in dto.get("inputs") or []) \
                    or "generator input" not in dto.get("edit_owner", ""):
                return _fail("a generated type's edit owner is its generator input (%s): %s" % (base, dto))
            if placed.get("org.springframework.http.ResponseEntity", {}).get("ownership") != "dependency":
                return _fail("a framework type is a dependency: %s" % placed)
            prod = next((p for p in rp.get("producers") or [] if p["type"] == "%s.mapper.LedgerMapper" % base), None)
            if not prod or prod.get("generated_impl") != "target/generated-sources/annotations/%s/mapper/LedgerMapperImpl.java" % pkg:
                return _fail("a mapper returning the type is named with its generated implementation (%s): %s" % (base, rp.get("producers")))
            legacy = worklist.response_path(root, "ep:%s.rest.LedgerController#legacy():http" % base)
            row = (legacy.get("types") or [{}])[0]
            if row.get("ownership") != "handwritten":
                return _fail("a handwritten class named *Dto is handwritten, never classified by its name: %s" % row)
            orphan = worklist.response_path(root, "ep:%s.rest.LedgerController#orphan():http" % base)
            row = (orphan.get("types") or [{}])[0]
            if row.get("ownership") != "unresolved" or "RESPONSE_TYPE_UNRESOLVED" not in row.get("edit_owner", "") \
                    or "target/generated-sources/openapi" not in row.get("searched", []):
                return _fail("an unplaceable type is RESPONSE_TYPE_UNRESOLVED with the roots searched: %s" % row)
        finally:
            worklist.dest_model = real
        # a getter matched by name is a hint, never a cause
        real_types, real_path = worklist.structure_types, worklist.structure_type_path
        worklist.structure_types = lambda _root: [{"fqn": "%s.domain.Unrelated" % base, "path": "x.java",
                                                   "methods": [{"name": "getEntries"}]}]
        worklist.structure_type_path = lambda _root, t: t["path"]
        try:
            hints = worklist.body_locus_hints(root, {"order_only": True, "differences": [
                {"path": "$[0].entries", "kind": "order"}]})
        finally:
            worklist.structure_types, worklist.structure_type_path = real_types, real_path
        if not hints or hints[0].get("status") != "unverified-name-match" or "produced by" in hints[0]["why"] \
                or "response_path" not in hints[0]["why"]:
            return _fail("an unrelated same-named getter is an unverified hint, not causal evidence: %s" % hints)
    # the order sentence the brief carries
    line = worklist.order_sentence({"path": "$[6].visits", "kind": "order", "order": {
        "relation": "reversed", "keys": [{"key": "postedAt", "expected": "desc", "observed": "asc"}]}})
    if "REVERSED" not in line or "postedAt DESC" not in line or "destination ASC" not in line:
        return _fail("a single-key reversal reads as one sentence: %s" % line)
    amb = worklist.order_sentence({"path": "$.xs", "kind": "order", "order": {
        "relation": "reversed", "keys": [{"key": "a", "expected": "desc", "observed": "asc"},
                                          {"key": "b", "expected": "desc", "observed": "asc"}]}})
    if "ambiguous" not in amb:
        return _fail("several candidate keys are reported as ambiguous: %s" % amb)
    return 0


def main() -> int:
    if _case("com.acme.ledger") or _case("org.example.bank.core"):
        return 1
    ref = (Path(__file__).resolve().parents[2] / "skills/migration/spring-to-quarkus-patterns/references/sorting.md").read_text(encoding="utf-8")
    if "The **third** argument is `ascending`. `false` means **descending**" not in ref or "nulls sort first when the order is descending" not in ref:
        return _fail("the Spring sorting reference states that ascending=false is descending, nulls first")
    print("OK: response path (generated types are found under their generated roots with their generator input as "
          "edit owner; a *Dto named handwritten class stays handwritten; an unplaceable type is "
          "RESPONSE_TYPE_UNRESOLVED; a mapper is named with its generated implementation; a name-matched getter is an "
          "unverified hint; order differences read as one sentence)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
