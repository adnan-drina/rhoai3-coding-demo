#!/usr/bin/env python3
"""K2 hook: env-assignment skip + opacity on every command (Operator 090438ZO)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "pre_tool_call.sh"

# Documented dest-3 t_5981bf7a shapes (hops 214337ZL / AD-020) plus the
# same encode class Operator counted 15/15 BLOCK. dest-3 is Stopped; this
# sitting does not dest-exec that log.
DEST3_OPAQUE = (
    "echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d | xargs ls",
    "REFERENT=$(echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d)",
    "LEGACY=$(echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d)",
    "ls -la $(echo L29wdC9rYW50cmE= | base64 -d)",
    "chmod +x $(echo L29wdC9rYW50cmEvamF2YS1leHRlcm5hbC1wcm92aWRlcg== | base64 -d)",
    "ls $(echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d)",
    "echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 --decode | xargs ls",
    "echo L29wdC9rYW50cmE= | base64 -D",
    "echo x | base64 -d | xxd -r",
    "cd $(echo L3Byb2plY3RzL2xlZ2FjeQ== | base64 -d)",
    "stat $(echo L29wdC9rYW50cmE= | base64 -d)",
    "cat $(echo L29wdC9rYW50cmEva2FudHJh | base64 -d)",
    "eval $(echo ls)",
    r"printf '\x2fprojects\x2flegacy'",
    r"$'\x2fprojects\x2flegacy'",
)


def run(
    cmd: str,
    roots: list[str],
    *,
    cwd: str | None = None,
    extra_cwd: str | None = None,
    tool: str = "terminal",
    extra_env: dict[str, str] | None = None,
    extra_input: dict | None = None,
    extra_payload: dict | None = None,
) -> dict:
    env = os.environ.copy()
    env["K2_ALLOW_ROOT"] = os.pathsep.join(roots)
    if extra_env:
        env.update(extra_env)
    payload: dict = {"tool_name": tool, "tool_input": {"command": cmd}}
    if extra_input:
        payload["tool_input"].update(extra_input)
    if extra_payload:
        payload.update(extra_payload)
    if cwd is not None:
        payload["cwd"] = cwd
    if extra_cwd is not None:
        payload["extra"] = {"cwd": extra_cwd}
    p = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    out = (p.stdout or "").strip() or "{}"
    return json.loads(out)


def main() -> int:
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "mod"
        leg = Path(td) / "leg"
        dest.mkdir()
        (dest / "src").mkdir()
        leg.mkdir()
        roots = [str(dest), str(leg)]
        cwd = str(dest)

        def expect_allow(cmd: str, name: str, **kw) -> None:
            nonlocal fails
            r = run(cmd, roots, **kw)
            if r.get("action") == "block":
                print("FAIL", name, r, file=sys.stderr)
                fails += 1
            else:
                print("ok", name)

        def expect_block(cmd: str, name: str, needle: str, **kw) -> None:
            nonlocal fails
            r = run(cmd, roots, **kw)
            msg = r.get("message") or ""
            if r.get("action") != "block" or needle not in msg:
                print("FAIL", name, r, file=sys.stderr)
                fails += 1
            else:
                print("ok", name)

        expect_allow("export JAVA_HOME=/usr/lib/jvm/java-21-openjdk", "java_home")
        expect_allow("export PATH=/bin:$PATH", "path_concat")
        expect_allow("export PATH=/bin:$PATH; ls", "pathless_ls_cwd", cwd=cwd)
        expect_block("export PATH=/bin:$PATH; ls", "pathless_ls_no_cwd", "unproven")
        expect_block("cat /etc/passwd", "etc_passwd", "outside allow root")
        expect_allow(f"ls {dest}", "inside_root")
        expect_block(
            "export JAVA_HOME=/usr/lib/jvm/x && cat /etc/passwd",
            "export_then_etc",
            "outside allow root",
        )
        expect_allow("mvn -q verify", "mvn_cwd", cwd=cwd)
        expect_allow("java -version", "java_cwd", cwd=cwd)
        expect_allow("git status", "git_cwd", cwd=cwd)
        expect_allow(
            "export JAVA_HOME=/usr/lib/jvm/java-21-openjdk; java -version",
            "export_then_java_cwd",
            cwd=cwd,
        )
        expect_allow("mvn -q verify", "mvn_extra_cwd", extra_cwd=cwd)
        expect_block("mvn -q verify", "mvn_no_cwd", "unproven")

        if len(DEST3_OPAQUE) != 15:
            print("FAIL dest3 corpus size", len(DEST3_OPAQUE), file=sys.stderr)
            fails += 1
        for i, cmd in enumerate(DEST3_OPAQUE, 1):
            expect_block(cmd, f"dest3_{i}", "opaque", cwd=cwd)

        expect_block(
            f"ls {dest} && ls $(echo L2V0Yy9wYXNzd2Q= | base64 -d)",
            "bypass_prefix_base64",
            "opaque",
            cwd=cwd,
        )
        expect_block(
            f"ls {dest} && ls $(xxd -r -p <<< 2f657463)",
            "bypass_prefix_xxd",
            "opaque",
            cwd=cwd,
        )

        expect_allow("cat /dev/null", "dev_null", cwd=cwd)
        expect_allow("ls /usr/lib/jvm", "jdk_list", cwd=cwd)
        r = run(
            "ls",
            roots,
            cwd=cwd,
            extra_env={"HERMES_PROFILE": "orchestrator"},
        )
        if r.get("action") != "block" or "terminal disabled for profile orchestrator" not in (
            r.get("message") or ""
        ):
            print("FAIL orch_terminal", r, file=sys.stderr)
            fails += 1
        else:
            print("ok orch_terminal")
        r = run(
            "hermes kanban complete t_x",
            roots,
            cwd=cwd,
            extra_env={"K2_BOUND_GATE_EXIT": "1", "K2_BOUND_GATE_NAME": "check-external-dirs"},
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "check-external-dirs" not in msg or "kanban_block" not in msg:
            print("FAIL complete_red_gate", r, file=sys.stderr)
            fails += 1
        else:
            print("ok complete_red_gate")
        home = Path(td) / "hermes-home"
        (home / "kanban" / "logs").mkdir(parents=True)
        (home / "kanban" / "logs" / "t_m4.log").write_text(
            "python3 .hermes/skills/gates/check-domain-parity/scripts/"
            "check-product-tests.py /projects/modernized  0.1s [exit 1]\n"
            "OK: assert-retrievable-tree (src/ and pom.xml committed)\n",
            encoding="utf-8",
        )
        r = run(
            "hermes kanban complete t_m4",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_HOME": str(home),
                "HERMES_KANBAN_TASK": "t_m4",
            },
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "check-product-tests" not in msg
            or "kanban_block" not in msg
        ):
            print("FAIL complete_ar28_not_cleared_by_later_ok", r, file=sys.stderr)
            fails += 1
        else:
            print("ok complete_ar28_not_cleared_by_later_ok")
        r = run(
            "mvn -q quarkus:add-extension -Dextensions=quarkus-smallrye-health",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "src/test/java/com/demo/HealthTest.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "polish",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "pom.xml" not in msg or "files_writable" not in msg:
            print("FAIL writeset_pom", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_pom")
        r = run(
            "mkdir -p .mvn",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "pom.xml",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "T001",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or ".mvn" not in msg or "files_writable" not in msg:
            print("FAIL mkdir_writeset_dot_mvn", r, file=sys.stderr)
            fails += 1
        else:
            print("ok mkdir_writeset_dot_mvn")
        r = run(
            "mkdir -p " + str(dest / ".mvn"),
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "pom.xml",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "T001",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or ".mvn" not in msg:
            print("FAIL mkdir_writeset_abs_mvn", r, file=sys.stderr)
            fails += 1
        else:
            print("ok mkdir_writeset_abs_mvn")
        r = run(
            "mkdir -p src",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        if r.get("action") == "block":
            print("FAIL mkdir_parent_of_writable", r, file=sys.stderr)
            fails += 1
        else:
            print("ok mkdir_parent_of_writable")
        r = run(
            "ls /greeting",
            roots,
            cwd=cwd,
            extra_env={"HERMES_WRITE_SAFE_ROOT": str(dest)},
        )
        msg = r.get("message") or ""
        if r.get("action") == "block" and "outside allow root" in msg:
            print("FAIL http_route_not_fs_path", r, file=sys.stderr)
            fails += 1
        else:
            print("ok http_route_not_fs_path")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "src" / "Out.java")},
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "Out.java" not in msg:
            print("FAIL writeset_file", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_file")
        hook_src = HOOK.read_text(encoding="utf-8")
        fn_start = hook_src.find("def looks_like_write_cmd")
        fn_end = hook_src.find("def in_dest_write_sandbox")
        write_fn = hook_src[fn_start:fn_end] if fn_start >= 0 and fn_end > fn_start else ""
        if "python" in write_fn.lower():
            print(
                "FAIL looks_like_write_cmd_lists_python",
                file=sys.stderr,
            )
            fails += 1
        else:
            print("ok looks_like_write_cmd_not_interpreter_list")
        if "def write_effect_paths" not in hook_src:
            print("FAIL missing write_effect_paths", file=sys.stderr)
            fails += 1
        else:
            print("ok write_effect_paths_present")
        if "advisory" not in hook_src.lower() or "not containment" not in hook_src.lower():
            print("FAIL write_effect_residual_limit_undocumented", file=sys.stderr)
            fails += 1
        else:
            print("ok write_effect_residual_limit_documented")
        py_open_out = (
            "python3 -c "
            "\"open('evidence/bodies/m3-setup.json', 'w').write('{}')\""
        )
        r = run(
            py_open_out,
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "pom.xml",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "setup",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "m3-setup.json" not in msg:
            print("FAIL writeset_python_open_w", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_python_open_w")
        r = run(
            "python3 -c \"open('src/In.java', 'w').write('class In {}')\"",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        if r.get("action") == "block":
            print("FAIL writeset_python_open_w_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_python_open_w_allowed")
        r = run(
            "python3 -c \"open('src/Out.java', 'r')\"",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        if r.get("action") == "block":
            print("FAIL writeset_python_open_r_not_a_write", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_python_open_r_not_a_write")
        r = run(
            "python3 -c \"from pathlib import Path; "
            "Path('evidence/bodies/m3-setup.json').write_text('{}')\"",
            roots,
            cwd=cwd,
            extra_env={
                "K2_FILES_WRITABLE": "pom.xml",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "setup",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "m3-setup.json" not in msg:
            print("FAIL writeset_path_write_text", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_path_write_text")
        r = run(
            "mvn -q quarkus:add-extension -Dextensions=quarkus-smallrye-health",
            roots,
            cwd=cwd,
            extra_env={
                "K2_CARD_PHASE": "M4",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "verdict",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "must not implement" not in msg:
            print("FAIL m4_add_extension", r, file=sys.stderr)
            fails += 1
        else:
            print("ok m4_add_extension")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "pom.xml")},
            extra_env={
                "K2_CARD_PHASE": "M4",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "verdict",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "pom.xml" not in msg:
            print("FAIL m4_write_pom", r, file=sys.stderr)
            fails += 1
        else:
            print("ok m4_write_pom")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "evidence" / "verdicts" / "x.json")},
            extra_env={
                "K2_CARD_PHASE": "M4",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "verdict",
            },
        )
        if r.get("action") == "block":
            print("FAIL m4_write_verdict", r, file=sys.stderr)
            fails += 1
        else:
            print("ok m4_write_verdict")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={
                "path": str(dest / "evidence" / "receipts" / "gates" / "check-domain-parity.json")
            },
            extra_env={
                "K2_CARD_PHASE": "M4",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "verdict",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "gate receipts" not in msg:
            print("FAIL m4_write_gate_receipt", r, file=sys.stderr)
            fails += 1
        else:
            print("ok m4_write_gate_receipt")
        expect_block(
            "cat /etc/passwd > /dev/null",
            "passwd_to_null",
            "outside allow root",
            cwd=cwd,
        )
        expect_allow(
            "ls",
            "impl_terminal",
            cwd=cwd,
            extra_env={"HERMES_PROFILE": "implementer"},
        )
        r = run(
            "hermes kanban complete t_x",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "implementer",
                "K2_BOUND_GATE_EXIT": "0",
            },
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "kanban_request_review" not in msg
        ):
            print("FAIL impl_complete_uses_request_review", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_complete_uses_request_review")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="kanban_complete",
            extra_env={
                "HERMES_PROFILE": "implementer",
                "K2_BOUND_GATE_EXIT": "0",
            },
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "kanban_request_review" not in msg
        ):
            print("FAIL impl_native_complete_uses_request_review", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_native_complete_uses_request_review")
        crumb = dest / "evidence" / "receipts" / "hook" / "complete-invocations.jsonl"
        if not crumb.is_file():
            print("FAIL complete_breadcrumb_written missing", file=sys.stderr)
            fails += 1
        else:
            rows = []
            for line in crumb.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            if not any(
                r.get("decision") == "refuse_implementer"
                and r.get("tool") == "kanban_complete"
                for r in rows
            ):
                print("FAIL complete_breadcrumb_refuse_implementer", rows, file=sys.stderr)
                fails += 1
            else:
                print("ok complete_breadcrumb_written")
        r = run(
            "ls",
            roots,
            cwd=cwd,
            extra_env={"HERMES_PROFILE": "reviewer"},
        )
        if r.get("action") == "block":
            print("FAIL reviewer_terminal", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_terminal")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "src" / "x.java")},
            extra_env={"HERMES_PROFILE": "reviewer"},
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "reviewer" not in msg:
            print("FAIL reviewer_file", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_file")
        r = run(
            "hermes kanban complete t_x",
            roots,
            cwd=cwd,
            extra_env={"HERMES_PROFILE": "reviewer"},
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "paved-road audit" not in msg
        ):
            print("FAIL reviewer_complete_without_audit", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_without_audit")
        r = run(
            "hermes kanban complete t_x",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "reviewer",
                "K2_PAVED_ROAD_AUDIT_EXIT": "0",
            },
        )
        if r.get("action") == "block":
            print("FAIL reviewer_complete_after_audit", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_after_audit")
        # Architect 183220ZA: hermes -p reviewer sets HERMES_HOME to
        # <root>/profiles/reviewer; the official log stays under
        # <root>/kanban/logs/. A missing log after that resolve is still
        # a refusal (do not treat absence as pass).
        profile_root = Path(td) / "hermes-root-profile"
        (profile_root / "kanban" / "logs").mkdir(parents=True)
        profile_home = profile_root / "profiles" / "reviewer"
        profile_home.mkdir(parents=True)
        audit_ok = (
            "  ┊ 💻 $         python3 /projects/modernized/.hermes/skills/"
            "paved-road/paved-road-m1/scripts/assert-paved-road-audit.py "
            "--log /projects/modernized/.hermes/home/kanban/logs/t_ok.log "
            "--root /projects/modernized  0.2s\n"
        )
        (profile_root / "kanban" / "logs" / "t_ok.log").write_text(
            audit_ok, encoding="utf-8"
        )
        r = run(
            "hermes kanban complete t_ok",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "reviewer",
                "HERMES_HOME": str(profile_home),
                "HERMES_KANBAN_TASK": "t_ok",
            },
        )
        if r.get("action") == "block":
            print("FAIL reviewer_complete_profile_home_audit_ok", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_profile_home_audit_ok")
        audit_red = (
            "  ┊ 💻 $         python3 /projects/modernized/.hermes/skills/"
            "paved-road/paved-road-m1/scripts/assert-paved-road-audit.py "
            "--log /projects/modernized/.hermes/home/kanban/logs/t_red.log "
            "--root /projects/modernized  0.2s [exit 1]\n"
        )
        (profile_root / "kanban" / "logs" / "t_red.log").write_text(
            audit_red, encoding="utf-8"
        )
        r = run(
            "hermes kanban complete t_red",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "reviewer",
                "HERMES_HOME": str(profile_home),
                "HERMES_KANBAN_TASK": "t_red",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "paved-road audit" not in msg:
            print("FAIL reviewer_complete_profile_home_audit_red", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_profile_home_audit_red")
        default_home = Path(td) / "hermes-root-default"
        (default_home / "kanban" / "logs").mkdir(parents=True)
        (default_home / "kanban" / "logs" / "t_def.log").write_text(
            audit_ok.replace("t_ok.log", "t_def.log"), encoding="utf-8"
        )
        r = run(
            "hermes kanban complete t_def",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "reviewer",
                "HERMES_HOME": str(default_home),
                "HERMES_KANBAN_TASK": "t_def",
            },
        )
        if r.get("action") == "block":
            print("FAIL reviewer_complete_base_home_audit_ok", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_base_home_audit_ok")
        r = run(
            "hermes kanban complete t_missing",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_PROFILE": "reviewer",
                "HERMES_HOME": str(profile_home),
                "HERMES_KANBAN_TASK": "t_missing",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "paved-road audit" not in msg:
            print("FAIL reviewer_complete_profile_home_log_absent", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_complete_profile_home_log_absent")
        (profile_root / "kanban" / "logs" / "t_bg.log").write_text(
            "python3 .hermes/skills/gates/check-domain-parity/scripts/"
            "check-product-tests.py /projects/modernized  0.1s [exit 1]\n",
            encoding="utf-8",
        )
        r = run(
            "hermes kanban complete t_bg",
            roots,
            cwd=cwd,
            extra_env={
                "HERMES_HOME": str(profile_home),
                "HERMES_KANBAN_TASK": "t_bg",
            },
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "check-product-tests" not in msg
            or "kanban_block" not in msg
        ):
            print("FAIL complete_bound_gate_profile_home", r, file=sys.stderr)
            fails += 1
        else:
            print("ok complete_bound_gate_profile_home")
        rows = []
        if crumb.is_file():
            for line in crumb.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        if not any(r.get("decision") == "allow" for r in rows):
            print("FAIL complete_breadcrumb_allow", rows, file=sys.stderr)
            fails += 1
        else:
            print("ok complete_breadcrumb_allow")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="kanban_complete",
            extra_env={"HERMES_PROFILE": "reviewer"},
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "paved-road audit" not in msg
        ):
            print("FAIL reviewer_native_complete_without_audit", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_native_complete_without_audit")
        expect_allow(
            "hermes kanban complete t_x",
            "complete_green_gate",
            cwd=cwd,
            extra_env={"K2_BOUND_GATE_EXIT": "0"},
        )
        home = dest / "hermes-home"
        (home / "kanban" / "logs").mkdir(parents=True)
        (home / "kanban" / "logs" / "t_live.log").write_text(
            "python3 assert-m2-speckit-conformance.py . [exit 1]\n",
            encoding="utf-8",
        )
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="kanban_complete",
            extra_payload={"task_id": "t_live"},
            extra_env={
                "HERMES_HOME": str(home),
                "HERMES_KANBAN_TASK": "",
                "HERMES_PROFILE": "",
            },
        )
        msg = r.get("message") or ""
        if (
            r.get("action") != "block"
            or "assert-m2-speckit-conformance" not in msg
        ):
            print("FAIL native_complete_payload_task_id_bound_gate", r, file=sys.stderr)
            fails += 1
        else:
            print("ok native_complete_payload_task_id_bound_gate")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "src" / "In.java")},
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        if r.get("action") == "block":
            print("FAIL writeset_inside", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_inside")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": "src/Out.java"},
            extra_env={
                "K2_FILES_WRITABLE": "src/In.java",
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "Out.java" not in msg:
            print("FAIL writeset_relative", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_relative")
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(leg / "x.java")},
            extra_env={"HERMES_WRITE_SAFE_ROOT": str(dest)},
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "write sandbox" not in msg:
            print("FAIL legacy_write_sandbox", r, file=sys.stderr)
            fails += 1
        else:
            print("ok legacy_write_sandbox")
        body = dest / "card.json"
        body.write_text(
            json.dumps({"files_writable": ["src/In.java"], "identity": {"story_id": "US1"}}),
            encoding="utf-8",
        )
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "src" / "Out.java")},
            extra_env={
                "K2_CARD_BODY": str(body),
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "Out.java" not in msg:
            print("FAIL writeset_card_body", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_card_body")
        import sqlite3

        db = Path(td) / "kanban.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, description TEXT)")
        con.execute(
            "INSERT INTO tasks VALUES (?, ?)",
            (
                "t_story",
                json.dumps({"files_writable": ["src/In.java"]}),
            ),
        )
        con.commit()
        con.close()
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "src" / "Out.java")},
            extra_env={
                "HERMES_KANBAN_TASK": "t_story",
                "HERMES_KANBAN_DB": str(db),
                "HERMES_WRITE_SAFE_ROOT": str(dest),
                "K2_STORY_ID": "US1",
            },
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "Out.java" not in msg:
            print("FAIL writeset_sqlite", r, file=sys.stderr)
            fails += 1
        else:
            print("ok writeset_sqlite")
        red_home = Path(td) / "p0b-home"
        (red_home / "kanban" / "logs").mkdir(parents=True)
        (red_home / "kanban" / "logs" / "t_p0b.log").write_text(
            "  ┊ 💻 $         python3 .hermes/skills/sdd/check-spec-readiness/"
            "scripts/check-partition-coverage.py . --write-receipt "
            "evidence/receipts/partition-coverage/latest.json  0.2s [exit 1]\n",
            encoding="utf-8",
        )
        p0b = {
            "HERMES_PROFILE": "implementer",
            "HERMES_HOME": str(red_home),
            "HERMES_KANBAN_TASK": "t_p0b",
            "HERMES_WRITE_SAFE_ROOT": str(dest),
            "K2_FILES_WRITABLE": "evidence/",
        }
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "evidence" / "partition.json")},
            extra_env=p0b,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "product-tree write refused" not in msg:
            print("FAIL p0b_write_after_exit1", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_write_after_exit1")
        r = run(
            "python3 .hermes/kernel/k4_mint.py --payloads evidence/partition-payloads.json --exec",
            roots,
            cwd=cwd,
            extra_env=p0b,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "continue after mandated" not in msg:
            print("FAIL p0b_k4_mint_after_exit1", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_k4_mint_after_exit1")
        r = run(
            "python3 .hermes/skills/sdd/check-spec-readiness/scripts/"
            "check-partition-coverage.py . --write-receipt "
            "evidence/receipts/partition-coverage/latest.json",
            roots,
            cwd=cwd,
            extra_env=p0b,
        )
        if r.get("action") == "block":
            print("FAIL p0b_rerun_same_needle", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_rerun_same_needle")
        r = run(
            "hermes kanban block t_p0b",
            roots,
            cwd=cwd,
            extra_env=p0b,
        )
        if r.get("action") == "block":
            print("FAIL p0b_kanban_block_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_kanban_block_allowed")
        r = run(
            "hermes kanban request_review t_p0b",
            roots,
            cwd=cwd,
            extra_env=p0b,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "kanban_request_review refused" not in msg:
            print("FAIL p0b_request_review_while_red", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_request_review_while_red")
        with (red_home / "kanban" / "logs" / "t_p0b.log").open(
            "a", encoding="utf-8"
        ) as fh:
            fh.write(
                "  ┊ 💻 $         python3 .hermes/skills/sdd/check-spec-readiness/"
                "scripts/check-partition-coverage.py . --write-receipt "
                "evidence/receipts/partition-coverage/latest.json  0.2s\n"
            )
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "evidence" / "partition.json")},
            extra_env=p0b,
        )
        if r.get("action") == "block":
            print("FAIL p0b_write_after_same_needle_green", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_write_after_same_needle_green")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
