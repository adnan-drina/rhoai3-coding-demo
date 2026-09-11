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
import re
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
from planner.canonical import canonical_bytes, write_canonical  # noqa: E402
from planner.decisions import DecisionsError, build_profiles, datasource, load_decisions  # noqa: E402
from planner.paths import VERIFY_BOOT, VERIFY_PACKAGE  # noqa: E402
from planner.worklist import runtime_environment_blocker  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import candidate_sha256  # noqa: E402

APP_DIR = Path("target") / "quarkus-app"
RUNNER = APP_DIR / "quarkus-run.jar"
LOG_TAIL_BYTES = 4000


def artifact_manifest(root: Path) -> tuple[dict[str, str], str]:
    """Every file of the packaged application, and one digest over all of them.

    A Quarkus fast-jar IS the quarkus-app directory: quarkus-run.jar is a thin
    launcher beside lib/, app/ and quarkus/. Hashing the launcher alone left
    the boot gate unable to notice that the thing it started had changed since
    packaging verified it (https://quarkus.io/version/3.27/guides/maven-tooling
    #using-fast-jar)."""
    base = Path(root) / APP_DIR
    files: dict[str, str] = {}
    if not base.is_dir():
        return files, ""
    for p in sorted(base.rglob("*")):
        if p.is_file():
            files[p.relative_to(base).as_posix()] = _sha256(p)
    return files, hashlib.sha256(canonical_bytes(files)).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _tail(text: str) -> str:
    return text[-LOG_TAIL_BYTES:]


ERROR_LINE = re.compile(r"^\[ERROR\]|\[error\]:")


def _errors(text: str, limit: int = 40) -> str:
    """The lines the build actually failed on.

    The tail of a Maven log is a summary, not a diagnosis: the [ERROR] lines
    naming the failing build step scroll past long before it ends. Classifying
    a failure from the tail measured the wrong part of the log (pilot v7: a
    repository method the platform could not derive was classified from
    surefire's closing lines and came out unclassified, at the wrong file)."""
    out = [line for line in (text or "").splitlines() if ERROR_LINE.search(line)]
    return "\n".join(out[:limit])


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


def configured_profiles(root: Path) -> list[str]:
    """What the tree itself says it builds with (quarkus.profile)."""
    prop = root / "src" / "main" / "resources" / "application.properties"
    if not prop.is_file():
        return []
    for raw in prop.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("quarkus.profile="):
            return [x.strip() for x in line.partition("=")[2].split(",") if x.strip()]
    return []


def package(root: Path, profiles: list[str], mvn: str, timeout: int, candidate: str) -> dict:
    """mvn verify with nothing skipped. The artifact and its digest are the
    identity the boot gate must match: readiness evidence for a different
    build is not readiness evidence for this one.

    The profile set comes from the BUILD PROFILE decision, never from the
    datasource's own profile field. A system property outranks
    application.properties, so passing the datasource profile here silently
    replaced the profile set the bootstrap had written and un-gated every bean
    the build was supposed to have (measured on the v8 draft: the tree said
    spring-data-jpa, the command said prod)."""
    log_p = root / "verification" / "build" / "package.log"
    log_p.parent.mkdir(parents=True, exist_ok=True)
    profile = ",".join(profiles)
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
        "argv": argv, "profile": profile, "profiles": list(profiles),
        "configured_profiles": configured_profiles(root), "at": _now(), "elapsed_ms": int((time.time() - started) * 1000),
        "failed_goal": _failed_goal(out) if rc else "",
        "detail": ("mvn verify exited %d at %s" % (rc, _failed_goal(out) or "an unnamed goal")) if rc else "",
        "log": str(log_p.relative_to(root)), "log_tail": _tail(out) if rc else "",
        "errors": _errors(out) if rc else "",
        "artifact": "", "artifact_sha256": "",
    }
    blocker = runtime_environment_blocker(out) if rc else ""
    if blocker:
        doc["blocker"] = "environment: %s" % blocker
    files, manifest = artifact_manifest(root)
    if files:
        doc["artifact"] = str(APP_DIR)
        doc["artifact_sha256"] = manifest
        doc["artifact_files"] = len(files)
        doc["artifact_manifest"] = files
    elif rc == 0:
        doc["rc"] = 1
        doc["detail"] = "mvn verify succeeded but %s is empty; there is no application to start" % APP_DIR
    doc["candidate_sha256"] = candidate
    return doc


def _probe(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - a local probe of our own app
            return int(resp.status), ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except Exception as exc:  # connection refused while it is still starting
        return 0, str(exc)


def port_owner(port: int, pid: int) -> tuple[bool, str]:
    """Is the process we started the one listening on this port?

    /proc is the referent: the listening socket's inode has to appear among our
    process's file descriptors. Without that check the gate passed on a 404
    from an unrelated server that happened to hold the port."""
    proc_net = Path("/proc/net/tcp")
    if not proc_net.is_file():
        return False, "/proc is not available, so the listener cannot be attributed to the process"
    want = "%04X" % int(port)
    inodes: set[str] = set()
    for name in ("tcp", "tcp6"):
        p = Path("/proc/net") / name
        if not p.is_file():
            continue
        for line in p.read_text(errors="replace").splitlines()[1:]:
            cols = line.split()
            if len(cols) < 10:
                continue
            local, state, inode = cols[1], cols[3], cols[9]
            if local.rsplit(":", 1)[-1] == want and state == "0A":  # LISTEN
                inodes.add(inode)
    if not inodes:
        return False, "nothing is listening on port %d" % port
    fd_dir = Path("/proc/%d/fd" % pid)
    if not fd_dir.is_dir():
        return False, "process %d has no /proc entry" % pid
    for fd in fd_dir.iterdir():
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:["):
            if target[len("socket:["):-1] in inodes:
                return True, ""
    return False, "the listener on port %d belongs to another process" % port


def database_ready(log_text: str, ds: dict) -> tuple[bool, str]:
    """Did the application actually bring its datasource up?

    An HTTP answer proves a web server. The decided JDBC extension appearing in
    the platform's own "Installed features" line, with no datasource error
    before it, is what proves the database side started."""
    artifact = str(ds.get("jdbc_extension") or "").split(":", 1)[-1]
    feature = artifact[len("quarkus-"):] if artifact.startswith("quarkus-") else artifact
    for line in log_text.splitlines():
        if "Installed features:" in line:
            if feature and feature in line:
                return True, "installed features include %s" % feature
            return False, "installed features do not include %s: %s" % (feature, line.strip()[-200:])
    return False, "the application never reported its installed features, so the datasource cannot be said to have started"


def boot(root: Path, ds: dict, profiles: list[str], package_doc: dict, port: int, root_path: str, timeout: int, java: str, candidate: str) -> dict:
    """Start the packaged artifact and give it a bounded time to answer.

    Every claim here is bound to something measured: the artifact is re-hashed
    before launch and must equal what packaging verified, the port must be free
    beforehand, the answer must come from the process we started, and the
    datasource must appear in the application's own startup report."""
    doc = {
        "schema": "rhoai3.verify-boot/v1", "gate": "boot", "ran": False, "rc": None, "ready": False,
        "at": _now(), "artifact": package_doc.get("artifact", ""), "artifact_sha256": "",
        "candidate_sha256": candidate, "port": port, "probe": "", "status": None, "elapsed_ms": 0,
        "pid": None, "attributed": False, "database_ready": False, "detail": "", "log": "", "log_tail": "",
    }
    files, manifest = artifact_manifest(root)
    if not files:
        doc["detail"] = "%s is empty; packaging must succeed first" % APP_DIR
        return doc
    doc["artifact_sha256"] = manifest
    if str(package_doc.get("artifact_sha256") or "") != manifest:
        doc["detail"] = ("the application on disk (%s) is not the one packaging verified (%s); "
                         "re-run the packaging gate before starting it"
                         % (manifest[:12], str(package_doc.get("artifact_sha256"))[:12]))
        return doc
    if candidate and str(package_doc.get("candidate_sha256") or "") not in ("", candidate):
        doc["detail"] = ("packaging verified candidate %s and the tree is now %s; startup evidence would be about another tree"
                         % (str(package_doc.get("candidate_sha256"))[:12], candidate[:12]))
        return doc
    missing = [str(ds[k]) for k in ("jdbc_url_env", "username_env", "password_env") if not os.environ.get(str(ds[k]))]
    if missing:
        doc["blocker"] = "environment: %s not set; the decided datasource (%s %s, instance %s) is not reachable from here" % (
            ", ".join(missing), ds.get("db_kind"), ds.get("db_version"), ds.get("instance"))
        doc["detail"] = doc["blocker"]
        return doc
    url = "http://127.0.0.1:%d%s" % (port, root_path if root_path.startswith("/") else "/" + root_path)
    doc["probe"] = url
    status, _ = _probe(url)
    if status:
        doc["detail"] = "port %d is already answering (status %s) before anything was started; a reading there would not be about this application" % (port, status)
        return doc
    log_p = root / "verification" / "build" / "boot.log"
    log_p.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["QUARKUS_HTTP_PORT"] = str(port)
    if profiles:
        env["QUARKUS_PROFILE"] = ",".join(profiles)
    doc["ran"] = True
    started = time.time()
    with log_p.open("wb") as sink:
        proc = subprocess.Popen([java, "-jar", str(RUNNER)], cwd=str(root), stdout=sink, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        doc["pid"] = proc.pid
        try:
            answered = 0
            while time.time() - started < timeout:
                if proc.poll() is not None:
                    break
                status, _ = _probe(url)
                if status and status < 500:
                    answered = status
                    break
                time.sleep(1.0)
            doc["elapsed_ms"] = int((time.time() - started) * 1000)
            doc["status"] = answered or None
            if proc.poll() is not None:
                doc["rc"] = int(proc.returncode)
                doc["detail"] = "the application exited with %d before becoming ready" % proc.returncode
            elif not answered:
                doc["rc"] = 124
                doc["detail"] = "no answer from %s within %ds (bounded startup)" % (url, timeout)
            else:
                owned, why = port_owner(port, proc.pid)
                doc["attributed"] = owned
                if not owned:
                    doc["rc"] = 1
                    doc["detail"] = "something answered %s but it is not the process this gate started: %s" % (url, why)
                else:
                    text = log_p.read_text(encoding="utf-8", errors="replace")
                    ok_db, why_db = database_ready(text, ds)
                    doc["database_ready"] = ok_db
                    doc["database_evidence"] = why_db
                    doc["rc"] = 0 if ok_db else 1
                    doc["ready"] = ok_db
                    if not ok_db:
                        doc["detail"] = "the application answered but its datasource did not start: %s" % why_db
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
        doc["errors"] = _errors(out)
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
        decisions = load_decisions(root)
        ds = datasource(decisions)
    except DecisionsError as exc:
        print("FAIL: RUNTIME %s" % exc, file=sys.stderr)
        return 1
    if not ds:
        print("FAIL: RUNTIME the effective datasource is not decided (decisions.yaml datasource under an accepted ADR); packaging and startup have no database to verify against", file=sys.stderr)
        return 1
    # The profile set is the BUILD PROFILE decision. The datasource's own
    # profile field says which profile that decision belongs to; if the build
    # does not activate it, the configuration measured here is not the
    # configuration decided, and that is a refusal rather than an override.
    profiles = [str(x) for x in (build_profiles(decisions).get("active") or [])]
    ds_profile = str(ds.get("profile") or "")
    if ds_profile and ds_profile not in profiles:
        print("FAIL: RUNTIME the datasource decision names profile %r and the build activates %s; a gate that passed the "
              "datasource profile on the command line would override the tree's own quarkus.profile (a system property "
              "outranks application.properties). Reconcile decisions.yaml build_profiles.active with datasource.profile."
              % (ds_profile, ", ".join(profiles) or "no profile"), file=sys.stderr)
        return 1
    in_tree = configured_profiles(root)
    if profiles and in_tree and sorted(in_tree) != sorted(profiles):
        print("FAIL: RUNTIME the tree is configured for %s and the decision says %s; run bootstrap-destination so the "
              "tree carries the decided set, rather than letting the command line replace it."
              % (",".join(in_tree), ",".join(profiles)), file=sys.stderr)
        return 1
    rc = 0
    pkg = None
    candidate = candidate_sha256(root)
    if args.gate in ("package", "both"):
        pkg = package(root, profiles, args.mvn, args.package_timeout, candidate)
        write_canonical(root / VERIFY_PACKAGE, pkg)
        print("%s: PACKAGE rc=%s %s" % ("OK" if pkg["rc"] == 0 else "REFUSE", pkg["rc"], pkg.get("detail") or pkg.get("artifact")))
        if pkg["rc"] != 0:
            rc = 1
    if args.gate in ("boot", "both"):
        if pkg is None:
            pkg = json.loads((root / VERIFY_PACKAGE).read_text(encoding="utf-8")) if (root / VERIFY_PACKAGE).is_file() else {}
        if rc == 0:
            b = boot(root, ds, profiles, pkg, args.port, root_path_of(root), args.boot_timeout, args.java, candidate)
            write_canonical(root / VERIFY_BOOT, b)
            print("%s: BOOT ready=%s rc=%s %s" % ("OK" if b.get("ready") else "REFUSE", b.get("ready"), b.get("rc"), b.get("detail") or b.get("probe")))
            if not b.get("ready"):
                rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
