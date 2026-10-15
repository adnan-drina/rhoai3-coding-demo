#!/usr/bin/env python3
"""Check product skills and READMEs against the Red Hat doc map.

The map (.agents/references/red-hat-doc-map.yaml) holds one docs_version per
product and the Git pin that must agree with it. This checker reports:

  PIN-MISMATCH      map docs_version differs from the Git pin
  PIN-UNREADABLE    the pin file or field cannot be read
  UNPINNED          the product has no Git pin (pin.none)
  FRONTMATTER       product skill lacks metadata.product / metadata.docs-version
  STALE             skill docs-version differs from the map
  LINK-VERSION      docs.redhat.com link uses another version than the map
  LINK-UNKNOWN      docs.redhat.com link to a product the map does not know
  MISSING-SKILL     reference to a skill that does not exist
  UNROUTED          product skill without a route in the map
  EXTRACTION        references/official-doc-extraction.md still present
  SOURCE-CAPTURE    references/source-capture.md still present
  SKILL-SIZE        SKILL.md longer than the thin-skill target
  LIVE-BROKEN       (--live) URL answered 404/410 or the #anchor is missing

Links are read from skills, component READMEs (gitops/stages/*/*/README.md),
stage READMEs (stages/*/README.md) and top-level docs (docs/*.md, not
docs/migration/). Static mode needs no network. Findings are attributed to
a product family and, when they come from a skill, to that skill; a README or
doc link belongs to the family of the product it links to. Default exit status is 1
when a finding belongs to a family in converted_families or to a skill in
converted_skills (a family converted skill by skill; pin findings of such a
family fail too); --report always exits 0. --live fetches each URL sequentially with a
delay; 403, 429 and 5xx answers are INCONCLUSIVE, never failures.

Usage:
  check-doc-links.py [--report] [--brief] [--family F,...]
  check-doc-links.py --live [--family F,...] [--delay 2] [--limit N]
  check-doc-links.py --versions     (print each product's docs_version and pin)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = Path(".agents/references/red-hat-doc-map.yaml")
SKILLS = Path(".agents/skills")
SKILL_LINES_TARGET = 150
LINK_RE = re.compile(
    r"https?://docs\.redhat\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?documentation/"
    r"([^/\s)>\]\"'`]+)/([^/\s)>\]\"'`#]+)([^\s)>\]\"'`]*)")
SKILL_PATH_RE = re.compile(r"\.agents/skills/([a-z0-9][a-z0-9-]*[a-z0-9])(?=/|`|\s|$|\))")
BACKTICK_RE = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".txt", ".json", ".sh", ".py"}
INCONCLUSIVE = {403, 429, 500, 502, 503, 504}


def load_yaml(text: str):
    """Parse YAML with PyYAML when present, else Ruby's Psych (repo precedent)."""
    try:
        import yaml  # type: ignore
        return list(yaml.safe_load_all(text))
    except ImportError:
        pass
    if not shutil.which("ruby"):
        raise SystemExit("check-doc-links: needs PyYAML or ruby to read YAML")
    script = "require 'yaml'; require 'json'; require 'date'; puts JSON.generate(YAML.load_stream(STDIN.read))"
    result = subprocess.run(["ruby", "-e", script], input=text, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit("check-doc-links: YAML parse failed: " + result.stderr.strip())
    return json.loads(result.stdout)


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.findings: list[tuple[str, str, str, str]] = []
        self.finding_skills: list[str | None] = []
        doc = load_yaml((root / MAP).read_text(encoding="utf-8"))[0]
        self.map = doc
        self.products: dict[str, dict] = {}
        for section in ("products", "cited_products"):
            for key, value in (doc.get(section) or {}).items():
                self.products[key] = value
        self.converted = set(doc.get("converted_families") or [])
        self.converted_skills = set(doc.get("converted_skills") or [])
        self.ignore = set(doc.get("skill_reference_ignore") or [])
        self.by_slug = {p["docs_slug"]: k for k, p in self.products.items() if p.get("docs_slug")}
        self.prefixes = sorted(
            ((p["skill_prefix"], k) for k, p in self.products.items() if p.get("skill_prefix")),
            key=lambda item: -len(item[0]))
        self.skills = {p.name for p in (root / SKILLS).iterdir() if (p / "SKILL.md").is_file()}

    # -- helpers -------------------------------------------------------------
    def add(self, code: str, family: str, where: str, message: str, skill: str | None = None) -> None:
        self.findings.append((code, family or "-", where, message))
        self.finding_skills.append(skill)

    def partial_families(self) -> set[str]:
        return {f for f in map(self.family_of_skill, self.converted_skills) if f}

    def failing(self, index: int) -> bool:
        code, family = self.findings[index][:2]
        if family in self.converted or self.finding_skills[index] in self.converted_skills:
            return True
        return code.startswith("PIN-") and family in self.partial_families()

    def skill_of_path(self, path: Path) -> str | None:
        parts = path.relative_to(self.root).parts
        return parts[2] if parts[:2] == (".agents", "skills") and len(parts) > 3 else None

    def family_of_skill(self, name: str) -> str | None:
        for prefix, key in self.prefixes:
            if name.startswith(prefix):
                return key
        return None

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    # -- checks --------------------------------------------------------------
    def check_pins(self) -> None:
        for key, product in self.products.items():
            pin = product.get("pin") or {}
            version = str(product.get("docs_version", ""))
            if not version:
                self.add("PIN-UNREADABLE", key, "map", "no docs_version")
                continue
            if "none" in pin:
                self.add("UNPINNED", key, "map", f"docs_version {version}: {pin['none']}")
                continue
            path = self.root / str(pin.get("file", ""))
            if not pin.get("file") or not path.is_file():
                self.add("PIN-UNREADABLE", key, "map", f"pin file missing: {pin.get('file')}")
                continue
            text = path.read_text(encoding="utf-8")
            value = text
            if path.suffix in (".yaml", ".yml") and pin.get("field"):
                value = None
                for doc in load_yaml(text):
                    node = doc
                    for part in str(pin["field"]).split("."):
                        node = node.get(part) if isinstance(node, dict) else None
                    if node is not None:
                        value = str(node)
                        break
                if value is None:
                    self.add("PIN-UNREADABLE", key, pin["file"], f"field {pin['field']} not found")
                    continue
            match = re.search(str(pin.get("pattern", r"(\d+\.\d+)")), value)
            if not match:
                self.add("PIN-UNREADABLE", key, pin["file"],
                         f"pattern {pin.get('pattern')} does not match {pin.get('field')}")
                continue
            if match.group(1) != version:
                self.add("PIN-MISMATCH", key, pin["file"],
                         f"{pin.get('field')} pins {match.group(1)}, map docs_version is {version}")

    def frontmatter(self, text: str) -> dict[str, str]:
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            return {}
        values = {}
        for key in ("product", "docs-version"):
            found = re.search(rf"^\s+{key}:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", match.group(1), re.M)
            if found:
                values[key] = found.group(1)
        return values

    def check_skills(self) -> None:
        routed = set()
        for key, product in self.products.items():
            for category in (product.get("categories") or {}).values():
                for route in category.get("routes") or []:
                    skill = route.get("skill")
                    routed.add(skill)
                    if route.get("status", "active") == "active" and skill not in self.skills:
                        self.add("MISSING-SKILL", key, "map", f"active route to {skill}", skill)
        for name in sorted(self.converted_skills - self.skills):
            self.add("MISSING-SKILL", self.family_of_skill(name) or "-", "map",
                     f"converted_skills lists {name}", name)
        for name in sorted(self.skills):
            family = self.family_of_skill(name)
            if not family:
                continue
            skill_dir = self.root / SKILLS / name
            md = skill_dir / "SKILL.md"
            text = md.read_text(encoding="utf-8")
            meta = self.frontmatter(text)
            where = self.rel(md)
            if "product" not in meta or "docs-version" not in meta:
                self.add("FRONTMATTER", family, where, "missing metadata.product or metadata.docs-version", name)
            else:
                if meta["product"] != family:
                    self.add("FRONTMATTER", family, where, f"metadata.product {meta['product']} != {family}", name)
                expected = str(self.products[family].get("docs_version"))
                if meta["docs-version"] != expected:
                    self.add("STALE", family, where,
                             f"reviewed against {meta['docs-version']}, product at {expected}", name)
            if name not in routed:
                self.add("UNROUTED", family, where, "no route in the doc map", name)
            lines = text.count("\n")
            if lines > SKILL_LINES_TARGET:
                self.add("SKILL-SIZE", family, where, f"{lines} lines > {SKILL_LINES_TARGET}", name)
            for leftover, code in (("official-doc-extraction.md", "EXTRACTION"),
                                   ("source-capture.md", "SOURCE-CAPTURE")):
                if (skill_dir / "references" / leftover).is_file():
                    self.add(code, family, self.rel(skill_dir / "references" / leftover), "copied-documentation file", name)

    def link_files(self):
        for path in sorted((self.root / SKILLS).rglob("*")):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path
        yield from sorted((self.root / "gitops" / "stages").glob("*/*/README.md"))
        # Stage READMEs and top-level operations docs; docs/migration/ is history.
        yield from sorted((self.root / "stages").glob("*/README.md"))
        yield from sorted((self.root / "docs").glob("*.md"))

    def file_family(self, path: Path) -> str | None:
        parts = path.relative_to(self.root).parts
        if parts[:2] == (".agents", "skills") and len(parts) > 2:
            return self.family_of_skill(parts[2])
        return None

    def check_links(self) -> list[tuple[str, str, str]]:
        urls = []
        for path in self.link_files():
            owner = self.file_family(path)
            skill = self.skill_of_path(path)
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for match in LINK_RE.finditer(line):
                    slug, version = match.group(1), match.group(2)
                    if any(c in slug + version for c in "<{$"):
                        continue
                    where = f"{self.rel(path)}:{number}"
                    product = self.by_slug.get(slug)
                    family = owner or product or "-"
                    url = match.group(0).rstrip(".,;:")
                    if not product:
                        self.add("LINK-UNKNOWN", family, where, f"unknown product slug {slug}", skill)
                        continue
                    expected = str(self.products[product]["docs_version"])
                    if version != expected:
                        self.add("LINK-VERSION", family, where, f"{slug} {version}, map has {expected}", skill)
                    urls.append((family, where, url, skill))
        return urls

    def check_references(self) -> None:
        known_prefixes = tuple(p for p, _ in self.prefixes) + ("project-", "env-")
        files = [self.root / "AGENTS.md", *sorted((self.root / ".agents" / "rules").glob("*.md")),
                 *sorted((self.root / SKILLS).rglob("*.md"))]
        for path in files:
            if not path.is_file():
                continue
            owner = self.file_family(path)
            skill = self.skill_of_path(path)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                names = set(SKILL_PATH_RE.findall(line))
                if "skill" in line.lower():
                    names |= {n for n in BACKTICK_RE.findall(line) if n.startswith(known_prefixes)}
                for name in sorted(names - self.skills - self.ignore):
                    family = owner or self.family_of_skill(name) or "-"
                    self.add("MISSING-SKILL", family, f"{self.rel(path)}:{number}", f"no skill named {name}", skill)

    def check_live(self, urls, delay: float, limit: int | None) -> None:
        seen: set[str] = set()
        pages: dict[str, tuple[int | None, str]] = {}  # one request per page, many anchors
        for family, where, url, skill in urls:
            base, _, anchor = url.partition("#")
            if url in seen or (base not in pages and limit is not None and len(pages) >= limit):
                continue
            seen.add(url)
            if base not in pages:
                if pages:
                    time.sleep(delay)
                pages[base] = fetch(base)
            status, body = pages[base]
            if status in (404, 410):
                self.add("LIVE-BROKEN", family, where, f"HTTP {status} {url}", skill)
            elif status is None or status in INCONCLUSIVE:
                print(f"INCONCLUSIVE {family} {where}: HTTP {status} {url}")
            elif anchor and f'id="{anchor}"' not in body:
                self.add("LIVE-BROKEN", family, where, f"anchor #{anchor} not found in {base}", skill)
        print(f"live: {len(seen)} URLs checked, {len(pages)} pages fetched")


def fetch(url: str) -> tuple[int | None, str]:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (rhoai3-coding-demo doc link check)",
        "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", action="store_true", help="report only; always exit 0")
    parser.add_argument("--brief", action="store_true",
                        help="print findings of converted families only, counts for the rest")
    parser.add_argument("--family", help="comma-separated families to show (default all)")
    parser.add_argument("--live", action="store_true", help="also fetch URLs (network)")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between live requests")
    parser.add_argument("--limit", type=int, help="maximum URLs to fetch in --live mode")
    parser.add_argument("--versions", action="store_true", help="print each product's docs_version and pin")
    args = parser.parse_args(argv)

    checker = Checker(args.root.resolve())
    if args.versions:
        for key, product in sorted(checker.products.items()):
            pin = product.get("pin") or {}
            source = f"unpinned: {pin['none']}" if "none" in pin else f"{pin.get('file')} {pin.get('field', '')}".strip()
            print(f"{key:24} {product.get('docs_version', '?'):8} {source}")
        return 0
    checker.check_pins()
    checker.check_skills()
    urls = checker.check_links()
    checker.check_references()
    families = set(args.family.split(",")) if args.family else None
    if args.live:
        if families:
            live = [u for u in urls if u[0] in families]
        else:
            live = [u for u in urls if u[0] in checker.converted or u[3] in checker.converted_skills]
        checker.check_live(live, args.delay, args.limit)

    shown = [i for i, f in enumerate(checker.findings) if families is None or f[1] in families]
    shown.sort(key=lambda i: (checker.findings[i][1], checker.findings[i][0], checker.findings[i][2]))
    counts: dict[str, dict[str, int]] = {}
    failing = 0
    for i in shown:
        code, family, where, message = checker.findings[i]
        counts.setdefault(family, {}).setdefault(code, 0)
        counts[family][code] += 1
        fails = checker.failing(i)
        failing += fails
        if not args.brief or fails:
            print(f"{code} {family} {where}: {message}")
    partial = checker.partial_families()
    print("summary:")
    for family in sorted(counts):
        tag = "converted" if family in checker.converted else "report-only"
        if family not in checker.converted and family in partial:
            done = sum(1 for name in checker.converted_skills if checker.family_of_skill(name) == family)
            tag = f"partial, {done} skills converted"
        detail = ", ".join(f"{code}={n}" for code, n in sorted(counts[family].items()))
        print(f"  {family} ({tag}): {sum(counts[family].values())} [{detail}]")
    print(f"  total={len(shown)} failing={failing} converted={','.join(sorted(checker.converted)) or '-'}"
          f" converted_skills={len(checker.converted_skills)}")
    return 0 if args.report or failing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
