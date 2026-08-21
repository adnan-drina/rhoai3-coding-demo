#!/usr/bin/env python3
"""V35-GEN-POST — dest-only generator configuration after write.

Ownership of a spec path is not configuration. Parse the dest build file
named in this story's write-set with parse_generator_plugins. Do not call
generator_input_paths() or iter_build_files() (those union legacy).

Trigger:
  - this body owns a generator spec path, or
  - this body owns pom.xml and the partition/type-inventory has generated types.

Require a generator plugin whose inputSpec matches the owned spec when a
spec is in the write-set; otherwise require a generator plugin with a
non-empty inputSpec.

Usage:
  python3 assert-dest-generator-configured.py <root> --body evidence/bodies/m3-setup.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from generated_sources import parse_generator_plugins

PLUGIN_BLOCK_RE = re.compile(r"<plugin>(.*?)</plugin>", re.S | re.I)
ARTIFACT_RE = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>", re.I)

REQUIRED_LIBRARY = "native"
REQUIRED_USE_JAKARTA_EE = "true"
REQUIRED_SERIALIZATION = "jackson"
REQUIRED_PLUGIN_CONFIGURATION = (
    "<configuration>\n"
    "  <inputSpec>PATH_TO_SPEC</inputSpec>\n"
    "  <modelPackage>DEST_MODEL_PACKAGE</modelPackage>\n"
    f"  <library>{REQUIRED_LIBRARY}</library>\n"
    "  <configOptions>\n"
    f"    <useJakartaEe>{REQUIRED_USE_JAKARTA_EE}</useJakartaEe>\n"
    f"    <serializationLibrary>{REQUIRED_SERIALIZATION}</serializationLibrary>\n"
    "  </configOptions>\n"
    "</configuration>"
)


def _jackson_jakarta_native_errors(pom_text: str) -> list[str]:
    """Refuse Gson / non-Jakarta / non-native library on the generator plugin."""
    errs: list[str] = []
    for block in PLUGIN_BLOCK_RE.findall(pom_text or ""):
        am = ARTIFACT_RE.search(block)
        aid = (am.group(1).strip() if am else "").lower()
        if "openapi-generator" not in aid:
            continue
        blob = block.lower()
        if "gson" in blob and "jackson" not in blob:
            errs.append("gson")
        if not re.search(
            rf"<library>\s*{re.escape(REQUIRED_LIBRARY)}\s*</library>",
            block,
            re.I,
        ):
            errs.append(f"library!={REQUIRED_LIBRARY}")
        if not re.search(
            rf"<useJakartaEe>\s*{re.escape(REQUIRED_USE_JAKARTA_EE)}\s*</useJakartaEe>",
            block,
            re.I,
        ):
            errs.append(f"useJakartaEe!={REQUIRED_USE_JAKARTA_EE}")
    return errs

SPEC_NAMES = ("api-docs.yml", "api-docs.yaml", "openapi.yml", "openapi.yaml", "openapi.json")


def _rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _is_spec(path: str) -> bool:
    n = Path(_rel(path)).name.lower()
    if n in SPEC_NAMES:
        return True
    return n.endswith((".yml", ".yaml", ".json")) and any(
        tok in n for tok in ("api-docs", "openapi", "swagger")
    )


def _is_pom(path: str) -> bool:
    p = _rel(path)
    return p == "pom.xml" or p.endswith("/pom.xml")


def _writable(body: dict) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = body.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(raw, list):
        return []
    return [_rel(x) for x in raw if isinstance(x, str) and x.strip()]


def _inner(doc: dict) -> dict:
    body = doc.get("body") if isinstance(doc.get("body"), dict) else doc
    return body if isinstance(body, dict) else {}


def _generated_present(root: Path) -> bool:
    inv = root / "evidence" / "type-inventory.json"
    if inv.is_file():
        try:
            data = json.loads(inv.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        rows = data if isinstance(data, list) else (data or {}).get("types") or []
        if isinstance(rows, list):
            for rec in rows:
                if isinstance(rec, dict) and (
                    rec.get("generated") is True
                    or str(rec.get("provider") or "") == "generated"
                ):
                    return True
    part = root / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        return False
    try:
        pdata = json.loads(part.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for story in pdata.get("stories") or []:
        if not isinstance(story, dict):
            continue
        for rec in story.get("types") or []:
            if isinstance(rec, dict) and str(rec.get("provider") or "") == "generated":
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument(
        "--require-plugin",
        action="store_true",
        help="Force the generator case when M1 required-extensions names the plugin",
    )
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
    writes = _writable(body)
    specs = [p for p in writes if _is_spec(p)]
    poms = [p for p in writes if _is_pom(p)]
    trigger = (
        bool(specs)
        or (bool(poms) and _generated_present(root))
        or bool(args.require_plugin)
    )
    if not trigger:
        print("OK: dest-generator skip (no owned spec / no pom+generated)")
        return 0
    if not poms:
        print(
            "REFUSE: DEST_GENERATOR this body triggered GEN-POST but pom.xml "
            "is not in files_writable (do not parse legacy)",
            file=sys.stderr,
        )
        return 1
    pom_rel = poms[0]
    pom_path = root / pom_rel
    if not pom_path.is_file():
        print(
            f"REFUSE: DEST_GENERATOR dest build file missing {pom_rel}",
            file=sys.stderr,
        )
        return 1
    plugins = parse_generator_plugins(pom_path.read_text(encoding="utf-8", errors="ignore"))
    if not plugins:
        print(
            f"REFUSE: DEST_GENERATOR dest {pom_rel} has no generator plugin "
            "(ownership is not configuration; do not union legacy poms). "
            "Required block:\n"
            + REQUIRED_PLUGIN_CONFIGURATION,
            file=sys.stderr,
        )
        return 1
    pom_text = pom_path.read_text(encoding="utf-8", errors="ignore")
    recipe_errs = _jackson_jakarta_native_errors(pom_text)
    if recipe_errs:
        print(
            "REFUSE: DEST_GENERATOR dest plugin recipe "
            + ",".join(recipe_errs)
            + " (Quarkus 3 / Jakarta / Jackson; library="
            + REQUIRED_LIBRARY
            + "). Required block:\n"
            + REQUIRED_PLUGIN_CONFIGURATION,
            file=sys.stderr,
        )
        return 1
    if specs:
        owned = {_rel(s) for s in specs}
        matched = False
        for rec in plugins:
            for spec in rec.get("input_specs") or []:
                if _rel(str(spec)) in owned:
                    matched = True
                    break
            if matched:
                break
        if not matched:
            print(
                "REFUSE: DEST_GENERATOR dest plugin inputSpec does not match "
                f"owned spec {sorted(owned)}",
                file=sys.stderr,
            )
            return 1
    else:
        if not any(rec.get("input_specs") for rec in plugins):
            print(
                "REFUSE: DEST_GENERATOR dest plugin has no inputSpec",
                file=sys.stderr,
            )
            return 1
    print(f"OK: dest-generator configured in {pom_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
