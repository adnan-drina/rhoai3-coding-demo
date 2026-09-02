#!/usr/bin/env python3
"""FAIL unless inventory scan root equals harvest_referent from the manifest.

Operator 190422ZO / W4: both M1 scanners take the same harvest_referent.
Hardcoded /projects/legacy against a derived tree is REFUSE.

Exit 0: roots agree (realpath).
Exit 1: missing files, missing harvest_referent, or roots differ.
Exit 2: --require-boot2-derivation on mode=identity (cannot close W4 on
gs-rest). Usage errors also 2.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fail(msg: str, rc: int = 1) -> int:
    print("REFUSE: harvest-referent pair: " + msg, file=sys.stderr)
    return rc


def load_manifest(root: Path) -> tuple[dict | None, str]:
    path = root / "evidence" / "derived" / "legacy-at-3.json"
    if not path.is_file():
        return None, "missing evidence/derived/legacy-at-3.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, "unreadable legacy-at-3.json: %s" % exc
    if not isinstance(doc, dict):
        return None, "legacy-at-3.json is not an object"
    return doc, ""


def harvest_referent_dir(root: Path, manifest: dict) -> Path | None:
    raw = str(manifest.get("harvest_referent") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    return p


def inventory_root(root: Path) -> tuple[Path | None, str]:
    path = root / "evidence" / "entry-point-inventory.json"
    if not path.is_file():
        return None, "missing evidence/entry-point-inventory.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, "unreadable entry-point-inventory.json: %s" % exc
    if not isinstance(doc, dict):
        return None, "entry-point-inventory.json is not an object"
    raw = str(doc.get("root") or "").strip()
    if not raw:
        return None, "inventory missing root"
    p = Path(raw)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    return p, ""


def check(root: Path, require_boot2: bool) -> int:
    manifest, err = load_manifest(root)
    if manifest is None:
        return _fail(err)
    harvest = harvest_referent_dir(root, manifest)
    if harvest is None:
        return _fail(
            "missing harvest_referent in evidence/derived/legacy-at-3.json "
            "(do not guess /projects/legacy)"
        )
    inv, err = inventory_root(root)
    if inv is None:
        return _fail(err)
    if harvest != inv:
        return _fail(
            "inventory root %s != harvest_referent %s" % (inv, harvest)
        )
    mode = str(manifest.get("mode") or "").strip()
    if require_boot2:
        if mode == "identity":
            print(
                "INCONCLUSIVE: mode=identity cannot close W4-boot2-pair "
                "(petclinic derivation only; not gs-rest)",
                file=sys.stderr,
            )
            return 2
        if mode != "derived":
            return _fail("mode=%r is not derived (W4 boot2 pair)" % mode)
    print(
        "OK: harvest-referent pair mode=%s root=%s" % (mode or "?", harvest)
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--require-boot2-derivation",
        action="store_true",
        help="INCONCLUSIVE (2) when mode=identity; do not close W4 on gs-rest",
    )
    args = ap.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print("usage: assert-harvest-referent-pair.py <dest-root>", file=sys.stderr)
        return 2
    return check(root.resolve(), args.require_boot2_derivation)


if __name__ == "__main__":
    sys.exit(main())
