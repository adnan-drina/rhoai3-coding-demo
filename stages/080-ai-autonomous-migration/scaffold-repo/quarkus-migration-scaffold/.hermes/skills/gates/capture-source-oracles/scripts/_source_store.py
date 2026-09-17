#!/usr/bin/env python3
"""The frozen source's database, held where the harness can observe it (ADR-020).

A refused write's effect on the SOURCE is only observable in the state the
source itself was left in. An in-process database is restored by restarting
the process, which is exactly what may not happen between the refused
request and the observation ("restarting from the original seed and calling
it a post-request observation" is refused). So for a revert-then-read
scenario the capture starts the source against a database of the SAME
engine, held by a separate server process built from the engine jar the
source's own artifact ships:

1. the server's database is initialised with the source's schema files and
   the variant dataset (the declared dataset plus the fixture statements);
2. the source is started with its datasource pointed at that server and the
   refused request is sent;
3. the engine's own full snapshot is written (retained, digested) -- the
   post-request state, before anything is changed;
4. the fixture's revert (computed by the derivation) is applied to that live
   database, checked -- it refuses unless it finds exactly the variant state
   on the fixture's rows -- and nothing else is touched;
5. the declared reads are taken through the still-running source as the
   base identity: the source's post-request state with only the fixture
   change undone.

Where the source's datasource is and which engine it is are read from the
source's OWN configuration files (a property whose value is an in-memory JDBC
URL of an engine this module knows); nothing names a specimen. An engine or a
configuration this module does not know is a typed reason, and the capture
then records that the source effect was NOT observed.
"""
from __future__ import annotations

import hashlib
import os
import signal
import socket
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESOURCES = Path("src") / "main" / "resources"
# engine -> (the in-memory URL prefix a source configures, the server main
# class, the jar name prefix inside the artifact, the server URL form)
ENGINES = {
    "hsqldb": ("jdbc:hsqldb:mem:", "org.hsqldb.server.Server", "hsqldb-", "jdbc:hsqldb:hsql://127.0.0.1:%d/%s"),
}
STORE_DB = "paritystore"
MECHANISM = "same-engine server database, observed live after the refused request"


def _properties(path: Path) -> list[tuple[str, str]]:
    """(key, raw value) pairs of a .properties file, in order; values keep
    their trailing whitespace the way the JVM's loader keeps it."""
    out: list[tuple[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.lstrip()
        if not line or line[0] in "#!":
            continue
        for i, ch in enumerate(line):
            if ch in "=:":
                out.append((line[:i].strip(), line[i + 1:].lstrip()))
                break
    return out


def discover(copy: Path) -> tuple[dict[str, Any], str]:
    """(the source's datasource as its own configuration declares it, why-not)."""
    found: list[dict[str, Any]] = []
    for p in sorted((Path(copy) / RESOURCES).glob("application*.properties")):
        props = _properties(p)
        for key, value in props:
            for engine, (prefix, _cls, _jar, _url) in ENGINES.items():
                if value.strip().startswith(prefix):
                    stem = key.rsplit(".", 1)[0]
                    siblings = dict(props)
                    found.append({"engine": engine, "file": p.relative_to(copy).as_posix(), "url_key": key,
                                  "url": value.strip(),
                                  "user_key": "%s.username" % stem if "%s.username" % stem in siblings else "",
                                  "user": siblings.get("%s.username" % stem, ""),
                                  "password_key": "%s.password" % stem if "%s.password" % stem in siblings else "",
                                  "password": siblings.get("%s.password" % stem, "")})
    keys = sorted({f["url_key"] for f in found})
    if not found:
        return {}, ("SOURCE_STORE_UNKNOWN the source's configuration (%s/application*.properties) names no in-memory "
                    "datasource of an engine the harness can hold outside the process (%s)"
                    % (RESOURCES.as_posix(), ", ".join(sorted(ENGINES))))
    if len(keys) != 1 or len({f["engine"] for f in found}) != 1:
        return {}, ("SOURCE_STORE_AMBIGUOUS the source's configuration names more than one in-memory datasource (%s)"
                    % ", ".join("%s in %s" % (f["url_key"], f["file"]) for f in found))
    return dict(found[0]), ""


def schema_files(dataset: Path) -> list[Path]:
    """The schema files beside the declared dataset (every other *.sql there
    that declares a table) -- the rule the derivation reads them by."""
    out: list[Path] = []
    for p in sorted(dataset.parent.glob("*.sql")):
        if p.name == dataset.name or not p.is_file():
            continue
        try:
            if "CREATE TABLE" in p.read_text(encoding="utf-8", errors="replace").upper():
                out.append(p)
        except OSError:
            continue
    return out


def engine_jar(artifact: Path | None, engine: str, work: Path) -> tuple[Path | None, dict[str, str], str]:
    """(the engine jar the source's artifact ships, its record, why-not)."""
    if artifact is None or not Path(artifact).is_file():
        return None, {}, "SOURCE_STORE_NO_ENGINE the source artifact is not packaged, so its engine jar is unknown"
    prefix = ENGINES[engine][2]
    try:
        with zipfile.ZipFile(artifact) as z:
            names = sorted(n for n in z.namelist() if n.endswith(".jar") and Path(n).name.startswith(prefix))
            if len(names) != 1:
                return None, {}, ("SOURCE_STORE_NO_ENGINE the source artifact %s ships %d %s*.jar (%s); the engine the "
                                  "source runs is not identifiable" % (Path(artifact).name, len(names), prefix,
                                                                      ", ".join(names) or "none"))
            work.mkdir(parents=True, exist_ok=True)
            out = work / Path(names[0]).name
            out.write_bytes(z.read(names[0]))
    except (OSError, zipfile.BadZipFile) as exc:
        return None, {}, "SOURCE_STORE_NO_ENGINE the source artifact cannot be read: %s" % exc
    return out, {"name": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                 "from": "%s!/%s" % (Path(artifact).name, names[0])}, ""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class SourceStore:
    """One server-held database for one scenario: started, initialised,
    snapshotted, reverted, stopped."""

    def __init__(self, spec: dict[str, Any], jar: Path, jar_record: dict[str, str], work: Path, java: str = "java",
                 javac: str = "javac") -> None:
        self.spec = dict(spec)
        self.jar = jar
        self.jar_record = dict(jar_record)
        self.work = work
        self.java = java
        self.javac = javac
        self.port = 0
        self.proc: subprocess.Popen | None = None
        self.classes = work / "classes"

    @property
    def url(self) -> str:
        return ENGINES[self.spec["engine"]][3] % (self.port, STORE_DB)

    @property
    def user(self) -> str:
        # the JVM keeps a property value's trailing blanks and a server-held
        # database does not forgive them the way an in-process one does
        return str(self.spec.get("user") or "sa").strip()

    @property
    def password(self) -> str:
        return str(self.spec.get("password") or "")

    def source_overrides(self) -> dict[str, str]:
        """The configuration the source is started WITH to use this store:
        its own keys, pointed here. Recorded by key only."""
        out = {self.spec["url_key"]: self.url}
        if self.spec.get("user_key"):
            out[self.spec["user_key"]] = self.user
        return out

    def _runner(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run([self.java, "-cp", "%s%s%s" % (self.jar, os.pathsep, self.classes), "StoreDb", args[0],
                               self.url, self.user, self.password] + list(args[1:]), text=True, capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).strip()[-600:]

    def start(self, files: list[Path], timeout: float = 30.0) -> str:
        self.classes.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([self.javac, "-d", str(self.classes), str(HERE / "reset-db" / "StoreDb.java")],
                              text=True, capture_output=True)
        if proc.returncode != 0:
            return "SOURCE_STORE_RUNNER the store runner did not compile: %s" % (proc.stdout + proc.stderr)[-300:]
        self.port = _free_port()
        log = (self.work / "store-server.log").open("wb")
        self.proc = subprocess.Popen([self.java, "-cp", str(self.jar), ENGINES[self.spec["engine"]][1],
                                      "--database.0", "mem:%s" % STORE_DB, "--dbname.0", STORE_DB,
                                      "--port", str(self.port), "--silent", "true", "--trace", "false"],
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.time() + timeout
        while True:
            rc, out = self._runner("ping")
            if rc == 0:
                break
            if time.time() > deadline or self.proc.poll() is not None:
                self.stop()
                return "SOURCE_STORE_START the store server did not accept connections: %s" % out[-200:]
            time.sleep(0.5)
        rc, out = self._runner("apply", *[str(f) for f in files])
        if rc != 0:
            self.stop()
            return "SOURCE_STORE_INIT the store could not be initialised with %s: %s" % (
                ", ".join(f.name for f in files), out[-300:])
        return ""

    def snapshot(self, path: Path) -> tuple[dict[str, Any], str]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        rc, out = self._runner("script", str(path))
        if rc != 0 or not path.is_file():
            return {}, "SOURCE_STORE_SNAPSHOT the post-request snapshot was not written: %s" % out[-200:]
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size}, ""

    def observe(self, tables: list[str], path: Path) -> tuple[dict[str, Any], str]:
        """Every row of each scoped table, all columns, read in one
        transaction and retained with its digest."""
        path.parent.mkdir(parents=True, exist_ok=True)
        listing = path.with_suffix(".tables")
        listing.write_text("\n".join(tables) + "\n", encoding="utf-8")
        rc, out = self._runner("observe", str(listing), str(path))
        if rc != 0 or not path.is_file():
            return {}, "SOURCE_STORE_OBSERVE the database state was not read: %s" % out[-200:]
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if not ln.endswith("\t#table"))}, ""

    def revert(self, plan: dict[str, Any]) -> tuple[int, str]:
        rows = []
        for r in plan.get("rows") or []:
            fields = [str(r[k]) for k in ("table", "column", "variant_value", "baseline_value", "where_column",
                                          "where_value", "rows", "table_rows")]
            if any("\t" in f or "\n" in f for f in fields):
                return 2, "REVERT_PLAN_MALFORMED a plan value carries a tab or a newline"
            rows.append("\t".join(fields))
        tsv = self.work / "revert-plan.tsv"
        tsv.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return self._runner("revert", str(tsv))

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=15)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.proc = None


COMPARISON_DEFINITION = ("every row of each scoped table, every column, read in one transaction immediately before "
                         "the refused request and again after it completed (before any revert); the two observations "
                         "are compared as multisets of whole rows, so a changed value, an added or removed row and a "
                         "changed reference (a foreign-key column) all differ. Nothing is excluded: the fixture is the "
                         "same at both points.")
_DIFF_CAP = 20


def compare_observations(before: Path, after: Path) -> dict[str, Any]:
    """The comparison of two observations, table by table."""
    def rows(p: Path) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for ln in p.read_text(encoding="utf-8").splitlines():
            table, _, rest = ln.partition("\t")
            if rest == "#table":
                out.setdefault(table, [])
            else:
                out.setdefault(table, []).append(rest)
        return out
    b, a = rows(before), rows(after)
    diffs: dict[str, dict[str, Any]] = {}
    for table in sorted(set(b) | set(a)):
        left, right = sorted(b.get(table, [])), sorted(a.get(table, []))
        if left == right:
            continue
        rl, rr = list(left), list(right)
        for row in left:
            if row in rr:
                rr.remove(row)
                rl.remove(row)
        diffs[table] = {"before_count": len(left), "after_count": len(right),
                        "only_before": rl[:_DIFF_CAP], "only_after": rr[:_DIFF_CAP]}
    return {"equal": not diffs, "tables": sorted(set(b) | set(a)), "differences": diffs,
            "definition": COMPARISON_DEFINITION}


def open_store(copy: Path, artifact: Path | None, work: Path, java: str = "java") -> tuple[SourceStore | None, str]:
    """A store for this source, or why none can be held."""
    spec, why = discover(copy)
    if why:
        return None, why
    jar, record, why = engine_jar(artifact, spec["engine"], work)
    if why or jar is None:
        return None, why
    javac = str(Path(java).with_name("javac")) if os.sep in java else "javac"
    return SourceStore(spec, jar, record, work, java=java, javac=javac), ""
