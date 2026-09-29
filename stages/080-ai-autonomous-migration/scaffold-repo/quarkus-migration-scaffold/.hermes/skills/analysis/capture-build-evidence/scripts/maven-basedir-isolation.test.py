#!/usr/bin/env python3
"""v27 M1 (architect first-task investigation): the source analysis copy lives inside the destination
tree (<dest>/.derived/frozen-input), and Maven's launcher finds its project base by walking UP from the
working directory to the nearest .mvn. A source without its own .mvn therefore read the DESTINATION's
.mvn/maven.config (`-s .mvn/settings.xml`, resolved against the copy, where it does not exist) and every
build failed: "The specified user settings file does not exist".

With the real Maven launcher, in that exact nested layout (the destination's settings file present):
  * a copy with no .mvn fails without MAVEN_BASEDIR (the reproduction) and validates with it;
  * a copy with its OWN .mvn/maven.config naming its own settings file is honoured with MAVEN_BASEDIR
    (the source's build settings are kept, not replaced);
and every producer that runs Maven on the analysis copy pins MAVEN_BASEDIR to it.

Offline `validate` on a pom-packaging project downloads nothing. SKIP (exit 0, with the reason) when
mvn is not on PATH."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[2]
POM = ("<project xmlns=\"http://maven.apache.org/POM/4.0.0\"><modelVersion>4.0.0</modelVersion>"
       "<groupId>g</groupId><artifactId>a</artifactId><version>1</version><packaging>pom</packaging></project>")
SETTINGS = "<settings xmlns=\"http://maven.apache.org/SETTINGS/1.0.0\"/>"
PRODUCERS = {
    "analysis/capture-build-evidence/scripts/capture-build-evidence.sh": 'export MAVEN_BASEDIR="${COPY}"',
    "gates/capture-source-oracles/scripts/capture-source-scenarios.py": "MAVEN_BASEDIR=str(self.copy)",
    "analysis/scan-with-mta/scripts/mta-analyze-legacy.sh": 'export MAVEN_BASEDIR="${INPUT}"',
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _mvn(cwd: Path, basedir: Path | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("MAVEN_BASEDIR", "MAVEN_ARGS", "MAVEN_OPTS")}
    if basedir is not None:
        env["MAVEN_BASEDIR"] = str(basedir)
    return subprocess.run(["mvn", "-o", "-B", "-q", "validate"], cwd=str(cwd), env=env, text=True,
                          capture_output=True, timeout=300)


def main() -> int:
    for rel, needle in PRODUCERS.items():
        if needle not in (SKILLS / rel).read_text(encoding="utf-8"):
            return _fail("%s does not pin the Maven project base to the analysis copy (%s)" % (rel, needle))
    if not shutil.which("mvn"):
        print("SKIP: maven-basedir-isolation: mvn is not on PATH (the producers' pins were checked)")
        return 0
    with tempfile.TemporaryDirectory(prefix="mvn-basedir-") as td:
        dest = Path(td) / "modernized"
        (dest / ".mvn").mkdir(parents=True)
        (dest / ".mvn" / "maven.config").write_text("-s\n.mvn/settings.xml\n", encoding="utf-8")
        (dest / ".mvn" / "settings.xml").write_text(SETTINGS, encoding="utf-8")
        bare = dest / ".derived" / "frozen-input"
        bare.mkdir(parents=True)
        (bare / "pom.xml").write_text(POM, encoding="utf-8")

        p = _mvn(bare, None)
        if p.returncode == 0 or "settings file does not exist" not in (p.stdout + p.stderr):
            return _fail("the reproduction: without MAVEN_BASEDIR the copy inherits the destination's maven.config "
                         "(rc=%s): %s" % (p.returncode, (p.stdout + p.stderr)[-300:]))
        p = _mvn(bare, bare)
        if p.returncode != 0:
            return _fail("with MAVEN_BASEDIR pinned to the copy, a source without .mvn validates: %s" % (p.stdout + p.stderr)[-400:])

        own = dest / ".derived" / "own-config"
        (own / ".mvn").mkdir(parents=True)
        (own / "pom.xml").write_text(POM, encoding="utf-8")
        (own / ".mvn" / "maven.config").write_text("-s\n.mvn/source-settings.xml\n", encoding="utf-8")
        p = _mvn(own, own)
        if p.returncode == 0 or "source-settings.xml" not in (p.stdout + p.stderr):
            return _fail("the source's own maven.config must be read (a missing source-settings.xml is named): %s"
                         % (p.stdout + p.stderr)[-300:])
        (own / ".mvn" / "source-settings.xml").write_text(SETTINGS, encoding="utf-8")
        p = _mvn(own, own)
        if p.returncode != 0:
            return _fail("the source's own settings are honoured: %s" % (p.stdout + p.stderr)[-400:])
    print("OK: maven-basedir-isolation (real Maven, nested layout: a copy without .mvn inherits the destination's "
          "maven.config unless MAVEN_BASEDIR pins it; pinned, it validates; a copy with its own .mvn is honoured; "
          "all three producers pin it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
