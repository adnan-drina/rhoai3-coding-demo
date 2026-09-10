#!/usr/bin/env python3
"""Print the head cluster's brief: the only thing a worker edits.

The brief is derived from the sealed work list (never written by a
model): cluster id, kind, write set, and every item (rule / compiler
code, line, detail). Exit 0 with the brief; 1 when the work list has no
open cluster (the loop is done or fully deferred).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_DIR, MTA_FINDINGS, MTA_RESCAN_FINDINGS, WORKLIST, BOM_MANAGED  # noqa: E402
from planner.worklist import head_cluster, items_of  # noqa: E402

PROCEDURE = (
    "Patch the write set one item at a time (targeted edits; never rewrite a whole file, never touch a "
    "path outside the write set, never tests). Each item names its rule, its advice (the rule's own guidance), "
    "and for pom.xml the exact element at the reported line. An item whose advice names an artifact that is "
    "already in the pom is marked advice_present: verify and move on, do not add it twice. Then run "
    "run-verify.sh and advance.py; the measure decides, not you."
)


def pom_elements(pom_path: Path) -> list[dict]:
    """Every <dependency>/<plugin>/<extension> element of a pom with its line
    span and GAV, from the XML parser's own line numbers (no text matching)."""
    import xml.parsers.expat

    els: list[dict] = []
    stack: list[dict] = []
    parser = xml.parsers.expat.ParserCreate()

    def start(name: str, _attrs: dict) -> None:
        stack.append({"name": name, "line": parser.CurrentLineNumber, "children": {}, "text": ""})

    def end(name: str) -> None:
        el = stack.pop()
        if stack and name in ("groupId", "artifactId", "version", "scope"):
            stack[-1]["children"][name] = el["text"].strip()
        if name in ("dependency", "plugin", "extension"):
            c = el["children"]
            els.append({"kind": name, "gav": "%s:%s" % (c.get("groupId", ""), c.get("artifactId", "")), "version": c.get("version", ""), "scope": c.get("scope", ""), "line_start": el["line"], "line_end": parser.CurrentLineNumber})

    def chars(data: str) -> None:
        if stack:
            stack[-1]["text"] += data

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        parser.Parse(pom_path.read_bytes(), True)
    except xml.parsers.expat.ExpatError:
        return []
    return els


def element_at(els: list[dict], line: int) -> dict | None:
    hits = [e for e in els if e["line_start"] <= line <= e["line_end"]]
    return min(hits, key=lambda e: e["line_end"] - e["line_start"]) if hits else None


def _backticked(text: str) -> list[str]:
    parts = text.split("`")
    return [parts[i].strip() for i in range(1, len(parts), 2) if parts[i].strip()]


def bom_managed(root: Path) -> set[str]:
    """group:artifact ids the pinned BOM manages (probe-bom-managed.py), or empty when unprobed."""
    p = root / BOM_MANAGED
    if not p.is_file():
        return set()
    return {str(x) for x in (load_json(p).get("managed") or [])}


def artifact_aliases(root: Path) -> dict[str, str]:
    """Documented renames from the bootstrap catalog (old group:artifact → managed group:artifact)."""
    p = root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
    if not p.is_file():
        return {}
    rows = (load_json(p).get("artifact_aliases") or {})
    return {k: str(v) for k, v in rows.items() if k != "note" and isinstance(v, str)}


def enrich(items: list[dict], root: Path, cluster: dict) -> list[dict]:
    """Attach the rule's advice/links (from the findings the work list was
    built on) and, for pom.xml loci, the element at the reported line plus
    which advised artifacts the pom already carries."""
    findings_p = next((root / rel for rel in (MTA_RESCAN_FINDINGS, MTA_FINDINGS) if (root / rel).is_file()), None)
    rules = (load_json(findings_p).get("violations") or {}) if findings_p else {}
    pom_p = root / "pom.xml"
    els = pom_elements(pom_p) if cluster.get("path") == "pom.xml" and pom_p.is_file() else []
    artifacts = {e["gav"].split(":")[-1] for e in els} | {e["gav"] for e in els}
    managed, aliases = bom_managed(root), artifact_aliases(root)
    out: list[dict] = []
    for it in items:
        row = dict(it)
        rule = rules.get(str(it.get("rule_id")))
        if it.get("rule_id") == "BUILD_UNRESOLVABLE":
            # the resolver's own words; nothing else is measurable until Maven resolves the pom
            row["advice"] = {"description": "Maven cannot resolve the pom: fix the named coordinate (a BOM-managed artifact needs no version; an artifact the BOM does not manage must not be added under an old name)", "message": str(it.get("message") or it.get("detail") or ""), "links": ["https://quarkus.io/guides/maven-tooling"]}
        if isinstance(rule, dict) and it.get("source") == "mta":
            incs = rule.get("incidents") if isinstance(rule.get("incidents"), list) else []
            msg = next((str(i.get("message")) for i in incs if isinstance(i, dict) and i.get("message")), "")
            row["advice"] = {"description": str(rule.get("description") or ""), "message": msg, "links": [l.get("url") for l in (rule.get("links") or []) if isinstance(l, dict) and l.get("url")]}
            present = sorted(t for t in _backticked(msg) if t in artifacts or t.split(":")[-1] in artifacts)
            if present:
                row["advice_present"] = present
            if managed:
                # advice written for Quarkus 2 names artifacts the pinned BOM does not manage
                # (as `io.quarkus:quarkus-resteasy-reactive` or bare `quarkus-resteasy-reactive-jackson`);
                # say so, and name the managed artifact the catalog documents for it
                managed_ids = {m.split(":")[-1] for m in managed}
                alias_ids = {k.split(":")[-1]: v for k, v in aliases.items()}
                unmanaged = sorted(t for t in _backticked(msg)
                                   if (t.startswith("io.quarkus:") and t not in managed) or (":" not in t and t.startswith("quarkus-") and t not in managed_ids))
                if unmanaged:
                    row["advice_unmanaged"] = unmanaged
                    eq = {t: (aliases.get(t) or alias_ids.get(t.split(":")[-1])) for t in unmanaged}
                    eq = {t: v for t, v in eq.items() if v}
                    if eq:
                        row["advice_managed_equivalent"] = eq
                        row["advice_managed_present"] = sorted(v for v in eq.values() if v in artifacts or v.split(":")[-1] in artifacts)
        if els:
            el = element_at(els, int(it.get("line") or 0))
            row["element"] = el or {"kind": "project", "gav": "", "line_start": 1, "line_end": 0}
        out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", default="", help="a specific cluster id (default: the head)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    doc = load_json(root / WORKLIST)
    cluster = next((c for c in doc["clusters"] if c["id"] == args.cluster), None) if args.cluster else head_cluster(doc)
    if cluster is None:
        print("REFUSE: LOOP_NO_OPEN_CLUSTER (work list head is empty)", file=sys.stderr)
        return 1
    brief = {
        "schema": "rhoai3.loop-brief/v1",
        "cluster": cluster,
        "write_set": list(cluster.get("write_set") or []),
        "items": enrich(items_of(doc, cluster), root, cluster),
        "measure": doc["measure"],
        "procedure": PROCEDURE,
        "rule": "Edit only the write set. Do not edit tests. Do not touch pom.xml unless it is in the write set. Then run run-verify.sh and advance.py; the measure decides, not you.",
    }
    write_canonical(root / LOOP_DIR / ("brief-%s.json" % cluster["id"].replace(":", "-")), brief)
    print(json.dumps(brief, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
