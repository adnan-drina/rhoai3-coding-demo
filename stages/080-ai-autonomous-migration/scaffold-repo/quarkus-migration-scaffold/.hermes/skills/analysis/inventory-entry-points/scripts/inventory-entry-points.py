#!/usr/bin/env python3
"""Entry-point inventory scanner (W2 §11.3).

Derives the referent's entry points: anything that initiates execution without
being called by other application code — HTTP handlers, @Scheduled methods,
message listeners, lifecycle hooks, CLI runners.

Output is digest-friendly JSON. A successful run always records execution
evidence even when the inventory is near-empty (ship anyway).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

HTTP_ANN = re.compile(
    r"@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|"
    r"PatchMapping|RestController|Controller|Path)\b"
)
HTTP_METHOD_ANN = re.compile(
    r"@(?:Get|Post|Put|Delete|Patch|Head|Options|GET|POST|PUT|DELETE|PATCH)\b"
)
NON_HTTP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("lifecycle", re.compile(r"@(?:PostConstruct|PreDestroy)\b")),
    ("scheduled", re.compile(r"@Scheduled\b")),
    ("messaging", re.compile(r"@(?:KafkaListener|RabbitListener|JmsListener|MessageDriven)\b")),
    ("cli", re.compile(r"\b(?:CommandLineRunner|ApplicationRunner)\b")),
    ("event", re.compile(r"@EventListener\b")),
]

SKIP_DIR_NAMES = {
    "target",
    "build",
    ".git",
    "node_modules",
    ".derived",
    "fixtures",
}


@dataclass
class EntryPoint:
    kind: str
    subtype: str
    file: str
    line: int
    symbol: str
    evidence: str


def iter_java(root: Path):
    root = root.resolve()
    for p in root.rglob("*.java"):
        # Skip only relative to the scan root. Absolute parts must not apply:
        # harvest_referent lives under /projects/.derived/… and ".derived" is
        # in SKIP_DIR_NAMES (clean-room M1 finding 2026-08-09).
        try:
            rel = p.resolve().relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        yield p


def enclosing_symbol(lines: list[str], idx: int) -> str:
    for j in range(idx, -1, -1):
        m = re.search(
            r"\b(?:class|interface|enum|record)\s+(\w+)",
            lines[j],
        )
        if m:
            class_name = m.group(1)
            # method if annotation sits on a method
            for k in range(idx, min(idx + 6, len(lines))):
                mm = re.search(
                    r"\b(?:public|protected|private|static|final|void|[\w<>\[\],\s]+)\s+(\w+)\s*\(",
                    lines[k],
                )
                if mm and mm.group(1) not in {"if", "for", "while", "switch", "catch"}:
                    return f"{class_name}#{mm.group(1)}"
            return class_name
    return "<unknown>"


def scan_file(path: Path, root: Path) -> list[EntryPoint]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rel = str(path.relative_to(root))
    found: list[EntryPoint] = []
    seen: set[tuple[int, str]] = set()

    for i, line in enumerate(lines):
        if HTTP_ANN.search(line) or HTTP_METHOD_ANN.search(line):
            # Prefer method-level HTTP mappings; class-level @RestController alone
            # is not an entry point without a mapping.
            if re.search(r"@RestController\b|@Controller\b", line) and not re.search(
                r"@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|Path)\b",
                line,
            ):
                continue
            # F11 / Architect E-20260811T070235Z: type-level @RequestMapping/@Path
            # path prefixes are not independently callable handlers (counting
            # them inflated the reference measurement 42→34). Keep method-level
            # Get/Post/… and method @RequestMapping.
            if re.search(r"@(?:RequestMapping|Path)\b", line) and not re.search(
                r"@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\b",
                line,
            ):
                type_level = False
                for j in range(i + 1, min(i + 12, len(lines))):
                    nxt = lines[j]
                    if re.search(
                        r"^\s*(public\s+|protected\s+|private\s+)?(class|interface|enum)\b",
                        nxt,
                    ):
                        type_level = True
                        break
                    if re.search(
                        r"^\s*(public|protected|private|static).+\(.*\).*\{?\s*$",
                        nxt,
                    ):
                        break
                if type_level:
                    continue
            key = (i + 1, "http")
            if key in seen:
                continue
            seen.add(key)
            found.append(
                EntryPoint(
                    kind="http",
                    subtype="spring-mvc-or-jaxrs",
                    file=rel,
                    line=i + 1,
                    symbol=enclosing_symbol(lines, i),
                    evidence=line.strip()[:200],
                )
            )
        for subtype, pat in NON_HTTP_PATTERNS:
            if pat.search(line):
                key = (i + 1, subtype)
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    EntryPoint(
                        kind="non-http",
                        subtype=subtype,
                        file=rel,
                        line=i + 1,
                        symbol=enclosing_symbol(lines, i),
                        evidence=line.strip()[:200],
                    )
                )
    return found


def sha256_file_list(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x)):
        h.update(str(p).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Source tree to scan (legacy@3.x or specimen root)",
    )
    ap.add_argument(
        "-o",
        "--output",
        default="evidence/entry-point-inventory.json",
        help="Output JSON path (relative to cwd unless absolute)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"inventory-entry-points: not a directory: {root}", file=sys.stderr)
        return 2

    java_files = list(iter_java(root))
    entries: list[EntryPoint] = []
    for jf in java_files:
        entries.extend(scan_file(jf, root))

    entries.sort(key=lambda e: (e.kind, e.subtype, e.file, e.line))
    out = {
        "schema": "rhoai3.entry-point-inventory/v1",
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(root),
        "execution_evidence": {
            "scanner": "inventory-entry-points.py",
            "java_files_seen": len(java_files),
            "inputs_digest_sha256": sha256_file_list(java_files) if java_files else "",
            "ran": True,
        },
        "counts": {
            "total": len(entries),
            "http": sum(1 for e in entries if e.kind == "http"),
            "non_http": sum(1 for e in entries if e.kind == "non-http"),
            "by_subtype": {},
        },
        "entry_points": [asdict(e) for e in entries],
    }
    by_sub: dict[str, int] = {}
    for e in entries:
        by_sub[e.subtype] = by_sub.get(e.subtype, 0) + 1
    out["counts"]["by_subtype"] = by_sub

    # Vacuity: zero files means the scan did not have inputs — INCONCLUSIVE for
    # consumers; we still write evidence that the scanner ran.
    if len(java_files) == 0:
        out["execution_evidence"]["vacuous"] = "zero_java_files"
    else:
        out["execution_evidence"]["vacuous"] = False

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: {out['counts']['total']} entry points "
        f"({out['counts']['http']} http, {out['counts']['non_http']} non-http) → {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
