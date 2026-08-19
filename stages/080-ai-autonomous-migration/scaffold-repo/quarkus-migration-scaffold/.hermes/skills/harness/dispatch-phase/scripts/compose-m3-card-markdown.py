#!/usr/bin/env python3
"""Emit M3 story card markdown from a typed body (holder never json.loads).

Operator E-20260819T173800Z / Lead E-20260819T173600Z: dumping
files_writable / kanban show --json into the holder caused a reconstruct
and batch spiral. This script prints title (--print-title) or F6 markdown
(default). Pointer to the typed body when the writable list would exceed
the 1500-char budget.

Usage:
  python3 compose-m3-card-markdown.py --root . --body evidence/bodies/m3-setup.json
  python3 compose-m3-card-markdown.py --root . --body evidence/bodies/m3-setup.json --print-title
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CARD_BUDGET = 1500
STANDING = (
    ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md"
)
DIGEST_SCRIPT = (
    ".hermes/skills/harness/record-run-evidence/scripts/"
    "check-body-digest-match.py"
)
PRECOMPLETE = (
    ".hermes/skills/gates/check-release-readiness/scripts/"
    "assert-complete-exit-criteria.py"
)


def load_obj(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("body"), dict):
        return raw["body"]
    if not isinstance(raw, dict):
        raise ValueError("body is not an object")
    return raw


def story_id_of(body: dict, body_path: Path) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    sid = str(ident.get("story_id") or "").strip()
    if sid:
        return sid
    stem = body_path.stem
    if stem.startswith("m3-"):
        return stem[3:]
    return stem


def heading_of(root: Path, story_id: str) -> str:
    part = root / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        return ""
    try:
        doc = json.loads(part.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    stories = doc.get("stories") or []
    if not isinstance(stories, list):
        return ""
    sid_l = story_id.lower()
    for st in stories:
        if not isinstance(st, dict):
            continue
        ident = st.get("identity") if isinstance(st.get("identity"), dict) else {}
        sid = str(st.get("story_id") or ident.get("story_id") or "").strip()
        if sid.lower() != sid_l:
            continue
        return str(st.get("heading") or st.get("title") or "").strip()
    return ""


def description_from_heading(story_id: str, heading: str) -> str:
    text = heading.strip()
    if not text:
        return ""
    text = re.sub(r"\s*\(Priority:\s*[^)]*\)\s*$", "", text, flags=re.I)
    m = re.match(r"^US(\d+)$", story_id, re.I)
    if m:
        text = re.sub(
            rf"^User Story {m.group(1)}\s*[-–—:]\s*",
            "",
            text,
            flags=re.I,
        )
    if text.lower().startswith(story_id.lower()):
        text = text[len(story_id) :].strip()
        text = text.lstrip(":-&—– ").strip()
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)
    text = text.strip(" \t:-&")
    if text.startswith("(") and text.endswith(")") and text.count("(") == 1:
        text = text[1:-1].strip()
    return text


def card_title(story_id: str, heading: str) -> str:
    desc = description_from_heading(story_id, heading)
    if desc:
        return f"M3 IMPLEMENT: {story_id} — {desc}"
    return f"M3 IMPLEMENT: {story_id}"


def sidecar_digest(body_path: Path) -> str:
    side = body_path.with_suffix(body_path.suffix + ".sha256.json")
    if not side.is_file():
        raise FileNotFoundError(
            f"missing sidecar {side.name}; run stamp-body-digest first"
        )
    doc = json.loads(side.read_text(encoding="utf-8"))
    digest = str(doc.get("body_sha256") or "").strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"sidecar body_sha256 is not 64-hex: {side}")
    return digest


def max_runtime(root: Path) -> str:
    script = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "scripts"
        / "read-phase-dispatch.py"
    )
    yaml_path = root / ".hermes" / "phase-dispatch.yaml"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--yaml",
            str(yaml_path),
            "--phase",
            "M3",
            "--print",
            "max_runtime_seconds",
        ],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(
            (cp.stderr or cp.stdout or "read-phase-dispatch failed").strip()
        )
    val = (cp.stdout or "").strip().splitlines()[0] if cp.stdout else ""
    if not val.isdigit():
        raise RuntimeError("max_runtime_seconds missing")
    return val


def path_strs(items: object) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for k in ("dest", "dst", "destination", "path", "file"):
                if item.get(k):
                    out.append(str(item[k]).strip())
                    break
    return out


def compose_markdown(
    *,
    story_id: str,
    body_rel: str,
    digest: str,
    exits: list[str],
    writables: list[str],
    runtime: str,
) -> str:
    header = (
        f"Typed body: {body_rel}\n"
        f"AR-4.3 digest: {digest}\n"
        f"Verify: python3 {DIGEST_SCRIPT} --expect {digest} --body {body_rel} .\n"
        f"  mismatch ⇒ REFUSE\n"
        f"Standing: {STANDING}\n"
        f"Pre-complete: python3 {PRECOMPLETE} . --body {body_rel}\n"
    )
    constraints = (
        "## Constraints\n"
        "- workspace: dir:/projects/modernized\n"
        f"- Do not re-plan. max-runtime: {runtime}. AD-008. AD-002E.\n"
    )
    exit_block = "## Exit Criteria\n"
    if exits:
        exit_block += "".join(f"- {e}\n" for e in exits)
    else:
        exit_block += "- see typed body\n"

    def with_files(files_block: str) -> str:
        return header + exit_block + files_block + constraints

    listed = "## Files Writable\n" + "".join(f"- {p}\n" for p in writables)
    text = with_files(listed)
    if len(text) <= CARD_BUDGET:
        return text
    pointer = f"## Files Writable\n- see typed body ({len(writables)} paths)\n"
    text = with_files(pointer)
    if len(text) <= CARD_BUDGET:
        return text
    raise ValueError(f"F6 card budget exceeded ({len(text)} > {CARD_BUDGET})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--print-title", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"REFUSE: missing body {args.body}", file=sys.stderr)
        return 1
    try:
        body = load_obj(body_path)
        sid = story_id_of(body, body_path)
        heading = heading_of(root, sid)
        title = card_title(sid, heading)
        if args.print_title:
            print(title)
            return 0
        digest = sidecar_digest(body_path)
        try:
            rel = str(body_path.resolve().relative_to(root))
        except ValueError:
            rel = str(args.body)
        runtime = max_runtime(root)
        md = compose_markdown(
            story_id=sid,
            body_rel=rel,
            digest=digest,
            exits=[str(x).strip() for x in (body.get("exit_criteria") or []) if str(x).strip()],
            writables=path_strs(body.get("files_writable")),
            runtime=runtime,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"REFUSE: {exc}", file=sys.stderr)
        return 1
    if md.lstrip()[:1] in "{[":
        print("REFUSE: composer leaked JSON", file=sys.stderr)
        return 1
    print(md, end="" if md.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
