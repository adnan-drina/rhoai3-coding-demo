"""ADR-025 follow-up: the three static triggers / per-site checks, each shown
failing on the defect shape and passing on the documented repair, on a
specimen and a renamed twin; the absent-result and transaction checks also
through the real compiler model (DestModel: calls, catches, private)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import static_triggers as ST  # noqa: E402
from planner.worklist import _assess_implementations  # noqa: E402

HERMES = Path(__file__).resolve().parents[2]
CATALOG = HERMES / "planning" / "catalogs" / "compat-mapping.json"

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>g</groupId><artifactId>a</artifactId><version>1</version>
<build><plugins><plugin><groupId>org.openapitools</groupId><artifactId>openapi-generator-maven-plugin</artifactId>
<version>%s</version><executions><execution><goals><goal>generate</goal></goals><configuration>
<inputSpec>${project.basedir}/src/main/resources/api.yml</inputSpec><generatorName>%s</generatorName><library>%s</library>
<modelNameSuffix>Dto</modelNameSuffix>%s<configOptions><useBeanValidation>true</useBeanValidation></configOptions>
</configuration></execution></executions></plugin></plugins></build></project>
"""
SPEC = """{"openapi": "3.0.1", "info": {"title": "t", "version": "1"}, "paths": {},
 "components": {"schemas": {
  "%(E)sFields": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
  "%(E)s": {"allOf": [{"$ref": "#/components/schemas/%(E)sFields"},
     {"type": "object", "properties": {"id": {"type": "integer", "readOnly": true},
       "%(P)s": {"type": "array", "items": {"type": "string"}, "readOnly": true}}, "required": ["%(P)s"]}]}}}}
"""


def gen_root(pkg: str, ent: str, prop: str, *, version="7.25.0", source_gen="spring", override: str | None = None) -> tuple[Path, dict]:
    root = Path(tempfile.mkdtemp(prefix="st-gen-"))
    (root / ".hermes" / "planning" / "catalogs").mkdir(parents=True)
    shutil.copyfile(CATALOG, root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json")
    tpl = ""
    if override is not None:
        (root / ST.TEMPLATE_DIR).mkdir(parents=True)
        (root / ST.TEMPLATE_FILE).write_text(override, encoding="utf-8")
        tpl = "<templateDirectory>${project.basedir}/%s</templateDirectory>" % ST.TEMPLATE_DIR
    (root / "pom.xml").write_text(POM % (version, "jaxrs-spec", "quarkus", tpl), encoding="utf-8")
    fz = root / ".derived" / "frozen-input"
    fz.mkdir(parents=True)
    (fz / "pom.xml").write_text(POM % ("5.2.1", source_gen, "spring-boot", ""), encoding="utf-8")
    (root / "src/main/resources").mkdir(parents=True)
    (root / "src/main/resources/api.yml").write_text(SPEC % {"E": ent, "P": prop}, encoding="utf-8")
    dto = "%s.dto.%sDto" % (pkg, ent)
    ctrl = "%s.rest.%sController" % (pkg, ent)
    bundle = {"entry_points": [{"id": "ep:1", "kind": "http", "type": ctrl, "member": "add(%s)" % dto}],
              "structure": {"types": [{"fqn": ctrl, "methods": [{"signature": "add(%s)" % dto, "params": [
                  {"type": dto, "annotations": [{"fqn": "org.springframework.web.bind.annotation.RequestBody"}]}]}]}]}}
    return root, bundle


class RequiredReadOnly(unittest.TestCase):
    def test_planned_until_the_template_restores_the_constraint(self):
        for pkg, ent, prop in (("org.acme.clinic", "Owner", "pets"), ("com.example.depot", "Crate", "labels")):
            root, bundle = gen_root(pkg, ent, prop)
            items, notes = ST.required_read_only_items(root, bundle)
            self.assertEqual(len(items), 1, notes)
            it = items[0]
            self.assertEqual((it["path"], it["gate"], it["kind"]), (ST.TEMPLATE_FILE, "plan", "build"))
            self.assertIn("%sDto.%s" % (ent, prop), it["message"])
            self.assertIn("templateDirectory", it["advice"]["first_action"])
            # the documented repair: the plugin's own 7.25.0 template without the readOnly guard
            guarded = "{{#required}}{{^isReadOnly}}@NotNull {{/isReadOnly}}{{/required}}"
            root2, _ = gen_root(pkg, ent, prop, override=guarded.replace("{{^isReadOnly}}", "").replace("{{/isReadOnly}}", ""))
            self.assertEqual(ST.required_read_only_items(root2, bundle), ([], []))
            # a template that still carries the guard restores nothing
            root3, _ = gen_root(pkg, ent, prop, override=guarded)
            self.assertEqual(len(ST.required_read_only_items(root3, bundle)[0]), 1)

    def test_other_generators_and_versions_are_not_guessed(self):
        root, bundle = gen_root("org.acme.clinic", "Owner", "pets", version="7.26.0")
        items, notes = ST.required_read_only_items(root, bundle)
        self.assertEqual(items, [])
        self.assertIn("UNRESOLVED", notes[0])
        root, bundle = gen_root("org.acme.clinic", "Owner", "pets", source_gen="java")
        self.assertEqual(ST.required_read_only_items(root, bundle), ([], []))


def _row(sig: str, kind: str = "query", effect: str = "read") -> dict:
    return {"behaviour": {"members": [{"signature": sig, "kind": kind, "effect": effect, "source": "X#%s" % sig}]}}


class AbsentResult(unittest.TestCase):
    def test_a_bare_single_result_read_is_refused_and_the_translations_pass(self):
        for fqn, ret in (("org.acme.clinic.repository.OwnerRepositoryImpl", "org.acme.clinic.model.Owner"),
                         ("com.example.depot.store.CrateStoreImpl", "com.example.depot.model.Crate")):
            def typ(calls, catches=None, r=ret):
                m = {"signature": "findById(int)", "type_refs": [r], "calls": calls}
                if catches:
                    m["catches"] = catches
                return {"fqn": fqn, "declared": [m]}
            bare = ["jakarta.persistence.TypedQuery.getSingleResult()"]
            self.assertIn("NoResultException", ST.absent_result_verdict(typ(bare), _row("findById(int)")))
            self.assertEqual(ST.absent_result_verdict(typ(["jakarta.persistence.TypedQuery.getResultStream()"]),
                                                      _row("findById(int)")), "")
            self.assertEqual(ST.absent_result_verdict(typ(bare, ["jakarta.persistence.NoResultException"]),
                                                      _row("findById(int)")), "")
            self.assertEqual(ST.absent_result_verdict(typ(bare, r="long"), _row("findById(int)")), "")      # a count
            self.assertEqual(ST.absent_result_verdict(typ(bare), _row("findById(int)", effect="write")), "")
            self.assertEqual(ST.absent_result_verdict(typ(bare), {"behaviour": {"members": []}}), "")


def _tx_models(dest_ann_member: bool, dest_ann_class: bool, private: bool = False, keep_member: bool = True):
    spring = [{"fqn": ST.SPRING_TX}]
    jak = [{"fqn": "jakarta.transaction.Transactional"}]
    frozen = {"types": [{"fqn": "org.acme.svc.ClinicServiceImpl", "path": "src/main/java/org/acme/svc/ClinicServiceImpl.java",
                         "annotations": [], "declared": [{"name": "save", "signature": "save(org.acme.O)", "params": [{}],
                                                          "annotations": spring}]}]}
    m = {"name": "save", "signature": "save(org.acme.O)", "params": [{}], "annotations": jak if dest_ann_member else []}
    if private:
        m["private"] = True
    dest = {"types": [{"fqn": "org.acme.svc.ClinicServiceImpl", "path": "src/main/java/org/acme/svc/ClinicServiceImpl.java",
                       "annotations": jak if dest_ann_class else [], "declared": [m] if keep_member else []}]}
    return frozen, dest


class TransactionBoundaries(unittest.TestCase):
    def test_a_deleted_or_private_boundary_is_refused(self):
        v = lambda f, d: [r["verdict"] for r in ST.transaction_verdicts(f, d)]  # noqa: E731
        self.assertEqual(v(*_tx_models(False, False)), ["violates"])
        self.assertEqual(v(*_tx_models(True, False)), ["ok"])
        self.assertEqual(v(*_tx_models(False, True)), ["ok"])
        self.assertEqual(v(*_tx_models(True, False, private=True)), ["violates"])
        self.assertEqual(v(*_tx_models(True, False, keep_member=False)), ["violates"])
        f, d = _tx_models(False, False)
        self.assertEqual(ST.transaction_verdicts(f, d, ["src/main/java/other/X.java"]), [])


class RealModel(unittest.TestCase):
    """The same checks through DestModel on a compiled tree (calls, catches, private)."""

    STUBS = {
        "jakarta/persistence/NoResultException.java": "package jakarta.persistence; public class NoResultException extends RuntimeException {}",
        "jakarta/persistence/TypedQuery.java": "package jakarta.persistence; public interface TypedQuery<X> { X getSingleResult(); java.util.stream.Stream<X> getResultStream(); TypedQuery<X> setParameter(String n, Object v); }",
        "jakarta/persistence/EntityManager.java": "package jakarta.persistence; public interface EntityManager { <T> TypedQuery<T> createQuery(String q, Class<T> c); }",
        "jakarta/transaction/Transactional.java": "package jakarta.transaction; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Transactional {}",
        "org/acme/model/Owner.java": "package org.acme.model; public class Owner {}",
        "org/acme/repository/OwnerRepository.java": "package org.acme.repository; public interface OwnerRepository { org.acme.model.Owner findById(int id); }",
    }
    BARE = "return em.createQuery(\"select o from Owner o where o.id = :id\", Owner.class).setParameter(\"id\", id).getSingleResult();"
    STREAM = "return em.createQuery(\"select o from Owner o where o.id = :id\", Owner.class).setParameter(\"id\", id).getResultStream().findFirst().orElse(null);"
    CATCH = "try { " + BARE + " } catch (NoResultException e) { return null; }"

    def tree(self, body: str, tx: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="st-real-"))
        src = root / "src/main/java"
        for rel, text in self.STUBS.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text, encoding="utf-8")
        (src / "org/acme/repository/OwnerRepositoryImpl.java").write_text(
            "package org.acme.repository;\nimport jakarta.persistence.*;\nimport org.acme.model.Owner;\n"
            "public class OwnerRepositoryImpl implements OwnerRepository {\n  EntityManager em;\n"
            "  public Owner findById(int id) { %s }\n}\n" % body, encoding="utf-8")
        (src / "org/acme/svc").mkdir(parents=True)
        (src / "org/acme/svc/ClinicServiceImpl.java").write_text(
            "package org.acme.svc;\npublic class ClinicServiceImpl {\n  %s void save(Object o) { }\n}\n" % tx, encoding="utf-8")
        return root

    def test_absent_result_and_boundary_through_the_compiler_model(self):
        if shutil.which("javac") is None:
            self.skipTest("javac is not on PATH")
        from planner.dest_model import dest_model
        from planner.worklist import _unit_path, _unit_types
        verdicts = {}
        for name, body in (("bare", self.BARE), ("stream", self.STREAM), ("catch", self.CATCH)):
            root = self.tree(body, "@jakarta.transaction.Transactional public")
            model = dest_model(root)
            by_path = {}
            for t in _unit_types(model):
                by_path.setdefault(_unit_path(t), []).append(t)
            path = "src/main/java/org/acme/repository/OwnerRepositoryImpl.java"
            scope = {"implementation_obligations": [dict(_row("findById(int)"), parent="org.acme.repository.OwnerRepository",
                                                         type="org.acme.repository.OwnerRepositoryImpl", path=path,
                                                         members=["findById(int)"])]}
            rows = _assess_implementations(root, scope, model, by_path, "unit/declaration-closure/v1")
            verdicts[name] = rows[0]["verdict"]
            if name == "bare":
                self.assertIn("NoResultException", rows[0]["detail"])
            if name == "catch":
                impl = next(t for t in _unit_types(model) if t["fqn"] == "org.acme.repository.OwnerRepositoryImpl")
                fb = next(m for m in impl["declared"] if m.get("signature") == "findById(int)")
                self.assertIn("jakarta.persistence.NoResultException", fb.get("catches") or [])
        self.assertEqual(verdicts, {"bare": "violates", "stream": "ok", "catch": "ok"})
        root = self.tree(self.STREAM, "@jakarta.transaction.Transactional private")
        model = dest_model(root)
        typ = next(t for t in _unit_types(model) if t["fqn"] == "org.acme.svc.ClinicServiceImpl")
        save = next(m for m in typ["declared"] if m.get("name") == "save")
        self.assertTrue(save.get("private"))
        frozen = {"types": [dict(typ, annotations=[], declared=[dict(save, annotations=[{"fqn": ST.SPRING_TX}])])]}
        self.assertEqual([r["verdict"] for r in ST.transaction_verdicts(frozen, model)], ["violates"])
        root = self.tree(self.STREAM, "@jakarta.transaction.Transactional public")
        self.assertEqual([r["verdict"] for r in ST.transaction_verdicts(frozen, dest_model(root))], ["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
