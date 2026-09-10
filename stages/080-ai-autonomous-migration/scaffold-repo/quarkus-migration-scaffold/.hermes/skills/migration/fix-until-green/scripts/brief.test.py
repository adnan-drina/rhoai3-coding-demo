#!/usr/bin/env python3
"""brief.py enrichment selftest: the brief carries the tools' facts per item kind.

pom items: advised artifacts present / unmanaged with the managed equivalent (catalog aliases).
compile items: the diagnostic, the inventory row for a missing legacy type, the Jakarta rename
for a javax.* package, the spring-to-quarkus-patterns reference that covers the symbol.
config items: the property line, the incident variables, the catalog mapping (key and value).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))
from brief import enrich  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cat_src = GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
        (root / ".hermes" / "planning" / "catalogs").mkdir(parents=True)
        shutil.copy(cat_src, root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json")
        refs_src = GOLDEN / ".hermes" / "skills" / "migration" / "spring-to-quarkus-patterns" / "references"
        shutil.copytree(refs_src, root / ".hermes" / "skills" / "migration" / "spring-to-quarkus-patterns" / "references")
        write_canonical(root / "evidence" / "build" / "bom-managed.json", {"managed": ["io.quarkus:quarkus-rest", "io.quarkus:quarkus-rest-jackson"]})
        write_canonical(root / "evidence" / "type-inventory.json", {"schema": "rhoai3.type-inventory/v1", "types": [
            {"fqn": "org.acme.dto.PetDto", "layer": "dto", "legacy_file": "src/main/java/org/acme/dto/PetDto.java", "dest_file": "src/main/java/org/acme/dto/PetDto.java", "generated": False},
            {"fqn": "org.acme.model.Owner", "layer": "model", "legacy_file": "src/main/java/org/acme/model/Owner.java", "dest_file": "src/main/java/org/acme/model/Owner.java", "generated": False},
        ]})
        (root / "src" / "main" / "java" / "org" / "acme" / "model").mkdir(parents=True)
        (root / "src" / "main" / "java" / "org" / "acme" / "model" / "Owner.java").write_text("class Owner {}\n", encoding="utf-8")
        (root / "src" / "main" / "java" / "org" / "acme" / "rest").mkdir(parents=True)
        (root / "src" / "main" / "java" / "org" / "acme" / "rest" / "PetResource.java").write_text(
            "package org.acme.rest;\nimport javax.persistence.Id;\nimport javax.validation.*;\nimport org.acme.dto.PetDto;\nclass PetResource {}\n", encoding="utf-8")
        (root / "src" / "main" / "resources").mkdir(parents=True)
        (root / "src" / "main" / "resources" / "application.properties").write_text(
            "# db\nspring.datasource.url=jdbc:h2:mem:x\nspring.jpa.hibernate.ddl-auto=create-drop\nlogging.level.org.acme=DEBUG\n", encoding="utf-8")
        (root / "pom.xml").write_text("<project><dependencies><dependency><groupId>io.quarkus</groupId><artifactId>quarkus-rest-jackson</artifactId></dependency></dependencies></project>\n", encoding="utf-8")
        findings = {"violations": {
            "springboot-web-to-quarkus-00010": {"description": "web", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "Add `quarkus-resteasy-reactive-jackson`."}], "links": []},
            "springboot-properties-to-quarkus-00001": {"description": "props", "incidents": [
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 2, "message": "Replace the property.", "variables": {"property": "spring.datasource.url"}},
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 3, "message": "Replace the property.", "variables": {}},
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 4, "message": "Replace the property.", "variables": {}},
            ], "links": []},
        }}
        write_canonical(root / "evidence" / "mta-findings.json", findings)

        pom_cluster = {"id": "c:pom", "kind": "build", "path": "pom.xml", "write_set": ["pom.xml"]}
        rows = enrich([{"id": "inc:1", "source": "mta", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 1, "rule_id": "springboot-web-to-quarkus-00010"}], root, pom_cluster)
        r = rows[0]
        if r.get("advice_unmanaged") != ["quarkus-resteasy-reactive-jackson"] or r.get("advice_managed_equivalent", {}).get("quarkus-resteasy-reactive-jackson") != "io.quarkus:quarkus-rest-jackson":
            return _fail("pom advice must flag the unmanaged Quarkus 2 name with the managed equivalent: %s" % r)
        if r.get("advice_managed_present") != ["io.quarkus:quarkus-rest-jackson"]:
            return _fail("the managed equivalent already in the pom must be reported present: %s" % r.get("advice_managed_present"))

        java_cluster = {"id": "c:java", "kind": "compile", "path": "src/main/java/org/acme/rest/PetResource.java", "write_set": ["src/main/java/org/acme/rest/PetResource.java"]}
        items = [
            {"id": "err:1", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 5, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class PetDto\n  location: class org.acme.rest.PetResource"},
            {"id": "err:2", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 3, "rule_id": "compiler.err.doesnt.exist",
             "message": "package javax.persistence does not exist"},
            {"id": "err:3", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 9, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class NamedParameterJdbcTemplate\n  location: class org.acme.rest.PetResource"},
            {"id": "err:4", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 12, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class Owner\n  location: class org.acme.rest.PetResource"},
            {"id": "err:5", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 2, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class Id\n  location: class org.acme.rest.PetResource"},
            {"id": "err:6", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 3, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class NotNull\n  location: class org.acme.rest.PetResource"},
        ]
        rows = enrich(items, root, java_cluster)
        a = rows[0]["advice"]
        if a.get("symbol") != {"kind": "class", "name": "PetDto"} or (a.get("inventory") or {}).get("fqn") != "org.acme.dto.PetDto" or a["inventory"].get("present_in_destination") is not False:
            return _fail("a missing legacy type must carry its inventory row and that it is not in the destination yet: %s" % a)
        if (rows[3]["advice"].get("inventory") or {}).get("present_in_destination") is not True:
            return _fail("a type already in the destination tree must say so: %s" % rows[3]["advice"])
        b = rows[1]["advice"]
        if b.get("package") != "javax.persistence" or b.get("rename") != {"from": "javax.persistence", "to": "jakarta.persistence"}:
            return _fail("a javax.* package must carry the documented Jakarta rename: %s" % b)
        c = rows[2]["advice"]
        if not any(ref.endswith("jdbc-anti-essay.md") for ref in c.get("references") or []):
            return _fail("a Spring symbol must cite the reference file that covers it: %s" % c)
        if "message" not in a or "cannot find symbol" not in a["message"]:
            return _fail("the compiler's own words must be in the advice")
        d = rows[4]["advice"]
        if d.get("imported_as") != "javax.persistence.Id" or d.get("rename") != {"from": "javax.persistence", "to": "jakarta.persistence"}:
            return _fail("a bare symbol bound by an explicit javax import must carry the rename: %s" % d)
        e = rows[5]["advice"]
        if e.get("imported_as") != "javax.validation.*" or (e.get("rename") or {}).get("to") != "jakarta.validation":
            return _fail("a bare symbol bound by a javax wildcard import must carry the rename: %s" % e)

        cfg_cluster = {"id": "c:cfg", "kind": "config", "path": "src/main/resources/application.properties", "write_set": ["src/main/resources/application.properties"]}
        items = [
            {"id": "inc:c1", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 2, "rule_id": "springboot-properties-to-quarkus-00001"},
            {"id": "inc:c2", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 3, "rule_id": "springboot-properties-to-quarkus-00001"},
            {"id": "inc:c3", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 4, "rule_id": "springboot-properties-to-quarkus-00001"},
        ]
        rows = enrich(items, root, cfg_cluster)
        c1 = rows[0].get("config") or {}
        if c1.get("line_text") != "spring.datasource.url=jdbc:h2:mem:x" or c1.get("property") != "spring.datasource.url" or (c1.get("mapping") or {}).get("to") != "quarkus.datasource.jdbc.url" or c1.get("variables") != {"property": "spring.datasource.url"}:
            return _fail("a config item must carry the line, the key, the incident variables and the catalog mapping: %s" % c1)
        c2 = rows[1].get("config") or {}
        if (c2.get("mapping") or {}).get("to") != "quarkus.hibernate-orm.database.generation" or c2.get("value_mapping") != {"from": "create-drop", "to": "drop-and-create"}:
            return _fail("a mapped key with a documented value mapping must carry both: %s" % c2)
        c3 = rows[2].get("config") or {}
        if (c3.get("mapping") or {}).get("to") != 'quarkus.log.category."org.acme".level':
            return _fail("a prefix mapping must expand the rest of the key: %s" % c3)
        # a file-level incident on a profile file lists every Spring key with its mapping
        (root / "src" / "main" / "resources" / "application-hsqldb.properties").write_text(
            "# db\nquarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\nspring.jpa.database=HSQL\nspring.datasource.username=sa\n", encoding="utf-8")
        prof = {"id": "c:prof", "kind": "config", "path": "src/main/resources/application-hsqldb.properties", "write_set": ["src/main/resources/application-hsqldb.properties"]}
        rows = enrich([{"id": "inc:p1", "source": "mta", "kind": "config", "category": "mandatory", "path": prof["path"], "line": 0, "rule_id": "springboot-properties-to-quarkus-00001"}], root, prof)
        c4 = rows[0].get("config") or {}
        if c4.get("profile") != "hsqldb" or [k["key"] for k in c4.get("spring_keys") or []] != ["spring.jpa.database", "spring.datasource.username"] or c4["spring_keys"][1]["to"] != "quarkus.datasource.username":
            return _fail("a file-level profile incident must name the profile and the remaining Spring keys with their mappings: %s" % c4)
    print("OK: brief enrichment (pom unmanaged→managed; compile: inventory hit / present flag / Jakarta rename / reference file; config: line, key, variables, key+value mapping, prefix expansion)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
