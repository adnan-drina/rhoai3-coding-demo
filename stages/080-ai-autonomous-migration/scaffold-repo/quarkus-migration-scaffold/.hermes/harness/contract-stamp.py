#!/usr/bin/env python3
"""O-STAMP-AUTO / O-STAMP-GATE — derive migration.yaml contract from legacy Spring Boot tree.

Deterministic scans of a legacy repo (default /projects/legacy). Used at outer-loop
entry before M1 analyze; idempotent when the stamped contract already matches.

Subcommands:
  stamp  [--legacy DIR] [--yaml FILE] [--write] [--json]
  gate   [--legacy DIR] [--yaml FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

TARGET_PACKAGE = "com.demo"
ANALYSIS_MODE = "source-only"
ANALYSIS_TARGETS = ["quarkus", "jakarta-ee9", "cloud-readiness", "openjdk17"]
BARE_ARRAY = "_array"
UNDECIDED = "UNDECIDED"


@dataclass
class EndpointCandidate:
    path: str
    method_name: str
    return_type: str
    collection: str
    item_type: str
    service_type: str
    score: int
    controller_file: str


@dataclass
class StampResult:
    legacy_package: str = UNDECIDED
    target_package: str = TARGET_PACKAGE
    acceptance: dict[str, Any] = field(default_factory=dict)
    preserve: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    target_contract: dict[str, bool] = field(default_factory=dict)
    contract_status: str = UNDECIDED
    warnings: list[str] = field(default_factory=list)
    alternatives: list[dict[str, str]] = field(default_factory=list)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _java_files(root: Path) -> list[Path]:
    base = root / "src" / "main" / "java"
    if not base.is_dir():
        return []
    return sorted(base.rglob("*.java"))


def _package_from_file(path: Path, text: str) -> str | None:
    m = re.search(r"^\s*package\s+([\w.]+)\s*;", text, re.M)
    return m.group(1) if m else None


def derive_legacy_package(root: Path) -> str:
    """Package of @SpringBootApplication, else longest common prefix of src/main/java."""
    app_pkg: str | None = None
    packages: list[str] = []
    for jf in _java_files(root):
        text = _read_text(jf)
        pkg = _package_from_file(jf, text)
        if pkg:
            packages.append(pkg)
        if re.search(r"@SpringBootApplication\b", text):
            if pkg:
                app_pkg = pkg
    if app_pkg:
        return app_pkg
    if not packages:
        return UNDECIDED
    parts_list = [p.split(".") for p in packages]
    common: list[str] = []
    for i in range(min(len(p) for p in parts_list)):
        seg = parts_list[0][i]
        if all(p[i] == seg for p in parts_list):
            common.append(seg)
        else:
            break
    return ".".join(common) if common else UNDECIDED


def _load_properties(root: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    for rel in (
        "src/main/resources/application.properties",
        "src/main/resources/application.yml",
    ):
        p = root / rel
        if not p.is_file():
            continue
        text = _read_text(p)
        if rel.endswith(".properties"):
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if not line or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                props[k.strip()] = v.strip()
        else:
            m = re.search(
                r"context-path:\s*['\"]?([^'\"\n]+)",
                text,
                re.I,
            )
            if m:
                props.setdefault("server.servlet.context-path", m.group(1).strip())
    return props


def _context_path(props: dict[str, str]) -> str:
    for key in (
        "server.servlet.context-path",
        "server.context-path",
    ):
        v = props.get(key, "").strip()
        if v:
            return v if v.startswith("/") else f"/{v}"
    return ""


def _needs_database(root: Path) -> bool:
    pom = root / "pom.xml"
    gradle = root / "build.gradle"
    text = ""
    if pom.is_file():
        text += _read_text(pom)
    if gradle.is_file():
        text += _read_text(gradle)
    if re.search(r"spring-boot-starter-data-jpa|spring-boot-starter-jdbc", text):
        return True
    props = _load_properties(root)
    if any("datasource" in k.lower() for k in props):
        return True
    for jf in _java_files(root):
        t = _read_text(jf)
        if re.search(r"@Entity\b|javax\.persistence|jakarta\.persistence", t):
            return True
    return False


def _derive_preserve(root: Path, props: dict[str, str]) -> list[str]:
    found: list[str] = []
    for k in props:
        if re.search(r"\.security\.enable", k, re.I):
            found.append(k)
    for key in ("server.servlet.context-path", "server.context-path"):
        if key in props and key not in found:
            found.append(key)
    # Env-style tokens referenced in properties (${VAR})
    for jf in (root / "src" / "main" / "resources").rglob("*") if (root / "src" / "main" / "resources").is_dir() else []:
        if jf.is_file():
            for m in re.finditer(r"\$\{([A-Z][A-Z0-9_]*)\}", _read_text(jf)):
                tok = m.group(1)
                if tok not in found:
                    found.append(tok)
    return sorted(dict.fromkeys(found))


def _strip_generics(s: str) -> str:
    s = s.strip()
    s = re.sub(r"<[^>]+>", "", s)
    return s.split(".")[-1].strip()


def _unwrap_return_type(ret: str) -> str:
    """Strip ResponseEntity<...> wrapper (common in Spring REST controllers)."""
    ret = ret.strip()
    m = re.match(r"ResponseEntity\s*<\s*(.+)\s*>\s*$", ret)
    return m.group(1).strip() if m else ret


def _parse_collection_from_return(ret: str) -> tuple[str, str]:
    """Returns (collection_key, item_type)."""
    ret = _unwrap_return_type(ret.strip())
    m = re.match(r"(?:java\.util\.)?(?:List|Collection|Set)<\s*([\w.]+)\s*>", ret)
    if m:
        return BARE_ARRAY, _strip_generics(m.group(1))
    simple = _strip_generics(ret)
    return simple, simple


def _mapping_path_from_args(ann_args: str) -> str:
    """Extract path from @GetMapping/@RequestMapping argument list."""
    m = re.search(r"(?:value|path)\s*=\s*[\"']([^\"']*)[\"']", ann_args)
    if m:
        return m.group(1)
    m = re.search(r"^[\"']([^\"']*)[\"']", ann_args.strip())
    if m:
        return m.group(1)
    return ""


def _find_dto_collection(root: Path, dto_type: str) -> tuple[str, str] | None:
    simple = _strip_generics(dto_type)
    for jf in _java_files(root):
        text = _read_text(jf)
        if not re.search(rf"\bclass\s+{re.escape(simple)}\b", text):
            continue
        fields = re.findall(
            r"(?:List|Collection|Set)<\s*([\w.]+)\s*>\s+(\w+)\s*;",
            text,
        )
        if len(fields) == 1:
            item, fname = fields[0]
            return fname, _strip_generics(item)
    return None


def _combine_paths(base: str, mapping: str) -> str:
    parts = []
    for p in (base, mapping):
        if not p:
            continue
        p = p.strip()
        if not p.startswith("/"):
            p = f"/{p}"
        parts.append(p.rstrip("/"))
    out = "".join(parts) if parts else "/"
    return re.sub(r"/+", "/", out) or "/"


def _extract_service_type(class_text: str) -> str:
    for m in re.finditer(
        r"(?:private|protected)\s+(?:final\s+)?([\w.]*Service)\s+\w+\s*;",
        class_text,
    ):
        return _strip_generics(m.group(1))
    m = re.search(
        r"@Autowired\s+(?:private\s+)?(?:final\s+)?([\w.]*Service)\s+\w+",
        class_text,
    )
    if m:
        return _strip_generics(m.group(1))
    return ""


def _scan_endpoints(root: Path, ctx: str) -> list[EndpointCandidate]:
    candidates: list[EndpointCandidate] = []
    class_path = ""
    for jf in _java_files(root):
        text = _read_text(jf)
        if not re.search(r"@RestController|@Controller", text):
            continue
        # Class-level path only (must precede `public class`).
        cm = re.search(
            r"@RequestMapping\s*\(([^)]*)\)\s*public\s+class\b",
            text,
        )
        class_path = _mapping_path_from_args(cm.group(1)) if cm else ""

        svc = _extract_service_type(text)
        # Method-level only: annotation indented (avoids class @RequestMapping
        # consuming the next public method via finditer non-overlap).
        for m in re.finditer(
            r"(?m)^[ \t]+@(GetMapping|RequestMapping)\s*\(([^)]*)\)"
            r"[\s\S]{0,400}?public\s+(?!class\b)([\w<>,\s\.]+)\s+(\w+)\s*\(",
            text,
        ):
            kind, ann_args, ret, method_name = (
                m.group(1),
                m.group(2),
                m.group(3).strip(),
                m.group(4),
            )
            if kind == "RequestMapping" and "RequestMethod.GET" not in ann_args:
                continue
            subpath = _mapping_path_from_args(ann_args)
            if "{" in subpath or "{" in class_path:
                continue
            full = _combine_paths(ctx, _combine_paths(class_path, subpath))
            collection, item_type = _parse_collection_from_return(ret)
            if collection != BARE_ARRAY:
                wrap = _find_dto_collection(root, _unwrap_return_type(ret))
                if wrap:
                    collection, item_type = wrap
                elif collection == item_type:
                    # scalar/DTO GET (e.g. getVet by id) — not acceptance surface
                    continue
            score = 100
            if collection == BARE_ARRAY:
                score += 50
            score -= len(full)
            if "acceptance" in full:
                score += 30
            # Prefer enumeration-style getters (getAll*/findAll*) over shorter
            # resource names when path length ties (petclinic pets vs vets).
            if re.match(r"^(?:get|find)All[A-Z]", method_name):
                score += 25
            candidates.append(
                EndpointCandidate(
                    path=full,
                    method_name=method_name,
                    return_type=ret,
                    collection=collection,
                    item_type=item_type,
                    service_type=svc,
                    score=score,
                    controller_file=str(jf),
                )
            )
    candidates.sort(key=lambda c: (-c.score, c.path))
    return candidates


def _derive_endpoint_env(root: Path) -> str | None:
    """First ${ENV} from legacy config that looks like a REST client endpoint.

    Migration-general: only stamp acceptance.endpointEnv when the legacy tree
    actually references an env var (e.g. cart catalog URL placeholder).
    Specimens without a remote REST client omit the field entirely (R-93 P2).
    """
    found: list[str] = []
    resources = root / "src" / "main" / "resources"
    paths: list[Path] = []
    if resources.is_dir():
        paths.extend(sorted(resources.glob("application*.properties")))
        paths.extend(sorted(resources.glob("application*.yml")))
        paths.extend(sorted(resources.glob("application*.yaml")))
    for jf in _java_files(root):
        paths.append(jf)
    pat = re.compile(
        r"\$\{([A-Z][A-Z0-9_]*(?:ENDPOINT|URL|URI|_HOST))(?::[^}]*)?\}"
    )
    for path in paths:
        text = _read_text(path)
        for m in pat.finditer(text):
            name = m.group(1)
            if name not in found:
                found.append(name)
    return found[0] if found else None


def _id_fields(root: Path, item_type: str) -> list[str]:
    simple = _strip_generics(item_type)
    for jf in _java_files(root):
        text = _read_text(jf)
        if not re.search(rf"\b(?:class|record)\s+{re.escape(simple)}\b", text):
            continue
        if re.search(r"@Id\b|\bprivate\s+\w+\s+id\s*;", text):
            fields = ["id"]
            if re.search(r"\bitemId\b", text):
                fields = ["itemId", "id"]
            return fields
    return ["id"]


def _has_valid_constraints(root: Path) -> bool:
    for jf in _java_files(root):
        t = _read_text(jf)
        if re.search(r"@Valid\b|@NotNull\b|@Min\b|@Max\b|@Size\b", t):
            return True
    return False


def _has_controller_advice(root: Path) -> bool:
    for jf in _java_files(root):
        t = _read_text(jf)
        if re.search(r"@ControllerAdvice\b|@RestControllerAdvice\b", t):
            return True
    return False


def _has_cacheable(root: Path) -> bool:
    for jf in _java_files(root):
        if re.search(r"@Cacheable\b", _read_text(jf)):
            return True
    return False


def _mutating_get_handlers(root: Path) -> bool:
    for jf in _java_files(root):
        text = _read_text(jf)
        if not re.search(r"@RestController|@Controller", text):
            continue
        for m in re.finditer(r"@GetMapping[^)]*\)[^{]*\{", text, re.S):
            block = text[m.end() : m.end() + 2000]
            if re.search(
                r"\.(?:save|delete|remove|put|add|clear|persist)\s*\(",
                block,
                re.I,
            ):
                return True
    return False


def _derived_aggregate_computation(root: Path) -> bool:
    for jf in _java_files(root):
        t = _read_text(jf)
        if re.search(
            r"\b(?:total|sum|subtotal|promo|shipping|derive|normalize)\w*\s*=",
            t,
            re.I,
        ) and re.search(r"\.stream\s*\(|for\s*\(", t):
            return True
    return False


def _thread_safe_state_needed(root: Path) -> bool:
    java_root = root / "src" / "main" / "java"
    if not java_root.is_dir():
        return False
    harness = Path(__file__).resolve().parent / "wiring-check.py"
    if not harness.is_file():
        return False
    try:
        proc = subprocess.run(
            [sys.executable, str(harness), str(java_root)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode != 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def derive_stamp(root: Path, prefer_path: str | None = None) -> StampResult:
    res = StampResult()
    res.target_package = TARGET_PACKAGE
    res.forbidden = []
    res.analysis = {"mode": ANALYSIS_MODE, "targets": list(ANALYSIS_TARGETS)}

    res.legacy_package = derive_legacy_package(root)
    props = _load_properties(root)
    ctx = _context_path(props)
    res.preserve = _derive_preserve(root, props)

    candidates = _scan_endpoints(root, ctx)
    if not candidates:
        res.contract_status = UNDECIDED
        res.acceptance = {"path": UNDECIDED, "collection": UNDECIDED}
        res.warnings.append("no collection-returning GET candidate — contract.status UNDECIDED")
        return res

    top = candidates[0]
    if prefer_path and prefer_path != UNDECIDED:
        for c in candidates:
            if c.path == prefer_path:
                top = c
                res.warnings.append(
                    f"kept existing acceptance.path among candidates: {prefer_path}"
                )
                break
    if len(candidates) > 1 and not (
        prefer_path and top.path == prefer_path
    ):
        res.warnings.append(
            f"multiple acceptance candidates ({len(candidates)}); stamped top: {top.path}"
        )
        for c in candidates[1:4]:
            res.alternatives.append(
                {"path": c.path, "method": c.method_name, "score": str(c.score)}
            )

    acc: dict[str, Any] = {
        "path": top.path,
        "collection": top.collection,
        "getter": top.method_name,
        "service": top.service_type or UNDECIDED,
        "itemType": top.item_type,
        "needsDatabase": _needs_database(root),
    }
    # Derive endpointEnv from legacy config (${FOO_ENDPOINT} / ${FOO_URL}).
    # Never hardcode a specimen env name (R-93 P2) — ALLOWED: derived-only.
    endpoint_env = _derive_endpoint_env(root)
    if endpoint_env:
        acc["endpointEnv"] = endpoint_env
    acc["idFields"] = _id_fields(root, top.item_type)
    res.acceptance = acc
    res.contract_status = "decided"

    res.target_contract = {
        "validateInput": _has_valid_constraints(root),
        "mapErrors": _has_controller_advice(root),
        "getIdempotent": not _mutating_get_handlers(root),
        "threadSafeState": _thread_safe_state_needed(root),
        "cacheRefreshGuard": _has_cacheable(root),
        "normalizeBeforeDerive": _derived_aggregate_computation(root),
    }
    return res


def _load_yaml_minimal(text: str) -> dict:
    """Parse migration.yaml-shaped docs without PyYAML (macOS CLT python).

    Supports one-level nested maps and scalar lists used by stamp/gate.
    Not a general YAML parser — enough for O-STAMP-GATE honesty.
    """
    doc: dict[str, Any] = {}
    cur_map: dict[str, Any] | None = None
    cur_list: list[Any] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- "):
            if cur_list is not None:
                cur_list.append(line[2:].strip().strip("'\""))
            continue
        if indent == 0 and line.endswith(":") and line.count(":") == 1:
            key = line[:-1].strip()
            # Peek whether children are list items or a map
            doc[key] = {}
            cur_map = doc[key]
            cur_list = None
            continue
        if indent == 0 and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                doc[key] = [] if not inner else [p.strip().strip("'\"") for p in inner.split(",")]
            elif val in ("true", "false"):
                doc[key] = val == "true"
            elif val == "":
                doc[key] = []
                cur_list = doc[key]
                cur_map = None
            else:
                doc[key] = val.strip("'\"")
            cur_map = None
            continue
        if cur_map is not None and indent >= 2 and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                cur_map[key] = [] if not inner else [p.strip().strip("'\"") for p in inner.split(",")]
            elif val in ("true", "false"):
                cur_map[key] = val == "true"
            elif val == "":
                cur_map[key] = []
                cur_list = cur_map[key]
            else:
                cur_map[key] = val.strip("'\"")
            continue
        if indent == 0:
            cur_map = None
            cur_list = None
    # Top-level keys that became {} but only ever got "- " children need list form.
    # Re-scan preserve/forbidden style: if key maps to {} and file has "- " under it.
    for key in list(doc.keys()):
        if doc[key] == {}:
            # Check if section used list items
            in_section = False
            items: list[str] = []
            for raw in text.splitlines():
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                indent = len(raw) - len(raw.lstrip(" "))
                line = raw.strip()
                if indent == 0:
                    in_section = line == f"{key}:" or line.startswith(f"{key}:")
                    if in_section and line != f"{key}:":
                        in_section = False
                    continue
                if in_section and line.startswith("- "):
                    items.append(line[2:].strip().strip("'\""))
            if items:
                doc[key] = items
    return doc


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = _read_text(path)
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _load_yaml_minimal(text)


def _stamp_to_doc(existing: dict, stamp: StampResult) -> dict:
    doc = dict(existing) if existing else {}
    mig = dict(doc.get("migration") or {})
    mig["legacyPackage"] = stamp.legacy_package
    mig["targetPackage"] = stamp.target_package
    doc["migration"] = mig
    doc["acceptance"] = dict(stamp.acceptance)
    doc["preserve"] = list(stamp.preserve)
    doc["forbidden"] = list(stamp.forbidden)
    doc["analysis"] = dict(stamp.analysis)
    doc["targetContract"] = {k: bool(v) for k, v in stamp.target_contract.items()}
    doc["contract"] = {"status": stamp.contract_status}
    if stamp.alternatives:
        doc["contract"]["acceptanceAlternatives"] = stamp.alternatives
    return doc


def _normalize_compare_doc(doc: dict) -> dict:
    """Subset used for idempotent compare."""
    out: dict[str, Any] = {}
    mig = doc.get("migration") or {}
    out["legacyPackage"] = mig.get("legacyPackage")
    out["targetPackage"] = mig.get("targetPackage")
    out["acceptance"] = doc.get("acceptance") or {}
    out["preserve"] = sorted(doc.get("preserve") or [])
    out["forbidden"] = doc.get("forbidden") or []
    out["analysis"] = doc.get("analysis") or {}
    out["targetContract"] = doc.get("targetContract") or {}
    out["contract"] = doc.get("contract") or {}
    return out


def apply_stamp(yaml_path: Path, stamp: StampResult, write: bool) -> bool:
    """Return True if migration.yaml would change / did change."""
    existing = _load_yaml(yaml_path)
    # Never clobber a decided human/harness stamp with UNDECIDED (dogfood safety).
    if stamp.contract_status == UNDECIDED:
        prev_path = str((existing.get("acceptance") or {}).get("path") or "")
        if prev_path and prev_path != UNDECIDED:
            print(
                "WARN: derive UNDECIDED — refusing to overwrite decided stamp",
                file=sys.stderr,
            )
            return False
    new_doc = _stamp_to_doc(existing, stamp)
    if _normalize_compare_doc(existing) == _normalize_compare_doc(new_doc):
        return False
    if not write:
        return True
    if yaml is not None:
        text = yaml.dump(new_doc, default_flow_style=False, sort_keys=False, allow_unicode=True)
    else:
        # Preserve full merged doc (legacyRepoUrl, provisionedBy, …) without PyYAML.
        text = _dump_yaml_minimal(new_doc)
    yaml_path.write_text(text, encoding="utf-8")
    return True


def _dump_yaml_minimal(doc: dict[str, Any]) -> str:
    """Serialize migration.yaml-shaped dicts without PyYAML."""

    def fmt_scalar(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(str(x) for x in v) + "]"
        return str(v)

    lines: list[str] = []
    # Stable section order, then any extras.
    order = [
        "migration",
        "acceptance",
        "analysis",
        "targetContract",
        "preserve",
        "forbidden",
        "contract",
    ]
    keys = [k for k in order if k in doc] + [k for k in doc.keys() if k not in order]
    for key in keys:
        val = doc[key]
        if isinstance(val, dict):
            lines.append(f"{key}:")
            for k, v in val.items():
                if isinstance(v, list) and v and not isinstance(v[0], (dict, list)):
                    if key == "contract" and k == "acceptanceAlternatives":
                        lines.append(f"  {k}:")
                        for item in v:
                            if isinstance(item, dict):
                                lines.append(f"    - path: {item.get('path', '')}")
                                for ik, iv in item.items():
                                    if ik != "path":
                                        lines.append(f"      {ik}: {iv}")
                            else:
                                lines.append(f"    - {item}")
                    else:
                        lines.append(f"  {k}: {fmt_scalar(v)}")
                elif isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for ik, iv in v.items():
                        lines.append(f"    {ik}: {fmt_scalar(iv)}")
                else:
                    lines.append(f"  {k}: {fmt_scalar(v)}")
        elif isinstance(val, list):
            lines.append(f"{key}:")
            if not val:
                # empty list as []
                lines[-1] = f"{key}: []"
            else:
                for item in val:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {fmt_scalar(val)}")
    return "\n".join(lines) + "\n"


def run_gate(root: Path, yaml_path: Path) -> int:
    doc = _load_yaml(yaml_path)
    errors: list[str] = []
    mig = doc.get("migration") or {}
    legacy_pkg = str(mig.get("legacyPackage") or "")
    if not legacy_pkg or legacy_pkg == UNDECIDED:
        errors.append(f"legacyPackage missing or {UNDECIDED}")
    else:
        rel = Path("src/main/java") / Path(*legacy_pkg.split("."))
        if not (root / rel).is_dir() and not any(
            legacy_pkg in _read_text(jf) for jf in _java_files(root)[:50]
        ):
            # at least one java file under package path or package declaration
            pkg_ok = False
            for jf in _java_files(root):
                pkg = _package_from_file(jf, _read_text(jf))
                if pkg and (pkg == legacy_pkg or pkg.startswith(legacy_pkg + ".")):
                    pkg_ok = True
                    break
            if not pkg_ok:
                errors.append(f"legacyPackage {legacy_pkg!r} not found under legacy tree")

    contract = doc.get("contract") or {}
    if str(contract.get("status") or "") == UNDECIDED:
        errors.append(f"contract.status is {UNDECIDED}")

    acc = doc.get("acceptance") or {}
    path = str(acc.get("path") or "")
    if path == UNDECIDED or not path:
        errors.append("acceptance.path missing or UNDECIDED")
    else:
        leaf = path.rstrip("/").split("/")[-1]
        found_leaf = False
        for jf in _java_files(root):
            t = _read_text(jf)
            if leaf in t and re.search(r"@(?:Get|Request)Mapping", t):
                found_leaf = True
                break
        if not found_leaf:
            errors.append(f"acceptance path leaf {leaf!r} not found in legacy controllers")

    def walk_undecided(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk_undecided(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk_undecided(v, f"{prefix}[{i}]")
        elif str(obj) == UNDECIDED:
            errors.append(f"{prefix or 'yaml'} has UNDECIDED sentinel")

    walk_undecided(doc)

    if errors:
        for e in errors:
            print(f"O-STAMP-GATE: {e}", file=sys.stderr)
        return 1
    print("O-STAMP-GATE: OK")
    return 0


def cmd_stamp(args: argparse.Namespace) -> int:
    root = Path(args.legacy).resolve()
    yaml_path = Path(args.yaml).resolve()
    if not root.is_dir():
        print(f"contract-stamp: legacy root missing: {root}", file=sys.stderr)
        return 1
    existing = _load_yaml(yaml_path) if yaml_path.is_file() else {}
    prefer = str((existing.get("acceptance") or {}).get("path") or "") or None
    if prefer == UNDECIDED:
        prefer = None
    stamp = derive_stamp(root, prefer_path=prefer)
    for w in stamp.warnings:
        print(f"WARN: {w}", file=sys.stderr)
    changed = apply_stamp(yaml_path, stamp, write=args.write)
    if args.json:
        print(json.dumps(_stamp_to_doc(_load_yaml(yaml_path) if yaml_path.is_file() else {}, stamp), indent=2))
    elif args.write:
        print("contract-stamp: wrote migration.yaml" if changed else "contract-stamp: already current (no-op)")
    else:
        print("contract-stamp: would change migration.yaml" if changed else "contract-stamp: no change")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    return run_gate(Path(args.legacy).resolve(), Path(args.yaml).resolve())


def main() -> int:
    p = argparse.ArgumentParser(description="O-STAMP-AUTO contract derivation")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("stamp", help="derive and optionally write migration.yaml")
    ps.add_argument("--legacy", default=os.environ.get("LEGACY_ROOT", "/projects/legacy"))
    ps.add_argument("--yaml", default="migration.yaml")
    ps.add_argument("--write", action="store_true")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_stamp)

    pg = sub.add_parser("gate", help="O-STAMP-GATE verifier")
    pg.add_argument("--legacy", default=os.environ.get("LEGACY_ROOT", "/projects/legacy"))
    pg.add_argument("--yaml", default="migration.yaml")
    pg.set_defaults(func=cmd_gate)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
