"""Static triggers and per-site checks for three known patterns (M-4 follow-up
to ADR-025; SOLUTION-ARCHITECTURE 7.3), each decided from files on disk and
the compiler models -- never from a destination failure:

  required_read_only_items      a request-body property the spec lists as
                                required AND readOnly: jaxrs-spec 7.25.0 omits
                                its @NotNull where the source's spring
                                generator kept it (compat-mapping build_plugins
                                ... jaxrs-spec.required_read_only); planned as
                                an obligation until the generator's own
                                template restores it
  absent_result_verdict         an owed fragment member whose selected source
                                behaviour is a READ answering null for no row
                                (Spring Data) but whose destination body calls
                                getSingleResult() without catching
                                NoResultException (repository_behaviour.
                                query_result_semantics)
  transaction_verdicts          every source @Transactional boundary (class or
                                method) still has a Jakarta @Transactional on
                                the destination's same type/member, and none
                                sits on a private method (objective_families.
                                transaction-annotations)

Isolated beside worklist.py: worklist and requirement_checks call these at
single, minimal sites. Specimen-agnostic. Python 3.9 compatible.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

TEMPLATE_DIR = "src/main/openapi-templates"
TEMPLATE_FILE = TEMPLATE_DIR + "/beanValidation.mustache"
READ_ONLY_GUARD = "{{^isReadOnly}}"
QUALIFIED_VERSIONS = ("7.25.0",)
SPRING_TX = "org.springframework.transaction.annotation.Transactional"
JAKARTA_TX = ("jakarta.transaction.Transactional", "javax.transaction.Transactional")
SINGLE_RESULT_OWNERS = ("jakarta.persistence.Query", "jakarta.persistence.TypedQuery",
                        "javax.persistence.Query", "javax.persistence.TypedQuery")
# a catch of any of these handles NoResultException (its supertypes)
NO_RESULT_HANDLERS = ("jakarta.persistence.NoResultException", "javax.persistence.NoResultException",
                      "jakarta.persistence.PersistenceException", "javax.persistence.PersistenceException",
                      "java.lang.RuntimeException", "java.lang.Exception", "java.lang.Throwable")
# a scalar return (a count) is never absent
SCALAR_RETURNS = ("int", "long", "short", "byte", "boolean", "double", "float", "java.lang.Integer", "java.lang.Long",
                  "java.lang.Short", "java.lang.Byte", "java.lang.Boolean", "java.lang.Double", "java.lang.Float",
                  "java.lang.Number", "java.math.BigInteger", "java.math.BigDecimal")


# --------------------------------------------------------------------------- required readOnly

def _pom_template_directory(root: Path) -> str:
    """The openapi-generator plugin's <templateDirectory>, '' when none."""
    pom = Path(root) / "pom.xml"
    if not pom.is_file():
        return ""
    try:
        tree = ET.parse(str(pom))
    except ET.ParseError:
        return ""
    for el in tree.iter():
        if el.tag.rsplit("}", 1)[-1] != "plugin":
            continue
        aid = next((c.text or "" for c in el if c.tag.rsplit("}", 1)[-1] == "artifactId"), "")
        if aid.strip() != "openapi-generator-maven-plugin":
            continue
        for sub in el.iter():
            if sub.tag.rsplit("}", 1)[-1] == "templateDirectory" and (sub.text or "").strip():
                return (sub.text or "").strip()
    return ""


def template_restores_constraint(root: Path) -> bool:
    """Does the build's own beanValidation template drop the readOnly guard?"""
    d = _pom_template_directory(root)
    if not d:
        return False
    d = d.replace("${project.basedir}/", "").replace("${basedir}/", "")
    p = (Path(d) if Path(d).is_absolute() else Path(root) / d) / "beanValidation.mustache"
    return p.is_file() and READ_ONLY_GUARD not in p.read_text(encoding="utf-8", errors="replace")


def _schema_props(schemas: dict[str, Any], name: str, depth: int = 0) -> tuple[set[str], dict[str, Any]]:
    """(required names, properties) of a schema with one level of allOf/$ref composition."""
    sch = schemas.get(name) if isinstance(schemas, dict) else None
    req: set[str] = set()
    props: dict[str, Any] = {}

    def add(s: Any, d: int) -> None:
        if not isinstance(s, dict):
            return
        req.update(str(x) for x in (s.get("required") or []) if str(x))
        if isinstance(s.get("properties"), dict):
            props.update(s["properties"])
        if d < 2:
            for part in s.get("allOf") or [] if isinstance(s.get("allOf"), list) else []:
                ref = str(part.get("$ref") or "") if isinstance(part, dict) else ""
                add(schemas.get(ref.rsplit("/", 1)[-1]) if ref else part, d + 1)
    add(sch, depth)
    return req, props


def required_read_only_facts(root: Path, bundle: dict[str, Any] | None) -> dict[str, Any]:
    """{status, cases: [{model, property, schema}], reasons}. applicable only for
    the qualified destination generator (jaxrs-spec 7.25.0) fed by a source whose
    generator annotated every required property (spring), with the guard still in
    the build's template."""
    from planner import worklist as W
    out: dict[str, Any] = {"status": "not-applicable", "cases": [], "reasons": []}
    plugin = W.generator_plugin_config(root)
    if not plugin:
        return out
    cfg = plugin.get("configuration") or {}
    if str(cfg.get("generatorName") or "") != "jaxrs-spec":
        return out
    ver = W.resolved_plugin_version(plugin, Path(root) / "pom.xml")
    if ver not in QUALIFIED_VERSIONS:
        out["status"] = "unresolved"
        out["reasons"].append("jaxrs-spec %s is not a version whose template the catalog read (%s)" % (ver, ", ".join(QUALIFIED_VERSIONS)))
        return out
    src = W.generator_plugin_config(Path(root) / W.FROZEN_INPUT)
    if str((src.get("configuration") or {}).get("generatorName") or "") != "spring":
        out["reasons"].append("the source build's generator is not spring (its required properties' constraints are unknown)")
        return out
    if template_restores_constraint(root):
        return out
    p = W._spec_path(Path(root), str(cfg.get("inputSpec") or ""))
    if p is None:
        out["status"] = "unresolved"
        out["reasons"].append("the plugin's inputSpec is not a file of this tree")
        return out
    doc, why = W._load_spec(p)
    schemas = ((doc.get("components") or {}).get("schemas") if isinstance(doc, dict) and isinstance(doc.get("components"), dict)
               else None) or (doc.get("definitions") if isinstance(doc, dict) else None) or {}
    if not isinstance(schemas, dict):
        out["status"] = "unresolved"
        out["reasons"].append(why or "the spec carries no schemas")
        return out
    opts = plugin.get("configOptions") or {}
    prefix = str(opts.get("modelNamePrefix") or cfg.get("modelNamePrefix") or "")
    suffix = str(opts.get("modelNameSuffix") or cfg.get("modelNameSuffix") or "")
    models = sorted({W._body_type_of(bundle or {}, str(e.get("id") or "")) for e in (bundle or {}).get("entry_points") or []
                     if isinstance(e, dict) and str(e.get("kind") or "") == "http"} - {""})
    for model in models:
        name = model.rsplit(".", 1)[-1]
        if prefix and name.startswith(prefix):
            name = name[len(prefix):]
        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)]
        req, props = _schema_props(schemas, name)
        for prop in sorted(req):
            ps = props.get(prop)
            if isinstance(ps, dict) and ps.get("readOnly") is True:
                out["cases"].append({"model": model, "property": prop, "schema": name})
    if out["cases"]:
        out["status"] = "applicable"
    return out


def required_read_only_items(root: Path, bundle: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """The planned obligation (gate plan), one per build: its locus is the
    template file the action creates (a build item, so the cluster also holds
    pom.xml). Discharged when the condition, re-evaluated on the candidate, no
    longer holds."""
    from planner import worklist as W
    from planner.canonical import sha256_bytes
    facts = required_read_only_facts(root, bundle)
    if facts["status"] == "unresolved":
        return [], ["required readOnly constraint UNRESOLVED: %s" % "; ".join(facts["reasons"])]
    if facts["status"] != "applicable":
        return [], []
    row = ((W._build_plugins_catalog(root).get("org.openapitools:" + W.OPENAPI_GENERATOR_ARTIFACT) or {})
           .get("generators") or {}).get("jaxrs-spec", {}).get("required_read_only") or {}
    names = ", ".join("%s.%s" % (c["model"].rsplit(".", 1)[-1], c["property"]) for c in facts["cases"][:6])
    iid = "plan:gbro:%s" % sha256_bytes(("required-read-only|" + names).encode("utf-8"))[:12]
    detail = ("%s: the spec lists %s as required and readOnly; jaxrs-spec 7.25.0 omits @NotNull there, the source's spring "
              "generator kept it, so an explicit null answers 500 instead of the source's 400 'must not be null'. %s"
              % (iid, names, " ".join(str(row.get("action") or "").split())))
    return [{"id": iid, "source": "plan", "kind": "build", "category": "mandatory", "gate": W.PLAN_GATE,
             "rule_id": W.RULE_PARITY_GENERATED_BODY, "cause": W.GENERATED_BODY_CAUSE, "path": TEMPLATE_FILE, "line": 0,
             "message": "a required readOnly request-body property lost the source's @NotNull (%s)" % names,
             "detail": detail, "message_sha256": sha256_bytes(detail.encode("utf-8")),
             "planned": {"trigger": "static (required readOnly)", "cases": facts["cases"]},
             "advice": {"first_action": " ".join(str(row.get("action") or "").split()) or detail}}], []


# --------------------------------------------------------------------------- absent single result

def absent_result_verdict(typ: dict[str, Any], row: dict[str, Any]) -> str:
    """'' or why an owed READ member answers NoResultException where the
    selected source behaviour answered null for no row."""
    beh = {str(b.get("signature") or ""): b for b in ((row.get("behaviour") or {}).get("members") or []) if isinstance(b, dict)}
    for m in typ.get("declared") or []:
        if not isinstance(m, dict):
            continue
        b = beh.get(str(m.get("signature") or ""))
        if not b or str(b.get("effect") or "") != "read" or str(b.get("kind") or "") not in ("query", "derived-query", "crud-default"):
            continue
        ret = str((m.get("type_refs") or [""])[0])
        if ret in SCALAR_RETURNS or ret.startswith(("java.util.Optional", "java.util.List", "java.util.Collection",
                                                     "java.util.Set", "java.util.stream")):
            continue
        single = [c for c in m.get("calls") or []
                  if str(c).split("(", 1)[0].rsplit(".", 1)[-1] == "getSingleResult"
                  and str(c).split("(", 1)[0].rsplit(".", 1)[0] in SINGLE_RESULT_OWNERS]
        if not single:
            continue
        caught = [str(x) for x in m.get("catches") or []]
        if "?" in caught or any(x in NO_RESULT_HANDLERS for x in caught):
            continue
        return ("%s.%s answers a missing row with NoResultException (getSingleResult) where the selected source behaviour "
                "(%s) answered null -- a 500 for the source's null path. Port it as getResultStream().findFirst().orElse(null) "
                "or catch NoResultException and return null (repository_behaviour.query_result_semantics)"
                % (str(typ.get("fqn") or "").rsplit(".", 1)[-1], m.get("signature"), b.get("source") or b.get("kind")))
    return ""


# --------------------------------------------------------------------------- transaction boundaries

def _anns(x: dict[str, Any]) -> set[str]:
    return {str(a.get("fqn") or "") for a in x.get("annotations") or [] if isinstance(a, dict)}


def _key(m: dict[str, Any]) -> tuple[str, int]:
    return str(m.get("name") or ""), len(m.get("params") or [])


def transaction_verdicts(frozen: dict[str, Any] | None, dest: dict[str, Any] | None, paths: list[str] | None = None,
                         *, rule: str = "transaction-boundaries") -> list[dict[str, Any]]:
    """Per source @Transactional site whose destination type lies in `paths`
    (all when None): ok / violates / inconclusive. A boundary is kept when the
    destination's same member or its type carries a Jakarta @Transactional; it
    is not kept on a private member (ArC never intercepts it)."""
    from planner.worklist import _unit_path, _unit_types
    if frozen is None or dest is None:
        return []
    by_fqn = {str(t.get("fqn") or ""): t for t in _unit_types(dest)}
    out: list[dict[str, Any]] = []
    for st in _unit_types(frozen):
        fqn = str(st.get("fqn") or "")
        cls = SPRING_TX in _anns(st)
        sites = [m for m in st.get("declared") or [] if isinstance(m, dict) and SPRING_TX in _anns(m)]
        if not cls and not sites:
            continue
        dt = by_fqn.get(fqn)
        dpath = _unit_path(dt) if dt else ""
        if paths is not None and dpath not in paths:
            continue
        base = {"path": dpath, "rule": rule, "state": "transaction-boundary"}
        if dt is None:
            out.append(dict(base, member="%s#*" % fqn, verdict="inconclusive",
                            detail="%s is not in the destination model: its transaction boundary cannot be judged" % fqn))
            continue
        dcls = bool(_anns(dt) & set(JAKARTA_TX))
        dm = {_key(m): m for m in dt.get("declared") or [] if isinstance(m, dict)}
        if cls:
            out.append(dict(base, member="%s#<class>" % fqn,
                            verdict="ok" if dcls else "violates",
                            detail=("%s keeps its class-level transaction boundary" % fqn) if dcls else
                            ("%s lost the class-level boundary of the source's @Transactional: put @jakarta.transaction."
                             "Transactional on the same class (objective_families.transaction-annotations)" % fqn)))
        for m in sites:
            k = _key(m)
            got = dm.get(k)
            label = "%s#%s" % (fqn, m.get("signature") or m.get("name"))
            if got is None:
                out.append(dict(base, member=label, verdict="violates",
                                detail="the source boundary %s has no destination member %s/%d: the boundary was deleted "
                                       "with it" % (label, k[0], k[1])))
            elif got.get("private") and (dcls or _anns(got) & set(JAKARTA_TX)):
                out.append(dict(base, member=label, verdict="violates",
                                detail="%s is private on the destination: @Transactional is an interceptor binding ArC never "
                                       "applies there -- make the boundary method non-private" % label))
            elif _anns(got) & set(JAKARTA_TX) or dcls:
                out.append(dict(base, member=label, verdict="ok", detail="%s keeps its transaction boundary" % label))
            else:
                out.append(dict(base, member=label, verdict="violates",
                                detail="%s lost the source's @Transactional boundary: put @jakarta.transaction.Transactional on "
                                       "the same method (never delete it; attribute mapping in objective_families."
                                       "transaction-annotations)" % label))
    return out


def unit_transaction_verdicts(root: Path, scope: dict[str, Any], dest: dict[str, Any] | None, rule: str) -> list[dict[str, Any]]:
    """assess_unit's single call site: a unit that retires Spring's
    @Transactional is also judged on the boundaries of the files it seals."""
    syms = {str(s.get("fqn") or "") for s in scope.get("symbols") or [] if isinstance(s, dict)}
    if SPRING_TX not in syms and SPRING_TX.rsplit(".", 1)[0] not in syms:
        return []
    from planner.worklist import frozen_source_model
    frozen, _why = frozen_source_model(Path(root))
    paths = [str(p) for p in scope.get("writable_paths") or []]
    return transaction_verdicts(frozen, dest, paths, rule=rule)
