#!/usr/bin/env python3
"""autostart-migration.sh mints M1+M2 only, idempotently. Not dest."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "autostart-migration.sh"
SKILL = HERE.parent / "SKILL.md"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def write_fake_hermes(path: Path, store: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json, sys
from pathlib import Path
store = Path(%r)
store.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
log = store / "argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] != ["kanban", "create"]:
    print("unexpected", args, file=sys.stderr)
    sys.exit(2)
rest = args[2:]
if "--json" not in rest:
    print("missing --json", file=sys.stderr)
    sys.exit(2)
if "--goal" in rest:
    print("OBJECT --goal", file=sys.stderr)
    sys.exit(2)
if "daemon" in rest or "--force" in rest:
    print("OBJECT kanban daemon --force", file=sys.stderr)
    sys.exit(2)
title = None
key = None
body = ""
parent = None
i = 0
while i < len(rest):
    tok = rest[i]
    if tok == "--json":
        i += 1
        continue
    if tok == "--idempotency-key":
        key = rest[i + 1]
        i += 2
        continue
    if tok == "--body":
        body = rest[i + 1]
        i += 2
        continue
    if tok == "--parent":
        parent = rest[i + 1]
        i += 2
        continue
    if tok.startswith("--"):
        i += 2 if i + 1 < len(rest) and not rest[i + 1].startswith("--") else 1
        continue
    if title is None:
        title = tok
    i += 1
if title in {"M3 IMPLEMENT", "M4 VERIFY"} or (title or "").startswith("M3 ") or (title or "").startswith("M4 "):
    print("OBJECT mint M3/M4 at T0", file=sys.stderr)
    sys.exit(2)
low = body.lower()
if "workflow run speckit" in low or "token:" in low or "verdict:" in low or "ship:" in low:
    print("OBJECT forbidden body token", file=sys.stderr)
    sys.exit(2)
if not key:
    print("missing --idempotency-key", file=sys.stderr)
    sys.exit(2)
keys = store / "keys.json"
known = json.loads(keys.read_text(encoding="utf-8")) if keys.is_file() else {}
if key in known:
    print(json.dumps({"id": known[key]}))
    sys.exit(0)
tid = "t_m1" if key == "m1-analyze" else "t_m2"
if key == "m2-plan" and parent != known.get("m1-analyze"):
    print("M2 parent must be M1 id", file=sys.stderr)
    sys.exit(2)
known[key] = tid
keys.write_text(json.dumps(known), encoding="utf-8")
print(json.dumps({"id": tid}))
"""
        % str(store),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_autostart(root: Path, fake_bin: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    env.pop("HERMES_HOME", None)
    return subprocess.run(
        ["bash", str(SCRIPT), "--root", str(root)],
        text=True,
        capture_output=True,
        env=env,
    )


def main() -> int:
    src = SCRIPT.read_text(encoding="utf-8")
    if "M3" in src and "k4_mint" not in src.split("M3", 1)[1][:200]:
        pass
    if "kanban daemon --force" in src and "Do not" not in src:
        return _fail("script must not invoke kanban daemon --force")
    if "create" in src and '"M3' in src:
        return _fail("script must not mint M3")
    if '"M4' in src or "'M4" in src:
        return _fail("script must not mint M4")
    if "--goal" in src:
        return _fail("script must not pass --goal")
    if "--idempotency-key m1-analyze" not in src or "--idempotency-key m2-plan" not in src:
        return _fail("script must pass dest-13-shaped idempotency keys")
    skill = SKILL.read_text(encoding="utf-8")
    if "When the instructions do not work" not in skill:
        return _fail("dispatch-phase SKILL.md needs stop-and-block")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        root = tmp_p / "proj"
        root.mkdir()
        store = tmp_p / "store"
        fake_bin = tmp_p / "bin"
        fake_bin.mkdir()
        write_fake_hermes(fake_bin / "hermes", store)
        proc = run_autostart(root, fake_bin)
        if proc.returncode != 0:
            return _fail("first run: %s%s" % (proc.stdout, proc.stderr))
        status = json.loads((root / ".hermes" / "AUTOSTART-STATUS").read_text())
        if status.get("state") != "minted":
            return _fail("status not minted: %s" % status)
        if status.get("m1_id") != "t_m1" or status.get("m2_id") != "t_m2":
            return _fail("ids: %s" % status)
        argv_log = [
            json.loads(line)
            for line in (store / "argv.jsonl").read_text().splitlines()
            if line.strip()
        ]
        if len(argv_log) != 2:
            return _fail("expected 2 creates, got %s" % argv_log)
        proc2 = run_autostart(root, fake_bin)
        if proc2.returncode != 0:
            return _fail("rerun: %s%s" % (proc2.stdout, proc2.stderr))
        argv_log = [
            json.loads(line)
            for line in (store / "argv.jsonl").read_text().splitlines()
            if line.strip()
        ]
        if len(argv_log) != 4:
            return _fail("rerun must call create again (idempotent keys): %s" % len(argv_log))
        status2 = json.loads((root / ".hermes" / "AUTOSTART-STATUS").read_text())
        if status2.get("m1_id") != "t_m1" or status2.get("m2_id") != "t_m2":
            return _fail("rerun changed ids: %s" % status2)
        keys = json.loads((store / "keys.json").read_text())
        if set(keys) != {"m1-analyze", "m2-plan"}:
            return _fail("keys: %s" % keys)

    print("OK: autostart-migration M1+M2 idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
