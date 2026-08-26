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
) -> dict:
    env = os.environ.copy()
    env["K2_ALLOW_ROOT"] = os.pathsep.join(roots)
    if extra_env:
        env.update(extra_env)
    payload: dict = {"tool_name": tool, "tool_input": {"command": cmd}}
    if extra_input:
        payload["tool_input"].update(extra_input)
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
        expect_allow(
            "hermes kanban complete t_x",
            "complete_green_gate",
            cwd=cwd,
            extra_env={"K2_BOUND_GATE_EXIT": "0"},
        )
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

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
