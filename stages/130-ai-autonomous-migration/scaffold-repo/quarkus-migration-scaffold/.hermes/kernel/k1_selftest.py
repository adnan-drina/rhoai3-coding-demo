#!/usr/bin/env python3
"""K1 land-time selftest. Not pytest. Run from anywhere: python3 k1_selftest.py"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k1_load import digest_file, load_body, stamp_sidecar  # noqa: E402
from k1_validate import validate_body, validate_file  # noqa: E402


def _codes(issues) -> set[str]:
    return {c for c, _, _ in issues}


def main() -> int:
    good = KERNEL / "fixtures" / "valid-m3.json"
    bad = KERNEL / "fixtures" / "bad-hermes-id.json"
    body = load_body(good)
    codes = _codes(validate_body(body, root=None))
    if codes & {"BODY_SCHEMA", "BODY_HERMES_ID", "BODY_SCOPE", "BODY_REF_MISSING", "BODY_RECEIPT", "BODY_INCREMENT", "BODY_WRITE_SET", "BODY_ARTIFACTS", "BODY_PROSE"}:
        print("FAIL: valid fixture hit %s" % codes, file=sys.stderr)
        return 1
    if "test-compile" in good.read_text(encoding="utf-8"):
        print("FAIL: valid-m3.json carries refused test-compile exit", file=sys.stderr)
        return 1

    bad_codes = _codes(validate_file(bad, root=None))
    need = {"BODY_HERMES_ID", "BODY_GENERATED", "BODY_REF_MISSING", "BODY_SCOPE", "BODY_EXIT", "BODY_INCREMENT", "BODY_RECEIPT"}
    missing = need - bad_codes
    if missing:
        print("FAIL: bad fixture missed codes %s got %s" % (missing, bad_codes), file=sys.stderr)
        return 1
    if len(bad_codes) < 5:
        print("FAIL: expected full gap set, got %s" % bad_codes, file=sys.stderr)
        return 1

    # increment-specific negatives on the valid body
    b = json.loads(good.read_text(encoding="utf-8"))
    b["receipt_sha256"] = "not-a-digest"
    if "BODY_RECEIPT" not in _codes(validate_body(b)):
        print("FAIL: bad receipt digest must BODY_RECEIPT", file=sys.stderr)
        return 1
    b = json.loads(good.read_text(encoding="utf-8"))
    b["files_writable"] = ["src/main/java/com/demo/owner/OwnerController.java", "src/main/java/com/demo/Extra.java"]
    if "BODY_WRITE_SET" not in _codes(validate_body(b)):
        print("FAIL: files_writable wider than write_set must BODY_WRITE_SET", file=sys.stderr)
        return 1
    b = json.loads(good.read_text(encoding="utf-8"))
    b["artifacts"] = b["artifacts"][:1]
    if "BODY_ARTIFACTS" not in _codes(validate_body(b)):
        print("FAIL: one artifact must BODY_ARTIFACTS", file=sys.stderr)
        return 1
    b = json.loads(good.read_text(encoding="utf-8"))
    b["worklist_sha256"] = "nope"
    b["attempt"] = 0
    if "BODY_INCREMENT" not in _codes(validate_body(b)):
        print("FAIL: bad worklist digest / attempt must BODY_INCREMENT", file=sys.stderr)
        return 1
    b = json.loads(good.read_text(encoding="utf-8"))
    b["nodes"] = []
    b["identity"]["codeSnip"] = "x"
    if "BODY_PROSE" not in _codes(validate_body(b)):
        print("FAIL: inlined graph/prose must BODY_PROSE", file=sys.stderr)
        return 1
    b = json.loads(good.read_text(encoding="utf-8"))
    b["increment_kind"] = "capability"
    if "BODY_INCREMENT" not in _codes(validate_body(b)):
        print("FAIL: unknown increment kind must BODY_INCREMENT", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="k1-selftest-"))
    try:
        copy = tmp / "valid-m3.json"
        shutil.copy2(good, copy)
        if stamp_sidecar(copy) != digest_file(copy):
            print("FAIL: sidecar stamp", file=sys.stderr)
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: K1 selftest (%d codes on bad fixture; receipt/write-set/artifacts/prose negatives)" % len(bad_codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
