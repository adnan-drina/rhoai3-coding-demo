"""V26-3: the RESOLVED CONTEXT of one issued objective (rhoai3.resolved-context/v1).

One attachment per issued M3 card, written beside its brief
(verification/loop/context-<cluster>.json) and named by ONE index line in the
digest -- never injected into it. It answers the questions a worker otherwise
answers by searching the repository (v25: which implementation is selected,
is this DTO generated, which recipe, which checks now), from the producers that
already computed them:

  source       FROZEN facts: the plan's owned requirement rows
               (source_requirements.derive -- statuses, facts, consumers,
               unknowns), the evidence bundle's structural model (handler
               parameter types, source roots) and decisions.yaml's build
               profiles (decisions.build_profiles). Bound to the plan.
  destination  facts of the CURRENT product tree, each carrying the tree it
               was measured on: where every type the objective names lives
               (generated root vs src/main/java, by file location -- as
               worklist.response_path, never by name), the build's generators
               (generated_sources.generator_plugins) and the measured
               obligations on the granted paths (worklist.json, bound to its
               candidate_sha256).
  recipe       the qualified recipe of each owned requirement
               (compat-mapping migration_recipes) with its prerequisites and
               what it refuses, and the issued objective family's row.
  checks       immediate (judged by this card) and deferred (named, with the
               phase or owner they are due at) -- the node's check_plan.
  unknowns     everything the producers could not establish, by name.

Every assertion is {"value", "provenance": "<file>#<selector>", "kind"}:
kind "fact" is read from a producer's artifact; "inference" is derived by a
named contract (a naming contract, a staging rule) and says so. Nothing is
derived from a type's or file's name, and nothing missing is filled in: an
absent input is an entry in ``unknowns``.

``staleness(doc, tree)`` compares each destination fact's tree with the
current product tree; ``fresh(doc, tree)`` withdraws the ones of another tree
into ``unknowns`` (``build`` applies it, so a work list measured on an older
candidate never enters as a fact). Pure over its arguments and the files it
names under ``root``; it writes nothing.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from planner.canonical import load_json
from planner.paths import CATALOGS_DIR, DECISIONS, EVIDENCE_BUNDLE, LOOP_ISSUED, PLAN_SEMANTICS, WORKLIST

SCHEMA = "rhoai3.resolved-context/v1"
CATALOG = (CATALOGS_DIR / "compat-mapping.json").as_posix()
HANDWRITTEN_ROOT = "src/main/java"
OBLIGATIONS_SHOWN = 40
GENERATION_COMMAND = "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance"


def fact(value: Any, provenance: str, kind: str = "fact", **extra: Any) -> dict[str, Any]:
    return dict({"value": value, "provenance": provenance, "kind": kind}, **extra)


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _read(root: Path, rel: Any) -> Any:
    p = Path(root) / rel
    try:
        return load_json(p) if p.is_file() else None
    except (OSError, ValueError):
        return None


def _decisions(root: Path) -> dict[str, Any] | None:
    from planner.yamlite import YamlLiteError, load_yaml
    p = Path(root) / DECISIONS
    try:
        doc = load_yaml(p) if p.is_file() else None
    except (OSError, YamlLiteError):
        return None
    return doc if isinstance(doc, dict) else None


def _dependency(fqn: str) -> bool:
    from planner.worklist import _DEPENDENCY_PREFIXES
    return fqn.startswith(_DEPENDENCY_PREFIXES) or "." not in fqn


def build(root: Path, plan: dict[str, Any] | None, node: dict[str, Any] | None, worklist: dict[str, Any] | None, tree: str,
          *, issued: dict[str, Any] | None = None, plan_ref: str = "") -> dict[str, Any]:
    """The resolved context of `node` (an outcome-board plan node, or the
    off-board projection {"outcome_id", "requirements"}) on product tree
    `tree`. `plan` carries the full requirement rows (plan["requirements"]);
    `plan_ref` names where they were read from (default plan-semantics.json);
    `issued` is the card's issued contract (default verification/loop/issued.json)."""
    root = Path(root)
    plan, node = plan or {}, node or {}
    ref = plan_ref or PLAN_SEMANTICS.as_posix()
    oid = _s(node.get("outcome_id"))
    unknowns: list[dict[str, str]] = []

    def unknown(subject: str, why: str, provenance: str) -> None:
        unknowns.append({"subject": subject, "why": why, "provenance": provenance})

    def rp(rid: str, *parts: str) -> str:
        return "%s#requirements[%s]%s" % (ref, rid, "".join("." + p for p in parts))

    by_id = {_s(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
    reqs = []
    for rid in [str(r) for r in node.get("requirements") or []]:
        if rid in by_id:
            reqs.append(by_id[rid])
        else:
            unknown(rid, "the plan carries no row for this owned requirement: its facts are unknown", "%s#requirements" % ref)
    if not node.get("requirements"):
        unknown("requirements", "this objective owns no planned requirement: no frozen-source responsibility describes it; "
                "only its measured obligations do", "%s#nodes[%s].requirements" % (ref, oid))
    bundle = _read(root, EVIDENCE_BUNDLE)
    if not isinstance(bundle, dict):
        unknown("structural model", "the evidence bundle is missing or unreadable: handler parameter types and source roots "
                "are unknown", EVIDENCE_BUNDLE.as_posix())
        bundle = {}
    catalog = _read(root, CATALOG) or {}
    if issued is None:
        issued = _read(root, LOOP_ISSUED) or {}

    # -- the issued card ---------------------------------------------------
    allowed = sorted(str(p) for p in (issued.get("allowed_paths") or issued.get("write_set") or []))
    unit = issued.get("planned_unit") if isinstance(issued.get("planned_unit"), dict) else {}
    card = {"cluster": fact(_s(issued.get("cluster")), "%s#cluster" % LOOP_ISSUED.as_posix()),
            "allowed_paths": fact(allowed, "%s#%s" % (LOOP_ISSUED.as_posix(), "allowed_paths" if issued.get("allowed_paths") else "write_set"))}
    if unit:
        card["planned_unit"] = fact({k: unit.get(k) for k in ("basis", "paths", "owed", "bounds") if k in unit},
                                    "%s#planned_unit" % LOOP_ISSUED.as_posix())

    # -- FROZEN source facts -----------------------------------------------
    source: dict[str, Any] = {"bound": {"plan": ref, "bundle": EVIDENCE_BUNDLE.as_posix(),
                                        "source_digest": _s((bundle.get("structure") or {}).get("source_digest"))},
                              "requirements": [], "implementations": [], "interfaces": [], "signatures": [], "callers": [],
                              "parameters": [], "generator": []}
    names: list[str] = []
    profiled = False
    for r in reqs:
        rid, f = _s(r.get("id")), r.get("facts") or {}
        source["requirements"].append(fact({k: r.get(k) for k in ("id", "rule", "status", "subject", "paths")}, rp(rid, "status")))
        for u in r.get("unknowns") or []:
            unknown(rid, str(u), rp(rid, "unknowns"))
        source["callers"] += [fact(c, rp(rid, "consumers")) for c in r.get("consumers") or []]
        for key in ("repository", "fragment"):
            if _s(f.get(key)):
                source["interfaces"].append(fact({"role": key, "type": f[key]}, rp(rid, "facts", key)))
                names.append(f[key])
        if f.get("members"):
            source["signatures"].append(fact({"type": _s(f.get("fragment")), "members": list(f["members"])}, rp(rid, "facts.members")))
        profiles = f.get("profiles") if isinstance(f.get("profiles"), dict) else {}
        profiled = profiled or bool(profiles)
        for t in f.get("selected") or []:
            source["implementations"].append(fact({"type": t, "role": "selected", "profiles": profiles.get(t, [])}, rp(rid, "facts.selected")))
            names.append(t)
        beh = f.get("behaviour") if isinstance(f.get("behaviour"), dict) else {}
        for x in beh.get("not_behaviour_sources") or []:
            source["implementations"].append(fact({"type": x.get("type"), "role": "not-selected", "profiles": x.get("profiles") or [],
                                                   "path": x.get("path"), "why": x.get("why")},
                                                  rp(rid, "facts.behaviour.not_behaviour_sources")))
            names.append(_s(x.get("type")))
        for m in beh.get("members") or []:
            if isinstance(m, dict) and _s(m.get("source")):
                source["signatures"].append(fact({"member": m.get("signature"), "behaviour_source": m.get("source"),
                                                  "behaviour_kind": m.get("kind")}, rp(rid, "facts.behaviour.members")))
        names += [str(t) for t in f.get("implementations") or []]
        if _s(f.get("owed_implementation")):
            source["implementations"].append(fact({"path": f["owed_implementation"], "role": "owed"}, rp(rid, "facts.owed_implementation"),
                                                  "inference", basis="the fragment's <Fragment>Impl naming contract "
                                                                     "(source_requirements.FRAGMENT_SUFFIX)"))
        if _s(f.get("parameter_type")):
            names.append(f["parameter_type"])
        if _s(r.get("rule")).startswith("generator-configuration"):
            source["generator"].append(fact({k: f.get(k) for k in ("generator", "model_package", "plugin_version", "options") if k in f},
                                            rp(rid, "facts")))
        # the handler's parameters as the frozen structural model resolved them (never parsed from the subject's spelling)
        subject = _s(r.get("subject")).split("|", 1)[0]
        if "#" in subject and "<-" not in subject and bundle:
            typ, sig = subject.split("#", 1)
            names.append(typ)
            t = next((x for x in (bundle.get("structure") or {}).get("types") or [] if isinstance(x, dict) and x.get("fqn") == typ), None)
            m = next((x for x in (t or {}).get("methods") or [] if isinstance(x, dict) and x.get("signature") == sig), None)
            if m is None:
                unknown(subject, "the structural model has no method %s on %s" % (sig, typ), "%s#structure.types[%s]" % (EVIDENCE_BUNDLE.as_posix(), typ))
            else:
                for p in m.get("params") or []:
                    if isinstance(p, dict):
                        source["parameters"].append(fact({"handler": subject, "parameter": p.get("name"), "type": p.get("type"),
                                                          "annotations": [_s(a.get("fqn")) for a in p.get("annotations") or [] if isinstance(a, dict)]},
                                                         "%s#structure.types[%s].methods[%s].params[%s]" % (EVIDENCE_BUNDLE.as_posix(), typ, sig, p.get("name"))))
                        names.append(_s(p.get("type")))
    build_rec = bundle.get("build") if isinstance(bundle.get("build"), dict) else {}
    if build_rec:
        source["source_roots"] = fact({"handwritten": list(build_rec.get("source_roots") or []),
                                       "generated": list(build_rec.get("generated_source_roots") or [])},
                                      "%s#build.source_roots" % EVIDENCE_BUNDLE.as_posix())
    dec = _decisions(root)
    from planner.decisions import build_profiles
    bp = build_profiles(dec) if dec is not None else {}
    if bp.get("active"):
        source["active_profiles"] = fact(list(bp["active"]), "%s#build_profiles.active" % DECISIONS.as_posix(), adr=_s(bp.get("adr")))
    elif profiled:
        unknown("active build profile", "no accepted build-profile decision: which profile-gated implementation is selected is "
                "unknown, never guessed", "%s#build_profiles" % DECISIONS.as_posix())

    # -- DESTINATION facts of the current tree ------------------------------
    from generated_sources import generator_plugins
    from planner.dest_model import generated_source_dirs, generated_type_file
    dest: dict[str, Any] = {"tree": tree, "source_roots": [], "generators": [], "types": [], "owed_paths": [], "open_obligations": []}
    gen_dirs = [d.relative_to(root).as_posix() for d in generated_source_dirs(root)]
    dest["source_roots"].append(fact({"handwritten": [HANDWRITTEN_ROOT] if (root / HANDWRITTEN_ROOT).is_dir() else [],
                                      "generated": gen_dirs}, "%s#dirs" % "target/generated-sources", tree=tree))
    plugins = generator_plugins(root, dest_only=True)
    for p in plugins:
        bf = Path(_s(p.get("build_file")))
        bf_rel = bf.relative_to(root).as_posix() if bf.is_absolute() and root in bf.parents else bf.as_posix()
        dest["generators"].append(fact({"plugin": p.get("artifactId"), "inputs": list(p.get("input_specs") or []),
                                        "packages": list(p.get("packages") or []), "build_file": bf_rel},
                                       "%s#build.plugins[%s]" % (bf_rel, p.get("artifactId")), tree=tree))
    if plugins:
        dest["generators"].append(fact(GENERATION_COMMAND, dest["generators"][0]["provenance"], "inference", tree=tree,
                                       basis="the generators are plugins of this build and run-verify.sh is the loop's only "
                                             "build: it regenerates the sources from the build file on disk"))
    # (declared package, where it is declared): the destination build's generators first, then the plan's generator facts
    model_pkgs = [(str(k), g["provenance"]) for g in dest["generators"] if isinstance(g["value"], dict) for k in g["value"]["packages"]] \
        + [(_s((g["value"] or {}).get("model_package")), g["provenance"]) for g in source["generator"]]
    for fqn in sorted(set(n for n in names if n and not _dependency(n))):
        gf, gd = generated_type_file(root, fqn)
        if gf is not None:
            owners = [p for p in plugins if any(fqn.startswith(str(k) + ".") for k in p.get("packages") or [])]
            inputs = sorted({str(s) for p in owners for s in p.get("input_specs") or []})
            ann = gd is not None and gd.name == "annotations"
            dest["types"].append(fact({"fqn": fqn, "ownership": "generated", "path": gf.relative_to(root).as_posix(),
                                       "generated_root": gd.relative_to(root).as_posix() if gd is not None else "",
                                       "generator": "annotation processor" if ann else ", ".join(sorted({_s(p.get("artifactId")) for p in owners})),
                                       "inputs": inputs,
                                       "edit_owner": ("the declaration it is generated from, never this file" if ann else
                                                      ("the generator input %s or its build configuration, never this file" % ", ".join(inputs))
                                                      if inputs else "the build's generator configuration, never this file")},
                                      "%s#type[%s]" % (gf.relative_to(root).as_posix(), fqn), tree=tree))
            continue
        rel = "%s/%s.java" % (HANDWRITTEN_ROOT, fqn.replace(".", "/"))
        if (root / rel).is_file():
            dest["types"].append(fact({"fqn": fqn, "ownership": "handwritten", "path": rel}, "%s#type[%s]" % (rel, fqn), tree=tree))
            continue
        pkg, where = next(((k, w) for k, w in model_pkgs if k and fqn.startswith(k + ".")), ("", ""))
        if pkg:
            dest["types"].append(fact({"fqn": fqn, "ownership": "generated", "path": None, "package": pkg,
                                       "note": "no generated file declares it on this tree: the sources were not generated yet"},
                                      where, "inference", tree=tree,
                                      basis="its package is a generator's declared model package"))
            continue
        unknown(fqn, "no file under %s or a generated-sources root declares it on this tree (a nested, renamed or deleted "
                "type): where it lives is unknown" % HANDWRITTEN_ROOT, "tree:%s" % tree[:12])
    for f_ in source["implementations"]:
        owed = _s((f_["value"] or {}).get("path")) if (f_["value"] or {}).get("role") == "owed" else ""
        if owed:
            dest["owed_paths"].append(fact({"path": owed, "exists": (root / owed).is_file()}, owed, tree=tree))
    wl = worklist if isinstance(worklist, dict) else None
    if wl is None:
        unknown("measured obligations", "no work list was supplied: the open obligations on the granted paths are unknown",
                WORKLIST.as_posix())
    else:
        wtree = _s(wl.get("candidate_sha256"))
        rows = [i for i in wl.get("items") or [] if isinstance(i, dict) and _s(i.get("path")) in set(allowed)]
        for i in rows[:OBLIGATIONS_SHOWN]:
            dest["open_obligations"].append(fact({k: i.get(k) for k in ("id", "path", "line", "rule_id", "category") if k in i},
                                                 "%s#items[%s]" % (WORKLIST.as_posix(), i.get("id")), tree=wtree))
        if len(rows) > OBLIGATIONS_SHOWN:
            dest["open_obligations_total"] = len(rows)

    # -- recipes ---------------------------------------------------------------
    from planner.source_requirements import RECIPE_RULES, recipes_of
    recipes = recipes_of(catalog)
    recipe: list[dict[str, Any]] = []
    for r in reqs:
        rid, f = _s(r.get("id")), r.get("facts") or {}
        rec_id = _s((r.get("recipe") or {}).get("id"))
        if not rec_id:
            if _s(r.get("rule")).split("/", 1)[0] in RECIPE_RULES:
                unknown(rid, "no qualified recipe translates this requirement", rp(rid, "recipe"))
            continue
        row = recipes.get(rec_id)
        if row is None:
            unknown(rid, "recipe %s is not in the pinned catalog" % rec_id, "%s#migration_recipes" % CATALOG)
            continue
        recipe.append(fact({"requirement": rid, "id": rec_id, "version": _s(row.get("version")),
                            "implementation": _s((row.get("implementation") or {}).get("kind")),
                            "architecture": (row.get("implementation") or {}).get("architecture"),
                            "prerequisites": sorted(set(str(d) for d in r.get("dependencies") or []))
                            + [str(x) for x in f.get("precedes") or []]
                            + ([row["precedence"]] if row.get("precedence") else []),
                            "unsupported": [str(x) for x in row.get("refuse") or []]
                            + ([f["capability_gap"]] if _s(f.get("capability_gap")) else [])},
                           "%s#migration_recipes.%s" % (CATALOG, rec_id)))
    fam = _s((issued.get("objective") or {}).get("family")) if isinstance(issued.get("objective"), dict) else ""
    if fam:
        row = ((catalog.get("objective_families") or {}).get("families") or {}).get(fam)
        if isinstance(row, dict):
            recipe.append(fact(dict({"family": fam}, **{k: row[k] for k in ("source_semantics", "action", "unsupported") if row.get(k)}),
                               "%s#objective_families.families.%s" % (CATALOG, fam)))
        else:
            unknown(fam, "the issued objective family has no catalog row", "%s#objective_families.families" % CATALOG)

    # -- checks: now and later --------------------------------------------------
    checks: dict[str, list[dict[str, Any]]] = {"immediate": [], "deferred": []}
    rows = [r for r in node.get("check_plan") or [] if isinstance(r, dict)]
    if rows:
        cp = "%s#nodes[%s].check_plan" % (ref, oid)
        for r in rows:
            if r.get("stage") == "later":
                checks["deferred"].append(fact({"check": r.get("check"), "requirement": r.get("requirement"),
                                                "due": list(r.get("due") or ["M4"])}, cp))
            else:
                checks["immediate"].append(fact({"check": r.get("check"), "requirement": r.get("requirement"),
                                                 "prerequisites": list(r.get("prerequisites") or [])}, cp))
    elif reqs:
        from planner.compatibility_objectives import LATER_CHECK_PREFIXES
        for r in reqs:
            rid = _s(r.get("id"))
            for c in r.get("acceptance") or []:
                later = str(c).startswith(LATER_CHECK_PREFIXES)
                checks["deferred" if later else "immediate"].append(
                    fact(dict({"check": c, "requirement": rid}, **({"due": ["M4"]} if later else {})), rp(rid, "acceptance"),
                         "inference", basis="no check_plan on this node: staged by compatibility_objectives.LATER_CHECK_PREFIXES"))
    else:
        unknown("checks", "the plan stages no requirement check for this objective: it is judged by the measured work list "
                "alone", "%s#nodes[%s].check_plan" % (ref, oid))

    doc = {"schema": SCHEMA, "outcome": oid, "card": card, "source": source, "destination": dest, "recipe": recipe,
           "checks": checks, "unknowns": unknowns}
    return fresh(doc, tree)


def _dest_facts(doc: dict[str, Any]):
    for key, rows in sorted((doc.get("destination") or {}).items()):
        if isinstance(rows, list):
            for i, f in enumerate(rows):
                if isinstance(f, dict) and "tree" in f:
                    yield key, i, f


def staleness(doc: dict[str, Any], tree: str) -> dict[str, Any]:
    """Whether the destination facts of `doc` are facts of product tree `tree`.
    {"state": "current"|"stale", "bound_tree", "current_tree", "rejected": [...]}:
    stale when the document was bound to another tree or any fact was measured
    on one (an empty or missing tree binding is never current)."""
    bound = _s((doc.get("destination") or {}).get("tree"))
    rejected = [{"section": k, "provenance": f.get("provenance"), "tree": _s(f.get("tree"))}
                for k, _i, f in _dest_facts(doc) if not _s(f.get("tree")) or _s(f.get("tree")) != tree]
    return {"state": "current" if bound and bound == tree and not rejected else "stale",
            "bound_tree": bound, "current_tree": tree, "rejected": rejected}


def fresh(doc: dict[str, Any], tree: str) -> dict[str, Any]:
    """A copy of `doc` whose destination holds only facts of `tree`: every other
    destination fact is withdrawn into ``unknowns`` naming both trees. A
    document bound to another tree loses all of them: refresh it (brief.py
    rebuilds the attachment on the tree it serves)."""
    out = copy.deepcopy(doc)
    dest = out.setdefault("destination", {})
    bound = _s(dest.get("tree"))
    drop = {(k, i) for k, i, f in _dest_facts(out) if bound != tree or _s(f.get("tree")) != tree}
    for k, i, f in list(_dest_facts(out)):
        if (k, i) in drop:
            out.setdefault("unknowns", []).append({
                "subject": "%s %s" % (k, f.get("provenance")),
                "why": "measured on tree %s, the current product tree is %s: a fact of another tree is not a fact of this one "
                       "(re-measure with run-verify.sh, or rebuild with brief.py)" % (_s(f.get("tree"))[:12] or "(unbound)", tree[:12]),
                "provenance": _s(f.get("provenance"))})
    for k in {k for k, _i in drop}:
        dest[k] = [f for i, f in enumerate(dest[k]) if (k, i) not in drop]
    if bound != tree:
        dest["tree"] = tree
        dest["withdrawn_from_tree"] = bound
    return out


def counts(doc: dict[str, Any]) -> dict[str, int]:
    src = doc.get("source") or {}
    return {"source": sum(len(v) for v in src.values() if isinstance(v, list)) + sum(1 for v in src.values() if isinstance(v, dict) and "value" in v),
            "destination": sum(1 for _ in _dest_facts(doc)), "recipes": len(doc.get("recipe") or []),
            "immediate": len((doc.get("checks") or {}).get("immediate") or []),
            "deferred": len((doc.get("checks") or {}).get("deferred") or []), "unknowns": len(doc.get("unknowns") or [])}


def text(doc: dict[str, Any]) -> str:
    """The same document, indented with sorted keys and one trailing newline: the .txt beside the canonical
    .json, readable by line (v32: the canonical form is ONE line of ~33K characters, of which read_file
    previews ~2K). It parses back to exactly the document; it carries no authority and nothing hashes it."""
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def key_lines(rendered: str) -> list[tuple[str, int, int, int]]:
    """(top-level key, first line, last line, characters) of each top-level key of a document rendered by
    ``text`` -- 1-based line numbers, for read_file offset/limit. JSON strings never span lines, so a line
    indented by exactly two spaces and opening with a quote starts a top-level key."""
    lines = rendered.splitlines()
    starts = [(i, json.JSONDecoder().raw_decode(ln[2:])[0]) for i, ln in enumerate(lines) if ln.startswith('  "')]
    out = []
    for n, (i, key) in enumerate(starts):
        end = (starts[n + 1][0] if n + 1 < len(starts) else len(lines) - 1) - 1
        out.append((key, i + 1, end + 1, sum(len(x) + 1 for x in lines[i:end + 1])))
    return out


def index_line(doc: dict[str, Any], rel: str, text_rel: str = "") -> str:
    """The ONE digest line naming the attachment (the context itself stays on disk). With ``text_rel``, the
    line also names the by-line copy and its top-level keys with their line ranges and sizes."""
    c = counts(doc)
    line = ("RESOLVED CONTEXT: %s -- %d frozen-source fact(s), %d destination fact(s) of tree %s, %d recipe(s), %d check(s) now, "
            "%d deferred, %d named unknown(s). Read it (provenance on every fact) for the active profile and selected "
            "implementation, generated vs handwritten types, the recipe and its checks BEFORE searching the repository."
            % (rel, c["source"], c["destination"], _s((doc.get("destination") or {}).get("tree"))[:12], c["recipes"],
               c["immediate"], c["deferred"], c["unknowns"]))
    if text_rel:
        keys = key_lines(text(doc))
        line += (" The .json is one line: read %s by line instead (read_file with offset/limit). Its top-level keys "
                 "(the only keys): %s." % (text_rel, ", ".join("%s (lines %d-%d, %d chars)" % k for k in keys)))
    return line
