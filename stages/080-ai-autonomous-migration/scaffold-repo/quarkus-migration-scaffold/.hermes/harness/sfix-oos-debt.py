#!/usr/bin/env python3
"""O-SFIXOOSREVERT — if remaining sonar deltas are outside task Owns, emit debt text.

Exit codes:
  0  all considered sonar paths are out-of-scope (caller: record_debt + skip sfix)
  1  has in-scope NEW failures or in-scope sonar — caller dispatches sfix
  2  usage / cannot decide

Stdout: one line `oos-debt:<paths>` or `in-scope:<n>` or `skip:<reason>`.

Considers NEW:sonar: from failure-delta first. If there is no NEW:sonar (post
scope-revert thrash: tip contentful, K7 new=0 or only OOS churn), falls back to
all sonar: keys in after-sig — still skip when every path is outside Owns and
there is no NEW:test/compile.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent


def owned_paths(tasks: Path, tid: str) -> set[str]:
    helper = HARNESS / "task-stage-paths.py"
    if not helper.is_file() or not tasks.is_file():
        return set()
    try:
        out = subprocess.check_output(
            [sys.executable, str(helper), str(tasks), tid],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        return set()
    return {ln.strip().replace("\\", "/") for ln in ln_split(out) if ln.strip()}


def ln_split(text: str) -> list[str]:
    return text.splitlines()


def parse_delta(delta: Path) -> tuple[list[str], list[str]]:
    """Return (sonar_paths_from_NEW, other_NEW_lines)."""
    sonar_paths: list[str] = []
    other: list[str] = []
    if not delta.is_file():
        return sonar_paths, other
    for ln in delta.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.startswith("NEW:"):
            continue
        if ln.startswith("NEW:sonar:"):
            rest = ln[len("NEW:sonar:") :]
            m = re.search(r"(src/(?:main|test)/[^\s:]+)", rest)
            if m:
                sonar_paths.append(m.group(1).replace("\\", "/"))
            else:
                leaf = rest.rsplit(":", 1)[-1].strip()
                if leaf:
                    sonar_paths.append(leaf)
        else:
            other.append(ln)
    return sonar_paths, other


def parse_after_sonar(after: Path) -> list[str]:
    """sonar:<rule>:<file> lines from after-sig (basenames or paths)."""
    out: list[str] = []
    if not after.is_file():
        return out
    for ln in after.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln.startswith("sonar:"):
            continue
        leaf = ln.rsplit(":", 1)[-1].strip()
        if leaf:
            out.append(leaf.replace("\\", "/"))
    return out


def path_owned(path: str, owned: set[str]) -> bool:
    p = path.replace("\\", "/")
    if p in owned:
        return True
    base = Path(p).name
    if "/" not in p:
        hits = [o for o in owned if Path(o).name == base]
        return len(hits) == 1
    for o in owned:
        if o.endswith("/" + p) or o.endswith(p) or p.endswith(o):
            return True
        if Path(o).name == base and ("/" + base) in ("/" + p):
            return True
    return False


def classify(paths: list[str], owned: set[str]) -> tuple[list[str], list[str]]:
    oos = [p for p in paths if not path_owned(p, owned)]
    ins = [p for p in paths if path_owned(p, owned)]
    return oos, ins


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "usage: sfix-oos-debt.py <tasks.md> <T-id> <failure-delta.txt> [after-sig.txt]",
            file=sys.stderr,
        )
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    delta = Path(sys.argv[3])
    after = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("/dev/null")
    owned = owned_paths(tasks, tid)
    if not owned:
        print("skip:no-owned-paths")
        return 1
    sonar_paths, other = parse_delta(delta)
    # NEW:test/compile → keep sfix (do not silence real tip debt).
    # NEW:sensor:* alone does not prove in-scope code debt.
    hard_other = [
        ln
        for ln in other
        if ln.startswith("NEW:test:") or ln.startswith("NEW:compile:")
    ]
    if hard_other:
        print(f"in-scope:other-new={len(hard_other)}")
        return 1
    if sonar_paths:
        oos, ins = classify(sonar_paths, owned)
        if ins:
            print(f"in-scope:{len(ins)}")
            return 1
        print("oos-debt:" + ",".join(dict.fromkeys(oos)))
        return 0
    # Fallback: no NEW:sonar — use after-sig sonar set (scope-revert re-RED)
    after_paths = parse_after_sonar(after)
    if not after_paths:
        print("skip:no-sonar")
        return 1
    oos, ins = classify(after_paths, owned)
    if ins:
        print(f"in-scope:after={len(ins)}")
        return 1
    print("oos-debt:after:" + ",".join(dict.fromkeys(oos)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
