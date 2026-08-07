#!/usr/bin/env python3
"""K8 — Maven Central GAV advisory (WARN never hard RED).

Usage: verify-dep.py <groupId> <artifactId> [version]
Exit 0 always (offline / unknown → WARN). Prints OK: or WARN: lines.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: verify-dep.py <groupId> <artifactId> [version]", file=sys.stderr)
        return 2
    g, a = sys.argv[1], sys.argv[2]
    ver = sys.argv[3] if len(sys.argv) > 3 else None
    q = f"g:{g} AND a:{a}"
    if ver:
        q += f" AND v:{ver}"
    url = (
        "https://search.maven.org/solrsearch/select?"
        + urllib.parse.urlencode({"q": q, "rows": "5", "wt": "json"})
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        print(f"WARN:verify-dep unreachable ({e}) — factory resolution is authority")
        return 0
    docs = (data.get("response") or {}).get("docs") or []
    if not docs:
        print(f"WARN:verify-dep unknown coordinates {g}:{a}" + (f":{ver}" if ver else ""))
        return 0
    versions = []
    for d in docs[:5]:
        v = d.get("latestVersion") or d.get("v") or "?"
        versions.append(str(v))
    print(f"OK:verify-dep {g}:{a} known (e.g. {', '.join(versions)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
