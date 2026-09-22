#!/usr/bin/env python3
"""autostart-migration.sh: M1 always; M2 only when pins.planner.activation is activated; idempotent. Not dest."""
from __future__ import annotations

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "autostart-migration.sh"
SKILL = HERE.parent / "SKILL.md"
GOLDEN = HERE.parents[4]


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def write_fake_hermes(path: Path, store: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json, sys
from pathlib import Path
store = Path(__STORE__)
store.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
with (store / "argv.jsonl").open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["kanban", "show"]:
    path = store / (args[2] + ".json")
    if not path.is_file(): sys.exit(1)
    print(path.read_text()); sys.exit(0)
if args[:2] != ["kanban", "create"]:
    print("unexpected", args, file=sys.stderr); sys.exit(2)
rest = args[2:]
if "--json" not in rest or "--goal" in rest or "daemon" in rest or "--force" in rest or "--triage" in rest:
    print("OBJECT flag", rest, file=sys.stderr); sys.exit(2)
title = None; key = None; body = ""; parents = []; workspace = ""
i = 0
while i < len(rest):
    tok = rest[i]
    if tok == "--json": i += 1; continue
    if tok == "--idempotency-key": key = rest[i + 1]; i += 2; continue
    if tok == "--body": body = rest[i + 1]; i += 2; continue
    if tok == "--parent": parents.append(rest[i + 1]); i += 2; continue
    if tok == "--workspace": workspace = rest[i + 1]; i += 2; continue
    if tok.startswith("--"):
        i += 2 if i + 1 < len(rest) and not rest[i + 1].startswith("--") else 1
        continue
    if title is None: title = tok
    i += 1
if (title or "").startswith("M3 ") or (title or "").startswith("M4 "):
    print("OBJECT mint M3/M4 at dest-init", file=sys.stderr); sys.exit(2)
low = body.lower()
if "speckit" in low or "specify" in low or "token:" in low or "verdict:" in low or "ship:" in low:
    print("OBJECT forbidden body token", file=sys.stderr); sys.exit(2)
if not key:
    print("missing --idempotency-key", file=sys.stderr); sys.exit(2)
keys = store / "keys.json"
known = json.loads(keys.read_text(encoding="utf-8")) if keys.is_file() else {}
if key in known:
    print(json.dumps({"id": known[key]})); sys.exit(0)
if key == "m1-analyze": tid = "t_m1"
elif key == "m2-plan":
    if parents != ["t_m1"]:
        print("M2 must parent M1", parents, file=sys.stderr); sys.exit(2)
    tid = "t_m2"
else:
    print("unexpected idempotency key", key, file=sys.stderr); sys.exit(2)
known[key] = tid
keys.write_text(json.dumps(known), encoding="utf-8")
(store / (tid + ".json")).write_text(json.dumps({"task": {"id": tid, "title": title, "workspace_kind": "dir", "workspace_path": workspace.removeprefix("dir:")}, "parents": parents}))
print(json.dumps({"id": tid}))
""".replace("__STORE__", repr(str(store))),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_autostart(root: Path, fake_bin: Path, extra_env: dict[str, str] | None = None, after_m1: str = "") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    env.pop("HERMES_HOME", None)
    if extra_env:
        env.update(extra_env)
    args = ["bash", str(SCRIPT), "--root", str(root)]
    if after_m1:
        args += ["--after-m1", after_m1]
    return subprocess.run(args, text=True, capture_output=True, env=env)


def _pins(root: Path, activation: str | None) -> None:
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
    pins = {"schema": "rhoai3.tooling-pins/v1", "pins": {}}
    if activation is not None:
        pins["pins"]["planner"] = {"activation": activation}
    (root / ".hermes" / "pins.json").write_text(json.dumps(pins), encoding="utf-8")


def _argv_log(store: Path) -> list[list[str]]:
    p = store / "argv.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.is_file() else []


def assert_bodies_name_native_backings() -> int:
    """A card body must name every native/kernel script its paved road mandates."""
    text = SCRIPT.read_text(encoding="utf-8")
    bad = []
    for kind in ("m1", "m2"):
        steps = GOLDEN / ".hermes" / "skills" / "paved-road" / ("paved-road-" + kind) / "steps.json"
        doc = json.loads(steps.read_text(encoding="utf-8"))
        for step in doc.get("steps", []):
            if step.get("backing") not in ("native", "kernel"):
                continue
            name = str(step.get(step["backing"]) or "")
            if name and name not in text:
                bad.append("%s body does not name %s backing %r (step %s)" % (kind.upper(), step["backing"], name, step.get("id")))
    for line in bad:
        sys.stderr.write("FAIL: " + line + "\n")
    return 1 if bad else 0


def main() -> int:
    src = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ('"M3', "'M3", '"M4', "'M4", "--goal", "--triage", "swarm ", "decompose ", "specify", "speckit", "legacy-at-3.json"):
        if forbidden in src.replace("Never kanban swarm, decompose, link, triage, or daemon --force.", "").replace("triage, specify, decompose, swarm", ""):
            return _fail("script must not carry %r" % forbidden)
    for needed in ("--idempotency-key m1-analyze", "--idempotency-key m2-plan", "--skill paved-road-m1", "--skill paved-road-m2", 'PLANNER_ACTIVATION}" == "activated"', "kanban_request_review", "kanban_block", "skill_view", '--parent "${M1_ID}"'):
        if needed not in src:
            return _fail("script must carry %r" % needed)
    if "--skill scan-with-mta" in src or "--skill plan-migration-increments" in src:
        return _fail("script must not pin subskills on the card")
    if "When the instructions do not work" in SKILL.read_text(encoding="utf-8"):
        return _fail("dispatch-phase SKILL.md must not copy the SOUL stop-and-block clause")
    soul = GOLDEN / ".hermes" / "config" / "profiles" / "implementer.SOUL.md"
    if "kanban_block" not in soul.read_text(encoding="utf-8"):
        return _fail("implementer.SOUL.md needs bounded stop-and-block")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        # not activated (golden default): M1 only, idempotent
        root = tmp_p / "proj"
        root.mkdir()
        _pins(root, "not-activated")
        store = tmp_p / "store"
        fake_bin = tmp_p / "bin"
        fake_bin.mkdir()
        write_fake_hermes(fake_bin / "hermes", store)
        proc = run_autostart(root, fake_bin)
        if proc.returncode != 0:
            return _fail("first run: %s%s" % (proc.stdout, proc.stderr))
        status = json.loads((root / ".hermes" / "AUTOSTART-STATUS").read_text())
        if status.get("state") != "minted" or status.get("m1_id") != "t_m1" or status.get("m2_id"):
            return _fail("not-activated status: %s" % status)
        if status.get("planner_activation") != "not-activated" or "section 12" not in status.get("reason", ""):
            return _fail("status must name the activation gate: %s" % status)
        if len(_argv_log(store)) != 1:
            return _fail("expected 1 create, got %s" % _argv_log(store))
        proc2 = run_autostart(root, fake_bin)
        if proc2.returncode != 0 or len(_argv_log(store)) != 2 or set(json.loads((store / "keys.json").read_text())) != {"m1-analyze"}:
            return _fail("rerun must be idempotent on M1 only")
        # missing planner block == not activated
        root_np = tmp_p / "nopins"
        root_np.mkdir()
        _pins(root_np, None)
        store_np = tmp_p / "store-np"
        bin_np = tmp_p / "bin-np"
        bin_np.mkdir()
        write_fake_hermes(bin_np / "hermes", store_np)
        if run_autostart(root_np, bin_np).returncode != 0 or json.loads((root_np / ".hermes" / "AUTOSTART-STATUS").read_text()).get("m2_id"):
            return _fail("absent planner pin must not mint M2")
        # activated: M2 minted as child of M1 with the fixed key; idempotent
        root_a = tmp_p / "activated"
        root_a.mkdir()
        _pins(root_a, "activated")
        store_a = tmp_p / "store-a"
        bin_a = tmp_p / "bin-a"
        bin_a.mkdir()
        write_fake_hermes(bin_a / "hermes", store_a)
        proc = run_autostart(root_a, bin_a)
        if proc.returncode != 0:
            return _fail("activated run: %s%s" % (proc.stdout, proc.stderr))
        status = json.loads((root_a / ".hermes" / "AUTOSTART-STATUS").read_text())
        if status.get("m1_id") != "t_m1" or status.get("m2_id") != "t_m2" or status.get("planner_activation") != "activated":
            return _fail("activated status: %s" % status)
        argv = _argv_log(store_a)
        if len(argv) != 2 or argv[1][argv[1].index("--parent") + 1] != "t_m1" or argv[1][argv[1].index("--skill") + 1] != "paved-road-m2":
            return _fail("M2 argv: %s" % argv)
        if any(t in " ".join(argv[1]) for t in ("M3 ", "M4 ")):
            return _fail("dest-init must never mint M3/M4")
        run_autostart(root_a, bin_a)
        if set(json.loads((store_a / "keys.json").read_text())) != {"m1-analyze", "m2-plan"}:
            return _fail("activated rerun must reuse keys")
        # A manually started native M1 continues even with startup disabled.
        os.symlink(GOLDEN / ".hermes/lib", root_a / ".hermes/lib")
        before = len(_argv_log(store_a))
        proc = run_autostart(root_a, bin_a, {"AUTO_START_MIGRATION": "false"}, after_m1="t_m1")
        status = json.loads((root_a / ".hermes/AUTOSTART-STATUS").read_text())
        if proc.returncode or status.get("m2_id") != "t_m2" or status.get("after_m1") != "t_m1":
            return _fail("explicit M1 continuation must survive startup off: %s%s" % (proc.stdout, proc.stderr))
        calls = _argv_log(store_a)[before:]
        if len(calls) != 2 or calls[0][:3] != ["kanban", "show", "t_m1"] or "M1 ANALYZE" in calls[1]:
            return _fail("continuation must show M1 and create/reuse only M2: %s" % calls)
        task_path = store_a / "t_m1.json"
        task = json.loads(task_path.read_text())
        for key, value in (("workspace_path", "/another-run"), ("title", "M3 FIX")):
            original = task["task"][key]
            task["task"][key] = value
            task_path.write_text(json.dumps(task))
            before = len(_argv_log(store_a))
            bad = run_autostart(root_a, bin_a, after_m1="t_m1")
            if bad.returncode == 0 or len(_argv_log(store_a)) != before + 1:
                return _fail("wrong native M1 %s must refuse before any mint" % key)
            task["task"][key] = original
        task_path.write_text(json.dumps(task))
        # Continuation is not a grant of planner activation.
        os.symlink(GOLDEN / ".hermes/lib", root / ".hermes/lib")
        proc = run_autostart(root, fake_bin, {"AUTO_START_MIGRATION": "false"}, after_m1="t_m1")
        if proc.returncode or json.loads((root / ".hermes/AUTOSTART-STATUS").read_text()).get("m2_id"):
            return _fail("continuation must preserve inactive planner")
        # pilot: at dest-init (no bundle yet) M1 only; after the Operator seals the bundle on disk, a re-run mints M2; a seal for another bundle never mints M2
        sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
        from planner.canonical import digest  # noqa: E402

        def _pilot_root(name: str, seal_digest: str | None, with_bundle: bool) -> tuple[Path, Path, Path]:
            r = tmp_p / name
            (r / ".hermes").mkdir(parents=True)
            os.symlink(GOLDEN / ".hermes" / "lib", r / ".hermes" / "lib")
            bundle = {"schema": "rhoai3.evidence-bundle/v1", "producers": {"mta": {"status": "ok"}}, "obligations": []}
            if with_bundle:
                (r / "evidence" / "planning").mkdir(parents=True)
                (r / "evidence" / "planning" / "evidence-bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
            seal = {"run_id": "pilot-1", "authorized_by": "stage owner", "evidence_bundle_sha256": seal_digest if seal_digest is not None else digest(bundle)}
            (r / ".hermes" / "pins.json").write_text(json.dumps({"schema": "rhoai3.tooling-pins/v1", "pins": {"planner": {"activation": "pilot", "pilot": seal}}}), encoding="utf-8")
            st = tmp_p / (name + "-store")
            b = tmp_p / (name + "-bin")
            b.mkdir()
            write_fake_hermes(b / "hermes", st)
            return r, b, st

        r_init, b_init, _ = _pilot_root("pilot-init", None, with_bundle=False)
        proc = run_autostart(r_init, b_init)
        st_init = json.loads((r_init / ".hermes" / "AUTOSTART-STATUS").read_text())
        if proc.returncode != 0 or st_init.get("m2_id") or st_init.get("planner_activation") != "not-activated":
            return _fail("pilot before M1 (no bundle) must mint M1 only: %s %s" % (st_init, proc.stderr[-200:]))
        r_seal, b_seal, st_seal = _pilot_root("pilot-sealed", None, with_bundle=True)
        proc = run_autostart(r_seal, b_seal)
        st_s = json.loads((r_seal / ".hermes" / "AUTOSTART-STATUS").read_text())
        if proc.returncode != 0 or st_s.get("m2_id") != "t_m2" or st_s.get("planner_activation") != "pilot":
            return _fail("pilot seal bound to the bundle on disk must mint M2: %s %s" % (st_s, proc.stderr[-300:]))
        argv = _argv_log(st_seal)
        if argv[1][argv[1].index("--parent") + 1] != "t_m1":
            return _fail("pilot M2 must parent M1: %s" % argv[1])
        r_bad, b_bad, _ = _pilot_root("pilot-mismatch", "0" * 64, with_bundle=True)
        proc = run_autostart(r_bad, b_bad)
        st_b = json.loads((r_bad / ".hermes" / "AUTOSTART-STATUS").read_text())
        if proc.returncode != 0 or st_b.get("m2_id") or st_b.get("planner_activation") != "not-activated":
            return _fail("pilot seal for another bundle must not mint M2: %s" % st_b)
        # off
        off_root = tmp_p / "off"
        off_root.mkdir()
        _pins(off_root, "activated")
        off_store = tmp_p / "off-store"
        off_bin = tmp_p / "off-bin"
        off_bin.mkdir()
        write_fake_hermes(off_bin / "hermes", off_store)
        off = run_autostart(off_root, off_bin, extra_env={"AUTO_START_MIGRATION": "false"})
        if off.returncode != 0 or json.loads((off_root / ".hermes" / "AUTOSTART-STATUS").read_text()).get("state") != "skipped" or (off_store / "argv.jsonl").exists():
            return _fail("off must not mint")
    # golden pins must not be activated in this cut
    golden_pins = json.loads((GOLDEN / ".hermes" / "pins.json").read_text(encoding="utf-8"))["pins"]
    if str((golden_pins.get("planner") or {}).get("activation") or "").lower() == "activated":
        return _fail("golden pins.json must not activate the planner (SAD §12 gate not passed)")
    rc = assert_bodies_name_native_backings()
    if rc:
        return rc
    print("OK: autostart-migration (M1 only when not activated; M2 child of M1 when activated; pilot mints M2 only for the sealed bundle on disk; idempotent; off; golden not activated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
