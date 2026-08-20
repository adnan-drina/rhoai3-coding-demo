#!/usr/bin/env python3
"""AD-H §16.5 / AR-1.1 — refuse worker self-ACK as stage authority.

Scans evidence/acks/*.{json,yaml,yml,ack.yaml,...}.
Fail closed when an acknowledged ack is authored by a worker role, lacks
task_id / digests, or is a bare .json grant without authenticated signer.

Human unlock/lock around real ACK remains F2 residual.

Usage:
  python3 check-ack-authority.py                 # scan the current directory
  python3 check-ack-authority.py /path/to/repo   # explicit workspace root
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — every acknowledged grant carries non-worker signer, task_id and
     digests; or lint idle (no evidence/acks dir, no grant files, or no
     acknowledged grants to validate)
  1  BLOCK — at least one FAIL: line on stderr (parse error, worker/self ACK
     author, missing task_id, missing artifact_digests, or a bare .json grant)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""

WORKER_AUTHORS = frozenset(
    {
        "planner",
        "spec-author",
        "spec_author",
        "implementer",
        "evidence-analyst",
        "evidence_analyst",
        "reviewer",  # reviewer may request; not grant human ACK
        "validator",
        "default",
        "worker",
        "hermes",
        "agent",
    }
)

# 5.1 gate-records (Architect E-20260819T121859Z / Operator E-20260820T122824Z).
# Not a worker. Unknown `gate:` prefixes are refuse — do not invent a
# second envelope checker.
ALLOWED_GATE_SIGNERS = frozenset(
    {
        "gate:check-findings-handoff",
        "gate:check-body-digest-match",
    }
)


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _parse_flow_map(raw: str) -> dict[str, str]:
    s = raw.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
    out: dict[str, str] = {}
    if not s:
        return out
    for part in s.split(","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k, v = _unquote(k), _unquote(v)
        if k:
            out[k] = v
    return out


def _parse_yaml_ack(raw: str) -> dict:
    """Subset YAML for Operator acks (no PyYAML).

    Scalars, inline `{k: v}` maps, indented block maps, and list-of-maps
    (`artifact_refs:`) are enough for AR-1.1. A line-scrape of
    `artifact_digests:` missed block mappings (Deputy E-20260816T173510Z).
    """
    lines = raw.splitlines()
    doc: dict = {}
    i = 0
    n = len(lines)

    def _is_top(s: str) -> bool:
        return bool(s.strip()) and not s.startswith(" ") and not s.startswith("\t")

    while i < n:
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        if not _is_top(ln) or ":" not in ln:
            i += 1
            continue
        key, rest = ln.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if key == "artifact_digests":
            if rest.startswith("{") or (rest and ":" in rest and not rest.startswith("-")):
                doc[key] = _parse_flow_map(rest)
            else:
                mapping: dict[str, str] = {}
                i += 1
                while i < n:
                    ch = lines[i]
                    if not ch.strip() or ch.lstrip().startswith("#"):
                        i += 1
                        continue
                    if _is_top(ch):
                        i -= 1
                        break
                    if ":" in ch:
                        k, v = ch.strip().split(":", 1)
                        mapping[_unquote(k)] = _unquote(v)
                    i += 1
                doc[key] = mapping
                continue
        elif key == "artifact_refs":
            refs: list[dict[str, str]] = []
            i += 1
            cur: dict[str, str] = {}
            while i < n:
                ch = lines[i]
                if not ch.strip() or ch.lstrip().startswith("#"):
                    i += 1
                    continue
                if _is_top(ch):
                    i -= 1
                    break
                st = ch.strip()
                if st.startswith("- "):
                    if cur:
                        refs.append(cur)
                    cur = {}
                    rest2 = st[2:].strip()
                    if ":" in rest2:
                        k, v = rest2.split(":", 1)
                        cur[_unquote(k)] = _unquote(v)
                elif ":" in st:
                    k, v = st.split(":", 1)
                    cur[_unquote(k)] = _unquote(v)
                i += 1
            if cur:
                refs.append(cur)
            doc[key] = refs
            continue
        else:
            doc[key] = _unquote(rest)
        i += 1
    return doc


def load_doc(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json" or path.name.endswith(".json"):
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    return _parse_yaml_ack(raw)


def author_head(author: str) -> str:
    a = author.strip().lower()
    if not a:
        return ""
    return re.split(r"[\s(/]", a, maxsplit=1)[0]


def author_is_gate(author: str) -> bool:
    return author_head(author) in ALLOWED_GATE_SIGNERS


def author_is_unknown_gate(author: str) -> bool:
    head = author_head(author)
    return head.startswith("gate:") and head not in ALLOWED_GATE_SIGNERS


def author_is_worker(author: str) -> bool:
    a = author.strip().lower()
    if not a:
        return True
    if author_is_gate(author):
        return False
    # "planner (M2 …)" → planner
    head = author_head(author)
    if head in WORKER_AUTHORS:
        return True
    for w in WORKER_AUTHORS:
        if a == w or a.startswith(w + " ") or a.startswith(w + "("):
            return True
    return False


def has_digests(doc: dict) -> bool:
    digests = doc.get("artifact_digests") or doc.get("digests")
    if isinstance(digests, dict) and digests:
        return True
    if isinstance(digests, list) and digests:
        return True
    if isinstance(digests, str) and digests.strip() and digests.strip() not in {"{}", "[]"}:
        return True
    refs = doc.get("artifact_refs")
    if isinstance(refs, list):
        for r in refs:
            if isinstance(r, dict) and (r.get("sha256") or r.get("digest")):
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root containing evidence/acks (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    adir = root / "evidence" / "acks"
    if not adir.is_dir():
        print("OK: no evidence/acks — AR-1.1 idle")
        return 0

    paths = sorted(
        p
        for p in adir.iterdir()
        if p.is_file()
        and p.name != "README.md"
        and not p.name.startswith(".")
        and (
            "ack" in p.name.lower()
            or p.suffix in {".json", ".yaml", ".yml"}
        )
    )
    if not paths:
        print("OK: acks dir empty of grants — AR-1.1 idle")
        return 0

    bad = 0
    checked = 0
    for path in paths:
        rel = str(path.relative_to(root))
        try:
            doc = load_doc(path)
        except Exception as e:
            print(f"FAIL: {rel}: parse error {e}", file=sys.stderr)
            bad = 1
            continue
        status = str(doc.get("status") or "").lower()
        # Non-ack sidecar files (e.g. README already skipped) — skip non-ack kinds
        kind = str(doc.get("kind") or "")
        if kind and kind != "migration-ack":
            continue
        if not kind and not doc.get("ack_type") and not doc.get("acknowledged_by"):
            continue
        checked += 1
        if status and status != "acknowledged":
            continue  # not claiming advance authority
        author = str(doc.get("acknowledged_by") or "")
        if author_is_unknown_gate(author):
            print(
                f"FAIL: AR-1.1 {rel}: unknown gate signer={author!r} "
                f"— allowed {sorted(ALLOWED_GATE_SIGNERS)}",
                file=sys.stderr,
            )
            bad = 1
        elif author_is_worker(author):
            print(
                f"FAIL: AR-1.1 {rel}: worker/self ACK author={author!r} "
                f"— not stage authority",
                file=sys.stderr,
            )
            bad = 1
        task_id = str(doc.get("task_id") or doc.get("taskId") or "").strip()
        if not task_id:
            print(f"FAIL: AR-1.1 {rel}: missing task_id", file=sys.stderr)
            bad = 1
        if not has_digests(doc):
            print(
                f"FAIL: AR-1.1 {rel}: missing artifact_digests / digest-bearing refs",
                file=sys.stderr,
            )
            bad = 1
        # Bare .json without .ack. in name is a forgeable grant pattern (live defect)
        if path.suffix == ".json" and ".ack." not in path.name and "ack" not in path.stem.lower():
            print(
                f"FAIL: AR-1.1 {rel}: bare JSON grant — use *.ack.yaml with signer+digests",
                file=sys.stderr,
            )
            bad = 1

    if checked == 0:
        print("OK: no acknowledged ack grants to validate")
        return 0
    if bad:
        print(f"AR-1.1 ack authority FAILED ({checked} grant(s))", file=sys.stderr)
        return 1
    print(f"OK: AR-1.1 ack authority ({checked} grant(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
