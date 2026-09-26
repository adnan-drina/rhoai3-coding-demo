"""Shared plumbing for the RUNTIME fixture tests (V17-3/4/5): package a fixture
offline with the pinned platform, run a disposable PostgreSQL in podman on a
loopback port, boot the packaged jar, and speak HTTP to it.

Nothing here judges anything; each test asserts its own facts. A missing
prerequisite (tool, local artifact, container image, loopback port) raises
Skip with the precise reason -- never a pass. Containers and processes are
always removed."""
from __future__ import annotations

import contextlib
import json
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
FIXTURES = HERE.parent / "fixtures"
PG_IMAGE = "registry.redhat.io/rhel9/postgresql-16"
_OFFLINE = ("Cannot access", "offline mode", "Could not resolve", "could not be resolved",
            "Non-resolvable import POM", "has not been downloaded")


class Skip(Exception):
    pass


def pin() -> dict:
    return json.loads((GOLDEN / ".hermes" / "pins.json").read_text(encoding="utf-8"))["pins"]["quarkus_platform"]


def need_tools(*tools: str) -> None:
    for t in tools:
        if not shutil.which(t):
            raise Skip("%s is not on PATH" % t)


def package(root: Path, *props: str) -> tuple[bool, str]:
    """mvn -o package with the pin; (ok, output). An offline resolution gap is Skip."""
    p = pin()
    argv = ["mvn", "-B", "-q", "-o", "-s", str(GOLDEN / ".mvn" / "settings.xml"),
            "-Dquarkus.platform.group-id=%s" % p["group_id"], "-Dquarkus.platform.version=%s" % p["version"],
            *props, "package", "-DskipTests"]
    r = subprocess.run(argv, cwd=str(root), text=True, capture_output=True, timeout=900)
    out = r.stdout + r.stderr
    if r.returncode != 0:
        hit = next((n for n in _OFFLINE if n in out), "")
        if hit:
            raise Skip("the pinned platform's artifacts are not all in the local Maven repository (%s)"
                       % next((ln.strip() for ln in out.splitlines() if hit in ln), hit)[:240])
    return r.returncode == 0, out


def free_port() -> int:
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])
    except OSError as exc:
        raise Skip("no loopback port (%s)" % exc)


@contextlib.contextmanager
def postgres() -> Iterator[dict]:
    """A disposable PostgreSQL 16 (the local image; never pulled) on a random
    loopback port: {"url", "user", "password"}. Removed on exit."""
    need_tools("podman")
    img = subprocess.run(["podman", "image", "exists", PG_IMAGE], capture_output=True)
    if img.returncode != 0:
        raise Skip("the container image %s is not present locally (not pulled by design)" % PG_IMAGE)
    port = free_port()
    user, password, db = "fixture", secrets.token_hex(8), "fixture"
    name = "rhoai3-runtime-fixture-%s" % secrets.token_hex(4)
    run = subprocess.run(["podman", "run", "-d", "--rm", "--pull=never", "--name", name, "-p", "127.0.0.1:%d:5432" % port,
                          "-e", "POSTGRESQL_USER=%s" % user, "-e", "POSTGRESQL_PASSWORD=%s" % password,
                          "-e", "POSTGRESQL_DATABASE=%s" % db, PG_IMAGE], capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        raise Skip("podman could not start %s: %s" % (PG_IMAGE, (run.stderr or run.stdout).strip()[-240:]))
    try:
        deadline = time.time() + 90
        while True:
            ready = subprocess.run(["podman", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", user, "-d", db],
                                   capture_output=True, text=True)
            if ready.returncode == 0:
                break
            if time.time() > deadline:
                raise RuntimeError("PostgreSQL did not become ready: %s" % (ready.stdout + ready.stderr)[-200:])
            time.sleep(1)
        yield {"url": "jdbc:postgresql://127.0.0.1:%d/%s" % (port, db), "user": user, "password": password,
               "container": name}
    finally:
        subprocess.run(["podman", "rm", "-f", name], capture_output=True, timeout=120)


def http(method: str, url: str, body=None, raw: bytes | None = None) -> tuple[int, dict, str]:
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - the fixture's own loopback app
            return int(resp.status), {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), {k.lower(): v for k, v in exc.headers.items()}, exc.read().decode("utf-8", "replace")


@contextlib.contextmanager
def boot(root: Path, probe: str, props: dict[str, str] | None = None) -> Iterator[str]:
    """Run the packaged jar on a free loopback port; yield its base URL once
    `probe` answers. The log stays at root/run.log."""
    port = free_port()
    argv = ["java", "-Dquarkus.http.host=127.0.0.1", "-Dquarkus.http.port=%d" % port]
    argv += ["-D%s=%s" % (k, v) for k, v in sorted((props or {}).items())]
    argv += ["-jar", str(root / "target" / "quarkus-app" / "quarkus-run.jar")]
    log = (root / "run.log").open("w")
    proc = subprocess.Popen(argv, cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d" % port
    try:
        deadline = time.time() + 90
        while True:
            try:
                http("GET", base + probe)
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                if proc.poll() is not None or time.time() > deadline:
                    raise RuntimeError("the packaged application did not start: %s" % (root / "run.log").read_text()[-900:])
                time.sleep(0.5)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def edit(root: Path, rel: str, start: str, end: str, replacement: str) -> None:
    """Replace the text between the marker comments `start`..`end` (exclusive)."""
    p = root / rel
    text = p.read_text(encoding="utf-8")
    a, b = text.index(start), text.index(end)
    a = text.index("\n", a) + 1
    b = text.rindex("\n", 0, b) + 1
    p.write_text(text[:a] + replacement + text[b:], encoding="utf-8")
