#!/usr/bin/env python3
"""Capture the M-3 reference oracle from the FROZEN source (never from a destination).

Boots the frozen source's own packaged jar (the build M1 froze, bound by the
frozen source-manifest digest) with the source's OWN profiles and sends the
reference corpus (fixtures/reference-qualification/corpus.json), recording
each first response unmodified except for the Date header. One oracle per
(engine, security mode):

  postgresql  --spring.profiles.active=postgresql,spring-data-jpa on a
              disposable PostgreSQL 16 (podman) seeded with the source's own
              db/postgresql/initDB.sql + populateDB.sql; the corpus's sql
              steps read the committed state on a new connection
  hsqldb      the source's default profiles (hsqldb,spring-data-jpa), its
              in-process database; sql steps are recorded as not measurable

  security    disabled: the source default (petclinic.security.enable=false)
              enabled:  --petclinic.security.enable=true (BasicAuthenticationConfig)

Usage:
  reference-oracle-capture.py --source-jar <frozen jar> --legacy-root <frozen source tree>
      [--source-manifest <evidence/frozen/source-manifest.json>] [--engines postgresql,hsqldb]
      [--modes disabled,enabled] [--out <dir>]

The oracle records the jar's sha256, the source-manifest digest, the Java
runtime, the profiles, the engine/image and the seed scripts' digests, and
the corpus digest it was captured for. A later corpus change makes the
oracle unusable until it is re-captured (reference_qualification.load_oracle).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference_qualification as rq  # noqa: E402
import test_runtime_fixture as rt  # noqa: E402


def java_line() -> str:
    p = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return ((p.stderr or p.stdout).splitlines() or [""])[0].strip()


def capture(jar: Path, legacy: Path, manifest_digest: str, engine: str, mode: str, out_dir: Path) -> Path:
    corpus = rq.load_corpus()
    root = corpus["application_root"]
    port = rq.free_port()
    profiles = "postgresql,spring-data-jpa" if engine == "postgresql" else "hsqldb,spring-data-jpa"
    args = ["java", "-jar", str(jar), "--server.address=127.0.0.1", "--server.port=%d" % port,
            "--spring.profiles.active=%s" % profiles,
            "--petclinic.security.enable=%s" % ("true" if mode == "enabled" else "false")]
    with tempfile.TemporaryDirectory(prefix="refqual-oracle-") as td:
        log = Path(td) / "source.log"
        if engine == "postgresql":
            scripts = [legacy / "src/main/resources/db/postgresql/initDB.sql",
                       legacy / "src/main/resources/db/postgresql/populateDB.sql"]
            ctx = rq.seeded_postgres(scripts)
        else:
            ctx = None
        pg = ctx.__enter__() if ctx is not None else None
        try:
            if pg is not None:
                args += ["--spring.datasource.url=%s" % pg["url"], "--spring.datasource.username=%s" % pg["user"],
                         "--spring.datasource.password=%s" % pg["password"]]
            probe = "http://127.0.0.1:%d%sapi/owners/1" % (port, root)
            with rq.boot_process(args, Path(td), log, probe, timeout=180):
                steps = rq.run_corpus("http://127.0.0.1:%d" % port, corpus, mode, engine, pg)
            db = {"engine": engine}
            if pg is not None:
                db.update({"image": rt.PG_IMAGE, "seed_scripts": [
                    {"path": str(Path(s["path"]).relative_to(legacy)), "sha256": s["sha256"]} for s in pg["scripts"]]})
            else:
                db["note"] = "the source's in-process hsqldb, seeded by its own db/hsqldb scripts at start"
        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)
    oracle = {
        "schema": "rhoai3.reference-oracle/v1",
        "provenance": {
            "producer": "reference-oracle-capture.py",
            "captured_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_jar": jar.name, "source_jar_sha256": rq.sha256_file(jar),
            "source_manifest_digest": manifest_digest,
            "java": java_line(), "spring_profiles": profiles,
            "security_mode": mode, "db": db,
            "corpus_sha256": rq.corpus_sha256(),
            "note": "captured from the frozen source; the destination never writes this file",
        },
        "steps": steps,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("%s-security-%s.json" % (engine, mode))
    path.write_text(json.dumps(oracle, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-jar", required=True)
    ap.add_argument("--legacy-root", required=True)
    ap.add_argument("--source-manifest", default="")
    ap.add_argument("--engines", default="postgresql,hsqldb")
    ap.add_argument("--modes", default="disabled,enabled")
    ap.add_argument("--out", default=str(rq.ORACLE_DIR))
    a = ap.parse_args()
    jar, legacy = Path(a.source_jar), Path(a.legacy_root)
    if not jar.is_file():
        print("SKIP: reference-oracle-capture: the frozen source jar %s is not present" % jar)
        return 3
    digest = ""
    if a.source_manifest and Path(a.source_manifest).is_file():
        digest = json.loads(Path(a.source_manifest).read_text(encoding="utf-8")).get("digest", "")
    try:
        for engine in [e for e in a.engines.split(",") if e]:
            for mode in [m for m in a.modes.split(",") if m]:
                p = capture(jar, legacy, digest, engine, mode, Path(a.out))
                print("captured %s" % p)
    except rt.Skip as exc:
        print("SKIP: reference-oracle-capture: %s" % exc)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
