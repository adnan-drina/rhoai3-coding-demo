#!/usr/bin/env python3
"""License inventory of the typed-repair executor's shaded runtime set.

Reads `mvn dependency:list` output (groupId:artifactId:type:version:scope),
then each artifact's POM from the local Maven repository, walking <parent>
until a <licenses> block is found. Prints JSON rows {gav, scope, licenses,
pom}; --check refuses (exit 1) when a runtime artifact has no declared license
or a license outside the permissive allow-list, or when a Moderne
source-available / proprietary license is named. Harness tooling only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

M2 = Path.home() / ".m2" / "repository"
NS = {"m": "http://maven.apache.org/POM/4.0.0"}
# normalized license families accepted for a HARNESS tool shipped in the workspace image
ALLOWED = {"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "EDL-1.0", "CC0-1.0", "Public-Domain"}
REFUSED = re.compile(r"moderne|source.available|proprietary|commercial|business source|BUSL|SSPL", re.I)


def normalize(name: str, url: str) -> str:
    s = "%s %s" % (name, url)
    if REFUSED.search(s):
        return "REFUSED:" + name
    if re.search(r"apache", s, re.I) and re.search(r"2", s):
        return "Apache-2.0"
    if re.search(r"\bMIT\b", s):
        return "MIT"
    if re.search(r"eclipse distribution|edl", s, re.I):
        return "EDL-1.0"
    if re.search(r"BSD.?3|new bsd|3-clause|revised bsd", s, re.I):
        return "BSD-3-Clause"
    if re.search(r"BSD.?2|simplified bsd|2-clause", s, re.I):
        return "BSD-2-Clause"
    if re.search(r"\bBSD\b", s, re.I):
        return "BSD-3-Clause"
    if re.search(r"CC0|creativecommons.org/publicdomain", s, re.I):
        return "CC0-1.0"
    if re.search(r"public domain", s, re.I):
        return "Public-Domain"
    if re.search(r"LGPL|Lesser General", s, re.I):
        return "LGPL"
    return "UNKNOWN:" + name


def pom_path(g: str, a: str, v: str) -> Path:
    return M2 / g.replace(".", "/") / a / v / ("%s-%s.pom" % (a, v))


def licenses(g: str, a: str, v: str, depth: int = 0) -> tuple[list[dict], str]:
    p = pom_path(g, a, v)
    if not p.is_file() or depth > 8:
        return [], str(p)
    root = ET.parse(p).getroot()
    rows = [{"name": (l.findtext("m:name", "", NS) or "").strip(), "url": (l.findtext("m:url", "", NS) or "").strip()}
            for l in root.findall("m:licenses/m:license", NS)]
    if rows:
        return rows, str(p.relative_to(M2))
    par = root.find("m:parent", NS)
    if par is None:
        return [], str(p.relative_to(M2))
    return licenses(par.findtext("m:groupId", "", NS), par.findtext("m:artifactId", "", NS),
                    par.findtext("m:version", "", NS), depth + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deps", help="mvn dependency:list -DoutputFile output")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out, bad = [], []
    for line in Path(args.deps).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+([^:\s]+):([^:\s]+):jar:([^:\s]+):(\w+)", line)
        if not m:
            continue
        g, a, v, scope = m.groups()
        rows, pom = licenses(g, a, v)
        fams = sorted({normalize(r["name"], r["url"]) for r in rows})
        # a dual-licensed artifact (JNA: Apache-2.0 OR LGPL-2.1) is taken under its permissive option
        chosen = [f for f in fams if f in ALLOWED]
        row = {"gav": "%s:%s:%s" % (g, a, v), "scope": scope, "declared": rows, "license": chosen[0] if chosen else "",
               "alternatives": [f for f in fams if f not in chosen], "pom": pom}
        out.append(row)
        if scope in ("compile", "runtime") and (not chosen or any(f.startswith("REFUSED") for f in fams)):
            bad.append(row["gav"])
    print(json.dumps(out, indent=1))
    if args.check and bad:
        print("REFUSED: no permissive license declared for %s" % ", ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
