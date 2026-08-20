#!/usr/bin/env python3
"""V35-EXTENSIONS — dest pom declares every required artifactId.

One dest-only predicate. Missing hibernate-orm, hibernate-validator, and
the OpenAPI generator plugin are the same defect: setup wrote an
under-specified pom. Do not call generator_input_paths() / iter_build_files()
(those union legacy).

Required set = identity.extensions_apply ∪ evidence/required-extensions.json.
If findings-handoff exists and required-extensions.json is missing, refuse
(M1 did not emit). Generator inputSpec matching is a case of this check
(assert-dest-generator-configured.py), not a sibling complete-path gate.

Usage:
  python3 assert-dest-pom-extensions.py <root> --body evidence/bodies/m3-setup.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from generated_sources import ARTIFACT_RE
from specimen_agnostic import load_required_extension_entries, writes_pom_xml

GENERATOR_AID = "openapi-generator-maven-plugin"
PLUGIN_BLOCK_RE = re.compile(r"<plugin>(.*?)</plugin>", re.S | re.I)
DEP_BLOCK_RE = re.compile(r"<dependency>(.*?)</dependency>", re.S | re.I)


def _rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _inner(doc: dict) -> dict:
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    return body if isinstance(body, dict) else {}


def _writable(body: dict) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = body.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(raw, list):
        return []
    return [_rel(x) for x in raw if isinstance(x, str) and x.strip()]


def _is_pom(path: str) -> bool:
    p = _rel(path)
    return p == "pom.xml" or p.endswith("/pom.xml")


def _apply(body: dict) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = ident.get("extensions_apply") if isinstance(ident, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip() and ":" not in item and "/" not in item:
            out.append(item.strip())
    return out


def dest_artifact_ids(text: str) -> set[str]:
    return {m.strip() for m in ARTIFACT_RE.findall(text or "") if m.strip()}


def dest_dependency_ids(text: str) -> set[str]:
    found: set[str] = set()
    for block in DEP_BLOCK_RE.findall(text or ""):
        found.update(m.strip() for m in ARTIFACT_RE.findall(block) if m.strip())
    return found


def dest_plugin_ids(text: str) -> set[str]:
    found: set[str] = set()
    for block in PLUGIN_BLOCK_RE.findall(text or ""):
        found.update(m.strip() for m in ARTIFACT_RE.findall(block) if m.strip())
    return found


def _run_dest_generator(root: Path, body_path: Path, *, require_plugin: bool) -> int:
    script = Path(__file__).resolve().parent / "assert-dest-generator-configured.py"
    if not script.is_file():
        print(f"FAIL: missing dest-generator helper {script}", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(script), str(root), "--body", str(body_path)]
    if require_plugin:
        cmd.append("--require-plugin")
    sub = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(sub.stdout or "")
    sys.stderr.write(sub.stderr or "")
    return sub.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: missing body {args.body}", file=sys.stderr)
        return 1
    try:
        doc = json.loads(body_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: body {body_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(doc, dict):
        print(f"FAIL: body {body_path} is not an object", file=sys.stderr)
        return 1
    body = _inner(doc)
    handoff = root / "evidence" / "findings-handoff.json"
    required_file = root / "evidence" / "required-extensions.json"
    if handoff.is_file() and not required_file.is_file():
        print(
            "REFUSE: DEST_EXTENSIONS findings-handoff present but "
            "evidence/required-extensions.json missing (M1 must emit)",
            file=sys.stderr,
        )
        return 1
    m1_entries = load_required_extension_entries(root)
    m1 = [e["artifactId"] for e in m1_entries]
    wanted = sorted(set(_apply(body)) | set(m1))
    kind_by_aid = {e["artifactId"]: e["kind"] for e in m1_entries}
    writes = _writable(body)
    poms = [p for p in writes if _is_pom(p)]
    owns_pom = bool(poms) or writes_pom_xml(body)
    if owns_pom:
        pom_rel = poms[0] if poms else "pom.xml"
        pom_path = root / pom_rel
        if not pom_path.is_file():
            print(
                f"REFUSE: DEST_EXTENSIONS dest build file missing {pom_rel}",
                file=sys.stderr,
            )
            return 1
        pom_text = pom_path.read_text(encoding="utf-8", errors="ignore")
        dest_ids = dest_artifact_ids(pom_text)
        missing = [aid for aid in wanted if aid not in dest_ids]
        if missing:
            print(
                "REFUSE: DEST_EXTENSIONS dest pom missing "
                f"{missing} (do not union legacy; Java count is irrelevant)",
                file=sys.stderr,
            )
            return 1
        deps = dest_dependency_ids(pom_text)
        plugins = dest_plugin_ids(pom_text)
        for aid in wanted:
            kind = kind_by_aid.get(
                aid,
                "plugin" if aid == GENERATOR_AID else "extension",
            )
            if kind == "plugin" and aid not in plugins:
                print(
                    "REFUSE: DEST_EXTENSIONS "
                    f"{aid} kind=plugin must be a <plugin>, not a <dependency>",
                    file=sys.stderr,
                )
                return 1
            if kind == "extension" and aid not in deps:
                print(
                    "REFUSE: DEST_EXTENSIONS "
                    f"{aid} kind=extension must be a <dependency>, not only a <plugin>",
                    file=sys.stderr,
                )
                return 1
        print(f"OK: dest pom declares required extensions in {pom_rel}")
    elif wanted:
        print(
            "OK: DEST_EXTENSIONS skip pom parse (this body does not write pom.xml)"
        )
    else:
        print("OK: DEST_EXTENSIONS skip (no pom writer / empty required set)")

    require_plugin = GENERATOR_AID in wanted
    gen_rc = _run_dest_generator(root, body_path, require_plugin=require_plugin)
    if gen_rc != 0:
        return gen_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
