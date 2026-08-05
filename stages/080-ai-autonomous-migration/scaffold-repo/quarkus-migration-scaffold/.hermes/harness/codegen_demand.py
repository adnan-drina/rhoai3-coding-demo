#!/usr/bin/env python3
"""O-CODEGENDEMAND — deterministic build-time codegen demand for M1 ANALYZE.

Scans the legacy build file (and optionally target/generated-sources as a
confirmatory signal) and emits reserved synthetic finding ids:

  build-codegen-<slug>-00001

Ids end in -NNNN so they flow through existing FINDING_RE / m2-compose /
roadmap-lint ownership without new ownership code.

Primary signals (required for emit):
  - <annotationProcessorPaths> / <annotationProcessor> coordinates
  - build plugins whose artifactId looks like a generator
    (*-processor, *codegen*, *generator*, *-maven-plugin with a
    generate-sources / generate-test-sources goal)

Confirmatory (optional): target/generated-sources/<dir> — when present,
attaches observed file counts; never the sole emit trigger for an unknown
slug (unbuilt trees must still emit from pom alone).

Does NOT treat bare API jars (jaxb-api, runtime mapstruct without a
processor/plugin) as generators.

Usage:
  codegen-demand.py <legacy-root>            # markdown sections → stdout
  codegen-demand.py --json <legacy-root>     # JSON list → stdout
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# Strip Maven POM namespaces so tag matching is local-name based.
_NS_RE = re.compile(r"\{[^}]+\}")

GENERATOR_ARTIFACT = re.compile(
    r"(?:^|-)(?:processor)$|codegen|generator",
    re.I,
)
# Plugins that generate sources even when artifactId is generic.
GENERATE_GOALS = frozenset(
    {
        "generate-sources",
        "generate-test-sources",
        "generate",
    }
)

# Bare API / runtime artifacts that must NOT mint a codegen finding alone.
API_ONLY = frozenset(
    {
        "mapstruct",
        "jaxb-api",
        "jakarta.xml.bind-api",
        "javax.xml.bind-api",
    }
)


def _local(tag: str) -> str:
    return _NS_RE.sub("", tag)


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _slug(artifact_id: str) -> str:
    """Map artifactId → stable slug (specimen-agnostic)."""
    a = artifact_id.lower()
    if "mapstruct" in a:
        return "mapstruct"
    if "openapi" in a:
        return "openapi"
    if "jaxb" in a or "xjc" in a:
        return "jaxb"
    if "lombok" in a:
        return "lombok"
    # generic: strip common suffixes
    s = re.sub(r"(-maven)?-plugin$", "", a)
    s = re.sub(r"-processor$", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "generator"


def _finding_id(slug: str) -> str:
    return f"build-codegen-{slug}-00001"


def _find_pom(legacy_root: str) -> str | None:
    for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
        p = os.path.join(legacy_root, name)
        if os.path.isfile(p):
            return p
    return None


def _scan_pom_xml(pom_path: str) -> dict[str, dict]:
    """Return slug → meta from Maven POM signals."""
    found: dict[str, dict] = {}
    try:
        tree = ET.parse(pom_path)
    except ET.ParseError:
        return found
    root = tree.getroot()

    # annotationProcessorPaths → path/{groupId,artifactId,version}
    for el in root.iter():
        if _local(el.tag) != "annotationProcessorPaths":
            continue
        for path_el in el.iter():
            if _local(path_el.tag) != "path":
                continue
            arts = {
                _local(ch.tag): _text(ch)
                for ch in list(path_el)
                if _local(ch.tag) in ("groupId", "artifactId", "version")
            }
            aid = arts.get("artifactId") or ""
            if not aid or aid.lower() in API_ONLY:
                continue
            # Prefer real processors; skip unrelated path entries
            if not (GENERATOR_ARTIFACT.search(aid) or "processor" in aid.lower()):
                continue
            slug = _slug(aid)
            found[slug] = {
                "slug": slug,
                "artifact_id": aid,
                "group_id": arts.get("groupId", ""),
                "signal": "annotationProcessorPath",
                "finding_id": _finding_id(slug),
            }

    # plugins with generator artifactId or generate-sources goals
    for el in root.iter():
        if _local(el.tag) != "plugin":
            continue
        arts: dict[str, str] = {}
        goals: list[str] = []
        for ch in list(el):
            ln = _local(ch.tag)
            if ln in ("groupId", "artifactId", "version"):
                arts[ln] = _text(ch)
            if ln == "executions":
                for g in ch.iter():
                    if _local(g.tag) == "goal":
                        goals.append(_text(g))
        aid = arts.get("artifactId") or ""
        if not aid or aid.lower() in API_ONLY:
            continue
        is_gen = bool(GENERATOR_ARTIFACT.search(aid)) or any(
            g in GENERATE_GOALS for g in goals
        )
        if not is_gen:
            continue
        slug = _slug(aid)
        if slug not in found:
            found[slug] = {
                "slug": slug,
                "artifact_id": aid,
                "group_id": arts.get("groupId", ""),
                "signal": "plugin",
                "goals": goals,
                "finding_id": _finding_id(slug),
            }
        else:
            found[slug].setdefault("goals", goals)
    return found


def _scan_generated_sources(legacy_root: str) -> dict[str, dict]:
    """Confirmatory counts from target/generated-sources/<dir>."""
    base = os.path.join(legacy_root, "target", "generated-sources")
    out: dict[str, dict] = {}
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        n_java = 0
        for dp, _, files in os.walk(path):
            n_java += sum(1 for f in files if f.endswith(".java"))
        # Map common dir names → slug; unknown dirs do NOT mint alone
        slug = name
        if name in ("annotations", "annotation-processors"):
            slug = "mapstruct"  # common MapStruct output dir — confirmatory only
        elif name == "openapi":
            slug = "openapi"
        out[slug] = {
            "dir": name,
            "generated_java_count": n_java,
            "path": f"target/generated-sources/{name}",
        }
    return out


def detect(legacy_root: str) -> list[dict]:
    pom = _find_pom(legacy_root)
    found: dict[str, dict] = {}
    if pom and pom.endswith("pom.xml"):
        found = _scan_pom_xml(pom)
    # Gradle: light heuristic (artifact lines)
    elif pom and ("gradle" in pom):
        text = open(pom, encoding="utf-8", errors="replace").read()
        for m in re.finditer(
            r'["\']([^"\']*(?:processor|codegen|generator)[^"\']*)["\']',
            text,
            re.I,
        ):
            coord = m.group(1)
            aid = coord.split(":")[-1]
            if aid.lower() in API_ONLY:
                continue
            slug = _slug(aid)
            found[slug] = {
                "slug": slug,
                "artifact_id": aid,
                "group_id": "",
                "signal": "gradle",
                "finding_id": _finding_id(slug),
            }

    confirm = _scan_generated_sources(legacy_root)
    results = []
    for slug, meta in sorted(found.items()):
        c = confirm.get(slug) or {}
        # MapStruct often lands under annotations/ — attach if mapstruct slug
        if not c and slug == "mapstruct":
            c = confirm.get("mapstruct") or confirm.get("annotations") or {}
        entry = dict(meta)
        if c:
            entry["generated_sources_dir"] = c.get("path") or c.get("dir")
            entry["generated_java_count"] = c.get("generated_java_count", 0)
            entry["signal_confirm"] = "target/generated-sources"
        else:
            entry["generated_java_count"] = 0
        entry["requirement"] = (
            "destination build must reproduce this generation "
            "(annotation processor / codegen plugin wiring)."
        )
        results.append(entry)
    return results


def render_markdown(entries: list[dict]) -> str:
    if not entries:
        return ""
    lines = [
        "## Build-time code generation (O-CODEGENDEMAND)",
        "",
        "Deterministic ANALYZE-side findings (not MTA). Reserved id namespace "
        "`build-codegen-<slug>-NNNN`. Destination build must configure matching "
        "processors/plugins before consumer types compile.",
        "",
    ]
    for e in entries:
        fid = e["finding_id"]
        lines.append(f"## {fid} [infer]")
        lines.append("")
        lines.append(
            f"- Build-time code generation: `{e.get('artifact_id', e['slug'])}` "
            f"(signal={e.get('signal')}"
            + (
                f", confirm={e.get('signal_confirm')}"
                if e.get("signal_confirm")
                else ""
            )
            + ")."
        )
        lines.append(f"- Decided target: {e['requirement']}")
        if e.get("generated_sources_dir"):
            lines.append(
                f"- Observed `{e['generated_sources_dir']}`: "
                f"{e.get('generated_java_count', 0)} generated .java files "
                "(confirmatory; emit does not require this tree)."
            )
        lines.append(
            f"- Configure destination pom/build so `{e['slug']}` generation "
            "runs (e.g. mapstruct-processor / openapi-generator) before "
            "harvesting consumer types."
        )
        lines.append("")
    return "\n".join(lines)


def render_dep_order_section(entries: list[dict]) -> str:
    if not entries:
        return ""
    lines = [
        "",
        "## Build-time code generation (O-CODEGENDEMAND)",
        "",
        "Codegen configuration precedes stories that harvest consumers of "
        "generated types. Synthetic finding ids must appear in a story's "
        "Findings after M2 partition.",
        "",
    ]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"{i}. `{e['finding_id']}` — configure `{e.get('artifact_id', e['slug'])}` "
            f"({e['slug']}) before converting consumers of its generated types."
        )
    lines.append("")
    return "\n".join(lines)


def summary_ids(entries: list[dict]) -> list[str]:
    return [e["finding_id"] for e in entries]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("legacy_root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dep-order", action="store_true", help="emit dep-order section only")
    args = ap.parse_args(argv)
    root = args.legacy_root
    if not os.path.isdir(root):
        print(f"codegen-demand: not a directory: {root}", file=sys.stderr)
        return 2
    entries = detect(root)
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    if args.dep_order:
        sys.stdout.write(render_dep_order_section(entries))
        return 0
    sys.stdout.write(render_markdown(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
