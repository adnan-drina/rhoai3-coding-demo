#!/usr/bin/env python3
"""O-TAGDEMAND — mint tech-<slug> demand from MTA tags/insights.

MTA output carries technology tags and insight codesnips that findings-inventory
previously discarded. Destination-consequence technologies become synthetic
findings in the reserved id namespace:

  tech-<slug>-00001

Inventory / discovery facts (Java Source, Maven XML, Properties, …) mint
nothing — same discipline as O-CODEGENDEMAND refusing API-only jars.

Also mines insight incident codesnips for hibernate dialect class names
(acceptance: inventory must mention dialect when present in findings).

Usage:
  tag_demand.py <findings.json>              # markdown → stdout
  tag_demand.py --json <findings.json>
  tag_demand.py --dep-order <findings.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

# Discovery / inventory facts — not migration work. Slug form after normalize.
INVENTORY_SLUGS = frozenset(
    {
        "java-source",
        "java-source-files",
        "maven-xml",
        "maven-xml-file",
        "properties",
        "properties-file",
        "application-properties-file",
        "application-properties-file-detected",
        "spring-properties",
        "spring-datasource-properties-detected",
        "spring-logging-properties-detected",
        "spring-jmx-configuration-detected",
    }
)

# Slug prefixes that are always discovery/inventory (file-type facts).
_INVENTORY_PREFIXES = (
    "java-source",
    "maven-xml",
    "properties",
    "application-properties",
    "spring-properties",
    "spring-datasource-properties",
    "spring-logging-properties",
)

# Prefix wrappers that add no technology identity.
_PREFIX_RE = re.compile(
    r"^(?:Embedded framework|Embedded library|Caching|Embedded)\s*[-–]\s*",
    re.I,
)

_DIALECT_RE = re.compile(
    r"org\.hibernate\.dialect\.([A-Za-z0-9_]+)",
    re.I,
)


def _slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "tech"


def _finding_id(slug: str) -> str:
    return f"tech-{slug}-00001"


def _is_inventory_slug(slug: str) -> bool:
    if slug in INVENTORY_SLUGS:
        return True
    return any(slug == p or slug.startswith(p + "-") for p in _INVENTORY_PREFIXES)


def _normalize_tag(raw: str) -> str | None:
    """Return a technology display name, or None if inventory-only / empty."""
    t = (raw or "").strip()
    if not t:
        return None
    # Category=Technology → Technology
    if "=" in t:
        t = t.split("=", 1)[1].strip()
    t = _PREFIX_RE.sub("", t).strip()
    if not t:
        return None
    slug = _slug(t)
    if _is_inventory_slug(slug):
        return None
    return t


def _collect_tag_strings(data: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(data, list):
        return out
    for rs in data:
        if not isinstance(rs, dict):
            continue
        for t in rs.get("tags") or []:
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, dict):
                name = t.get("name") or t.get("value") or ""
                if name:
                    out.append(str(name))
        for _rid, v in (rs.get("violations") or {}).items():
            if not isinstance(v, dict):
                continue
            for t in v.get("tags") or []:
                if isinstance(t, str):
                    out.append(t)
        # Insight labels often carry tag=<name>
        insights = rs.get("insights") or {}
        if isinstance(insights, dict):
            for _k, insight in insights.items():
                if not isinstance(insight, dict):
                    continue
                for lab in insight.get("labels") or []:
                    if isinstance(lab, str) and lab.lower().startswith("tag="):
                        out.append(lab.split("=", 1)[1])
                # Do NOT mint from insight descriptions — discovery rulesets
                # use short descriptions like "Java source files" / "Maven XML
                # file" that are inventory facts, not destination demand.
    return out


def _collect_dialects(data: Any) -> list[str]:
    found: set[str] = set()
    if not isinstance(data, list):
        return []
    blob_parts: list[str] = []
    for rs in data:
        if not isinstance(rs, dict):
            continue
        insights = rs.get("insights") or {}
        if not isinstance(insights, dict):
            continue
        for _k, insight in insights.items():
            if not isinstance(insight, dict):
                continue
            for inc in insight.get("incidents") or []:
                if isinstance(inc, dict):
                    snip = inc.get("codesnip") or inc.get("codeSnip") or ""
                    if snip:
                        blob_parts.append(str(snip))
            # also description / whole insight for resilience
            blob_parts.append(json.dumps(insight))
    for part in blob_parts:
        for m in _DIALECT_RE.finditer(part):
            found.add(m.group(1))
    return sorted(found)


def detect(findings_path: str) -> list[dict]:
    with open(findings_path, encoding="utf-8") as fh:
        data = json.load(fh)

    by_slug: dict[str, dict] = {}
    for raw in _collect_tag_strings(data):
        name = _normalize_tag(raw)
        if not name:
            continue
        slug = _slug(name)
        if _is_inventory_slug(slug):
            continue
        if slug not in by_slug:
            by_slug[slug] = {
                "slug": slug,
                "name": name,
                "signal": "mta-tag",
                "finding_id": _finding_id(slug),
                "requirement": (
                    f"Destination must account for technology `{name}` "
                    "(MTA tag/insight) — configure Quarkus equivalent or "
                    "explicitly defer with rationale in the roadmap."
                ),
            }

    dialects = _collect_dialects(data)
    if dialects:
        slug = "hibernate-dialect"
        by_slug[slug] = {
            "slug": slug,
            "name": "Hibernate Dialect",
            "signal": "insight-codesnip",
            "dialects": dialects,
            "finding_id": _finding_id(slug),
            "requirement": (
                "Destination persistence must configure the correct DB dialect / "
                f"db-kind for observed Hibernate dialects: {', '.join(dialects)}."
            ),
        }

    return [by_slug[k] for k in sorted(by_slug)]


def render_markdown(entries: list[dict]) -> str:
    if not entries:
        return ""
    lines = [
        "## Technology demand from MTA tags/insights (O-TAGDEMAND)",
        "",
        "Deterministic ANALYZE-side findings (not Windup rule ids). Reserved id "
        "namespace `tech-<slug>-NNNN`. Inventory/discovery tags (Java Source, "
        "Maven XML, Properties, …) are excluded.",
        "",
    ]
    for e in entries:
        fid = e["finding_id"]
        lines.append(f"## {fid} [infer]")
        lines.append("")
        lines.append(
            f"- Technology demand: `{e.get('name', e['slug'])}` "
            f"(signal={e.get('signal')})."
        )
        if e.get("dialects"):
            lines.append(
                "- Observed Hibernate dialect classes: "
                + ", ".join(f"`org.hibernate.dialect.{d}`" for d in e["dialects"])
            )
        lines.append(f"- Decided target: {e['requirement']}")
        lines.append("")
    return "\n".join(lines)


def render_dep_order_section(entries: list[dict]) -> str:
    if not entries:
        return ""
    lines = [
        "",
        "## Technology demand (O-TAGDEMAND)",
        "",
        "Tag/insight-derived technologies must appear in a story's Findings "
        "after M2 partition (or be explicitly deferred).",
        "",
    ]
    for i, e in enumerate(entries, 1):
        extra = ""
        if e.get("dialects"):
            extra = f" — dialects: {', '.join(e['dialects'])}"
        lines.append(
            f"{i}. `{e['finding_id']}` — `{e.get('name', e['slug'])}` "
            f"({e['slug']}){extra}."
        )
    lines.append("")
    return "\n".join(lines)


def summary_ids(entries: list[dict]) -> list[str]:
    return [e["finding_id"] for e in entries]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("findings_json")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dep-order", action="store_true")
    args = ap.parse_args(argv)
    try:
        entries = detect(args.findings_json)
    except OSError as exc:
        print(f"tag-demand: {exc}", file=sys.stderr)
        return 2
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
