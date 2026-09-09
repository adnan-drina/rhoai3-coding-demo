#!/usr/bin/env python3
"""Normalize the raw JDK-model extractor output into the admitted structural evidence.

Writes (canonical JSON):
  evidence/structure/structure.json          rhoai3.structure/v1 (sorted, source_digest stamped)
  evidence/producers/jdk-model.json          producer receipt
  evidence/entry-point-inventory.json        v1-compatible view derived from structure + catalog
  evidence/type-inventory.json               v1-compatible view (dest twins) derived from structure

`--refuse <status> --reason <text>` records a fail-closed receipt (unpinned
or failed) and exits 1 without writing structural evidence.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json, sha256_file, strip_observations, write_canonical  # noqa: E402
from planner.evidence import derive_entry_points, load_catalogs  # noqa: E402
from planner.paths import ENTRY_POINT_INVENTORY, SCHEMAS_DIR, STRUCTURE, TYPE_INVENTORY, producer_receipt  # noqa: E402
from planner.schema_lite import load_schema, validate  # noqa: E402
from planner.yamlite import load_yaml  # noqa: E402

RECEIPT_SCHEMA = "rhoai3.producer-receipt/v1"


def _sorted_type(t: dict) -> dict:
    out = dict(t)
    out["annotations"] = sorted((a for a in (t.get("annotations") or []) if isinstance(a, dict) and a.get("fqn")), key=lambda a: a["fqn"])
    for a in out["annotations"]:
        a["values"] = {k: (list(v) if isinstance(v, list) else [v]) for k, v in sorted((a.get("values") or {}).items())}
    out["supertypes"] = sorted(set(str(s) for s in (t.get("supertypes") or [])))
    out["fields"] = sorted((dict(f) for f in (t.get("fields") or [])), key=lambda f: str(f.get("name")))
    out["constructors"] = sorted((dict(c) for c in (t.get("constructors") or [])), key=lambda c: len(c.get("params") or []))
    out["methods"] = sorted((dict(m) for m in (t.get("methods") or [])), key=lambda m: str(m.get("signature") or m.get("name")))
    for m in out["methods"]:
        m["type_refs"] = sorted(set(str(x) for x in (m.get("type_refs") or [])))
        m["annotations"] = sorted((a for a in (m.get("annotations") or []) if isinstance(a, dict)), key=lambda a: a.get("fqn", ""))
    out["type_refs"] = sorted(set(str(x) for x in (t.get("type_refs") or [])))
    out["modifiers"] = sorted(set(str(x) for x in (t.get("modifiers") or [])))
    return out


def _known_fqns(catalogs: dict) -> set[str]:
    """Catalog-known FQNs a wildcard-imported simple name may resolve to."""
    out: set[str] = set()
    ep = catalogs.get("entry-points") or {}
    for key in ("method_annotations", "type_path_annotations", "method_path_annotations", "supertypes", "type_markers"):
        out |= set((ep.get(key) or {}).keys())
    out |= set(ep.get("container_markers") or [])
    cc = catalogs.get("cross-cutting") or {}
    out |= set((cc.get("annotations") or {}).keys()) | set((cc.get("supertypes") or {}).keys())
    out |= set(((catalogs.get("framework-generated") or {}).get("annotations") or {}).keys())
    out |= {
        "org.springframework.beans.factory.annotation.Autowired", "jakarta.inject.Inject", "javax.inject.Inject",
        "jakarta.annotation.Resource", "javax.annotation.Resource", "org.springframework.context.annotation.Primary",
        "jakarta.persistence.Entity", "javax.persistence.Entity", "org.springframework.stereotype.Repository",
        "org.springframework.stereotype.Service", "org.springframework.stereotype.Component",
    }
    return out


def _import_resolver(imports: list[str], known: set[str], model_types: set[str], own_package: str):
    """Mechanical resolution of an unresolved name through the CU imports.

    javac attributing without a classpath leaves an unresolved name as
    written (bare, or qualified with the current package). Both are
    unresolved when no model type has that FQN. Resolution order: explicit import; exactly one wildcard candidate
    that is a catalog-known FQN; the only wildcard package; else unchanged.
    """
    explicit = {i.rsplit(".", 1)[-1]: i for i in imports if "." in i and not i.endswith(".*")}
    wild = [i[:-2] for i in imports if i.endswith(".*")]

    def resolve(name: str) -> str:
        if not name:
            return name
        if name in model_types:
            return name
        if "." in name:
            pkg, simple = name.rsplit(".", 1)
            if pkg != own_package or not simple:
                return name
        else:
            simple = name
        if simple in explicit:
            return explicit[simple]
        cands = ["%s.%s" % (pkg, simple) for pkg in wild]
        hits = [c for c in cands if c in known]
        if len(hits) == 1:
            return hits[0]
        if len(cands) == 1:
            return cands[0]
        return name

    return resolve


def _resolve_names(t: dict, resolve) -> None:
    for a in t.get("annotations") or []:
        a["fqn"] = resolve(str(a.get("fqn") or ""))
    t["supertypes"] = sorted({resolve(s) for s in (t.get("supertypes") or [])})
    for f in t.get("fields") or []:
        f["type"] = resolve(str(f.get("type") or ""))
        for a in f.get("annotations") or []:
            a["fqn"] = resolve(str(a.get("fqn") or ""))
    for c in t.get("constructors") or []:
        for pr in c.get("params") or []:
            pr["type"] = resolve(str(pr.get("type") or ""))
        for a in c.get("annotations") or []:
            a["fqn"] = resolve(str(a.get("fqn") or ""))
    for m in t.get("methods") or []:
        for a in m.get("annotations") or []:
            a["fqn"] = resolve(str(a.get("fqn") or ""))
        for pr in m.get("params") or []:
            pr["type"] = resolve(str(pr.get("type") or ""))
            for a in pr.get("annotations") or []:
                a["fqn"] = resolve(str(a.get("fqn") or ""))


def normalize(raw: dict, source_digest: str, model_types: set[str], catalogs: dict | None = None) -> dict:
    types = []
    known = _known_fqns(catalogs or {})
    for t in raw.get("types") or []:
        if not isinstance(t, dict) or not t.get("fqn"):
            continue
        nt = _sorted_type(t)
        own_pkg = str(nt["fqn"]).rsplit(".", 1)[0] if "." in str(nt["fqn"]) else ""
        _resolve_names(nt, _import_resolver([str(i) for i in (t.get("imports") or [])], known, model_types, own_pkg))
        nt.pop("imports", None)
        nt["type_refs"] = [r for r in nt["type_refs"] if r in model_types and r != nt["fqn"]]
        types.append(nt)
    types.sort(key=lambda t: t["fqn"])
    mode = str(raw.get("mode") or (raw.get("producer") or {}).get("mode") or "partial")
    return {
        "schema": "rhoai3.structure/v1",
        "producer": {"tool": "jdk-model", "version": str((raw.get("producer") or {}).get("version") or ""), "runtime": str((raw.get("producer") or {}).get("runtime") or ""), "mode": mode},
        "source_digest": source_digest,
        "mode": mode,
        "types": types,
    }


def entry_point_inventory_v1(structure: dict, entry_points: list[dict], source_root: str) -> dict:
    rows = []
    by_sub: dict[str, int] = {}
    for ep in entry_points:
        kind = "http" if ep["kind"] == "http" else "non-http"
        sub = "spring-mvc-or-jaxrs" if ep["kind"] == "http" else ep["kind"]
        by_sub[sub] = by_sub.get(sub, 0) + 1
        rows.append({
            "kind": kind,
            "subtype": sub,
            "file": ep["path"],
            "line": 0,
            "symbol": ("%s#%s" % (ep["type"].rsplit(".", 1)[-1], ep["member"].split("(")[0])) if ep["member"] else ep["type"].rsplit(".", 1)[-1],
            "evidence": ep["evidence"],
            "http_method": ep["http_method"],
            "http_path": ep["http_path"],
            "entry_point_id": ep["id"],
            "resolution": ep["resolution"],
        })
    rows.sort(key=lambda r: (r["kind"], r["subtype"], r["file"], r["entry_point_id"]))
    java_seen = sum(1 for t in structure["types"])
    return {
        "schema": "rhoai3.entry-point-inventory/v1",
        "root": source_root,
        "execution_evidence": {"scanner": "normalize-structure.py (jdk-model)", "java_files_seen": java_seen, "inputs_digest_sha256": structure["source_digest"], "ran": True, "vacuous": False if java_seen else "zero_java_files", "provenance": "jdk-model:%s" % structure["mode"]},
        "counts": {"total": len(rows), "http": sum(1 for r in rows if r["kind"] == "http"), "non_http": sum(1 for r in rows if r["kind"] != "http"), "by_subtype": dict(sorted(by_sub.items()))},
        "entry_points": rows,
    }


def type_inventory_v1(structure: dict, entry_points: list[dict], base_pkg: str, dest_pkg: str, catalogs: dict, source_root: str) -> dict:
    types = {t["fqn"]: t for t in structure["types"]}
    gen_roots = (catalogs.get("framework-generated") or {}).get("generated_source_roots") or []
    gen_anns = set((catalogs.get("framework-generated") or {}).get("annotations") or {})
    seeds = sorted({ep["type"] for ep in entry_points})
    seed_file = {ep["type"]: ep["path"] for ep in entry_points}
    reached: dict[str, dict] = {}
    for seed in seeds:
        stack = [seed]
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in types:
                continue
            seen.add(cur)
            t = types[cur]
            path = str(t.get("path") or "")
            if not path:
                continue
            dest = path  # spring-compat path: packages are kept, the dest twin is the same path
            rec = reached.setdefault(dest, {
                "legacy_file": path,
                "dest_file": dest,
                "layer": path.rsplit("/", 2)[-2] if "/" in path else "",
                "generated": any(path.startswith(r) for r in gen_roots) or any(a.get("fqn") in gen_anns and a.get("fqn", "").endswith("Generated") for a in (t.get("annotations") or [])),
                "reached_from": [],
                "fqn": cur,
                "resolution": str(t.get("resolution") or "partial"),
            })
            sf = seed_file.get(seed, "")
            if sf and sf not in rec["reached_from"]:
                rec["reached_from"].append(sf)
            for ref in sorted(set(t.get("type_refs") or []) | set(t.get("supertypes") or [])):
                if ref in types:
                    stack.append(ref)
            if str(t.get("kind")) == "interface" or "abstract" in (t.get("modifiers") or []):
                # compat view over-approximates: every application implementation
                # of a reached abstraction is a dest twin candidate. The planner
                # resolves the real binding from probe evidence.
                for impl_fqn, impl in types.items():
                    if cur in (impl.get("supertypes") or []):
                        stack.append(impl_fqn)
    rows = [reached[k] for k in sorted(reached)]
    for r in rows:
        r["reached_from"] = sorted(r["reached_from"])
    by_layer: dict[str, int] = {}
    for r in rows:
        by_layer[r["layer"] or "_"] = by_layer.get(r["layer"] or "_", 0) + 1
    return {
        "schema": "rhoai3.type-inventory/v1",
        "root": source_root,
        "execution_evidence": {"scanner": "normalize-structure.py (jdk-model)", "entry_files_seen": len(seeds), "types_seen": len(rows), "ran": True, "vacuous": False if seeds else "no_entry_files", "provenance": "jdk-model:%s" % structure["mode"]},
        "counts": {"total": len(rows), "by_layer": dict(sorted(by_layer.items()))},
        "types": rows,
    }


def _base_and_dest(root: Path, structure: dict) -> tuple[str, str]:
    mig = load_yaml(root / "migration.yaml") if (root / "migration.yaml").is_file() else {}
    base = str(((mig or {}).get("migration") or {}).get("legacyBasePackage") or "").strip()
    if not base:
        pkgs = sorted({t["fqn"].rsplit(".", 1)[0] for t in structure["types"] if "." in t["fqn"] and str(t.get("path", "")).startswith("src/main/")})
        if pkgs:
            parts = [p.split(".") for p in pkgs]
            common = []
            for i in range(min(len(p) for p in parts)):
                if all(p[i] == parts[0][i] for p in parts):
                    common.append(parts[0][i])
                else:
                    break
            base = ".".join(common)
    dest = "com.demo"
    try:
        platforms = load_json(root / ".hermes" / "planning" / "catalogs" / "destination-platforms.json").get("platforms") or {}
        dec = load_yaml(root / "decisions.yaml") if (root / "decisions.yaml").is_file() else {}
        pid = str(((dec or {}).get("destination_platform") or {}).get("id") or "")
        if pid in platforms:
            dest = str(platforms[pid].get("destination_package_root") or dest)
    except Exception:  # noqa: BLE001 — catalogs are optional for the compat view
        pass
    return base, dest


def write_receipt(root: Path, *, status: str, version: str, sha: str | None, source_digest: str, mode: str, reasons: list[str], outputs: list[dict], runtime: str = "") -> None:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "producer": "jdk-model",
        "status": status,
        "tool": {"name": "jdk-model", "version": version or None, "pin_status": "unpinned" if status == "unpinned" else "pinned", "artifact_sha256": sha, "runtime": runtime, "implementation": "javax.lang.model + com.sun.source (JavacTask); extractor source sha256 in artifact_sha256"},
        "inputs": {"source_digest": source_digest},
        "outputs": outputs,
        "reasons": reasons,
        "mode": mode,
    }
    write_canonical(producer_receipt(root, "jdk-model"), receipt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--raw", default="")
    ap.add_argument("--tool-version", default="")
    ap.add_argument("--tool-sha256", default="")
    ap.add_argument("--runtime", default="")
    ap.add_argument("--refuse", default="", choices=["", "unpinned", "failed"])
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    freeze_path = producer_receipt(root, "freeze")
    if not freeze_path.is_file():
        print("FAIL: STRUCTURE_NO_FREEZE missing %s" % freeze_path, file=sys.stderr)
        return 1
    freeze = load_json(freeze_path)
    source_digest = str(freeze.get("source_digest") or "")
    source_root = str(freeze.get("analysis_copy") or freeze.get("inputs", {}).get("source_root") or "")
    if args.refuse:
        write_receipt(root, status=args.refuse, version=args.tool_version, sha=None, source_digest=source_digest, mode="missing", reasons=[args.reason or args.refuse], outputs=[])
        print("REFUSE: jdk-model %s — %s" % (args.refuse, args.reason), file=sys.stderr)
        return 1
    if not args.raw or not Path(args.raw).is_file():
        print("FAIL: --raw structure JSON required", file=sys.stderr)
        return 2
    raw = load_json(args.raw)
    model_types = {str(t.get("fqn")) for t in (raw.get("types") or []) if isinstance(t, dict)}
    catalogs = load_catalogs(root)
    structure = normalize(raw, source_digest, model_types, catalogs)
    if args.tool_version and not structure["producer"]["version"]:
        structure["producer"]["version"] = args.tool_version
    errors = validate(structure, load_schema(root / SCHEMAS_DIR / "structure.schema.json"))
    if errors:
        write_receipt(root, status="failed", version=args.tool_version, sha=args.tool_sha256 or None, source_digest=source_digest, mode=structure["mode"], reasons=["structure schema: " + "; ".join(errors[:5])], outputs=[])
        print("FAIL: STRUCTURE_SCHEMA %s" % "; ".join(errors[:5]), file=sys.stderr)
        return 1
    if not structure["types"]:
        write_receipt(root, status="failed", version=args.tool_version, sha=args.tool_sha256 or None, source_digest=source_digest, mode=structure["mode"], reasons=["zero types extracted"], outputs=[])
        print("FAIL: STRUCTURE_ZERO_TYPES", file=sys.stderr)
        return 1
    entry_points = derive_entry_points(structure, catalogs)
    base, dest = _base_and_dest(root, structure)
    write_canonical(root / STRUCTURE, structure)
    write_canonical(root / ENTRY_POINT_INVENTORY, entry_point_inventory_v1(structure, entry_points, source_root))
    write_canonical(root / TYPE_INVENTORY, type_inventory_v1(structure, entry_points, base, dest, catalogs, source_root))
    outputs = [{"path": str(rel), "sha256": sha256_file(root / rel)} for rel in (STRUCTURE, ENTRY_POINT_INVENTORY, TYPE_INVENTORY)]
    write_receipt(root, status="ok", version=structure["producer"]["version"], sha=args.tool_sha256 or None, source_digest=source_digest, mode=structure["mode"], reasons=[], outputs=outputs, runtime=args.runtime or structure["producer"].get("runtime", ""))
    print("OK: structure %d types mode=%s entry_points=%d → %s" % (len(structure["types"]), structure["mode"], len(entry_points), STRUCTURE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
