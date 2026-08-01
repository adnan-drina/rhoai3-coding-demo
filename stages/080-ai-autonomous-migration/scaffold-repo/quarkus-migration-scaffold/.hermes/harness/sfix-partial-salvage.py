#!/usr/bin/env python3
"""O-SFIXPARTIAL — salvage in-scope hunks from an O-SFIXSCOPE /tmp/strays archive.

When sensor-fix leaves the triggering sensor RED, the supervisor archives the
tip and hard-resets. This restores only paths owned by the task (Target/Owns)
from the archived SHA so partial Sonar/compile wins are not discarded.

Usage:
  sfix-partial-salvage.py <archive-dir> <tasks.md> <task-id-or-prefix>

Exit 0 if at least one in-scope path was restored to the working tree.
Exit 1 if nothing salvaged (out-of-scope-only or missing archive).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_JAVA = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java")
_SHARED = re.compile(
    r"(?<![\w./])(?:pom\.xml|"
    r"src/(?:main|test)/resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml)|"
    r"k8s/[A-Za-z0-9_./-]+)"
)
_CLAIM = re.compile(
    r"(?i)(?:^\s*\*?\*?(?:Absorbs|Owns|Target\s*design|Target|Design)\*?\*?\s*:)"
    r"|(?:→|->)\s*`?(?:src/|pom\.xml|k8s/)"
)


def _task_body(tasks: Path, tid: str) -> str:
    text = tasks.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"^#{2,6} +(T[-A-Za-z0-9]*\d+):", text, flags=re.M)
    for i in range(1, len(blocks) - 1, 2):
        if blocks[i] == tid or tid.startswith(blocks[i]):
            return blocks[i + 1]
        # prefix like "T-011 sensor fix" → T-011
        if tid.startswith(blocks[i]):
            return blocks[i + 1]
    m = re.match(r"(T-\d+)", tid)
    if m:
        want = m.group(1)
        for i in range(1, len(blocks) - 1, 2):
            if blocks[i] == want:
                return blocks[i + 1]
    return ""


def _owned_paths(body: str) -> set[str]:
    owned: set[str] = set()
    for line in body.splitlines():
        if _CLAIM.search(line) or "→" in line or "->" in line:
            for p in _JAVA.findall(line):
                owned.add(p)
            for p in _SHARED.findall(line):
                owned.add(p)
    # Also accept bare Target lines listing paths anywhere in body
    for p in _JAVA.findall(body):
        owned.add(p)
    return owned


def _in_scope(path: str, owned: set[str]) -> bool:
    if path in owned:
        return True
    for o in owned:
        if path == o or path.startswith(o.rstrip("/") + "/"):
            return True
        # directory ownership: Owns: src/main/java/com/demo/service/
        if o.endswith("/") and path.startswith(o):
            return True
        if path.startswith(o + "/") or o.startswith(path + "/"):
            return True
    # package-dir Owns without trailing slash
    for o in owned:
        if "/java/" in o and not o.endswith(".java"):
            if path.startswith(o.rstrip("/") + "/"):
                return True
    return False


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: sfix-partial-salvage.py <arch> <tasks.md> <T-NNN>", file=sys.stderr)
        return 2
    arch = Path(sys.argv[1])
    tasks = Path(sys.argv[2])
    tid = sys.argv[3]
    sha_file = arch / "sha.txt"
    if not sha_file.is_file():
        print("NO_SHA", file=sys.stderr)
        return 1
    sha = sha_file.read_text(encoding="utf-8").strip().splitlines()[0]
    if not sha:
        return 1
    body = _task_body(tasks, tid)
    owned = _owned_paths(body)
    if not owned:
        # Fall back: any src/ path from the tip (still better than total discard
        # when the task body omitted Target lines — WARN via stdout).
        print("WARN: no Owns/Target paths — salvaging src/ + pom.xml only")
        owned = {"src/", "pom.xml"}
    try:
        out = subprocess.check_output(
            ["git", "show", "--name-only", "--format=", sha],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"SHOW_FAIL:{e}", file=sys.stderr)
        return 1
    paths = [ln.strip() for ln in out.splitlines() if ln.strip()]
    kept = [p for p in paths if _in_scope(p, owned)]
    dropped = [p for p in paths if p not in kept]
    if not kept:
        print("NOTHING_IN_SCOPE")
        if dropped:
            print("dropped: " + " ".join(dropped[:20]))
        return 1
    restored = []
    for p in kept:
        try:
            subprocess.check_call(
                ["git", "checkout", sha, "--", p],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            restored.append(p)
        except subprocess.CalledProcessError:
            continue
    if not restored:
        print("CHECKOUT_FAIL")
        return 1
    print("SALVAGED " + " ".join(restored))
    if dropped:
        print("dropped_oos " + " ".join(dropped[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
