#!/usr/bin/env python3
"""The upstream text of ONE code-generator template, from the generator version the build pins (v30 H-1/H-2).

v30 t_6fa85bc5 (M3 BUILD beanValidation.mustache): the worker downloaded the whole generator jar into the
product root (`mvn dependency:copy -DoutputDirectory=/projects/modernized/.tmp-og`), which made the next issue
refuse ISSUE_BASELINE_DRIFT, then re-read templates with ~20 `unzip -p ... | sed -n` calls until the loop guard
halted two runs. This answers the one question directly, read-only and bounded:

    generator-template.py --root . --list JavaJaxRS/spec/
    generator-template.py --root . --template JavaJaxRS/spec/beanValidation.mustache [--lines 1:80]

The generator is the pom's own plugin declaration (groupId/artifactId/version, ${property} resolved from the
pom's <properties>), read with an XML parser. Its codegen jar is read from the local Maven repository the build
already filled. When it is not there, nothing is downloaded: the answer is the exact fetch command, whose output
directory is this card's sanctioned scratch (.derived/scratch/<card>/, outside the product: never judged, never
parked, never drift). Every answer names the generator version; an absent template is stated as an answer."""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# Which plugin is a code generator, and which artifact carries its templates, is migration KNOWLEDGE: it lives in
# the run's catalog (compat-mapping.json build_plugins[<group:artifact>].template_source), never in this code, so
# another application's generator is supported by a catalog row, not a harness change.
CATALOG = Path(__file__).resolve().parents[4] / "planning" / "catalogs" / "compat-mapping.json"
SCRATCH = ".derived/scratch"
LIMIT_LINES = 200


def scratch_dir(card: str = "") -> str:
    """This card's sanctioned scratch directory, relative to the destination root."""
    card = card or (os.environ.get("HERMES_KANBAN_TASK") or "").strip() or "unassigned"
    return "%s/%s" % (SCRATCH, card)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(node, name: str):
    return next((c for c in list(node) if _local(c.tag) == name), None)


def _text(node, name: str) -> str:
    c = _child(node, name)
    return (c.text or "").strip() if c is not None and c.text else ""


def codegen_map(catalog: dict | None = None) -> dict[tuple[str, str], tuple[str, str]]:
    """(plugin group, artifact) -> (codegen group, artifact), from the catalog's build_plugins template_source rows."""
    if catalog is None:
        try:
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            catalog = {}
    out = {}
    for key, row in ((catalog or {}).get("build_plugins") or {}).items():
        src = (row or {}).get("template_source") if isinstance(row, dict) else None
        if ":" in key and isinstance(src, dict) and ":" in str(src.get("artifact") or ""):
            out[tuple(key.split(":", 1))] = tuple(str(src["artifact"]).split(":", 1))
    return out


def generators(pom: Path, catalog: dict | None = None) -> list[dict[str, str]]:
    """[{group, artifact, version, codegen_group, codegen_artifact}] for every catalogued generator plugin the pom
    declares, the version's ${property} resolved from the pom's own <properties>."""
    codegen = codegen_map(catalog)
    root = ET.parse(str(pom)).getroot()
    props = {}
    pnode = _child(root, "properties")
    for p in list(pnode) if pnode is not None else []:
        props[_local(p.tag)] = (p.text or "").strip()
    out = []
    for plugin in root.iter():
        if _local(plugin.tag) != "plugin":
            continue
        key = (_text(plugin, "groupId"), _text(plugin, "artifactId"))
        if key not in codegen:
            continue
        version = _text(plugin, "version")
        if version.startswith("${") and version.endswith("}"):
            version = props.get(version[2:-1], "")
        cg, ca = codegen[key]
        out.append({"group": key[0], "artifact": key[1], "version": version, "codegen_group": cg, "codegen_artifact": ca})
    return out


def local_repository() -> Path:
    env = os.environ.get("MAVEN_REPO_LOCAL") or os.environ.get("RHOAI3_MAVEN_REPO")
    return Path(env) if env else Path.home() / ".m2" / "repository"


def codegen_jar(gen: dict[str, str], repo: Path) -> Path:
    return (repo / gen["codegen_group"].replace(".", "/") / gen["codegen_artifact"] / gen["version"]
            / ("%s-%s.jar" % (gen["codegen_artifact"], gen["version"])))


def answer(root: Path, *, template: str = "", listing: str = "", lines: str = "", repo: Path | None = None,
           catalog: dict | None = None) -> tuple[int, str]:
    pom = Path(root) / "pom.xml"
    if not pom.is_file():
        return 1, "no pom.xml at %s: no generator is declared" % root
    gens = [g for g in generators(pom, catalog) if g["version"]]
    if len(gens) != 1:
        return 1, ("the pom declares %d catalogued generator plugin(s) with a resolved version (%s); this lookup answers "
                   "exactly one. A generator the catalog does not describe (build_plugins[<group:artifact>]."
                   "template_source) is not guessed."
                   % (len(gens), ", ".join("%s:%s" % (g["artifact"], g["version"] or "?") for g in generators(pom, catalog)) or "none"))
    gen = gens[0]
    jar = codegen_jar(gen, repo or local_repository())
    head = "%s:%s:%s (the version this build pins)" % (gen["codegen_group"], gen["codegen_artifact"], gen["version"])
    if not jar.is_file():
        return 2, ("%s is not in the local Maven repository (%s). Fetch it OUTSIDE the product, then ask again:\n"
                   "  mvn -q dependency:copy -Dartifact=%s:%s:%s -DoutputDirectory=%s\n"
                   "  (or set MAVEN_REPO_LOCAL to the repository that holds it)"
                   % (head, jar, gen["codegen_group"], gen["codegen_artifact"], gen["version"], scratch_dir()))
    with zipfile.ZipFile(str(jar)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        if listing:
            hits = sorted(n for n in names if n.startswith(listing.lstrip("/")))
            if not hits:
                return 0, "%s: 0 entries under %s. That is the answer; do not repeat the query unchanged." % (head, listing)
            return 0, "\n".join(["%s: %d entr(ies) under %s" % (head, len(hits), listing)] + ["  " + n for n in hits[:LIMIT_LINES]])
        name = template.lstrip("/")
        if name not in names:
            near = sorted(n for n in names if n.endswith("/" + name.rsplit("/", 1)[-1]))[:10]
            return 1, ("%s has no template %s.%s" % (head, name, (" Same file name at: " + ", ".join(near)) if near else
                                                    " Use --list <prefix> to see the templates."))
        text = z.read(name).decode("utf-8", "replace").splitlines()
    a, b = 1, min(len(text), LIMIT_LINES)
    if lines:
        x, _, y = lines.partition(":")
        try:
            a = max(1, int(x or 1))
            b = min(len(text), int(y) if y else len(text))
        except ValueError:
            return 1, ("--lines takes a:b with whole numbers (got %r); %s has %d lines: e.g. --lines 1:%d"
                       % (lines, name, len(text), min(len(text), LIMIT_LINES)))
        if a > len(text) or b < a:
            return 1, ("--lines %s is outside %s (lines 1-%d): e.g. --lines 1:%d"
                       % (lines, name, len(text), min(len(text), LIMIT_LINES)))
        # architect review (H-2): one page at most, whatever range is asked for
        b = min(b, a + LIMIT_LINES - 1)
    body = ["%5d  %s" % (n, text[n - 1]) for n in range(a, b + 1)]
    more = "" if b >= len(text) else "  (%d more line(s): --lines %d:%d)" % (len(text) - b, b + 1, len(text))
    return 0, "\n".join(["%s %s, lines %d-%d of %d%s" % (head, name, a, b, len(text), more)] + body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--template", default="", help="a template path inside the generator jar, e.g. JavaJaxRS/spec/pojo.mustache")
    g.add_argument("--list", dest="listing", default="", help="list the templates under this prefix")
    ap.add_argument("--lines", default="", help="a:b, the line range to print (default: the first %d)" % LIMIT_LINES)
    args = ap.parse_args()
    rc, text = answer(Path(args.root), template=args.template, listing=args.listing, lines=args.lines)
    print(text)
    return rc


if __name__ == "__main__":
    sys.exit(main())
