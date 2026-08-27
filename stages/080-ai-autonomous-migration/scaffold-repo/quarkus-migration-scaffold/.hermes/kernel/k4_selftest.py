#!/usr/bin/env python3
"""K4 land-time selftest. Not pytest. Not dest. Not create_task."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from k1_validate import validate_body  # noqa: E402
from k4_convert import (  # noqa: E402
    DEST_POM_EXT_CMD,
    DB_STORY_ID,
    convert_file,
    convert_partition,
    dd3_union_gaps,
    harvest_database_needed,
    main as convert_main,
    stamp_write_set,
    validate_inputs,
    validate_result,
)
from k4_schema import STAMP_ID, STAMP_SKILL, VERIFIER_ID, WRITER_ID  # noqa: E402


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
    expect = ["setup", "US1", "US2", STAMP_ID]
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
    if by_id["US1"]["parents"] != ["setup"]:
        return _fail("US1 parents %s" % by_id["US1"]["parents"])
    if WRITER_ID in by_id or VERIFIER_ID in by_id:
        return _fail("dest factory cards must not be minted")
    if by_id["setup"]["assignee"] != "implementer":
        return _fail("setup assignee")
    for sid in ("setup", "US1", "US2"):
        if by_id[sid].get("max_retries") != 1:
            return _fail("%s max_retries %s" % (sid, by_id[sid].get("max_retries")))
        skills = by_id[sid].get("skills") or []
        if not skills:
            return _fail("%s skills empty" % sid)
        if "k4:%s:" % sid not in str(by_id[sid].get("idempotency_key") or ""):
            return _fail("%s idempotency_key %s" % (sid, by_id[sid].get("idempotency_key")))
    if "spring-to-quarkus-patterns" not in by_id["US1"]["skills"]:
        return _fail("US1 skills %s" % by_id["US1"]["skills"])
    if "author-destination-pom" not in by_id["setup"]["skills"]:
        return _fail("setup skills %s" % by_id["setup"]["skills"])
    stamp = by_id[STAMP_ID]
    if stamp["parents"] != ["setup", "US1", "US2"]:
        return _fail("stamp parents %s" % stamp["parents"])
    if stamp.get("skills") != [STAMP_SKILL]:
        return _fail("stamp skills %s" % stamp.get("skills"))
    if stamp.get("max_retries") != 1:
        return _fail("stamp max_retries %s" % stamp.get("max_retries"))
    if stamp.get("assignee") != "implementer":
        return _fail("stamp assignee %s" % stamp.get("assignee"))
    if stamp.get("title") != "M3 %s" % STAMP_ID:
        return _fail("stamp title %s" % stamp.get("title"))
    stamp_body = json.loads(stamp["body"])
    if stamp_body["files_writable"] != [
        "pom.xml",
        "src/main/java/com/demo/service/AlphaService.java",
        "src/main/java/com/demo/resource/AlphaResource.java",
        "src/main/java/com/demo/service/BetaService.java",
    ]:
        return _fail("stamp files_writable %s" % stamp_body["files_writable"])
    if stamp_body["phase"] != "M3":
        return _fail("stamp phase %s" % stamp_body["phase"])
    stamp_k1 = validate_body(stamp_body, root=None)
    stamp_k1_codes = {c for c, _, _ in stamp_k1}
    if stamp_k1_codes & {"BODY_SCHEMA", "BODY_SCOPE", "BODY_REF_MISSING", "BODY_HERMES_ID"}:
        return _fail("stamp body failed K1: %s" % stamp_k1)
    filtered = stamp_write_set(
        [{"files_writable": ["pom.xml", "evidence/x", ".env", "src/A.java"]}]
    )
    if filtered != ["pom.xml", "src/A.java"]:
        return _fail("stamp OBJECT filter %s" % filtered)
    evidence_only = json.loads(valid.read_text(encoding="utf-8"))
    for story in evidence_only["stories"]:
        story["files_writable"] = ["evidence/secret.txt"]
    ev_issues = validate_inputs(evidence_only)
    if not any(c == "K4_SCOPE" and STAMP_ID in d for c, d, _ in ev_issues):
        return _fail("evidence-only write-set missed stamp K4_SCOPE: %s" % ev_issues)
    factory = validate_result(
        {
            "payloads": [
                {
                    "logical_id": WRITER_ID,
                    "title": "Mint writer",
                    "assignee": "orchestrator",
                    "parents": [],
                    "body": "{}",
                }
            ],
            "manifest": {"created_cards": [WRITER_ID]},
        }
    )
    factory_codes = {c for c, _, _ in factory}
    if "K4_FACTORY" not in factory_codes:
        return _fail("retired factory payload missed K4_FACTORY: %s" % factory_codes)
    if result.get("claimed_control") is not False:
        return _fail("claimed_control must stay false")
    us1_assert = " ".join(
        str(item.get("assert") or "") for item in us1.get("exit_criteria") or []
    )
    if "silence invalid AD-002E" in us1_assert and "false consult" not in us1_assert:
        return _fail("US1 still stamps phantom AD-002E with no definition")
    if "kanban_block" not in us1_assert:
        return _fail("US1 body must name kanban_block as a legal outcome")
    if "dependency_wait" not in us1_assert or "done parent" not in us1_assert:
        return _fail(
            "US1 body must forbid dependency_wait on a done parent: %s" % us1_assert
        )
    us1_cmds = [str(item.get("cmd") or "") for item in us1.get("exit_criteria") or []]
    if "mvn -q compile" not in us1_cmds:
        return _fail("US1 src/main must stamp mvn -q compile: %s" % us1_cmds)
    if any("test-compile" in c for c in us1_cmds):
        return _fail("US1 must not stamp test-compile: %s" % us1_cmds)
    setup_valid = json.loads(by_id["setup"]["body"])
    setup_valid_cmds = [
        str(item.get("cmd") or "") for item in setup_valid.get("exit_criteria") or []
    ]
    if any("test-compile" in c for c in setup_valid_cmds):
        return _fail("pom-only setup must not stamp test-compile: %s" % setup_valid_cmds)

    extra = KERNEL / "fixtures" / "k4-tasks-extra.md"
    _, extra_issues = convert_file(valid, tasks_path=extra)
    extra_codes = {c for c, _, _ in extra_issues}
    if "K4_PLANNING_DEFECT" not in extra_codes:
        return _fail("extra tasks.md path missed K4_PLANNING_DEFECT: %s" % extra_codes)
    detail = next(d for c, d, _ in extra_issues if c == "K4_PLANNING_DEFECT")
    if "Missing.java" not in detail:
        return _fail("planning defect did not list Missing.java: %s" % detail)

    negated = KERNEL / "fixtures" / "k4-tasks-negated.md"
    _, neg_issues = convert_file(valid, tasks_path=negated)
    neg_codes = {c for c, _, _ in neg_issues}
    if "K4_PLANNING_DEFECT" in neg_codes:
        return _fail("negated src/test prose must not be a write claim: %s" % neg_issues)

    noskill = KERNEL / "fixtures" / "k4-no-skills.json"
    _, skill_issues = convert_file(noskill)
    skill_codes = {c for c, _, _ in skill_issues}
    if "K4_SKILLS" not in skill_codes:
        return _fail("story with no kind/skills missed K4_SKILLS: %s" % skill_codes)

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

    health_np = KERNEL / "fixtures" / "k4-health-no-pom.json"
    _, health_issues = convert_file(health_np)
    health_codes = {c for c, _, _ in health_issues}
    if "K4_SCOPE" not in health_codes:
        return _fail("health AC without pom missed K4_SCOPE: %s" % health_codes)
    health_detail = next(d for c, d, _ in health_issues if c == "K4_SCOPE")
    if "pom.xml" not in health_detail:
        return _fail("health K4_SCOPE did not name pom.xml: %s" % health_detail)

    with_test = KERNEL / "fixtures" / "k4-with-test.json"
    test_result, test_issues = convert_file(with_test)
    if test_issues or test_result is None:
        return _fail("k4-with-test convert: %s" % test_issues)
    polish = json.loads(
        next(p["body"] for p in test_result["payloads"] if p["logical_id"] == "polish")
    )
    cmds = [str(item.get("cmd") or "") for item in polish.get("exit_criteria") or []]
    if "mvn -q test" not in cmds:
        return _fail("polish with src/test must stamp mvn -q test: %s" % cmds)
    if any("test-compile" in c for c in cmds):
        return _fail("polish with src/test must not stamp test-compile: %s" % cmds)
    setup_body = json.loads(
        next(p["body"] for p in test_result["payloads"] if p["logical_id"] == "setup")
    )
    setup_cmds = [str(item.get("cmd") or "") for item in setup_body.get("exit_criteria") or []]
    if any("test-compile" in c for c in setup_cmds):
        return _fail("setup without tests must not stamp test-compile: %s" % setup_cmds)
    if any("mvn -q test" == c for c in setup_cmds):
        return _fail("setup without tests must not stamp mvn test: %s" % setup_cmds)

    smoke = KERNEL / "fixtures" / "k4-setup-smoke.json"
    smoke_result, smoke_issues = convert_file(smoke)
    if smoke_issues or smoke_result is None:
        return _fail("k4-setup-smoke convert: %s" % smoke_issues)
    smoke_body = json.loads(
        next(p["body"] for p in smoke_result["payloads"] if p["logical_id"] == "setup")
    )
    smoke_cmds = [str(item.get("cmd") or "") for item in smoke_body.get("exit_criteria") or []]
    if "mvn -q test" not in smoke_cmds:
        return _fail("setup with smoke test must stamp mvn -q test: %s" % smoke_cmds)
    if any("test-compile" in c for c in smoke_cmds):
        return _fail("setup with smoke test must not stamp test-compile: %s" % smoke_cmds)

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
    if "files_writable" not in t03_remedy and "write-set" not in t03_remedy:
        return _fail("T0_3 remedy missing write-set legality: %s" % t03_remedy)
    if "MAY own a shared facade" not in t03_remedy:
        return _fail("T0_3 remedy missing shared-facade grant: %s" % t03_remedy)
    if "methods in a shared ClinicService" not in t03_remedy:
        return _fail("T0_3 remedy missing ClinicService wrong reading: %s" % t03_remedy)
    if "not this mint refuse" not in t03_remedy:
        return _fail("T0_3 remedy still treats split-per-aggregate as mint: %s" % t03_remedy)

    http_part = json.loads(valid.read_text(encoding="utf-8"))
    http_part["stories"][1]["endpoints"] = ["GET /greeting"]
    miss = validate_inputs(http_part)
    if not any(c == "K4_LEGACY_SOURCE" for c, _, _ in miss):
        return _fail(
            "HTTP story without legacy_source missed K4_LEGACY_SOURCE: %s" % miss
        )
    src = "src/main/java/com/example/restservice/GreetingController.java"
    http_part["stories"][1]["legacy_source"] = src
    miss_dest = validate_inputs(http_part)
    if not any(c == "K4_DEST_FILE" for c, _, _ in miss_dest):
        return _fail(
            "HTTP story without dest_file missed K4_DEST_FILE: %s" % miss_dest
        )
    dest_twin = "src/main/java/com/demo/resource/AlphaResource.java"
    http_part["stories"][1]["dest_file"] = dest_twin
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "http.json"
        path.write_text(json.dumps(http_part), encoding="utf-8")
        http_result, http_issues = convert_file(path)
        if http_issues or http_result is None:
            return _fail(
                "HTTP story with legacy_source and dest_file must convert: %s"
                % http_issues
            )
        us1_http = json.loads(
            next(p["body"] for p in http_result["payloads"] if p["logical_id"] == "US1")
        )
        if us1_http.get("identity", {}).get("legacy_source") != src:
            return _fail("US1 identity.legacy_source %s" % us1_http.get("identity"))
        locus = next(
            r for r in us1_http.get("refs") or [] if r.get("key") == "legacy_locus"
        )
        if "entry-point-inventory.json" not in str(locus.get("path") or ""):
            return _fail("legacy_locus path %s" % locus)

    from k4_roundtrip import roundtrip_result, roundtrip_story  # noqa: PLC0415

    typed = KERNEL / "fixtures" / "k4-typed-operand.json"
    typed_result, typed_issues = convert_file(typed)
    if typed_issues or typed_result is None:
        return _fail("typed operand partition must convert: %s" % typed_issues)
    typed_part = json.loads(typed.read_text(encoding="utf-8"))
    rt = roundtrip_result(typed_part, typed_result)
    if rt:
        return _fail("typed operand must round-trip: %s" % rt)
    us1_typed = json.loads(
        next(
            p["body"]
            for p in typed_result["payloads"]
            if p["logical_id"] == "us1_greeting"
        )
    )
    ident = us1_typed.get("identity") or {}
    if ident.get("operand_class") != ["http"]:
        return _fail("operand_class dropped at K4: %s" % ident)
    dropped = roundtrip_story(
        typed_part["stories"][1],
        {"files_writable": typed_part["stories"][1]["files_writable"], "identity": {}},
    )
    if not dropped:
        return _fail("body missing operand_class must REFUSE round-trip")

    from k4_roundtrip import dest_file_invented  # noqa: PLC0415

    dest9 = KERNEL / "fixtures" / "k4-dest9-invented-files.json"
    dest9_result, dest9_issues = convert_file(dest9)
    if dest9_issues or dest9_result is None:
        return _fail("dest-9 dest_file partition must convert: %s" % dest9_issues)
    dest9_part = json.loads(dest9.read_text(encoding="utf-8"))
    dest9_rt = roundtrip_result(dest9_part, dest9_result)
    blob = " ".join(dest9_rt)
    if "Application.java" not in blob or "GreetingResource.java" not in blob:
        return _fail(
            "dest_file round-trip must REFUSE dest-9 Application.java and "
            "GreetingResource.java: %s" % dest9_rt
        )
    if any(g.endswith("Greeting.java") and "invented" in g for g in dest9_rt):
        return _fail("dest_file twin Greeting.java must not REFUSE: %s" % dest9_rt)
    invented = dest_file_invented(dest9_part["stories"][1])
    if set(invented) != {
        "src/main/java/com/demo/Application.java",
        "src/main/java/com/demo/GreetingResource.java",
    }:
        return _fail("dest_file_invented dest-9 %s" % invented)
    setup_skip = dest_file_invented(dest9_part["stories"][0])
    if setup_skip:
        return _fail("setup without dest_file must skip invented check: %s" % setup_skip)

    live = KERNEL / "fixtures" / "k4-dest9-live-partition.json"
    _, live_issues = convert_file(live)
    live_codes = {c for c, _, _ in live_issues}
    if "K4_DEST_FILE" not in live_codes:
        return _fail(
            "live dest-9 partition missed K4_DEST_FILE: %s" % live_issues
        )
    live_part = json.loads(live.read_text(encoding="utf-8"))
    live_invented = dest_file_invented(live_part["stories"][1])
    if live_invented:
        return _fail(
            "live dest_file absent must skip dest_file_invented "
            "(do not rewrite k4_roundtrip skip): %s" % live_invented
        )
    from k4_roundtrip import main as roundtrip_main  # noqa: PLC0415

    live_rc = roundtrip_main([str(live)])
    if live_rc != 1:
        return _fail(
            "k4_roundtrip live dest-9 must rc 1 via convert K4_DEST_FILE: %s"
            % live_rc
        )

    frozen = KERNEL / "fixtures" / "k4-dest9-live-convert-no-dd3.json"
    frozen_doc = json.loads(frozen.read_text(encoding="utf-8"))
    frozen_gaps = dd3_union_gaps(frozen_doc)
    if not any("extensions_apply" in g for g in frozen_gaps):
        return _fail(
            "dest-9 live convert without DD3 must REFUSE missing union: %s"
            % frozen_gaps
        )
    live_stamped = convert_partition(live_part)
    live_gaps = dd3_union_gaps(live_stamped)
    if live_gaps:
        return _fail("dest-9 live convert after DD3 must stamp union: %s" % live_gaps)
    setup_live = json.loads(
        next(p["body"] for p in live_stamped["payloads"] if p["logical_id"] == "setup")
    )
    apply = (setup_live.get("identity") or {}).get("extensions_apply") or []
    if "quarkus-rest" not in apply or "quarkus-rest-jackson" not in apply:
        return _fail("setup extensions_apply %s" % apply)
    us1_live = json.loads(
        next(
            p["body"]
            for p in live_stamped["payloads"]
            if p["logical_id"] == "us1_greeting"
        )
    )
    if "extensions_apply" in (us1_live.get("identity") or {}):
        return _fail("us1_greeting must not carry extensions_apply")
    pom_cmds = [
        str(e.get("cmd") or "")
        for e in setup_live.get("exit_criteria") or []
        if isinstance(e, dict)
    ]
    if not any("assert-dest-pom-extensions.py" in c for c in pom_cmds):
        return _fail("setup missing dest_pom_extensions exit: %s" % pom_cmds)
    if "stamp_dd3_extensions(" not in (KERNEL / "k4_convert.py").read_text(
        encoding="utf-8"
    ):
        return _fail("k4_convert.py must call stamp_dd3_extensions")
    if "write_m3_bodies(" not in (KERNEL / "k4_convert.py").read_text(encoding="utf-8"):
        return _fail("k4_convert.py must write M3 bodies at convert")

    stray = KERNEL / "fixtures" / "bodies"
    if stray.exists():
        return _fail("convert_file on kernel fixtures must not write fixtures/bodies")

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        evid = dest / "evidence"
        evid.mkdir()
        part_dst = evid / "partition.json"
        part_dst.write_text(
            (KERNEL / "fixtures" / "k4-valid-partition.json").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        written, wissues = convert_file(part_dst)
        if wissues or written is None:
            return _fail("write-root convert: %s" % wissues)
        setup_path = dest / "evidence" / "bodies" / "m3-setup.json"
        if not setup_path.is_file():
            return _fail("convert must write evidence/bodies/m3-setup.json")
        on_disk = json.loads(setup_path.read_text(encoding="utf-8"))
        in_payload = json.loads(
            next(
                p["body"]
                for p in written["payloads"]
                if p["logical_id"] == "setup"
            )
        )
        if on_disk != in_payload:
            return _fail("written setup body must match payload body")
        cmd = DEST_POM_EXT_CMD % "setup"
        if "evidence/bodies/m3-setup.json" not in cmd:
            return _fail("DEST_POM_EXT_CMD must name the written path")
        if not (dest / "evidence" / "bodies" / "m3-setup.json").is_file():
            return _fail("dest_pom_extensions --body path missing after convert")

    harvest_part = json.loads(valid.read_text(encoding="utf-8"))
    if harvest_database_needed(None):
        return _fail("missing root must not claim database.needed")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        evid = root / "evidence"
        evid.mkdir()
        (evid / "required-extensions.json").write_text(
            json.dumps(
                {
                    "database": {
                        "needed": True,
                        "kind": "postgresql",
                        "from": "selftest",
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )
        needed = convert_partition(harvest_part, root=root)
        lids = needed["manifest"]["created_cards"]
        if DB_STORY_ID not in lids:
            return _fail("harvest needed true must inject %s: %s" % (DB_STORY_ID, lids))
        if lids.count(DB_STORY_ID) != 1:
            return _fail("duplicate %s in created_cards: %s" % (DB_STORY_ID, lids))
        by_id = {p["logical_id"]: p for p in needed["payloads"]}
        db_payload = by_id[DB_STORY_ID]
        if "form-entity-persistence" not in (db_payload.get("skills") or []):
            return _fail("database story skills %s" % db_payload.get("skills"))
        db_body = json.loads(db_payload["body"])
        if db_body["files_writable"] != ["k8s/postgres.yaml", "k8s/app.yaml"]:
            return _fail("database files_writable %s" % db_body["files_writable"])
        if DB_STORY_ID not in (by_id[STAMP_ID].get("parents") or []):
            return _fail("stamp parents missing %s: %s" % (DB_STORY_ID, by_id[STAMP_ID].get("parents")))
        stamp_fw = json.loads(by_id[STAMP_ID]["body"])["files_writable"]
        if "k8s/postgres.yaml" not in stamp_fw or "k8s/app.yaml" not in stamp_fw:
            return _fail("stamp write-set missing k8s paths: %s" % stamp_fw)
        k1_db = validate_body(db_body, root=None)
        k1_db_codes = {c for c, _, _ in k1_db}
        if k1_db_codes & {"BODY_SCHEMA", "BODY_SCOPE", "BODY_REF_MISSING", "BODY_HERMES_ID"}:
            return _fail("database body failed K1: %s" % k1_db)
        already = list(harvest_part["stories"]) + [
            {
                "story_id": DB_STORY_ID,
                "kind": "database",
                "skills": ["form-entity-persistence"],
                "files_writable": ["k8s/postgres.yaml", "k8s/app.yaml"],
            }
        ]
        dup_part = dict(harvest_part)
        dup_part["stories"] = already
        dup = convert_partition(dup_part, root=root)
        if dup["manifest"]["created_cards"].count(DB_STORY_ID) != 1:
            return _fail(
                "existing %s must not be reminted: %s"
                % (DB_STORY_ID, dup["manifest"]["created_cards"])
            )
        (evid / "required-extensions.json").write_text(
            json.dumps({"database": {"needed": False, "kind": "", "from": ""}})
            + "\n",
            encoding="utf-8",
        )
        off = convert_partition(harvest_part, root=root)
        if DB_STORY_ID in off["manifest"]["created_cards"]:
            return _fail(
                "harvest needed false must not inject: %s"
                % off["manifest"]["created_cards"]
            )
        (evid / "required-extensions.json").unlink()
        missing = convert_partition(harvest_part, root=root)
        if DB_STORY_ID in missing["manifest"]["created_cards"]:
            return _fail(
                "missing harvest must not inject: %s"
                % missing["manifest"]["created_cards"]
            )
        part_dst = evid / "partition.json"
        part_dst.write_text(valid.read_text(encoding="utf-8"), encoding="utf-8")
        (evid / "required-extensions.json").write_text(
            json.dumps({"database": {"needed": True, "kind": "postgresql"}})
            + "\n",
            encoding="utf-8",
        )
        written_db, wdb_issues = convert_file(part_dst)
        if wdb_issues or written_db is None:
            return _fail("harvest convert_file: %s" % wdb_issues)
        if DB_STORY_ID not in written_db["manifest"]["created_cards"]:
            return _fail(
                "convert_file harvest must inject: %s"
                % written_db["manifest"]["created_cards"]
            )
        db_on_disk = root / "evidence" / "bodies" / ("m3-%s.json" % DB_STORY_ID)
        if not db_on_disk.is_file():
            return _fail("convert must write evidence/bodies/m3-%s.json" % DB_STORY_ID)

    help_rc = convert_main(["--help"])
    if help_rc != 0:
        return _fail("k4_convert --help must exit 0, got %s" % help_rc)

    print("OK: K4 selftest (PATH_TOKEN + created_cards + partition copy + T0_3_SERVICE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
