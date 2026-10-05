#!/usr/bin/env python3
"""Assemble evidence/planning/evidence-bundle.json from M1 producer outputs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.evidence import EvidenceError  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, SCHEMAS_DIR  # noqa: E402
from planner.pipeline import assemble_bundle  # noqa: E402
from planner.schema_lite import load_schema, validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        bundle, digest = assemble_bundle(root)
    except (EvidenceError, FileNotFoundError, ValueError) as exc:
        print("FAIL: EVIDENCE_BUNDLE %s" % exc, file=sys.stderr)
        return 1
    errors = validate(bundle, load_schema(root / SCHEMAS_DIR / "evidence-bundle.schema.json"))
    if errors:
        print("FAIL: EVIDENCE_BUNDLE_SCHEMA %s" % "; ".join(errors[:8]), file=sys.stderr)
        return 1
    print("OK: evidence-bundle digest=%s types=%d entry_points=%d obligations=%d → %s" % (digest[:16], bundle["structure"]["type_count"], len(bundle["entry_points"]), len(bundle["obligations"]), EVIDENCE_BUNDLE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
