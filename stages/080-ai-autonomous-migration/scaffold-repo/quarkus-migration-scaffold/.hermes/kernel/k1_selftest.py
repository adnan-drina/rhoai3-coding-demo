#!/usr/bin/env python3
"""K1 land-time selftest. Not pytest. Run from anywhere: python3 k1_selftest.py"""
from __future__ import annotations

import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k1_load import digest_file, load_body, stamp_sidecar  # noqa: E402
from k1_validate import validate_body, validate_file  # noqa: E402


def main() -> int:
    good = KERNEL / "fixtures" / "valid-m3.json"
    bad = KERNEL / "fixtures" / "bad-hermes-id.json"
    body = load_body(good)
    issues = validate_body(body, root=None)
    codes = {c for c, _, _ in issues}
    # No file digest checks without root files; type-inventory key is present.
    if "BODY_SCHEMA" in codes or "BODY_HERMES_ID" in codes or "BODY_SCOPE" in codes:
        print("FAIL: valid fixture hit schema/scope/hermes-id", issues, file=sys.stderr)
        return 1
    if "BODY_REF_MISSING" in codes:
        print("FAIL: valid fixture missing type-inventory", issues, file=sys.stderr)
        return 1
    if "test-compile" in good.read_text(encoding="utf-8"):
        print(
            "FAIL: valid-m3.json carries refused test-compile exit "
            "(Lead:valid-m3-fixture-carries-a-refused-exit)",
            file=sys.stderr,
        )
        return 1

    bad_issues = validate_file(bad, root=None)
    bad_codes = {c for c, _, _ in bad_issues}
    need = {"BODY_HERMES_ID", "BODY_GENERATED", "BODY_REF_MISSING", "BODY_SCOPE", "BODY_EXIT"}
    missing = need - bad_codes
    if missing:
        print("FAIL: bad fixture missed codes %s got %s" % (missing, bad_codes), file=sys.stderr)
        return 1
    # Full-gap: more than one code (not first-fail).
    if len(bad_codes) < 4:
        print("FAIL: expected full gap set, got %s" % bad_codes, file=sys.stderr)
        return 1

    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp(prefix="k1-selftest-"))
    try:
        copy = tmp / "valid-m3.json"
        shutil.copy2(good, copy)
        digest = stamp_sidecar(copy)
        if digest != digest_file(copy):
            print("FAIL: sidecar stamp", file=sys.stderr)
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: K1 selftest (%d codes on bad fixture)" % len(bad_codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
