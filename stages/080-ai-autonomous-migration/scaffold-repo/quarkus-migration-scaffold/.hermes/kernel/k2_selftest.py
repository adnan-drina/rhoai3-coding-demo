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
        # loop card: the transaction verdict is the audit; REVERTED is a complete, recorded outcome
        for verdict in ("ACCEPTED", "REVERTED", "DEFERRED"):
            r = run(
                "hermes kanban complete t_x",
                roots,
                cwd=cwd,
                extra_env={"HERMES_PROFILE": "reviewer", "K2_LOOP_VERDICT": verdict, "K2_BOUND_GATE_EXIT": "1", "K2_BOUND_GATE_NAME": "fix-until-green/scripts/advance"},
            )
            if r.get("action") == "block":
                print("FAIL reviewer_complete_loop_%s" % verdict.lower(), r, file=sys.stderr)
                fails += 1
            else:
                print("ok reviewer_complete_loop_%s" % verdict.lower())
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
        # after a green audit the reviewer may only terminate: exploration is refused
        green_env = {"HERMES_PROFILE": "reviewer", "HERMES_HOME": str(profile_home), "HERMES_KANBAN_TASK": "t_ok", "K2_BOUND_GATE_EXIT": "0"}
        for cmdline, tl in (("find /projects/modernized -name t_ok.log", "terminal"), ("python3 -c \"import json; print(1)\"", "terminal"), ("", "kanban_attach")):
            r = run(cmdline, roots, cwd=cwd, tool=tl, extra_env=green_env)
            if r.get("action") != "block" or "already exited 0" not in (r.get("message") or ""):
                print("FAIL reviewer_after_green_refuses %r" % (cmdline or tl), r, file=sys.stderr)
                fails += 1
            else:
                print("ok reviewer_after_green_refuses")
        for cmdline, tl in (("python3 /projects/modernized/.hermes/skills/paved-road/paved-road-m1/scripts/assert-paved-road-audit.py --root .", "terminal"), ("", "kanban_request_changes"), ("", "kanban_complete")):
            r = run(cmdline, roots, cwd=cwd, tool=tl, extra_env=green_env)
            if r.get("action") == "block" and "already exited 0" in (r.get("message") or ""):
                print("FAIL reviewer_after_green_allows %r" % (cmdline or tl), r, file=sys.stderr)
                fails += 1
            else:
                print("ok reviewer_after_green_allows")
        r = run("find . -name x", roots, cwd=cwd, tool="terminal", extra_env={"HERMES_PROFILE": "reviewer", "HERMES_HOME": str(profile_home), "HERMES_KANBAN_TASK": "t_red", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block" and "already exited 0" in (r.get("message") or ""):
            print("FAIL reviewer_before_green_allows", r, file=sys.stderr)
            fails += 1
        else:
            print("ok reviewer_before_green_allows")
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
            "python3 admit-migration-plan.py --root . [exit 1]\n",
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
            or "admit-migration-plan" not in msg
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
            "  ┊ 💻 $         python3 .hermes/skills/planning/admit-migration-plan/"
            "scripts/verify-admission-receipt.py --root . "
            "--any-status  0.2s [exit 1]\n",
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
            extra_input={"path": str(dest / "evidence" / "planning" / "ownership-map.json")},
            extra_env=p0b,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "product-tree write refused" not in msg:
            print("FAIL p0b_write_after_exit1", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_write_after_exit1")
        r = run(
            "python3 .hermes/kernel/k4_mint.py --root . --exec",
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
            "python3 .hermes/skills/planning/admit-migration-plan/scripts/"
            "verify-admission-receipt.py --root . "
            "--any-status",
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
        # loop road: after a red advance the implementer may re-run run-verify.sh (then advance), not only advance
        r = run("bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .", roots, cwd=cwd,
                extra_env={"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_p0b", "K2_BOUND_GATE_EXIT": "1", "K2_BOUND_GATE_NAME": "fix-until-green/scripts/advance"})
        if r.get("action") == "block":
            print("FAIL loop_run_verify_after_red_advance", r, file=sys.stderr)
            fails += 1
        else:
            print("ok loop_run_verify_after_red_advance")
        with (red_home / "kanban" / "logs" / "t_p0b.log").open(
            "a", encoding="utf-8"
        ) as fh:
            fh.write(
                "  ┊ 💻 $         python3 .hermes/skills/planning/admit-migration-plan/"
                "scripts/verify-admission-receipt.py --root . "
                "--any-status  0.2s\n"
            )
        r = run(
            "",
            roots,
            cwd=cwd,
            tool="write_file",
            extra_input={"path": str(dest / "evidence" / "planning" / "ownership-map.json")},
            extra_env=p0b,
        )
        if r.get("action") == "block":
            print("FAIL p0b_write_after_same_needle_green", r, file=sys.stderr)
            fails += 1
        else:
            print("ok p0b_write_after_same_needle_green")

    # graph-mutation veto (SAD §9): a worker never creates/links cards; K4 does
    with tempfile.TemporaryDirectory() as td2:
        dest2 = Path(td2) / "dest"
        dest2.mkdir()
        roots2 = [str(dest2)]
        impl = {"HERMES_PROFILE": "implementer", "HERMES_WRITE_SAFE_ROOT": str(dest2)}
        for tool_name in ("kanban_create", "kanban_link", "kanban_swarm", "kanban_decompose", "create_task"):
            r = run("", roots2, cwd=str(dest2), tool=tool_name, extra_env=impl)
            if r.get("action") != "block" or "K4 only" not in (r.get("message") or ""):
                print("FAIL veto_tool_%s" % tool_name, r, file=sys.stderr)
                fails += 1
            else:
                print("ok veto_tool_%s" % tool_name)
        for cmdline in ("hermes kanban create 'M3 hand-made' --assignee implementer", "hermes kanban link t_a t_b", "hermes kanban swarm t_x", "hermes kanban daemon --force"):
            r = run(cmdline, roots2, cwd=str(dest2), extra_env=impl)
            if r.get("action") != "block":
                print("FAIL veto_cmd %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok veto_cmd %r" % cmdline)
        r = run("python3 .hermes/kernel/k4_mint.py --root . --exec --verify-board", roots2, cwd=str(dest2), extra_env=impl)
        if r.get("action") == "block":
            print("FAIL veto_allows_k4_mint", r, file=sys.stderr)
            fails += 1
        else:
            print("ok veto_allows_k4_mint")
        r = run("hermes kanban list --json", roots2, cwd=str(dest2), extra_env=impl)
        if r.get("action") == "block":
            print("FAIL veto_allows_list", r, file=sys.stderr)
            fails += 1
        else:
            print("ok veto_allows_list")
        # request_review must name the reviewer (v6 t_b2fe5a8d: reviewer=None re-dispatched the review to the implementer)
        r = run("", roots, cwd=cwd, tool="kanban_request_review", extra_env={"HERMES_PROFILE": "implementer", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") != "block" or "reviewer=reviewer" not in (r.get("message") or ""):
            print("FAIL impl_request_review_needs_reviewer", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_request_review_needs_reviewer")
        # paved-road-m3: the implementer completes a loop card on the recorded verdict once the road ran
        loop_env = {"HERMES_PROFILE": "implementer", "K2_BOUND_GATE_EXIT": "1", "K2_BOUND_GATE_NAME": "fix-until-green/scripts/advance"}
        for verdict in ("ACCEPTED", "REVERTED"):
            r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env=dict(loop_env, K2_LOOP_VERDICT=verdict, K2_LOOP_ROAD="1"))
            if r.get("action") == "block":
                print("FAIL impl_complete_loop_%s" % verdict.lower(), r, file=sys.stderr)
                fails += 1
            else:
                print("ok impl_complete_loop_%s" % verdict.lower())
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env=dict(loop_env, K2_LOOP_VERDICT="ACCEPTED", K2_LOOP_ROAD="0"))
        if r.get("action") != "block" or "brief.py" not in (r.get("message") or ""):
            print("FAIL impl_complete_loop_without_road", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_complete_loop_without_road")
        r = run("", roots, cwd=cwd, tool="kanban_request_review", extra_input={"reviewer": "reviewer"}, extra_env=dict(loop_env, K2_LOOP_VERDICT="ACCEPTED", K2_LOOP_ROAD="1"))
        if r.get("action") != "block" or "loop card" not in (r.get("message") or ""):
            print("FAIL impl_request_review_on_loop_card", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_request_review_on_loop_card")
        # the durable form: the loop record under the allow root names the card, the official log shows the road
        loop_root = Path(td) / "hermes-root-loop"
        (loop_root / "kanban" / "logs").mkdir(parents=True)
        loop_home = loop_root / "profiles" / "implementer"
        loop_home.mkdir(parents=True)
        (loop_root / "kanban" / "logs" / "t_loop.log").write_text(
            "Query: work kanban task t_loop\n"
            "  ┊ 📚 skill  fix-until-green\n"
            "  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .  0.3s\n"
            "  ┊ 🔧 patch     /projects/modernized/pom.xml  0.2s\n"
            "  ┊ 💻 $         bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .  70.4s\n"
            "  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster c:1 --card t_loop  7.4s [exit 1]\n"
            "REVERTED c:1 attempt 1/3: measure [1, 1, 0] did not decrease from [1, 1, 0]\n",
            encoding="utf-8",
        )
        (dest / "verification" / "loop").mkdir(parents=True, exist_ok=True)
        (dest / "verification" / "loop" / "steps.json").write_text(
            json.dumps({"schema": "rhoai3.loop-steps/v1", "steps": [{"card": "", "cluster": "bootstrap"}], "rejected": [{"card": "t_loop", "cluster": "c:1", "reason": "no progress"}], "attempts": {"c:1": 1}}),
            encoding="utf-8",
        )
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env={"HERMES_PROFILE": "implementer", "HERMES_HOME": str(loop_home), "HERMES_KANBAN_TASK": "t_loop", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block":
            print("FAIL impl_complete_loop_record_and_log", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_complete_loop_record_and_log")
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env={"HERMES_PROFILE": "implementer", "HERMES_HOME": str(loop_home), "HERMES_KANBAN_TASK": "t_other", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") != "block":
            print("FAIL impl_complete_loop_unrecorded_card", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_complete_loop_unrecorded_card")
        (dest / "verification" / "loop" / "steps.json").write_text(
            json.dumps({"schema": "rhoai3.loop-steps/v1", "steps": [{"card": "", "cluster": "bootstrap"}], "pending": [{"card": "t_pend", "cluster": "c:1", "cause": "harness"}], "rejected": [], "attempts": {}}),
            encoding="utf-8",
        )
        (loop_root / "kanban" / "logs" / "t_pend.log").write_text(
            "Query: work kanban task t_pend\n"
            "  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .  0.3s\n"
            "  ┊ 💻 $         bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .  70.4s\n"
            "  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster c:1 --card t_pend  7.4s [exit 1]\n"
            "VERIFICATION_PENDING c:1 cause=harness card=t_pend: tests unknown\n",
            encoding="utf-8",
        )
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env={"HERMES_PROFILE": "implementer", "HERMES_HOME": str(loop_home), "HERMES_KANBAN_TASK": "t_pend", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") != "block":
            print("FAIL impl_complete_loop_pending_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_complete_loop_pending_refused")
        # v9 t_cc3b6aac: brief.py LOOP_WRONG_CARD / LOOP_CLUSTER_NOT_OPEN is a
        # legal stop. kanban_block must work without run-verify/advance in
        # the log; rummage and the rest of the road must not.
        brief_home = Path(td) / "brief-refuse-home"
        (brief_home / "kanban" / "logs").mkdir(parents=True)
        (brief_home / "kanban" / "logs" / "t_brief.log").write_text(
            "Query: work kanban task t_brief\n"
            "  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/"
            "scripts/brief.py --root . --cluster c:1  0.3s [exit 1]\n"
            "REFUSE: LOOP_CLUSTER_NOT_OPEN issued cluster c:1 is not on the open work list\n",
            encoding="utf-8",
        )
        (dest / "verification" / "loop").mkdir(parents=True, exist_ok=True)
        (dest / "verification" / "loop" / "issued.json").write_text(
            json.dumps({
                "schema": "rhoai3.loop-issued/v1",
                "task_id": "t_brief",
                "cluster": "c:1",
                "write_set": ["pom.xml"],
            }),
            encoding="utf-8",
        )
        brief_env = {
            "HERMES_PROFILE": "implementer",
            "HERMES_HOME": str(brief_home),
            "HERMES_KANBAN_TASK": "t_brief",
            "HERMES_WRITE_SAFE_ROOT": str(dest),
            "K2_FILES_WRITABLE": "pom.xml",
        }
        r = run("", roots, cwd=cwd, tool="kanban_block", extra_env=brief_env)
        if r.get("action") == "block":
            print("FAIL brief_refuse_kanban_block_tool", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_kanban_block_tool")
        r = run("hermes kanban block t_brief", roots, cwd=cwd, extra_env=brief_env)
        if r.get("action") == "block":
            print("FAIL brief_refuse_kanban_block_cli", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_kanban_block_cli")
        r = run(
            "python3 .hermes/skills/migration/fix-until-green/scripts/brief.py "
            "--root . --cluster c:1",
            roots,
            cwd=cwd,
            extra_env=brief_env,
        )
        if r.get("action") == "block":
            print("FAIL brief_refuse_rerun_brief", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_rerun_brief")
        r = run(
            "cat verification/loop/issued.json",
            roots,
            cwd=cwd,
            extra_env=brief_env,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "continue after mandated" not in msg:
            print("FAIL brief_refuse_rummage_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_rummage_refused")
        r = run(
            "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .",
            roots,
            cwd=cwd,
            extra_env=brief_env,
        )
        msg = r.get("message") or ""
        if r.get("action") != "block" or "continue after mandated" not in msg:
            print("FAIL brief_refuse_run_verify_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_run_verify_refused")
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_env=brief_env)
        if r.get("action") != "block":
            print("FAIL brief_refuse_complete_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok brief_refuse_complete_refused")
        # v7 item 8: inline python is refused on the issued loop card only; scripts the road names stay allowed
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1"}), encoding="utf-8")
        loop_card_env = {"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_loopcard", "K2_BOUND_GATE_EXIT": "0"}
        for cmdline in ("python3 -c \"import json; print(json.load(open('verification/loop/state.json')))\"", "cd /projects/modernized && python3 - <<'PY'\nprint(1)\nPY"):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") != "block" or "brief" not in (r.get("message") or ""):
                print("FAIL loop_card_inline_python_refused %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_card_inline_python_refused")
        for cmdline in ("python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .", "cat verification/loop/brief-c-1.json", "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root ."):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") == "block" and "inline python" in (r.get("message") or ""):
                print("FAIL loop_card_road_allowed %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_card_road_allowed")
        r = run("", roots, cwd=cwd, tool="execute_code", extra_input={"code": "print(1)"}, extra_env=loop_card_env)
        if r.get("action") != "block":  # refused by the mutation rule or the loop-card rule; either way it does not run
            print("FAIL loop_card_execute_code_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok loop_card_execute_code_refused")
        r = run("python3 -c \"print(1)\"", roots, cwd=cwd, extra_env={"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_notloop", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block" and "inline python" in (r.get("message") or ""):
            print("FAIL non_loop_card_inline_python_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok non_loop_card_inline_python_allowed")
        # the evidence rule: a server the worker starts, a dev-profile build or a
        # jar it runs is not the measured artifact on a loop card (v9 t_d280284d)
        for cmdline in ("mvn quarkus:dev", "cd /projects/modernized && ./mvnw -q quarkus:dev -Dquarkus.http.port=8081",
                        "mvn -o quarkus:run", "java -jar target/quarkus-app/quarkus-run.jar", "mvn package -Dquarkus.profile=dev",
                        "quarkus dev", "nohup java -Dquarkus.http.port=8081 -jar target/quarkus-app/quarkus-run.jar &"):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") != "block" or "starting the application refused" not in (r.get("message") or ""):
                print("FAIL loop_card_app_start_refused %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_card_app_start_refused")
        for cmdline in ("bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance",
                        "cat verification/parity/receipt.json", "grep -n quarkus:dev pom.xml"):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") == "block" and "starting the application" in (r.get("message") or ""):
                print("FAIL loop_card_app_start_road_allowed %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_card_app_start_road_allowed")
        r = run("mvn quarkus:dev", roots, cwd=cwd, extra_env={"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_notloop", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block" and "starting the application" in (r.get("message") or ""):
            print("FAIL non_loop_card_app_start_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok non_loop_card_app_start_allowed")
        # H9b: advance.py under the terminal tool's own timeout, or a coreutils
        # `timeout 600` prefix, is the road step it always was
        for cmdline in ("timeout 600 python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster c:1 --card t_loopcard",
                        "python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster c:1 --card t_loopcard"):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") == "block":
                print("FAIL loop_card_advance_timeout_prefix_allowed %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_card_advance_timeout_prefix_allowed")
        # H9a (dest v9 t_2da2458b): the REAL hook payload -- tool_input, the Hermes PROCESS cwd (not the
        # session's), extra.task_id -- with the process cwd a directory that is NOT the dest root. The
        # file tools resolve a relative path against the session cwd (the dest root for a loop card), so
        # K2 must too: write_file / patch (mode replace, and mode patch with the path inside the V4A
        # text) on the AMENDED file pass, on a third file are refused, and sed on the third file is refused.
        (dest / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
        for name in ("Ctl.java", "Impl.java", "Other.java"):
            (dest / "src" / "main" / "java" / name).write_text("class X {}", encoding="utf-8")
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps(
            {"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1",
             "write_set": ["src/main/java/Ctl.java", "src/main/java/Impl.java"],
             "amendments": [{"path": "src/main/java/Impl.java", "reason": "the 5xx stack's first product frame"}]}), encoding="utf-8")
        real_env = dict(loop_card_env, K2_FILES_WRITABLE="src/main/java/Ctl.java", HERMES_WRITE_SAFE_ROOT=str(dest))
        real_extra = {"hook_event_name": "pre_tool_call", "session_id": "s1", "extra": {"task_id": "t_loopcard", "tool_call_id": "call-1"}}
        parent_cwd = str(dest.parent)
        v4a = "*** Begin Patch\n*** Update File: %s\n@@ class @@\n-class X {}\n+class Y {}\n*** End Patch\n"
        impl_rel, impl_abs, other_rel = "src/main/java/Impl.java", str(dest / "src/main/java/Impl.java"), "src/main/java/Other.java"
        for label, tl, ti in (("write_file rel", "write_file", {"path": impl_rel, "content": "x"}),
                              ("write_file abs", "write_file", {"path": impl_abs, "content": "x"}),
                              ("patch replace rel", "patch", {"mode": "replace", "path": impl_rel, "old_string": "X", "new_string": "Y"}),
                              ("patch replace abs", "patch", {"mode": "replace", "path": impl_abs, "old_string": "X", "new_string": "Y"}),
                              ("patch v4a rel", "patch", {"mode": "patch", "patch": v4a % impl_rel}),
                              ("patch v4a abs", "patch", {"mode": "patch", "patch": v4a % impl_abs})):
            r = run("", roots, cwd=parent_cwd, tool=tl, extra_input=ti, extra_payload=real_extra, extra_env=real_env)
            if r.get("action") == "block":
                print("FAIL amended_path_real_payload_allowed %s" % label, r, file=sys.stderr)
                fails += 1
            else:
                print("ok amended_path_real_payload_allowed")
        for label, tl, ti in (("write_file rel", "write_file", {"path": other_rel, "content": "x"}),
                              ("patch replace rel", "patch", {"mode": "replace", "path": other_rel, "old_string": "X", "new_string": "Y"}),
                              ("patch v4a rel", "patch", {"mode": "patch", "patch": v4a % other_rel}),
                              ("patch v4a abs", "patch", {"mode": "patch", "patch": v4a % str(dest / other_rel)}),
                              ("sed rel", "terminal", {"command": "sed -i 's/X/Y/' src/main/java/Other.java"}),
                              ("sed abs", "terminal", {"command": "sed -i 's/X/Y/' %s" % (dest / other_rel)})):
            r = run(ti.get("command", ""), roots, cwd=parent_cwd, tool=tl, extra_input={k: v for k, v in ti.items() if k != "command"},
                    extra_payload=real_extra, extra_env=real_env)
            if r.get("action") != "block" or "outside" not in (r.get("message") or ""):
                print("FAIL third_file_real_payload_refused %s" % label, r, file=sys.stderr)
                fails += 1
            else:
                print("ok third_file_real_payload_refused")
        # H9b: a card whose step is recorded ACCEPTED has one terminator; kanban_block on it is refused
        (dest / "verification" / "loop" / "steps.json").write_text(json.dumps({"steps": [
            {"cluster": "", "card": "", "verdict": "accepted", "commit": "0000000000"},
            {"cluster": "c:1", "card": "t_loopcard", "verdict": "accepted", "commit": "825dd0cabc123456"}]}), encoding="utf-8")
        (dest / "verification" / "loop" / "issued.json").unlink()
        r = run("", roots, cwd=cwd, tool="kanban_block", extra_input={"task_id": "t_loopcard", "kind": "needs_input", "reason": "LOOP_STALE_STATE"}, extra_env=loop_card_env)
        if r.get("action") != "block" or "acceptance of this card is recorded" not in (r.get("message") or "") or "825dd0cabc12" not in (r.get("message") or ""):
            print("FAIL accepted_card_block_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok accepted_card_block_refused")
        r = run("", roots, cwd=cwd, tool="kanban_complete", extra_input={"task_id": "t_loopcard"}, extra_env=dict(loop_card_env, K2_LOOP_ROAD="1", K2_LOOP_VERDICT="ACCEPTED"))
        if r.get("action") == "block" and "acceptance of this card is recorded" in (r.get("message") or ""):
            print("FAIL accepted_card_complete_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok accepted_card_complete_allowed")
        r = run("", roots, cwd=cwd, tool="kanban_block", extra_input={"task_id": "t_other", "kind": "needs_input", "reason": "x"},
                extra_env=dict(loop_card_env, HERMES_KANBAN_TASK="t_other"))
        if r.get("action") == "block" and "acceptance of this card is recorded" in (r.get("message") or ""):
            print("FAIL unaccepted_card_block_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok unaccepted_card_block_allowed")
        (dest / "verification" / "loop" / "steps.json").unlink()
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1"}), encoding="utf-8")
        # a loop card may not write a product path outside its write set: advance reverts the whole candidate over one
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1", "write_set": ["pom.xml"]}), encoding="utf-8")
        for target in ("tmp-deps/x.jar", "src/main/java/A.java"):
            r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / target), "content": "x"}, extra_env=loop_card_env)
            if r.get("action") != "block" or "outside this card write set" not in (r.get("message") or ""):
                print("FAIL loop_write_outside_write_set %s" % target, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_write_outside_write_set")
        for target in ("pom.xml", "verification/build/scratch.txt", "evidence/notes.json"):
            r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / target), "content": "x"}, extra_env=loop_card_env)
            if r.get("action") == "block" and "outside this card write set" in (r.get("message") or ""):
                print("FAIL loop_write_allowed %s" % target, r, file=sys.stderr)
                fails += 1
            else:
                print("ok loop_write_allowed")
        # ADR-015/ADR-019: the generated test roots are the harness's; a worker write there is refused even when
        # the card's write set (wrongly) names the file. The roots come from the generator's own declaration.
        sys.path.insert(0, str(HOOK.parent.parent / "skills" / "gates" / "generate-product-tests" / "scripts"))
        import parity_pom  # noqa: PLC0415
        gen_file = "%s/org/x/generated/AParityTest.java" % parity_pom.DEFAULT_OUT
        gen_res = "%s/generated/a.body" % parity_pom.DEFAULT_RESOURCES
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1", "write_set": ["pom.xml", gen_file, gen_res]}), encoding="utf-8")
        for target in (gen_file, gen_res):
            r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / target), "content": "x"}, extra_env=loop_card_env)
            if r.get("action") != "block" or "harness-owned generated test root" not in (r.get("message") or ""):
                print("FAIL generated_root_write_refused_despite_write_set %s" % target, r, file=sys.stderr)
                fails += 1
            else:
                print("ok generated_root_write_refused_despite_write_set")
        for cmdline in ("sed -n p ./verification/x > %s" % gen_file, "cp ./verification/x %s" % gen_file,
                        "tee %s < ./verification/x" % gen_file, "rm -f %s" % gen_file):
            r = run(cmdline, roots, cwd=cwd, extra_env=loop_card_env)
            if r.get("action") != "block" or "harness-owned generated test root" not in (r.get("message") or ""):
                print("FAIL generated_root_command_refused %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok generated_root_command_refused")
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / gen_file), "content": "x"}, extra_env={"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_story", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") != "block" or "harness-owned generated test root" not in (r.get("message") or ""):
            print("FAIL generated_root_refused_for_any_implementer", r, file=sys.stderr)
            fails += 1
        else:
            print("ok generated_root_refused_for_any_implementer")
        # the manifest can declare a root of its own; it is honoured too
        man = dest / parity_pom.GENERATED_MANIFEST
        man.parent.mkdir(parents=True, exist_ok=True)
        man.write_text(json.dumps({"out": "src/it-generated/java", "resources": "src/it-generated/resources"}), encoding="utf-8")
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "src/it-generated/java/B.java"), "content": "x"}, extra_env=dict(loop_card_env, HERMES_WRITE_SAFE_ROOT=str(dest)))
        if r.get("action") != "block" or "harness-owned generated test root" not in (r.get("message") or ""):
            print("FAIL generated_root_from_manifest_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok generated_root_from_manifest_refused")
        man.unlink()
        # an ordinary write in the write set is unaffected, and a reviewer reading the generated tests is unaffected
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "pom.xml"), "content": "x"}, extra_env=loop_card_env)
        if r.get("action") == "block":
            print("FAIL generated_root_rule_leaves_write_set_alone", r, file=sys.stderr)
            fails += 1
        else:
            print("ok generated_root_rule_leaves_write_set_alone")
        r = run("cat %s" % gen_file, roots, cwd=cwd, extra_env=loop_card_env)
        if r.get("action") == "block" and "harness-owned" in (r.get("message") or ""):
            print("FAIL generated_root_read_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok generated_root_read_allowed")
        # H4 (dest v9 t_4d75569c): amend-scope.py widened the ISSUED card's write set on the record (Pet.java), the
        # card body's files_writable stayed as minted, and K2 refused the file-tool write to the amended path --
        # while a terminal `sed -i` on it went unseen. The file tool honours the issued record beside the body's
        # list; terminal in-place editors and redirections name their operands and are checked against the same set.
        (dest / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
        for name in ("Ctl.java", "Pet.java", "Other.java"):
            (dest / "src" / "main" / "java" / name).write_text("class X {}", encoding="utf-8")
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps(
            {"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1",
             "write_set": ["src/main/java/Ctl.java", "src/main/java/Pet.java"],
             "amendments": [{"path": "src/main/java/Pet.java", "reason": "the order-only body difference is produced by Pet.getVisits()"}]}),
            encoding="utf-8")
        amended_env = dict(loop_card_env, K2_FILES_WRITABLE="src/main/java/Ctl.java")
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "src/main/java/Pet.java"), "content": "x"}, extra_env=amended_env)
        if r.get("action") == "block":
            print("FAIL amended_path_file_write_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok amended_path_file_write_allowed")
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "src/main/java/Other.java"), "content": "x"}, extra_env=amended_env)
        if r.get("action") != "block" or "outside" not in (r.get("message") or ""):
            print("FAIL unamended_path_file_write_refused", r, file=sys.stderr)
            fails += 1
        else:
            print("ok unamended_path_file_write_refused")
        for cmdline in ("sed -i 's/naturalOrder/reverseOrder/' src/main/java/Other.java",
                        "sed -i '' -e 's/a/b/' ./src/main/java/Other.java",
                        "sed --in-place=.bak -e 's/a/b/' src/main/java/Other.java",
                        "perl -pi -e 's/a/b/' src/main/java/Other.java",
                        "cd %s && sed -i 's/a/b/' src/main/java/Other.java" % dest,
                        "echo x > src/main/java/Other.java",
                        "cat verification/x >> src/main/java/Other.java"):
            r = run(cmdline, roots, cwd=cwd, extra_env=amended_env)
            if r.get("action") != "block" or "outside" not in (r.get("message") or ""):
                print("FAIL terminal_edit_outside_write_set_refused %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok terminal_edit_outside_write_set_refused")
        for cmdline in ("sed -i 's/naturalOrder/reverseOrder/' src/main/java/Pet.java",
                        "perl -pi -e 's/a/b/' src/main/java/Ctl.java",
                        "sed -n '1,5p' src/main/java/Other.java",
                        "sed -e 's/a/b/' src/main/java/Other.java | head",
                        "grep -n order src/main/java/Other.java",
                        "mvn -q verify 2>/dev/null"):
            r = run(cmdline, roots, cwd=cwd, extra_env=amended_env)
            if r.get("action") == "block":
                print("FAIL terminal_edit_in_write_set_or_read_allowed %r" % cmdline, r, file=sys.stderr)
                fails += 1
            else:
                print("ok terminal_edit_in_write_set_or_read_allowed")
        # without an issued record the body's list alone decides, as before
        (dest / "verification" / "loop" / "issued.json").unlink()
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "src/main/java/Pet.java"), "content": "x"}, extra_env=amended_env)
        if r.get("action") != "block" or "files_writable" not in (r.get("message") or ""):
            print("FAIL body_list_alone_without_issued_record", r, file=sys.stderr)
            fails += 1
        else:
            print("ok body_list_alone_without_issued_record")
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "task_id": "t_loopcard", "cluster": "c:1", "write_set": ["pom.xml"]}), encoding="utf-8")
        r = run("", roots, cwd=cwd, tool="write_file", extra_input={"path": str(dest / "tmp-deps/x.jar"), "content": "x"}, extra_env={"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": "t_notloop", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block" and "outside this card write set" in (r.get("message") or ""):
            print("FAIL non_loop_write_unrestricted", r, file=sys.stderr)
            fails += 1
        else:
            print("ok non_loop_write_unrestricted")
        (dest / "verification" / "loop" / "issued.json").unlink()
        r = run("", roots, cwd=cwd, tool="kanban_request_review", extra_input={"reviewer": "reviewer", "summary": "x"}, extra_env={"HERMES_PROFILE": "implementer", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block":
            print("FAIL impl_request_review_with_reviewer_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_request_review_with_reviewer_allowed")
        r = run("hermes kanban request-review t_x --reviewer reviewer", roots, cwd=cwd, extra_env={"HERMES_PROFILE": "implementer", "K2_BOUND_GATE_EXIT": "0"})
        if r.get("action") == "block":
            print("FAIL impl_request_review_cli_reviewer_allowed", r, file=sys.stderr)
            fails += 1
        else:
            print("ok impl_request_review_cli_reviewer_allowed")
    fails += scratch_removal_checks()
    return 1 if fails else 0


ADVANCE = (Path(__file__).resolve().parents[1] / "skills" / "migration" / "fix-until-green" / "scripts" / "advance.py")
ADVANCE_LINE = ("  ┊ 💻 $         python3 .hermes/skills/migration/fix-until-green/scripts/advance.py "
                "--root . --cluster c:1 --card t_scr  1.2s [exit 1]\n")


def scratch_refusal_line(paths: list[str]) -> str:
    """advance.py's LOOP_SCRATCH_IN_TREE line, built the way advance.py builds it."""
    return ("REFUSE: LOOP_SCRATCH_IN_TREE %d untracked file(s) outside this migration's product sit in the tree "
            "and moved the candidate digest: %s. The verified candidate is otherwise intact, so nothing is "
            "judged, no attempt is spent and the candidate stays where it is: remove the files (they are tool "
            "output, not a repair) and run advance.py again.\n"
            % (len(paths), ", ".join(paths[:8]) + (", ..." if len(paths) > 8 else "")))


def scratch_removal_checks() -> int:
    """v9: advance.py refused LOOP_SCRATCH_IN_TREE and asked for the named
    files to be removed; K2 refused the rm as a product-tree write while
    advance was red, so the worker could only block. The removal of exactly
    the named paths is allowed while that refusal is the latest advance
    output; nothing else is."""
    fails = 0
    src = ADVANCE.read_text(encoding="utf-8")
    # the format the hook parses is advance.py's own
    for frag in ('"REFUSE: LOOP_SCRATCH_IN_TREE %d untracked file(s) outside this migration\'s product sit in the tree "',
                 '"and moved the candidate digest: %s. The verified candidate is otherwise intact',
                 '", ".join(scratch[:8]) + (", ..." if len(scratch) > 8 else "")'):
        if frag not in src:
            print("FAIL scratch_refusal_format_drifted %r" % frag, file=sys.stderr)
            fails += 1
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "dest"
        (dest / "src" / "main" / "java").mkdir(parents=True)
        (dest / "io" / "quarkus").mkdir(parents=True)
        (dest / "io" / "quarkus" / "A.class").write_bytes(b"x")
        (dest / "io" / "quarkus" / "B.class").write_bytes(b"x")
        (dest / "notes.txt").write_text("x", encoding="utf-8")
        (dest / "pom.xml").write_text("<project/>", encoding="utf-8")
        (dest / "verification" / "loop").mkdir(parents=True)
        (dest / "verification" / "loop" / "issued.json").write_text(json.dumps(
            {"schema": "rhoai3.loop-issued/v1", "task_id": "t_scr", "cluster": "c:1",
             "write_set": ["src/main/java/App.java"]}), encoding="utf-8")
        home = Path(td) / "home"
        (home / "kanban" / "logs").mkdir(parents=True)
        log = home / "kanban" / "logs" / "t_scr.log"
        named = ["io/quarkus/A.class", "io/quarkus/B.class"]
        base_log = ("Query: work kanban task t_scr\n"
                    "  ┊ 💻 $         bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .  70.4s\n")
        log.write_text(base_log + ADVANCE_LINE + scratch_refusal_line(named), encoding="utf-8")
        roots = [str(dest)]
        env = {"HERMES_PROFILE": "implementer", "HERMES_HOME": str(home), "HERMES_KANBAN_TASK": "t_scr",
               "HERMES_WRITE_SAFE_ROOT": str(dest)}
        cwd = str(dest)

        def check(cmd: str, name: str, allowed: bool, needle: str = "") -> None:
            nonlocal fails
            r = run(cmd, roots, cwd=cwd, extra_env=env)
            blocked = r.get("action") == "block"
            if blocked == allowed or (needle and needle not in (r.get("message") or "")):
                print("FAIL %s %r" % (name, cmd), r, file=sys.stderr)
                fails += 1
            else:
                print("ok", name)

        for cmd in ("rm io/quarkus/A.class io/quarkus/B.class",
                    "rm -f io/quarkus/A.class",
                    "rm -rf io/quarkus/A.class io/quarkus/B.class",
                    "rm -r -f -- io/quarkus/B.class",
                    "rm %s" % (dest / "io" / "quarkus" / "A.class")):
            check(cmd, "scratch_removal_named_allowed", True)
        for cmd, why in (("rm pom.xml", "product file"),
                         ("rm -rf src/main/java", "product dir"),
                         ("rm -rf src", "product dir"),
                         ("rm notes.txt", "unnamed path"),
                         ("rm io/quarkus/A.class notes.txt", "one unnamed operand"),
                         ("rm -rf io", "ancestor of a named path"),
                         ("rm -rf io/quarkus/*.class", "glob"),
                         ("rm io/quarkus/?.class", "glob"),
                         ("rm io/quarkus/../quarkus/A.class", "dotdot"),
                         ("rm ../dest/io/quarkus/A.class", "dotdot"),
                         ("rm /etc/io/quarkus/A.class", "absolute outside root"),
                         ("rm -rf .", "root itself"),
                         ("rm -i io/quarkus/A.class", "unlisted flag"),
                         ("rm io/quarkus/A.class; rm pom.xml", "compound"),
                         ("rm io/quarkus/A.class && touch pom.xml", "compound"),
                         ("rm $(cat list) ", "substitution"),
                         ("mv io/quarkus/A.class /tmp/x", "not rm"),
                         ("cat io/quarkus/A.class", "not a removal")):
            check(cmd, "scratch_removal_refused (%s)" % why, False)
        # a rm of a product file names the red advance, as before
        check("rm pom.xml", "scratch_removal_product_message", False, "product-tree write refused")
        # re-running advance is still the legal next step
        check("python3 .hermes/skills/migration/fix-until-green/scripts/advance.py --root . --cluster c:1 --card t_scr",
              "scratch_rerun_advance_allowed", True)
        # a later tool call after the refusal does not withdraw it; a later
        # advance verdict does
        log.write_text(base_log + ADVANCE_LINE + scratch_refusal_line(named)
                       + "  ┊ 💻 $         bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root .  70.4s\n",
                       encoding="utf-8")
        check("rm io/quarkus/A.class", "scratch_removal_after_run_verify_allowed", True)
        log.write_text(base_log + ADVANCE_LINE + scratch_refusal_line(named) + ADVANCE_LINE
                       + "REVERTED c:1 attempt 1/3: measure [1, 1, 0] did not decrease from [1, 1, 0]\n",
                       encoding="utf-8")
        check("rm io/quarkus/A.class", "scratch_removal_after_later_verdict_refused", False, "product-tree write refused")
        log.write_text(base_log + ADVANCE_LINE + scratch_refusal_line(named) + ADVANCE_LINE
                       + "REFUSE: LOOP_CANDIDATE_CHANGED product tree edited after verification (verified a, on disk b); nothing promoted\n",
                       encoding="utf-8")
        check("rm io/quarkus/A.class", "scratch_removal_after_other_refusal_refused", False)
        # prose that quotes the refusal after another tool call is not advance output
        log.write_text(base_log + ADVANCE_LINE + "REVERTED c:1 attempt 1/3: no progress\n"
                       + "  ┊ 💻 $         cat verification/loop/state.json  0.1s\n" + scratch_refusal_line(named),
                       encoding="utf-8")
        check("rm io/quarkus/A.class", "scratch_removal_quoted_prose_refused", False)
        # the truncated list names only the paths it printed
        many = ["tmp-%d/x.class" % i for i in range(10)]
        log.write_text(base_log + ADVANCE_LINE + scratch_refusal_line(many), encoding="utf-8")
        check("rm -rf tmp-0/x.class tmp-7/x.class", "scratch_removal_truncated_named_allowed", True)
        check("rm tmp-8/x.class", "scratch_removal_truncated_unprinted_refused", False)
        check("rm ...", "scratch_removal_ellipsis_refused", False)
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
