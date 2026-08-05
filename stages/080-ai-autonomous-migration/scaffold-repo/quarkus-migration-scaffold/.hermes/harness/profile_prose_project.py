#!/usr/bin/env python3
"""ADR-37 — per-section prose input projection (checklist, not recall).

A §§1–6 packet must contain the facts that section asserts over — not
pointers to where they live. If the harness can derive it, the model must
never read it (F-prose-no-discovery).

Sources are existing harness machinery: model.json, render_dependency_order_md,
profile_anchors, migration.yaml, findings. Specimen-agnostic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent

_SURFACE_TOKENS = (
    "@RestController",
    "@Controller",
    "@RequestMapping",
    "@GetMapping",
    "@PostMapping",
    "@PutMapping",
    "@DeleteMapping",
    "@PatchMapping",
    "@Path",
    "@Entity",
    "@Repository",
    "@Table",
    "@Service",
    "@PreAuthorize",
    "@Cacheable",
)
# Generic config-key tokens only — never a specimen app prefix (O-NOSPECIMEN).
# App-specific prefixes are appended at project time from migration.yaml
# legacyPackage / targetPackage leaf (see _config_key_re).
_CONFIG_KEY_BASE = (
    r"(?i)(datasource|jpa|hibernate|security|server\.port|"
    r"spring\.(datasource|jpa|security))"
)
# Never project credential-ish keys even as names alone is OK; values are forbidden.
_SECRET_KEY_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)"
)


def _package_leaf(fqn: str) -> str:
    """Last segment of a Java package FQN — safe for config-key prefix match."""
    leaf = (fqn or "").strip().rstrip(".").split(".")[-1]
    if leaf and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", leaf):
        return leaf
    return ""


def _config_key_re(root: Path) -> re.Pattern[str]:
    """Match generic + migration.yaml package-leaf prefixes (no specimen literals)."""
    leaves: list[str] = []
    yml = root / "migration.yaml"
    if yml.is_file():
        try:
            text = yml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for key in ("legacyPackage", "targetPackage"):
            m = re.search(rf"(?m)^\s*{key}:\s*['\"]?([A-Za-z0-9_.]+)['\"]?", text)
            if m:
                leaf = _package_leaf(m.group(1))
                if leaf and leaf not in leaves:
                    leaves.append(leaf)
    if not leaves:
        return re.compile(_CONFIG_KEY_BASE)
    # _CONFIG_KEY_BASE is (?i)(a|b|c) — splice package-leaf prefixes into the group.
    inner = _CONFIG_KEY_BASE[len("(?i)(") : -1]
    parts = [inner] + [re.escape(x) + r"\." for x in leaves]
    return re.compile(r"(?i)(" + "|".join(parts) + ")")


def _load_model(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(HERE))
    from model import load  # type: ignore

    mp = root / "migration" / "model.json"
    if not mp.is_file():
        return {"units": [], "findings": [], "sccs": [], "order": []}
    return load(root)


def _java_units(model: dict[str, Any]) -> list[dict[str, Any]]:
    return [u for u in (model.get("units") or []) if u.get("kind") == "java"]


def _cite_token(path: str, line: int = 1) -> str:
    """Emit a profile-rubric CITE-shaped path:line (O-PROFPROSECITE)."""
    p = (path or "").replace("\\", "/").strip()
    if not p:
        return ""
    ln = max(1, int(line or 1))
    return f"{p}:{ln}"


def _first_anchor_cite(anchors: list[dict[str, Any]], fallback_path: str) -> str:
    for a in anchors:
        p = str(a.get("path") or fallback_path or "").replace("\\", "/")
        if not p.startswith("src/"):
            continue
        return _cite_token(p, int(a.get("line") or 1))
    if (fallback_path or "").replace("\\", "/").startswith("src/"):
        return _cite_token(fallback_path, 1)
    return ""


def _project_s1(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Purpose & domain — entity units + annotation hints."""
    sys.path.insert(0, str(HERE))
    from profile_anchors import anchors_for_unit, resolve_legacy_root  # type: ignore

    lr = resolve_legacy_root(root, legacy)
    lines = [
        "===== PROJECTED FACTS §1 (Purpose & domain) =====",
        "Compose prose from these facts only. Do NOT open the legacy tree.",
        "O-PROFPROSECITE: copy ≥1 REQUIRED CITE string into the body verbatim.",
        "",
        "Java profile-units (fqn · path:line · fan-in · sample anchors):",
    ]
    cites: list[str] = []
    units = sorted(_java_units(model), key=lambda u: u.get("key") or "")
    for u in units[:40]:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        path = u.get("legacy_path") or "?"
        fi = u.get("fan_in", 0)
        anchors = anchors_for_unit(root, u, legacy_root=lr)
        cite = _first_anchor_cite(anchors, path)
        if cite and cite not in cites:
            cites.append(cite)
        ann = [
            a.get("token")
            for a in anchors
            if str(a.get("kind") or "") == "annotation"
            or str(a.get("token") or "").startswith("@")
        ][:4]
        ann_s = (", ".join(str(x) for x in ann)) if ann else "-"
        cite_s = cite or path
        lines.append(f"- {fqn} | {cite_s} | fan-in={fi} | anchors={ann_s}")
    if len(units) > 40:
        lines.append(f"… +{len(units) - 40} more units omitted")
    lines.append("")
    lines.append("## REQUIRED CITE (copy ≥1 verbatim into body)")
    for c in cites[:12]:
        lines.append(f"- {c}")
    if not cites:
        lines.append("- (no src/ paths in model — cite migration/dependency-order.md:1)")
    return "\n".join(lines)


def _project_s2(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Components & relationships — condensed dependency graph."""
    sys.path.insert(0, str(HERE))
    from model import render_dependency_order_md  # type: ignore
    from profile_anchors import anchors_for_unit, resolve_legacy_root  # type: ignore

    lr = resolve_legacy_root(root, legacy)
    dep = render_dependency_order_md(model)
    # Cap edges: list depends_on for highest fan-in units
    units = _java_units(model)
    by_fqn = {
        (u.get("legacy_fqn") or u.get("key") or ""): u for u in units
    }
    top = sorted(units, key=lambda u: (-int(u.get("fan_in") or 0), u.get("key") or ""))[
        :12
    ]
    edge_lines = ["", "Top depends_on edges (high fan-in units · endpoint path:line):"]
    cites: list[str] = []
    for u in top:
        deps = list(u.get("depends_on") or [])[:8]
        if not deps:
            continue
        fqn = u.get("legacy_fqn") or u.get("key")
        path = u.get("legacy_path") or ""
        anchors = anchors_for_unit(root, u, legacy_root=lr)
        cite = _first_anchor_cite(anchors, path)
        if cite and cite not in cites:
            cites.append(cite)
        # Endpoint cites for first few deps
        dep_cites = []
        for d in deps[:4]:
            du = by_fqn.get(d)
            if not du:
                continue
            dc = _first_anchor_cite(
                anchors_for_unit(root, du, legacy_root=lr),
                du.get("legacy_path") or "",
            )
            if dc:
                dep_cites.append(dc)
                if dc not in cites:
                    cites.append(dc)
        edge_lines.append(
            f"- {fqn} ({cite or path}) → {', '.join(deps)}"
            + (f" [endpoints: {', '.join(dep_cites)}]" if dep_cites else "")
        )
    edge_lines.append(f"(edge rows shown for {len(top)} units; sample deps capped)")
    edge_lines.append("")
    edge_lines.append("## REQUIRED CITE (copy ≥1 verbatim into body)")
    edge_lines.append("- migration/dependency-order.md:1")
    for c in cites[:10]:
        edge_lines.append(f"- {c}")
    # Prefer full dep md but keep packet bounded
    if len(dep) > 12000:
        dep = dep[:12000] + "\n… [truncated]\n"
    return (
        "===== PROJECTED FACTS §2 (Components & relationships) =====\n"
        "Compose prose from this graph only. Do NOT open the legacy tree "
        "or re-read dependency-order.md.\n"
        "O-PROFPROSECITE: copy ≥1 REQUIRED CITE string into the body verbatim.\n\n"
        + dep
        + "\n".join(edge_lines)
    )


def _project_s3(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Integration surfaces — annotation anchors + config key slice."""
    sys.path.insert(0, str(HERE))
    from profile_anchors import anchors_for_unit, resolve_legacy_root  # type: ignore

    lr = resolve_legacy_root(root, legacy)
    by_kind: dict[str, list[str]] = {
        "http": [],
        "persistence": [],
        "security": [],
        "other": [],
    }
    for u in _java_units(model):
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        path = u.get("legacy_path") or "?"
        anchors = anchors_for_unit(root, u, legacy_root=lr)
        tokens = [str(a.get("token") or "") for a in anchors]
        hit = [t for t in tokens if any(s in t for s in _SURFACE_TOKENS)]
        if not hit:
            # also match simple name heuristics
            simple = fqn.rsplit(".", 1)[-1]
            if simple.endswith("RestController") or simple.endswith("Controller"):
                hit = ["@RestController?"]
            elif simple.endswith("Repository") or "Repository" in simple:
                hit = ["@Repository?"]
            elif simple.endswith("Config") and "Security" in simple:
                hit = ["security-config"]
            else:
                continue
        bucket = "other"
        joined = " ".join(hit)
        if any(
            x in joined
            for x in (
                "@RestController",
                "@Controller",
                "@RequestMapping",
                "@GetMapping",
                "@Path",
                "RestController",
            )
        ):
            bucket = "http"
        elif any(
            x in joined for x in ("@Entity", "@Repository", "@Table", "Repository")
        ):
            bucket = "persistence"
        elif any(x in joined for x in ("@PreAuthorize", "Security", "security-config")):
            bucket = "security"
        by_kind[bucket].append(f"{fqn} | {path} | {', '.join(hit[:6])}")

    lines = [
        "===== PROJECTED FACTS §3 (Integration surfaces) =====",
        "Compose prose from these surfaces + config keys. Do NOT open the legacy tree.",
        "",
    ]
    for kind in ("http", "persistence", "security", "other"):
        rows = by_kind[kind]
        lines.append(f"## {kind} ({len(rows)})")
        for r in rows[:30]:
            lines.append(f"- {r}")
        if len(rows) > 30:
            lines.append(f"… +{len(rows) - 30} more")
        lines.append("")

    # Config / properties slice (mechanical — not LLM discovery)
    lines.append("## config keys (application*.properties)")
    props_root = lr / "src" / "main" / "resources"
    if not props_root.is_dir():
        props_root = lr
    found_props = 0
    for prop in sorted(props_root.rglob("application*.properties")):
        if "target" in prop.parts or "build" in prop.parts:
            continue
        try:
            body = prop.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(prop.relative_to(lr)) if lr in prop.parents or prop == lr else prop.name
        keys: list[str] = []
        for line in body.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key = s.split("=", 1)[0].strip()
            if not key or not _config_key_re(root).search(key):
                continue
            # W4-503 blocker 1: project KEY ONLY — never RHS (passwords on specimen).
            if _SECRET_KEY_RE.search(key):
                keys.append(f"{key}=<redacted>")
            else:
                keys.append(key)
        if keys:
            found_props += 1
            lines.append(f"- file: {rel}")
            for k in keys[:20]:
                lines.append(f"    {k}")
    if found_props == 0:
        lines.append("- (no application*.properties keys matched datasource/jpa/security)")

    # findings-inventory rows that look integration-related (first lines)
    inv = root / "migration" / "findings-inventory.md"
    if inv.is_file():
        lines.append("")
        lines.append("## findings-inventory excerpt (integration-relevant lines)")
        try:
            inv_lines = inv.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            inv_lines = []
        picked = [
            ln
            for ln in inv_lines
            if re.search(r"(?i)rest|jpa|jdbc|security|servlet|spring", ln)
        ][:40]
        lines.extend(picked or ["- (no matching inventory lines)"])
    return "\n".join(lines)


def _project_s4(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Behavioral contract sources — tests + targetContract flags."""
    lines = [
        "===== PROJECTED FACTS §4 (Behavioral contract sources) =====",
        "Compose from these facts. Do NOT open the legacy tree.",
        "",
        "## migration.yaml targetContract / preserve",
    ]
    yml = root / "migration.yaml"
    if yml.is_file():
        try:
            text = yml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        # keep compact: targetContract + preserve blocks
        keep = False
        buf = []
        for ln in text.splitlines():
            if re.match(r"^(targetContract|preserve)\s*:", ln):
                keep = True
            elif keep and re.match(r"^[A-Za-z]", ln):
                keep = False
            if keep:
                buf.append(ln)
        lines.extend(buf[:80] or ["- (no targetContract/preserve block)"])
    else:
        lines.append("- migration.yaml missing")

    lines.append("")
    lines.append("## test / contract-adjacent units")
    for u in model.get("units") or []:
        path = (u.get("legacy_path") or "").replace("\\", "/")
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        kind = u.get("kind") or "?"
        if (
            "/test/" in path
            or path.endswith("Test.java")
            or "IT.java" in path
            or kind == "test"
            or fqn.endswith("Test")
        ):
            lines.append(f"- {fqn} | {path} | kind={kind}")
    # Controllers / services as contract carriers
    lines.append("")
    lines.append("## service/controller units (contract carriers)")
    for u in _java_units(model):
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        simple = fqn.rsplit(".", 1)[-1]
        if simple.endswith(("Service", "ServiceImpl", "RestController", "Controller")):
            lines.append(f"- {fqn} | {u.get('legacy_path')}")
    return "\n".join(lines)


def _project_s5(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Modernization surface — findings + unit edges."""
    findings = list(model.get("findings") or [])
    by_rule: Counter[str] = Counter()
    for f in findings:
        rule = str(f.get("rule") or f.get("id") or f.get("title") or "?")
        by_rule[rule] += 1
    lines = [
        "===== PROJECTED FACTS §5 (Modernization surface) =====",
        "Compose from these findings. Do NOT invent incidents or open the legacy tree.",
        "",
        f"findings_n={len(findings)}",
        "## counts by rule",
    ]
    for rule, n in by_rule.most_common(40):
        lines.append(f"- {n}× {rule}")
    lines.append("")
    lines.append("## unit → finding edges")
    edge_n = 0
    for u in _java_units(model):
        fids = list(u.get("findings") or [])
        if not fids:
            continue
        fqn = u.get("legacy_fqn") or u.get("key")
        lines.append(f"- {fqn}: {', '.join(str(x) for x in fids[:12])}")
        edge_n += len(fids)
        if edge_n > 120:
            lines.append("… [truncated]")
            break
    # recipe-log head if present
    recipe = root / "migration" / "recipe-log.md"
    if recipe.is_file():
        lines.append("")
        lines.append("## recipe-log.md excerpt")
        try:
            lines.extend(recipe.read_text(encoding="utf-8", errors="replace").splitlines()[:40])
        except OSError:
            pass
    return "\n".join(lines)


def _project_s6(root: Path, model: dict[str, Any], legacy: str) -> str:
    """Domain boundaries — packages + condensation."""
    sys.path.insert(0, str(HERE))
    from profile_anchors import anchors_for_unit, resolve_legacy_root  # type: ignore

    lr = resolve_legacy_root(root, legacy)
    pkg_hist: Counter[str] = Counter()
    pkg_rep: dict[str, dict[str, Any]] = {}
    for u in _java_units(model):
        fqn = u.get("legacy_fqn") or u.get("key") or ""
        pkg = fqn.rsplit(".", 1)[0] if "." in fqn else "(default)"
        pkg_hist[pkg] += 1
        # Prefer a higher fan-in representative with a src/ path
        cur = pkg_rep.get(pkg)
        if cur is None or int(u.get("fan_in") or 0) > int(cur.get("fan_in") or 0):
            if (u.get("legacy_path") or "").replace("\\", "/").startswith("src/"):
                pkg_rep[pkg] = u
    lines = [
        "===== PROJECTED FACTS §6 (Domain boundaries) =====",
        "Compose from package histogram + condensation. Do NOT open the legacy tree.",
        "O-PROFPROSECITE: copy ≥1 REQUIRED CITE string into the body verbatim.",
        "",
        "## package histogram (count · package · representative path:line)",
    ]
    cites: list[str] = []
    for pkg, n in pkg_hist.most_common(40):
        rep = pkg_rep.get(pkg)
        if rep:
            cite = _first_anchor_cite(
                anchors_for_unit(root, rep, legacy_root=lr),
                rep.get("legacy_path") or "",
            )
            if cite and cite not in cites:
                cites.append(cite)
            lines.append(f"- {n}× {pkg} · {cite or rep.get('legacy_path')}")
        else:
            lines.append(f"- {n}× {pkg}")
    lines.append("")
    lines.append("## condensation / SCC ids in order")
    for i, item in enumerate(model.get("order") or [], 1):
        if item.startswith("SCC-"):
            scc = next((s for s in model.get("sccs") or [] if s.get("id") == item), None)
            members = ", ".join((scc or {}).get("members") or [])
            lines.append(f"{i}. {item}: {members}")
        else:
            lines.append(f"{i}. {item}")
        if i >= 60:
            lines.append("… [truncated]")
            break
    lines.append("")
    lines.append("## REQUIRED CITE (copy ≥1 verbatim into body)")
    for c in cites[:12]:
        lines.append(f"- {c}")
    if not cites:
        lines.append("- migration/dependency-order.md:1")
    return "\n".join(lines)


_PROJECTORS = {
    1: _project_s1,
    2: _project_s2,
    3: _project_s3,
    4: _project_s4,
    5: _project_s5,
    6: _project_s6,
}


def project_section(root: Path, num: int, *, legacy: str) -> str:
    """Return projected facts markdown for one architecture-profile section."""
    if num not in _PROJECTORS:
        raise ValueError(f"no projector for section {num}")
    model = _load_model(root)
    text = _PROJECTORS[num](root, model, legacy)
    # Hard cap packet growth (O-CTX) — prefer truncation over rediscovery
    if len(text) > 24000:
        text = text[:24000] + "\n… [packet truncated]\n"
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="Prose section fact projection")
    ap.add_argument("--root", default=".")
    ap.add_argument("--legacy", default="/projects/legacy")
    ap.add_argument("--section", type=int, required=True, choices=range(1, 7))
    args = ap.parse_args()
    print(project_section(Path(args.root).resolve(), args.section, legacy=args.legacy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
