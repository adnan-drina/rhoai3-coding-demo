#!/usr/bin/env python3
"""brief.py enrichment selftest: the brief carries the tools' facts per item kind.

pom items: advised artifacts present / unmanaged with the managed equivalent (catalog aliases).
compile items: the diagnostic, the inventory row for a missing legacy type, the Jakarta rename
for a javax.* package, the spring-to-quarkus-patterns reference that covers the symbol.
config items: the property line, the incident variables, the catalog mapping (key and value).
"""
from __future__ import annotations

import json
import os
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


def _repository_inventory_case() -> int:
    """A *Repository.java brief names every declared method and what it extends."""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("brief_mod", HERE / "brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="repoinv-") as td:
        root = Path(td)
        f = root / "src" / "main" / "java" / "a" / "UserRepository.java"
        f.parent.mkdir(parents=True)
        f.write_text("package a;\npublic interface UserRepository extends JpaRepository<User, Long> {\n"
                     "    @Query(\"SELECT u FROM User u\")\n"
                     "    List<User> findAll();\n"
                     "    void save(User u);\n}\n", encoding="utf-8")
        inv = mod.repository_inventory(root, "src/main/java/a/UserRepository.java")
        names = {m["name"] for m in (inv or {}).get("methods") or []}
        if inv is None or "JpaRepository" not in (inv.get("extends") or "") or names != {"findAll", "save"}:
            return _fail("repository inventory must list extends + methods: %s" % inv)
        finder = next(m for m in inv["methods"] if m["name"] == "findAll")
        if not finder.get("query") or finder.get("modifying"):
            return _fail("findAll must be marked @Query: %s" % finder)
        if "one transformation" not in (inv.get("batch") or ""):
            return _fail("inventory must carry the batching rule: %s" % inv.get("batch"))
        if mod.repository_inventory(root, "src/main/java/a/ClinicService.java") is not None:
            return _fail("non-repository paths have no inventory")
    return 0


def _runtime_advice_case() -> int:
    """A packaging obligation names one member; the brief names the rest."""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("brief_mod", HERE / "brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="rtadv-") as td:
        root = Path(td)
        f = root / "src" / "main" / "java" / "a" / "UserRepository.java"
        f.parent.mkdir(parents=True)
        f.write_text("package a;\npublic interface UserRepository {\n"
                     "    void save(User u);\n    void delete(User u);\n    User findById(int id);\n}\n", encoding="utf-8")
        item = {"source": "runtime", "gate": "package", "cause": "underivable-query-method", "member": "save",
                "path": "src/main/java/a/UserRepository.java", "message": "Method 'save' cannot be parsed"}
        adv = mod.runtime_advice(item, root)
        if adv.get("siblings") != ["delete", "findById"]:
            return _fail("the brief must name the other declared members: %s" % adv.get("siblings"))
        if "another full verification" not in adv.get("sibling_note", ""):
            return _fail("and say why fixing them together matters: %s" % adv.get("sibling_note"))
        # the answer already in the tree: the same member, annotated, elsewhere
        other = root / "src" / "main" / "java" / "a" / "SpringDataUserRepository.java"
        other.write_text("package a;\npublic interface SpringDataUserRepository extends UserRepository {\n"
                         "    @Override\n    @Query(\"SELECT u FROM User u\")\n    void save(User u);\n}\n", encoding="utf-8")
        adv = mod.runtime_advice(item, root)
        refs = adv.get("declared_elsewhere") or []
        if not refs or refs[0]["path"] != "src/main/java/a/SpringDataUserRepository.java" or "@Query" not in refs[0]["snippet"]:
            return _fail("the brief must show where the member is declared elsewhere, with its annotations: %s" % refs)
        if "already present in this destination" not in adv.get("elsewhere_note", ""):
            return _fail("and say that it is not something to invent: %s" % adv.get("elsewhere_note"))
        # the query the destination cannot see, because a retirement removed it
        frozen = root / ".derived" / "frozen-input" / "src" / "main" / "java" / "a" / "jpa" / "JpaUserRepositoryImpl.java"
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text("package a.jpa;\npublic class JpaUserRepositoryImpl {\n"
                          "    public void save(User u) {\n"
                          "        this.em.createQuery(\"SELECT u FROM User u ORDER BY u.id\");\n    }\n}\n", encoding="utf-8")
        adv = mod.runtime_advice(item, root)
        fi = adv.get("frozen_implementations") or []
        if not fi or fi[0]["query"] != "SELECT u FROM User u ORDER BY u.id":
            return _fail("the brief must carry the frozen implementation and its query: %s" % fi)
        if "rather than writing one" not in adv.get("frozen_note", ""):
            return _fail("and say why it is there: %s" % adv.get("frozen_note"))

        # a write must not be "repaired" with a bare @Query
        if "not a repair for it" not in (adv.get("caution") or ""):
            return _fail("a write needs the caution: %s" % adv.get("caution"))
        read = mod.runtime_advice({"source": "runtime", "gate": "package", "cause": "underivable-query-method",
                                   "member": "findByLastName", "path": "src/main/java/a/UserRepository.java",
                                   "message": "Method 'findByLastName' of repository"}, root)
        if read.get("caution"):
            return _fail("a finder is not a write and needs no such caution: %s" % read.get("caution"))
        bare = mod.runtime_advice({"source": "runtime", "gate": "boot", "cause": "datasource-unconfigured",
                                   "path": "src/main/resources/application.properties", "message": "x"}, root)
        if bare.get("siblings"):
            return _fail("a failure that names no member has no siblings to name: %s" % bare)
    return 0


def main() -> int:
    if _repository_inventory_case():
        return 1
    if _runtime_advice_case():
        return 1

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

        # the rule's own condition, verbatim from the pinned rulesets (MTA_CLI_HOME)
        rs = root / "mta" / "rulesets" / "java" / "quarkus"; rs.mkdir(parents=True)
        (rs / "236-springboot-web-to-quarkus.windup.yaml").write_text(
            "- category: mandatory\n  ruleID: springboot-web-to-quarkus-00000\n  when:\n    java.dependency:\n      name: x\n"
            "- category: mandatory\n  description: Add jackson\n  ruleID: springboot-web-to-quarkus-00010\n  when:\n    or:\n    - and:\n      - java.dependency:\n          name: io.quarkus.quarkus-spring-web\n      - java.dependency:\n          name: io.quarkus.quarkus-resteasy-reactive-jackson\n        not: true\n  message: m\n- category: optional\n  ruleID: other\n", encoding="utf-8")
        os.environ["MTA_CLI_HOME"] = str(root / "mta")
        pom_cluster = {"id": "c:pom", "kind": "build", "path": "pom.xml", "write_set": ["pom.xml"]}
        rows = enrich([{"id": "inc:1", "source": "mta", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 1, "rule_id": "springboot-web-to-quarkus-00010"}], root, pom_cluster)
        r = rows[0]
        if r.get("advice_unmanaged") != ["quarkus-resteasy-reactive-jackson"] or r.get("advice_managed_equivalent", {}).get("quarkus-resteasy-reactive-jackson") != "io.quarkus:quarkus-rest-jackson":
            return _fail("pom advice must flag the unmanaged Quarkus 2 name with the managed equivalent: %s" % r)
        if r.get("advice_managed_present") != ["io.quarkus:quarkus-rest-jackson"]:
            return _fail("the managed equivalent already in the pom must be reported present: %s" % r.get("advice_managed_present"))
        g = enrich([{"id": "err:g", "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "GENERATED_SOURCE_ERROR",
                     "message": "target/generated-sources/openapi/src/main/java/a/PetDto.java:9: package javax.validation does not exist", "generated_path": "target/generated-sources/openapi/src/main/java/a/PetDto.java"}], root, pom_cluster)[0]
        ga = g.get("advice") or {}
        if ga.get("plugin") != "org.openapitools:openapi-generator-maven-plugin" or (ga.get("plugin_config") or {}).get("configuration", {}).get("generatorName") != "jaxrs-spec" or "generated file" not in ga.get("description", ""):
            return _fail("a generated-source error must point at the generator plugin and the catalog's documented configuration: %s" % ga)
        from brief import collapse_generated
        gens = [{"id": "err:%d" % i, "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "GENERATED_SOURCE_ERROR",
                 "message": "target/generated-sources/openapi/src/main/java/a/D%d.java:9: package javax.validation does not exist" % i, "generated_path": "target/generated-sources/openapi/src/main/java/a/D%d.java" % (i % 3)} for i in range(7)]
        col = collapse_generated(gens + [{"id": "inc:x", "source": "mta", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 1, "rule_id": "r"}])
        if len(col) != 2 or col[0].get("count") != 7 or len(col[0].get("item_ids") or []) != 7 or len(col[0].get("generated_files") or []) != 3 or col[0]["generated_root"] != "target/generated-sources/openapi" or col[1]["id"] != "inc:x":
            return _fail("generated-source errors must collapse to one item per generated root with count, files and ids: %s" % [(c.get("id"), c.get("count")) for c in col])
        cond = r.get("rule_condition") or ""
        if not cond.startswith("when:") or "quarkus-resteasy-reactive-jackson" not in cond or "not: true" not in cond or "message: m" in cond or "ruleID: other" in cond:
            return _fail("the brief must carry the rule's when-block verbatim and nothing else: %r" % cond)

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
    print("OK: brief enrichment (pom unmanaged→managed; compile: inventory hit / present flag / Jakarta rename / reference file; config: line, key, variables, key+value mapping, prefix expansion; runtime: the cause, the member, and the siblings likely to carry it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
