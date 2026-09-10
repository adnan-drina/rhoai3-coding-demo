#!/usr/bin/env python3
"""Package the destination, then start it against the decided database.

The compile/test tuple is a repair measure, not a readiness claim: a tree can
compile and pass its tests and still be unbuildable (pilot v7 reached [0,0,0]
and then failed the coverage plugin on Java 21 class files and Quarkus
augmentation on an unconfigured datasource). So the transition out of the
repair loop is measured here, in two gates:

  package  the FULL configured Maven lifecycle (`mvn verify`), coverage and
           integration checks retained, no goal skipped. Writes
           verification/build/package.json with the artifact and its digest.
  boot     that same artifact started with the decided datasource, given a
           bounded time to become ready, probed over HTTP. Writes
           verification/build/boot.json.

Neither gate is ever initialised to a pass: a gate that did not run is absent
from its receipt as ``ran: false``, and the work list treats that as unknown.
A failure that the destination cannot repair by editing its own tree (no
credentials, database unreachable) is recorded as a ``blocker``, not as a
repair obligation.

Exit 0 when every gate it was asked to run passed, 1 when one failed or was
blocked, 2 usage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: RUNTIME .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import write_canonical  # noqa: E402
from planner.decisions import DecisionsError, datasource, load_decisions  # noqa: E402
from planner.paths import VERIFY_BOOT, VERIFY_PACKAGE  # noqa: E402
from planner.worklist import runtime_environment_blocker  # noqa: E402

RUNNER = Path("target") / "quarkus-app" / "quarkus-run.jar"
LOG_TAIL_BYTES = 4000


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _tail(text: str) -> str:
    return text[-LOG_TAIL_BYTES:]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _failed_goal(log: str) -> str:
    for line in log.splitlines():
        if "Failed to execute goal" in line:
            return line.split("Failed to execute goal", 1)[1].strip()[:200]
    return ""


def package(root: Path, profile: str, mvn: str, timeout: int) -> dict:
    """mvn verify with nothing skipped. The artifact and its digest are the
    identity the boot gate must match: readiness evidence for a different
    build is not readiness evidence for this one."""
    log_p = root / "verification" / "build" / "package.log"
    log_p.parent.mkdir(parents=True, exist_ok=True)
    argv = [mvn, "-B", "verify"]
    if profile:
        argv.append("-Dquarkus.profile=%s" % profile)
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=str(root), text=True, capture_output=True, timeout=timeout)
        out = proc.stdout + proc.stderr
        rc = proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "") if isinstance(exc.stdout, str) else ""
        rc = 124
    log_p.write_text(out, encoding="utf-8")
    doc = {
        "schema": "rhoai3.verify-package/v1", "gate": "package", "ran": True, "rc": rc,
        "argv": argv, "profile": profile, "at": _now(), "elapsed_ms": int((time.time() - started) * 1000),
        "failed_goal": _failed_goal(out) if rc else "",
        "detail": ("mvn verify exited %d at %s" % (rc, _failed_goal(out) or "an unnamed goal")) if rc else "",
        "log": str(log_p.relative_to(root)), "log_tail": _tail(out) if rc else "",
        "artifact": "", "artifact_sha256": "",
    }
    blocker = runtime_environment_blocker(out) if rc else ""
    if blocker:
        doc["blocker"] = "environment: %s" % blocker
    artifact = root / RUNNER
    if artifact.is_file():
        doc["artifact"] = str(RUNNER)
        doc["artifact_sha256"] = _sha256(artifact)
    elif rc == 0:
        doc["rc"] = 1
        doc["detail"] = "mvn verify succeeded but %s does not exist; there is no artifact to start" % RUNNER
    return doc


def _probe(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - a local probe of our own app
            return int(resp.status), ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except Exception as exc:  # connection refused while it is still starting
        return 0, str(exc)


def boot(root: Path, ds: dict, package_doc: dict, port: int, root_path: str, timeout: int, java: str) -> dict:
    """Start the packaged artifact and give it a bounded time to answer.

    Readiness is an HTTP answer from the application, not a log line: a line
    can be printed before the datasource is touched."""
    doc = {
        "schema": "rhoai3.verify-boot/v1", "gate": "boot", "ran": False, "rc": None, "ready": False,
        "at": _now(), "artifact": package_doc.get("artifact", ""), "artifact_sha256": package_doc.get("artifact_sha256", ""),
        "port": port, "probe": "", "status": None, "elapsed_ms": 0, "detail": "", "log": "", "log_tail": "",
    }
    artifact = root / RUNNER
    if not artifact.is_file():
        doc["detail"] = "%s does not exist; packaging must succeed first" % RUNNER
        return doc
    missing = [str(ds[k]) for k in ("jdbc_url_env", "username_env", "password_env") if not os.environ.get(str(ds[k]))]
    if missing:
        doc["blocker"] = "environment: %s not set; the decided datasource (%s %s, instance %s) is not reachable from here" % (
            ", ".join(missing), ds.get("db_kind"), ds.get("db_version"), ds.get("instance"))
        doc["detail"] = doc["blocker"]
        return doc
    log_p = root / "verification" / "build" / "boot.log"
    log_p.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["QUARKUS_HTTP_PORT"] = str(port)
    if ds.get("profile"):
        env["QUARKUS_PROFILE"] = str(ds["profile"])
    url = "http://127.0.0.1:%d%s" % (port, root_path if root_path.startswith("/") else "/" + root_path)
    doc["probe"] = url
    doc["ran"] = True
    started = time.time()
    with log_p.open("wb") as sink:
        proc = subprocess.Popen([java, "-jar", str(RUNNER)], cwd=str(root), stdout=sink, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        try:
            while time.time() - started < timeout:
                if proc.poll() is not None:
                    break
                status, _ = _probe(url)
                if status and status < 500:
                    doc["ready"] = True
                    doc["status"] = status
                    break
                time.sleep(1.0)
            doc["elapsed_ms"] = int((time.time() - started) * 1000)
            if proc.poll() is not None and not doc["ready"]:
                doc["rc"] = int(proc.returncode)
                doc["detail"] = "the application exited with %d before becoming ready" % proc.returncode
            elif doc["ready"]:
                doc["rc"] = 0
            else:
                doc["rc"] = 124
                doc["detail"] = "no answer from %s within %ds (bounded startup)" % (url, timeout)
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=20)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        pass
    out = log_p.read_text(encoding="utf-8", errors="replace")
    doc["log"] = str(log_p.relative_to(root))
    if not doc["ready"]:
        doc["log_tail"] = _tail(out)
        blocker = runtime_environment_blocker(out)
        if blocker:
            doc["blocker"] = "environment: %s" % blocker
    return doc


def root_path_of(root: Path) -> str:
    p = root / "src" / "main" / "resources" / "application.properties"
    if p.is_file():
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = raw.strip()
            if s.startswith("quarkus.http.root-path="):
                return s.partition("=")[2].strip() or "/"
    return "/"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--gate", choices=["package", "boot", "both"], default="both")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--package-timeout", type=int, default=1800)
    ap.add_argument("--boot-timeout", type=int, default=180, help="bounded startup: the application answers within this or the gate fails")
    ap.add_argument("--mvn", default="mvn")
    ap.add_argument("--java", default="java")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        ds = datasource(load_decisions(root))
    except DecisionsError as exc:
        print("FAIL: RUNTIME %s" % exc, file=sys.stderr)
        return 1
    if not ds:
        print("FAIL: RUNTIME the effective datasource is not decided (decisions.yaml datasource under an accepted ADR); packaging and startup have no database to verify against", file=sys.stderr)
        return 1
    rc = 0
    pkg = None
    if args.gate in ("package", "both"):
        pkg = package(root, str(ds.get("profile") or ""), args.mvn, args.package_timeout)
        write_canonical(root / VERIFY_PACKAGE, pkg)
        print("%s: PACKAGE rc=%s %s" % ("OK" if pkg["rc"] == 0 else "REFUSE", pkg["rc"], pkg.get("detail") or pkg.get("artifact")))
        if pkg["rc"] != 0:
            rc = 1
    if args.gate in ("boot", "both"):
        if pkg is None:
            pkg = json.loads((root / VERIFY_PACKAGE).read_text(encoding="utf-8")) if (root / VERIFY_PACKAGE).is_file() else {}
        if rc == 0:
            b = boot(root, ds, pkg, args.port, root_path_of(root), args.boot_timeout, args.java)
            write_canonical(root / VERIFY_BOOT, b)
            print("%s: BOOT ready=%s rc=%s %s" % ("OK" if b.get("ready") else "REFUSE", b.get("ready"), b.get("rc"), b.get("detail") or b.get("probe")))
            if not b.get("ready"):
                rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
