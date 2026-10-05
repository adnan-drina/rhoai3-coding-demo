"""Assemble `evidence-bundle.json` from M1 producer receipts (SAD §5.1, §6).

Inputs (all produced mechanically by M1 skills):

- ``evidence/producers/<name>.json``  producer receipts
- ``evidence/frozen/source-manifest.json``  frozen source manifest
- ``evidence/structure/structure.json``  JDK-model claims (mandatory)
- ``evidence/structure/bytecode.json``  jQAssistant claims (optional)
- ``evidence/structure/context-probe.json``  Spring context probe
- ``evidence/mta-findings.json``  normalized MTA findings
- ``.hermes/planning/catalogs/*.json``  versioned catalogs
- ``migration.yaml``  MTA analysis inputs (targets, canary id, base package)
- ``decisions.yaml``  declared environments and binding overrides

The bundle records facts and their provenance. It decides nothing.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes, sha256_file, sort_unique, strip_observations
from planner.paths import (
    CATALOGS_DIR,
    MIGRATION,
    MTA_FINDINGS,
    PRODUCER_NAMES,
    SOURCE_MANIFEST,
    STRUCTURE,
    producer_receipt,
)
from planner.yamlite import load_yaml

SCHEMA = "rhoai3.evidence-bundle/v1"
INJECT_ANNOTATIONS = frozenset(
    {
        "org.springframework.beans.factory.annotation.Autowired",
        "jakarta.inject.Inject",
        "javax.inject.Inject",
        "jakarta.annotation.Resource",
        "javax.annotation.Resource",
        "org.springframework.beans.factory.annotation.Qualifier",
    }
)
PRIMARY_ANNOTATIONS = frozenset({"org.springframework.context.annotation.Primary"})
ENTITY_ANNOTATIONS = frozenset({"jakarta.persistence.Entity", "javax.persistence.Entity"})
REPOSITORY_SUPERTYPES = (
    "org.springframework.data.repository.Repository",
    "org.springframework.data.repository.CrudRepository",
    "org.springframework.data.jpa.repository.JpaRepository",
    "org.springframework.data.repository.PagingAndSortingRepository",
)
REPOSITORY_ANNOTATIONS = frozenset({"org.springframework.stereotype.Repository"})
FILE_URI_RE = re.compile(r"^file://")


class EvidenceError(ValueError):
    pass


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def _load_receipt(root: Path, name: str) -> dict[str, Any] | None:
    path = producer_receipt(root, name)
    if not path.is_file():
        return None
    doc = load_json(path)
    if not isinstance(doc, dict):
        raise EvidenceError("%s: receipt must be an object" % path)
    return doc


def load_catalogs(root: Path) -> dict[str, Any]:
    base = Path(root) / CATALOGS_DIR
    out: dict[str, Any] = {}
    for path in sorted(base.glob("*.json")):
        out[path.stem] = load_json(path)
    for name in ("entry-points", "cross-cutting", "framework-generated", "destination-platforms", "compat-mapping"):
        if name not in out:
            raise EvidenceError("missing catalog %s" % (base / (name + ".json")))
    return out


def catalog_digests(root: Path) -> dict[str, str]:
    base = Path(root) / CATALOGS_DIR
    return {p.name: sha256_file(p) for p in sorted(base.glob("*.json"))}


def load_migration(root: Path) -> dict[str, Any]:
    path = Path(root) / MIGRATION
    doc = load_yaml(path) if path.is_file() else {}
    doc = doc if isinstance(doc, dict) else {}
    mig = doc.get("migration") if isinstance(doc.get("migration"), dict) else {}
    ana = doc.get("analysis") if isinstance(doc.get("analysis"), dict) else {}
    return {
        "legacy_base_package": str(mig.get("legacyBasePackage") or mig.get("legacy_base_package") or "").strip(),
        "targets": [str(t) for t in (ana.get("targets") or [])],
        "custom_rules": str(ana.get("custom_rules") or "").strip(),
        "canary_rule_id": str(ana.get("canary_rule_id") or "").strip(),
        "mode": str(ana.get("mode") or "containerless").strip(),
    }


# ---------------------------------------------------------------------------
# source classification
# ---------------------------------------------------------------------------


def classify_source_path(path: str, catalogs: dict[str, Any]) -> str:
    p = path.replace("\\", "/")
    gen_roots = (catalogs.get("framework-generated") or {}).get("generated_source_roots") or []
    if any(p.startswith(r) for r in gen_roots):
        return "generated"
    if p.startswith("src/test/"):
        return "test"
    if p.startswith("src/main/java/") and p.endswith(".java"):
        return "production"
    if p.startswith("src/main/resources/") or p.startswith("src/main/webapp/"):
        return "resource"
    build = (catalogs.get("cross-cutting") or {}).get("build_files") or []
    if any(p == b or (b.endswith("/") and p.startswith(b)) for b in build):
        return "build"
    integ = (catalogs.get("cross-cutting") or {}).get("integration_paths") or []
    if any(p == b or (b.endswith("/") and p.startswith(b)) for b in integ):
        return "integration"
    if p.startswith("src/main/") and p.endswith(".java"):
        return "production"
    return "other"


# ---------------------------------------------------------------------------
# entry points from structure + catalog
# ---------------------------------------------------------------------------


def _ann_map(annotations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ann in annotations or []:
        if isinstance(ann, dict) and ann.get("fqn"):
            out[str(ann["fqn"])] = ann.get("values") if isinstance(ann.get("values"), dict) else {}
    return out


def _first_path(values: dict[str, Any], attrs: list[str]) -> str:
    for attr in attrs:
        raw = values.get(attr)
        if isinstance(raw, list) and raw:
            return str(raw[0])
        if isinstance(raw, str) and raw:
            return raw
    return ""


def _join_path(prefix: str, rel: str) -> str:
    def norm(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        if not s.startswith("/"):
            s = "/" + s
        return s.rstrip("/") or "/"

    p, r = norm(prefix), norm(rel)
    if not r or r == "/":
        return p or "/"
    if not p or p == "/":
        return r
    return (p.rstrip("/") + r).rstrip("/") or "/"


def derive_entry_points(structure: dict[str, Any], catalogs: dict[str, Any]) -> list[dict[str, Any]]:
    cat = catalogs["entry-points"]
    method_anns = cat.get("method_annotations") or {}
    type_paths = cat.get("type_path_annotations") or {}
    method_paths = cat.get("method_path_annotations") or {}
    supertypes = cat.get("supertypes") or {}
    type_markers = cat.get("type_markers") or {}
    out: list[dict[str, Any]] = []
    for t in structure.get("types") or []:
        fqn = str(t.get("fqn"))
        path = str(t.get("path") or "")
        resolution = str(t.get("resolution") or "partial")
        tanns = _ann_map(t.get("annotations") or [])
        prefix = ""
        for ann_fqn, spec in type_paths.items():
            if ann_fqn in tanns:
                prefix = _first_path(tanns[ann_fqn], spec.get("path_attributes") or [])
                break
        for ann_fqn, spec in type_markers.items():
            if ann_fqn in tanns:
                out.append(
                    {
                        "id": "ep:%s:%s" % (fqn, spec["kind"]),
                        "kind": spec["kind"],
                        "type": fqn,
                        "member": "",
                        "path": path,
                        "evidence": "type-annotation:%s" % ann_fqn,
                        "resolution": resolution,
                        "http_method": "",
                        "http_path": "",
                        "channel": "",
                    }
                )
        for st in t.get("supertypes") or []:
            spec = supertypes.get(str(st))
            if spec:
                out.append(
                    {
                        "id": "ep:%s#%s" % (fqn, spec.get("member", "")),
                        "kind": spec["kind"],
                        "type": fqn,
                        "member": str(spec.get("member", "")),
                        "path": path,
                        "evidence": "supertype:%s" % st,
                        "resolution": resolution,
                        "http_method": "",
                        "http_path": "",
                        "channel": "",
                    }
                )
        for m in t.get("methods") or []:
            manns = _ann_map(m.get("annotations") or [])
            sig = str(m.get("signature") or m.get("name") or "")
            mpath = ""
            for ann_fqn, spec in method_paths.items():
                if ann_fqn in manns:
                    mpath = _first_path(manns[ann_fqn], spec.get("path_attributes") or [])
            for ann_fqn, spec in method_anns.items():
                if ann_fqn not in manns:
                    continue
                values = manns[ann_fqn]
                kind = spec["kind"]
                http_method = str(spec.get("http_method") or "")
                http_path = ""
                channel = ""
                if kind == "http":
                    rel = _first_path(values, spec.get("path_attributes") or []) or mpath
                    http_path = _join_path(prefix, rel)
                    if not http_method and spec.get("method_attribute"):
                        raw = values.get(spec["method_attribute"])
                        if isinstance(raw, list) and raw:
                            http_method = str(raw[0]).split(".")[-1].upper()
                        elif isinstance(raw, str) and raw:
                            http_method = raw.split(".")[-1].upper()
                elif kind == "messaging":
                    channel = _first_path(values, spec.get("channel_attributes") or [])
                out.append(
                    {
                        "id": "ep:%s#%s:%s" % (fqn, sig, kind),
                        "kind": kind,
                        "type": fqn,
                        "member": sig,
                        "path": path,
                        "evidence": "method-annotation:%s" % ann_fqn,
                        "resolution": str(m.get("resolution") or resolution),
                        "http_method": http_method,
                        "http_path": http_path,
                        "channel": channel,
                    }
                )
    dedup: dict[str, dict[str, Any]] = {}
    for ep in out:
        dedup.setdefault(ep["id"], ep)
    return [dedup[k] for k in sorted(dedup)]


# ---------------------------------------------------------------------------
# injection candidates and bindings
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MTA obligations
# ---------------------------------------------------------------------------


def _locus_path(uri: str, analysis_root: str) -> str:
    p = FILE_URI_RE.sub("", str(uri or "")).replace("\\", "/")
    root = (analysis_root or "").replace("\\", "/").rstrip("/")
    if root and p.startswith(root + "/"):
        return p[len(root) + 1 :]
    for marker in ("/src/main/", "/src/test/", "/pom.xml"):
        idx = p.find(marker)
        if idx >= 0:
            return p[idx + 1 :]
    return p.lstrip("/")


def _incident_identity(rule_id: str, path: str, line: int, variables: dict[str, Any], message: str) -> str:
    return sha256_bytes(canonical_bytes({"rule": rule_id, "path": path, "line": line, "variables": variables, "message": message}))[:16]


def derive_obligations(findings: dict[str, Any] | None, mta_receipt: dict[str, Any] | None, canary_id: str) -> tuple[list[dict[str, Any]], bool, int]:
    """Every MTA incident as an obligation, plus canary state and raw count.

    Nothing is dropped: an incident without a file locus is kept at path
    ``GLOBAL``; incidents sharing a file and line but differing in
    variables or message stay distinct; byte-identical repeats collapse
    into one record with ``multiplicity``. Ids are content-addressed
    (rule, locus, variables, message) so adding an earlier incident never
    renumbers a later one. ``sum(multiplicity) == raw incident count`` is
    part of the ledger conservation equation.
    """
    if not findings:
        return [], False, 0
    violations = findings.get("violations") if isinstance(findings.get("violations"), dict) else {}
    insights = findings.get("insights") if isinstance(findings.get("insights"), dict) else {}
    analysis_root = str(((mta_receipt or {}).get("input") or {}).get("analysis_root") or "")
    by_id: dict[str, dict[str, Any]] = {}
    # MTA 8.x files zero-effort rules (the canary) under insights: proof of the
    # effective ruleset, never an obligation
    canary_fired = bool(canary_id) and isinstance(insights.get(canary_id), dict) and bool(insights[canary_id].get("incidents"))
    raw_count = 0
    for rid in sorted(violations):
        v = violations[rid]
        if not isinstance(v, dict):
            continue
        rule_id = str(v.get("ruleID") or rid)
        incidents = v.get("incidents") if isinstance(v.get("incidents"), list) else []
        if canary_id and rule_id == canary_id:
            canary_fired = canary_fired or len(incidents) > 0
            continue
        category = str(v.get("category") or "potential").lower()
        if category not in ("mandatory", "optional", "potential"):
            category = "potential"
        effort = v.get("effort")
        for inc in incidents:
            if not isinstance(inc, dict):
                inc = {"message": str(inc)}
            raw_count += 1
            path = _locus_path(str(inc.get("uri") or ""), analysis_root)
            if not path or path == "(absent-from-tool)":
                path = "GLOBAL"
            try:
                line = int(inc.get("lineNumber") or 0)
            except (TypeError, ValueError):
                line = 0
            variables = inc.get("variables") if isinstance(inc.get("variables"), dict) else {}
            message = str(inc.get("message") or "")
            ident = _incident_identity(rule_id, path, line, variables, message)
            oid = "obl:%s:%s" % (rule_id, ident)
            row = by_id.get(oid)
            if row is None:
                by_id[oid] = {
                    "id": oid,
                    "rule_id": rule_id,
                    "category": category,
                    "effort": effort if isinstance(effort, int) else 0,
                    "locus": {"path": path, "line": line},
                    "variables_sha256": sha256_bytes(canonical_bytes(variables)),
                    "message_sha256": sha256_bytes(message.encode("utf-8")),
                    "multiplicity": 1,
                }
            else:
                row["multiplicity"] += 1
    out = [by_id[k] for k in sorted(by_id)]
    return out, canary_fired, raw_count


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


# Receipt keys that describe the machine, not the evidence. The bundle must
# not carry environment-dependent content (SAD v3 §5): two workspaces that
# froze the same source must seal the same bundle.
ENV_KEYS = frozenset({"analysis_copy", "analysis_root", "binary_path", "binary_realpath", "install_prefix", "binary_bytes", "argv", "custom_rules_dir", "provider_artifacts", "runtime", "source_root"})


def _strip_env(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_env(v) for k, v in obj.items() if k not in ENV_KEYS}
    if isinstance(obj, list):
        return [_strip_env(v) for v in obj]
    return obj


def _receipt_summary(rec: dict[str, Any] | None) -> dict[str, Any]:
    if rec is None:
        return {"status": "missing"}
    return _strip_env(strip_observations(rec))


def assemble(root: Path, *, decisions: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(root)
    catalogs = load_catalogs(root)
    migration = load_migration(root)
    receipts = {name: _load_receipt(root, name) for name in PRODUCER_NAMES}

    manifest_path = root / SOURCE_MANIFEST
    if not manifest_path.is_file():
        raise EvidenceError("missing %s (freeze-migration-input did not run)" % SOURCE_MANIFEST)
    manifest = load_json(manifest_path)
    files = []
    for row in manifest.get("files") or []:
        if not isinstance(row, dict) or not row.get("path"):
            continue
        files.append({"path": str(row["path"]), "sha256": str(row.get("sha256") or ""), "class": classify_source_path(str(row["path"]), catalogs)})
    files.sort(key=lambda r: r["path"])
    source = {
        "digest": str(manifest.get("digest") or ""),
        "root_kind": str(manifest.get("root_kind") or "frozen-legacy"),
        "file_count": len(files),
        "files": files,
    }

    structure_path = root / STRUCTURE
    structure = load_json(structure_path) if structure_path.is_file() else None
    model_rec = receipts.get("jdk-model")
    structure_ok = bool(structure) and model_rec is not None and str(model_rec.get("status")) == "ok"
    if structure and str(structure.get("source_digest") or "") and str(structure.get("source_digest")) != source["digest"]:
        structure_ok = False

    findings_path = root / MTA_FINDINGS
    mta_rec = receipts.get("mta")
    findings = load_json(findings_path) if (findings_path.is_file() and mta_rec is not None and str(mta_rec.get("status")) == "ok") else None

    types_sorted: list[dict[str, Any]] = []
    entry_points: list[dict[str, Any]] = []
    if structure:
        for t in sorted((structure.get("types") or []), key=lambda t: str(t.get("fqn"))):
            types_sorted.append(strip_observations(t))
        norm_structure = dict(structure)
        norm_structure["types"] = types_sorted
        entry_points = derive_entry_points(norm_structure, catalogs)

    obligations, canary_fired, raw_incidents = derive_obligations(findings, mta_rec, migration["canary_rule_id"])

    build_rec = receipts.get("build") or {}
    build = {
        "attempted": build_rec.get("status") not in (None, "skipped"),
        "outcome": str(build_rec.get("outcome") or ("success" if build_rec.get("status") == "ok" else ("failure" if build_rec else "not-attempted"))),
        "classpath_available": bool(build_rec.get("classpath_available")),
        "source_roots": sort_unique(build_rec.get("source_roots") or []),
        "generated_source_roots": sort_unique(build_rec.get("generated_source_roots") or []),
        "toolchain": build_rec.get("toolchain") if isinstance(build_rec.get("toolchain"), dict) else {},
        "warmup": build_rec.get("warmup") if isinstance(build_rec.get("warmup"), dict) else {},
    }

    mta_tool = (mta_rec or {}).get("tool") if isinstance((mta_rec or {}).get("tool"), dict) else {}
    mta = {
        "status": str((mta_rec or {}).get("status") or "missing"),
        "admissible": bool(mta_tool.get("admissible")) if mta_tool else False,
        "product_pin": str(mta_tool.get("product_version_pin") or ""),
        "provenance": str(mta_tool.get("provenance") or ""),
        "targets": sort_unique((mta_rec or {}).get("targets") or []),
        "custom_rules_digest": str((mta_rec or {}).get("custom_rules_digest") or ""),
        "bundled_rules_digest": str((mta_rec or {}).get("bundled_rules_digest") or ""),
        "input_digest": str(((mta_rec or {}).get("input") or {}).get("digest") or ""),
        "output_digest": str((mta_rec or {}).get("output_digest") or ""),
        "exit_status": (mta_rec or {}).get("exit_status"),
        "canary": {"rule_id": migration["canary_rule_id"], "fired": canary_fired},
        "incidents": {"raw": raw_incidents, "normalized": sum(int(o.get("multiplicity") or 1) for o in obligations), "records": len(obligations)},
    }

    bundle = {
        "schema": SCHEMA,
        "source": source,
        "migration": migration,
        "catalogs": catalog_digests(root),
        "producers": {name: _receipt_summary(rec) for name, rec in receipts.items() if name != "bootstrap"},
        "build": build,
        "structure": {
            "available": structure_ok,
            "mode": str((structure or {}).get("mode") or ((structure or {}).get("producer") or {}).get("mode") or ("partial" if structure else "missing")),
            "source_digest": str((structure or {}).get("source_digest") or ""),
            "type_count": len(types_sorted),
            "types": types_sorted,
        },
        "entry_points": entry_points,
        "obligations": obligations,
        "mta": mta,
    }
    bundle["observations"] = {
        "raw_input_sha256": {
            "source_manifest": sha256_file(manifest_path),
            "structure": sha256_file(structure_path) if structure_path.is_file() else "",
            "mta_findings": sha256_file(findings_path) if findings_path.is_file() else "",
        }
    }
    return bundle


def bundle_digest(bundle: dict[str, Any]) -> str:
    return digest(bundle)
