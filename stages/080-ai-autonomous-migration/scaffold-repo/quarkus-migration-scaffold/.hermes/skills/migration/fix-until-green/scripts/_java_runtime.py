"""Which `java` starts the packaged destination, and whether it can.

One resolution for every starter of the artifact. run-verify.sh exports
JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}" and puts its bin/ first on PATH
before the boot gate runs, so the boot gate's `java` is that one. A starter
that took whatever `java` was first on PATH (dest v9: the parity runner on the
Dev Spaces image) started the same artifact on an older runtime and died with
UnsupportedClassVersionError (class file version 65.0), which then read as
"the destination did not become ready".

Order: $JAVA_HOME_21/bin/java, then $JAVA_HOME/bin/java, then `java` on PATH
-- the first variable that is set and non-empty wins, exactly as run-verify.sh
chooses. An explicit --java on either script overrides it.
"""
from __future__ import annotations

import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Mapping, Optional, Tuple

# class-file major version = Java feature version + 44 (JVMS 4.1; 52 is Java 8)
CLASS_MAJOR_OFFSET = 44


def resolve_java(env: Optional[Mapping[str, str]] = None) -> Tuple[str, str]:
    """(binary, source): source is JAVA_HOME_21, JAVA_HOME or PATH."""
    e = os.environ if env is None else env
    for var in ("JAVA_HOME_21", "JAVA_HOME"):
        home = str(e.get(var) or "")
        if home:
            return str(Path(home) / "bin" / "java"), var
    return "java", "PATH"


def feature_of(version_line: str) -> Optional[int]:
    """The feature version named by `java -version`'s first line.

    `openjdk version "21.0.4" 2024-07-16` -> 21; `java version "1.8.0_402"` -> 8."""
    m = re.search(r'version\s+"([^"]+)"', version_line or "")
    if not m:
        return None
    parts = re.split(r"[.+_-]", m.group(1))
    try:
        if parts[0] == "1" and len(parts) > 1:
            return int(parts[1])
        return int(parts[0])
    except ValueError:
        return None


def java_version(java: str, timeout: int = 30) -> Tuple[str, Optional[int], str]:
    """(first line of `java -version`, feature version, error). The JDK prints
    the banner on stderr; stdout is read too for a launcher that does not."""
    try:
        p = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return "", None, "%s -version could not run: %s" % (java, exc)
    lines = [ln.strip() for ln in ((p.stderr or "") + "\n" + (p.stdout or "")).splitlines() if ln.strip()]
    first = lines[0] if lines else ""
    if p.returncode != 0:
        return first, None, "%s -version exited %d: %s" % (java, p.returncode, first[:200])
    return first, feature_of(first), ""


def artifact_class_major(root: Path, app_dir: Path) -> Tuple[Optional[int], str]:
    """(class-file major version, where it was read) of the application's own
    code: the first `.class` entry of the first jar under <app_dir>/app, bytes
    6-7 of its header. (None, reason) when there is nothing to read."""
    app = Path(root) / app_dir / "app"
    jars = sorted(app.glob("*.jar")) if app.is_dir() else []
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as zf:
                for name in zf.namelist():
                    if not name.endswith(".class"):
                        continue
                    head = zf.open(name).read(8)
                    if len(head) < 8 or head[:4] != b"\xca\xfe\xba\xbe":
                        return None, "%s!%s is not a class file" % (jar.name, name)
                    return int.from_bytes(head[6:8], "big"), "%s!%s" % (jar.name, name)
        except (OSError, zipfile.BadZipFile) as exc:
            return None, "%s could not be read: %s" % (jar.name, exc)
    return None, "no .class entry under %s/*.jar" % (Path(app_dir) / "app").as_posix()


def runtime_check(root: Path, app_dir: Path, java: str, source: str) -> Tuple[dict, str]:
    """What the resolved runtime is and whether it can run the artifact.

    Returns (record, refusal). The refusal is empty when the runtime can run
    the application's classes or when either side is unknown -- an unreadable
    header is not a reason to refuse, and an unrunnable `java` is refused by
    its own error."""
    line, feature, err = java_version(java)
    major, where = artifact_class_major(root, app_dir)
    requires = (major - CLASS_MAJOR_OFFSET) if major is not None else None
    rec = {"binary": java, "source": source, "version": line, "feature": feature,
           "artifact_class": where, "artifact_class_major": major, "artifact_requires_java": requires}
    if err:
        return rec, "the resolved java %s (%s) cannot be run: %s" % (java, source, err)
    if feature is not None and requires is not None and requires > feature:
        return rec, ("the resolved java %s (%s) cannot run classes compiled for Java %d (%s, class file version %d)"
                     % (java, line, requires, where, major))
    return rec, ""
