#!/usr/bin/env python3
"""K6 — findings oracle for already-complete / O-ESCW.

Exit 0 + `absent:…`  — all of the task's Findings rule ids are satisfied.
Exit 1 + `present:…` — at least one Findings rule still needs work.
Exit 3 + `no-findings` — task lists no Findings ids (other probes apply).

Snapshot preference when judging "gone from analysis":
  migration/mta-findings-current.json → mta-findings-after.json → optional argv[3]
Otherwise: before (mta-findings.json) + tree heuristics + scaffold-presatisfied.

Usage: findings-oracle.py <tasks.md> <T-xxx> [snapshot.json]
Env: ORACLE_ROOT / ALREADY_COMPLETE_ROOT
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(os.environ.get("ORACLE_ROOT", os.environ.get("ALREADY_COMPLETE_ROOT", "."))).resolve()

SPRING = re.compile(
    r"@(RestController|Service|Component|Autowired|SpringBootApplication|Configuration)\b"
)
QUARKUS = re.compile(
    r"@(ApplicationScoped|RequestScoped|Singleton|Inject|Path|RegisterRestClient)\b"
)


def task_findings(tasks: Path, tid: str) -> list[str]:
    text = tasks.read_text(encoding="utf-8", errors="replace")
    heads = list(re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M))
    body = ""
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end() : end]
        break
    if not body:
        return []
    ids: list[str] = []
    for m in re.finditer(r"(?im)^\s*-?\s*\*\*Findings\*\*:\s*(.+)$", body):
        ids.extend(re.findall(r"[a-z][a-z0-9_-]*-\d+", m.group(1), re.I))
    return list(dict.fromkeys(ids))


def load_rules(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for rs in data:
        for rid, v in (rs.get("violations") or {}).items():
            out[rid] = v
    return out


def load_presat() -> set[str]:
    out: set[str] = set()
    for base in (
        ROOT / "migration/scaffold-presatisfied.generated.txt",
        ROOT / ".hermes/harness/scaffold-presatisfied.txt",
        Path(__file__).resolve().parent / "scaffold-presatisfied.txt",
    ):
        try:
            for ln in base.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    out.add(ln)
        except OSError:
            continue
    return out


def incident_basenames(v: dict) -> list[str]:
    names = []
    for inc in v.get("incidents") or []:
        uri = unquote(inc.get("uri") or "")
        if uri.startswith("file:"):
            uri = urlparse(uri).path or uri
        base = Path(uri).name
        if base and base != "?":
            names.append(base)
    return names


def basename_in_src(name: str) -> Path | None:
    for rel in ("src/main", "src/test"):
        d = ROOT / rel
        if not d.is_dir():
            continue
        for p in d.rglob(name):
            return p
    return None


def pick_snapshot() -> tuple[dict[str, dict] | None, str]:
    if len(sys.argv) > 3:
        p = Path(sys.argv[3])
        return load_rules(p), f"explicit:{p}"
    for rel in (
        "migration/mta-findings-current.json",
        "migration/mta-findings-after.json",
    ):
        p = ROOT / rel
        if p.is_file():
            return load_rules(p), rel
    return None, "tree"


def rule_satisfied_in_tree(rid: str, v: dict, presat: set[str]) -> bool:
    if rid in presat:
        return True
    if "springboot" in rid or "javaee-pom" in rid:
        pom = ROOT / "pom.xml"
        if not pom.is_file():
            return False
        t = pom.read_text(encoding="utf-8", errors="replace")
        return "quarkus-maven-plugin" in t and "spring-boot" not in t.lower()
    bases = incident_basenames(v)
    if not bases:
        return rid in presat
    for base in bases:
        if base == "pom.xml":
            continue
        dest = basename_in_src(base)
        if dest is None:
            return False
        try:
            text = dest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if SPRING.search(text) and not QUARKUS.search(text):
            return False
    return True


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: findings-oracle.py <tasks.md> <T-xxx> [snapshot.json]", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    ids = task_findings(tasks, tid)
    if not ids:
        print("no-findings")
        return 3

    snap, mode = pick_snapshot()
    before = load_rules(ROOT / "migration/mta-findings.json")
    presat = load_presat()
    present: list[str] = []
    absent: list[str] = []

    if snap is not None and mode != "tree":
        for rid in ids:
            if rid in snap and (snap[rid].get("incidents") or []):
                present.append(rid)
            else:
                absent.append(rid)
    else:
        for rid in ids:
            v = before.get(rid) or {}
            if rule_satisfied_in_tree(rid, v, presat):
                absent.append(rid)
            else:
                present.append(rid)

    if present:
        print("present:" + ",".join(present))
        return 1
    print("absent:" + ",".join(absent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
