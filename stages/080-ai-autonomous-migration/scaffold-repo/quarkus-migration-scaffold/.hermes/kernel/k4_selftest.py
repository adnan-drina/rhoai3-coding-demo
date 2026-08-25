#!/usr/bin/env python3
"""K4 land-time selftest. Not pytest. Not dest. Not create_task."""
from __future__ import annotations

import json
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k1_validate import validate_body  # noqa: E402
from k4_convert import convert_file, validate_result  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def main() -> int:
    src = (KERNEL / "k4_convert.py").read_text(encoding="utf-8")
    schema = (KERNEL / "k4_schema.py").read_text(encoding="utf-8")
    for blob, label in ((src, "k4_convert.py"), (schema, "k4_schema.py")):
        for line in blob.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and "create_task" in stripped:
                return _fail("%s imports create_task: %s" % (label, stripped))
    if "reached_from" in src:
        return _fail("converter must not consume reached_from")

    valid = KERNEL / "fixtures" / "k4-valid-partition.json"
    result, issues = convert_file(valid)
    if issues or result is None:
        return _fail("valid partition: %s" % issues)
    created = result["manifest"]["created_cards"]
    expect = ["mint-writer", "mint-verifier", "setup", "US1", "US2"]
    if created != expect:
        return _fail("created_cards %s != %s" % (created, expect))
    by_id = {p["logical_id"]: p for p in result["payloads"]}
    us1 = json.loads(by_id["US1"]["body"])
    fw = us1["files_writable"]
    if fw != [
        "src/main/java/com/demo/service/AlphaService.java",
        "src/main/java/com/demo/resource/AlphaResource.java",
    ]:
        return _fail("US1 files_writable not copied from partition: %s" % fw)
    if us1["files_in_scope"] != fw:
        return _fail("US1 files_in_scope diverged from files_writable")
    k1_issues = validate_body(us1, root=None)
    k1_codes = {c for c, _, _ in k1_issues}
    if k1_codes & {"BODY_SCHEMA", "BODY_SCOPE", "BODY_REF_MISSING", "BODY_HERMES_ID"}:
        return _fail("US1 body failed K1: %s" % k1_issues)
    if by_id["US1"]["parents"] != ["mint-verifier", "setup"]:
        return _fail("US1 parents %s" % by_id["US1"]["parents"])
    if by_id["mint-writer"]["assignee"] != "orchestrator":
        return _fail("writer assignee")
    if by_id["setup"]["assignee"] != "implementer":
        return _fail("setup assignee")
    for sid in ("setup", "US1", "US2"):
        if by_id[sid].get("max_retries") != 1:
            return _fail("%s max_retries %s" % (sid, by_id[sid].get("max_retries")))
    if "max_retries" in by_id["mint-writer"] or "max_retries" in by_id["mint-verifier"]:
        return _fail("factory cards must not pin story max_retries")
    if result.get("claimed_control") is not False:
        return _fail("claimed_control must stay false")

    extra = KERNEL / "fixtures" / "k4-tasks-extra.md"
    _, extra_issues = convert_file(valid, tasks_path=extra)
    extra_codes = {c for c, _, _ in extra_issues}
    if "K4_PLANNING_DEFECT" not in extra_codes:
        return _fail("extra tasks.md path missed K4_PLANNING_DEFECT: %s" % extra_codes)
    detail = next(d for c, d, _ in extra_issues if c == "K4_PLANNING_DEFECT")
    if "Missing.java" not in detail:
        return _fail("planning defect did not list Missing.java: %s" % detail)

    token = KERNEL / "fixtures" / "k4-tasks-path-token.md"
    _, token_issues = convert_file(valid, tasks_path=token)
    token_codes = {c for c, _, _ in token_issues}
    if "K4_PATH_TOKEN" not in token_codes:
        return _fail("PATH_TOKEN scrape missed K4_PATH_TOKEN: %s" % token_codes)

    empty_w = KERNEL / "fixtures" / "k4-empty-writable.json"
    _, scope_issues = convert_file(empty_w)
    scope_codes = {c for c, _, _ in scope_issues}
    if "K4_SCOPE" not in scope_codes:
        return _fail("empty files_writable missed K4_SCOPE: %s" % scope_codes)

    empty_cards = validate_result(
        {"payloads": [], "manifest": {"created_cards": []}}
    )
    empty_codes = {c for c, _, _ in empty_cards}
    if "K4_CREATED_CARDS" not in empty_codes:
        return _fail("empty created_cards missed K4_CREATED_CARDS: %s" % empty_codes)

    t03 = KERNEL / "fixtures" / "k4-t0-3-shared-service.json"
    _, t03_issues = convert_file(t03)
    t03_codes = {c for c, _, _ in t03_issues}
    if "K4_T0_3_SERVICE" not in t03_codes:
        return _fail("shared ClinicService missed K4_T0_3_SERVICE: %s" % t03_codes)
    t03_detail, t03_remedy = next(
        (d, r) for c, d, r in t03_issues if c == "K4_T0_3_SERVICE"
    )
    if "methods in shared ClinicService" not in t03_detail:
        return _fail("T0_3 detail missing wrong reading: %s" % t03_detail)
    if "one service class per aggregate" not in t03_remedy:
        return _fail("T0_3 remedy missing class-per-aggregate: %s" % t03_remedy)
    if "methods in a shared ClinicService" not in t03_remedy:
        return _fail("T0_3 remedy missing ClinicService wrong reading: %s" % t03_remedy)

    print("OK: K4 selftest (PATH_TOKEN + created_cards + partition copy + T0_3_SERVICE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
