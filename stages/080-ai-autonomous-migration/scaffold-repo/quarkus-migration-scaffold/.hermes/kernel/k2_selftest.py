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


def run(cmd: str, roots: list[str], *, cwd: str | None = None, extra_cwd: str | None = None) -> dict:
    env = os.environ.copy()
    env["K2_ALLOW_ROOT"] = os.pathsep.join(roots)
    payload: dict = {"tool_name": "terminal", "tool_input": {"command": cmd}}
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

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
