#!/usr/bin/env python3
"""The outcome authority never executes analyzer code from the destination tree.

Architect reproduction (2026-09-27): through outcome_lifecycle.requirement_measurement,
a replacement verification/build/.dest-model/classes/DestModel.class carrying
the expected .tool-sha256 stamp EXECUTED. Both files are worker-writable.

Every case runs the production measurement entry point
(outcome_lifecycle.requirement_measurement -> requirement_checks.measure ->
dest_model) on a real JDK in a CHILD process, because the authority binding is
once per process:

  worker   no binding: the worker-side analyzer (and, before the fix, the
           authority) uses the workspace cache -- the planted class runs.
  service  the real outcome_authority.Service is constructed first, exactly as
           the service does at start, which binds its private analyzer
           directory; the planted class, stamp, raw output and model cache in
           the workspace are never executed, read or written.

Checked:
 1. worker: a planted DestModel.class + matching stamp writes the harmless
    marker (the reproduction; the worker's own cache is its own business).
 2. service: the same planted class never runs (no marker), and the valid
    candidate still measures PASS while a stub candidate still FAILS.
 3. service: a planted class with no stamp, a wrong stamp, a garbage class and
    a forged model cache claiming the stub is fine select nothing: no marker,
    the stub still FAILS.
 4. service: the workspace .dest-model replaced by a symlink to an outside
    directory receives nothing; an analyzer directory that is a symlink, group-
    or world-accessible, or inside the destination tree is refused at bind.
 5. the service leaves no analyzer artifact in the destination tree.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[1]
CHECKS = ["unit:fragment-implementation", "unit:fragment-behaviour-bodies", "structure:single-injectable-implementation"]
MARKER_JAVA = """public class DestModel {
  public static void main(String[] a) throws Exception {
    java.nio.file.Files.writeString(java.nio.file.Path.of(System.getenv("RHOAI3_MARKER")), "EXECUTED FROM THE WORKSPACE");
    System.exit(3);
  }
}
"""


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------- child side
def child(mode: str, root: str, store: str, req_file: str) -> int:
    sys.path.insert(0, str(HERMES / "lib"))
    from planner import outcome_lifecycle as L
    if mode == "service":
        from planner.outcome_authority import Service
        Service(Path(root), Path(store))
    req = json.loads(Path(req_file).read_text(encoding="utf-8"))
    node = {"requirements": [req["id"]], "acceptance": {"requirement_checks": CHECKS}}
    got = L.requirement_measurement(Path(root), {"requirements": [req]}, node,
                                    {"items": [], "measure": {"known": True}}, [], "")
    # the three structural checks this fixture measures; the requirement's other
    # checks (package, startup, write effects) are unknown here by design
    print(json.dumps({k: v["status"] for k, v in (got or {}).items() if k in CHECKS}))
    return 0


def run_child(mode: str, root: Path, store: Path, req_file: Path, marker: Path) -> dict:
    env = dict(os.environ, RHOAI3_MARKER=str(marker), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, __file__, "--child", mode, str(root), str(store), str(req_file)],
                       capture_output=True, text=True, env=env, timeout=900)
    if p.returncode != 0:
        raise AssertionError("child %s failed: %s" % (mode, p.stderr[-800:]))
    return json.loads(p.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------- parent side
def plant_class(root: Path, stamp: str | None, *, garbage: bool = False) -> None:
    classes = root / "verification" / "build" / ".dest-model" / "classes"
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True)
    if garbage:
        (classes / "DestModel.class").write_bytes(b"\xca\xfe\xba\xbe not a class")
    else:
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "DestModel.java").write_text(MARKER_JAVA, encoding="utf-8")
            subprocess.run(["javac", "-d", str(classes), str(Path(t) / "DestModel.java")], check=True)
    if stamp is not None:
        (classes / ".tool-sha256").write_text(stamp, encoding="utf-8")


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP analyzer_isolation: no javac (NOT RUN)")
        return 0
    sys.path.insert(0, str(HERMES / "lib"))
    from planner import dest_model as DM
    from planner import source_requirements as SR
    from planner.canonical import load_json
    fbt = _load("fbt", HERMES / "skills/migration/fix-until-green/scripts/fragment-behaviour.test.py")
    n = fbt.A
    types, eps = fbt.source_types(n)
    doc = SR.derive(types=types, entry_points=eps, catalog=load_json(HERMES / "planning/catalogs/compat-mapping.json"),
                    decisions={"build_profiles": {"adr": "x", "active": [n["profile"]]}},
                    oracles=None, structure_complete=True, generator=None)
    parent = "%s.%s.%s" % (n["base"], n["repo_pkg"], n["parent"])
    req = next(r for r in doc["requirements"] if r["rule"] == "repository-architecture/v1" and r["facts"]["fragment"] == parent)
    good = fbt.bodies(n)
    stub = fbt.bodies(n, q2="    public Collection<%s> %s() { throw new UnsupportedOperationException(); }\n" % (n["entity"], n["q2"]))
    tool_sha = hashlib.sha256(DM._TOOL.read_bytes()).hexdigest()
    fails: list[str] = []

    def check(cond: bool, name: str, detail: object = "") -> None:
        print(("ok " if cond else "FAIL ") + name + ("" if cond else " :: %s" % (detail,)))
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory(prefix="an-iso-") as td:
        td = Path(os.path.realpath(td))
        req_file = td / "req.json"
        req_file.write_text(json.dumps(req), encoding="utf-8")

        def fresh(name: str, body: str) -> tuple[Path, Path, Path]:
            root = Path(fbt.make_root(str(td / name), n, body))
            return root, td / ("store-" + name), td / ("marker-" + name)

        # 1. the reproduction, worker side (= the authority before the fix)
        root, store, marker = fresh("worker", good)
        plant_class(root, tool_sha)
        run_child("worker", root, store, req_file, marker)
        check(marker.exists(), "1 worker path executes a planted class with the expected stamp (reproduction)")

        # 2. service: the planted class never runs; valid PASS, stub FAIL
        root, store, marker = fresh("svc-good", good)
        plant_class(root, tool_sha)
        got = run_child("service", root, store, req_file, marker)
        check(not marker.exists(), "2a service never executes the planted class")
        check(set(got.values()) == {"pass"}, "2b service measures the valid candidate PASS", got)
        root, store, marker = fresh("svc-stub", stub)
        plant_class(root, tool_sha)
        got = run_child("service", root, store, req_file, marker)
        check(not marker.exists() and set(got.values()) == {"fail"}, "2c service measures the stub candidate FAIL", got)

        # 3. missing / corrupt / misleading workspace cache selects nothing
        forged_src = fresh("forge-src", good)[0]
        run_child("worker", forged_src, td / "store-forge-src", req_file, td / "marker-forge-src")
        good_models = sorted((forged_src / "verification/build/.dest-model").glob("src-main-java-*.json"))
        for label, stamp, garbage in (("no stamp", None, False), ("wrong stamp", "0" * 64, False), ("garbage class", tool_sha, True)):
            root, store, marker = fresh("c-" + label.replace(" ", "-"), stub)
            plant_class(root, stamp, garbage=garbage)
            got = run_child("service", root, store, req_file, marker)
            check(not marker.exists() and set(got.values()) == {"fail"}, "3 %s selects nothing; stub still FAILS" % label, got)
        root, store, marker = fresh("c-forged-model", stub)
        plant_class(root, tool_sha)
        if good_models:
            key = DM._sources_digest(root, "src/main/java")
            forged = json.loads(good_models[0].read_text(encoding="utf-8"))
            forged["sources_digest"] = key
            (root / "verification/build/.dest-model" / ("src-main-java-%s.json" % key[:16])).write_text(json.dumps(forged), encoding="utf-8")
        got = run_child("service", root, store, req_file, marker)
        check(bool(good_models) and not marker.exists() and set(got.values()) == {"fail"},
              "3 a forged model cache claiming the stub is fine is ignored; stub still FAILS", got)

        # 4. symlinks: the workspace cache redirected outside receives nothing
        outside = td / "outside"
        outside.mkdir()
        root, store, marker = fresh("sym", good)
        dm = root / "verification/build/.dest-model"
        if dm.exists():
            shutil.rmtree(dm)
        dm.parent.mkdir(parents=True, exist_ok=True)
        dm.symlink_to(outside, target_is_directory=True)
        got = run_child("service", root, store, req_file, marker)
        check(set(got.values()) == {"pass"} and not any(outside.iterdir()),
              "4a a workspace .dest-model symlinked outside receives nothing", sorted(p.name for p in outside.iterdir()))
        for label, make in (("symlinked analyzer dir", "link"), ("group-readable analyzer dir", "mode"),
                            ("analyzer dir inside the tree", "inside")):
            code = ("import sys, os; sys.path.insert(0, %r); from pathlib import Path; from planner import dest_model as DM\n"
                    "root = Path(%r); real = Path(%r); real.mkdir(parents=True, exist_ok=True)\n"
                    "m = %r\n"
                    "if m == 'link':\n  d = real.parent / 'alias'; d.symlink_to(real, target_is_directory=True)\n"
                    "elif m == 'mode':\n  d = real; os.chmod(d, 0o750)\n"
                    "else:\n  d = root / 'verification' / 'priv'\n"
                    "try:\n  DM.bind_private_work(d, root); print('BOUND')\n"
                    "except DM.DestModelUnsafe as e:\n  print('REFUSED', e)\n") % (
                str(HERMES / "lib"), str(root), str(td / ("priv-" + make) / "real"), make)
            if make == "mode":
                # bind creates-or-tightens a missing dir; a pre-existing open one is re-checked
                code = code.replace("DM.bind_private_work(d, root)", "DM._check_private(d, os.path.realpath(root))")
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout
            check(out.startswith("REFUSED"), "4b %s is refused" % label, out.strip()[-200:])

        # 5. the service wrote no analyzer artifact into the destination tree
        root, store, marker = fresh("clean", good)
        run_child("service", root, store, req_file, marker)
        leaked = sorted(str(p.relative_to(root)) for p in (root / "verification/build").rglob("*")) if (root / "verification/build").exists() else []
        check(not [p for p in leaked if ".dest-model" in p], "5 no analyzer artifact in the destination tree", leaked)
        check((store / "analyzer").is_dir() and oct((store / "analyzer").stat().st_mode & 0o777) == "0o700",
              "5 the analyzer directory is private (0700) under the service store")

    if fails:
        print("FAIL: analyzer isolation (%d): %s" % (len(fails), ", ".join(fails)), file=sys.stderr)
        return 1
    print("OK: analyzer isolation (the worker path executes a planted class -- the reproduction; the authority "
          "service never executes, reads or writes analyzer artifacts in the destination tree; valid PASS, stub "
          "FAIL; missing/wrong stamp, garbage class and forged model cache select nothing; workspace symlinks "
          "receive nothing; unsafe private directories refused)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        raise SystemExit(child(*sys.argv[2:6]))
    raise SystemExit(main())
