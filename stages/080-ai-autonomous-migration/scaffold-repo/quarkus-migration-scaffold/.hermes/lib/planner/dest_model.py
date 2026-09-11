"""The destination's own structure, asked of the JDK compiler.

Three checks used to read Java with regular expressions, and each one was
wrong in a way regex cannot avoid: a fully qualified `@io.quarkus.arc.profile
.IfBuildProfile` was invisible, a redeclared `findAll()` looked underivable,
and a member that had been DELETED looked inherited. Absence of text is not
evidence of anything, and two identical annotations in one file are two
declarations, not one.

So the tree is compiled and asked. `DestModel.java` is the tool; this module
runs it, caches its answer against the content of the sources it read, and
fails CLOSED: a caller that cannot get a model must refuse, never assume.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

PROFILE_ANNOTATION_FQNS = (
    "org.springframework.context.annotation.Profile",
    "io.quarkus.arc.profile.IfBuildProfile",
    "io.quarkus.arc.profile.UnlessBuildProfile",
)
PROFILE_ANNOTATION_SIMPLE = tuple(f.rsplit(".", 1)[-1] for f in PROFILE_ANNOTATION_FQNS)

SOURCE_ROOTS = ("src/main/java", "src/test/java")
_TOOL = Path(__file__).resolve().parents[2] / "skills" / "migration" / "fix-until-green" / "scripts" / "jdk-dest-model" / "DestModel.java"


class DestModelUnavailable(RuntimeError):
    """The model could not be produced. Never downgrade this to an assumption."""


def _sources_digest(root: Path, source_root: str) -> str:
    h = hashlib.sha256()
    # WHICH root was asked for is part of the answer's identity. Without it
    # the first caller's model was handed to the second, so a request for the
    # test sources returned the main ones and the bootstrap invented a
    # test-path copy of a main condition (measured 2026-09-11).
    h.update(b"source_root\0")
    h.update(source_root.encode("utf-8"))
    h.update(b"\0")
    # The classpath is an INPUT to resolution: the same sources with and
    # without it are two different answers, and a cache that ignored it
    # handed back a resolved model for a tree that no longer builds.
    cp = Path(root) / "verification" / "build" / ".work" / "classpath.txt"
    h.update(b"classpath\0")
    h.update(cp.read_bytes() if cp.is_file() else b"")
    h.update(b"\0")
    for rel in SOURCE_ROOTS:
        base = Path(root) / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.java")):
            h.update(p.relative_to(root).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def _release(root: Path) -> str:
    try:
        pins = json.loads((Path(root) / ".hermes" / "pins.json").read_text(encoding="utf-8"))["pins"]
        return str((pins.get("quarkus_platform") or {}).get("java_release") or 21)
    except (OSError, ValueError, KeyError):
        return "21"


def dest_model(root: Path, *, source_root: str = "src/main/java", refresh: bool = False) -> dict[str, Any]:
    """The compiled model of `source_root`, cached against its content.

    Raises DestModelUnavailable when there is no JDK, no tool, or the tool
    refused. The caller's job is then to block, not to guess."""
    root = Path(root)
    src = root / source_root
    if not src.is_dir():
        raise DestModelUnavailable("%s is not a directory of this tree" % source_root)
    key = _sources_digest(root, source_root)
    work = root / "verification" / "build" / ".dest-model"
    cache = work / ("%s-%s.json" % (source_root.replace("/", "-"), key[:16]))
    if cache.is_file() and not refresh:
        try:
            doc = json.loads(cache.read_text(encoding="utf-8"))
            # and it is checked again on the way out: a cache entry that does
            # not say it is about this root is not about this root
            if str(doc.get("sources_digest") or "") == key and str(doc.get("source_root") or "") == source_root:
                return doc
        except (OSError, ValueError):
            pass
    if not _TOOL.is_file():
        raise DestModelUnavailable("the model tool %s is not in this tree" % _TOOL.name)
    java_home = os.environ.get("JAVA_HOME_21") or os.environ.get("JAVA_HOME") or ""
    bindir = (Path(java_home) / "bin") if java_home else None
    javac = str(bindir / "javac") if bindir and (bindir / "javac").is_file() else shutil.which("javac")
    java = str(bindir / "java") if bindir and (bindir / "java").is_file() else shutil.which("java")
    if not javac or not java:
        raise DestModelUnavailable("javac/java are not on PATH (a JDK, not a JRE, is the model)")
    # The tool is compiled once per tree, not once per question: a refresh of
    # both source roots used to rebuild it four times over.
    classes = work / "classes"
    stamp = classes / ".tool-sha256"
    tool_sha = hashlib.sha256(_TOOL.read_bytes()).hexdigest()
    if not (stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == tool_sha
            and (classes / "DestModel.class").is_file()):
        if classes.is_dir():
            shutil.rmtree(classes)
        classes.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([javac, "-d", str(classes), str(_TOOL)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise DestModelUnavailable("DestModel.java did not compile: %s" % (proc.stderr or proc.stdout)[-300:])
        stamp.write_text(tool_sha, encoding="utf-8")
    out = work / "raw.json"
    argv = [java, "-cp", str(classes), "DestModel", "--source", str(src), "--out", str(out), "--release", _release(root)]
    cp = root / "verification" / "build" / ".work" / "classpath.txt"
    if cp.is_file() and cp.stat().st_size:
        argv += ["--classpath", str(cp)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out.is_file():
        raise DestModelUnavailable("DestModel exited %s: %s" % (proc.returncode, (proc.stderr or "")[-300:]))
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["sources_digest"] = key
    doc["source_root"] = source_root
    doc["classpath_available"] = cp.is_file() and bool(cp.stat().st_size)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def above_members(typ: dict[str, Any]) -> list[dict[str, Any]]:
    """Every method reachable from a supertype, as SEEN FROM this type.

    `save(T)` on `JpaRepository<Vet,Integer>` is `save(p.Vet)` here, which is
    how an override is written; comparing the declared form would miss every
    generic override and comparing names would match every overload."""
    return list(typ.get("supertype_methods") or []) + list(typ.get("inherited") or [])


def types_of(model: dict[str, Any], rel_from_root: str, source_root: str = "src/main/java") -> list[dict[str, Any]]:
    """Every type the model has for a path expressed from the TREE root."""
    prefix = source_root.rstrip("/") + "/"
    want = rel_from_root[len(prefix):] if rel_from_root.startswith(prefix) else rel_from_root
    return [t for t in model.get("types") or [] if str(t.get("path") or "") == want]


def profile_conditions(model: dict[str, Any], source_root: str = "src/main/java") -> list[dict[str, Any]]:
    """Every profile condition the model found, one row per DECLARATION.

    Two identical annotations on two members of one file are two rows: they
    are two decisions, and approving one has never meant approving the other.
    `resolution` says whether the compiler could name the annotation; only a
    fully resolved condition may be retired."""
    out: list[dict[str, Any]] = []
    prefix = source_root.rstrip("/") + "/"
    for t in model.get("types") or []:
        path = prefix + str(t.get("path") or "")
        fqn = str(t.get("fqn") or "")
        # A simple name an import binds unambiguously IS resolved, whether or
        # not the dependency was on the classpath. A wildcard import is not a
        # binding, and neither is a name nothing imports.
        imports = [str(i) for i in (t.get("imports") or [])]
        bound = {i.rsplit(".", 1)[-1]: i for i in imports if not i.endswith(".*")}
        wild = any(i.endswith(".*") for i in imports)
        sites = [("", t.get("annotations") or [], str(t.get("resolution") or ""))]
        for m in t.get("declared") or []:
            sites.append((str(m.get("signature") or m.get("name") or ""), m.get("annotations") or [], str(m.get("resolution") or "")))
        for member, anns, res in sites:
            for a in anns:
                simple = str(a.get("simple") or "")
                if simple not in PROFILE_ANNOTATION_SIMPLE:
                    continue
                afqn = str(a.get("fqn") or "")
                # Two different questions. WHICH PROFILE this selects on is a
                # string literal and is readable in an unbuilt tree -- that is
                # all accounting needs. WHICH ANNOTATION this is can only be
                # settled by the compiler, and only a settled one may be
                # retired, because retirement removes code.
                value_known = bool(a.get("values")) and a.get("resolution") == "full"
                by_import = (not wild) and bound.get(simple, "") in PROFILE_ANNOTATION_FQNS
                fully_qualified = afqn in PROFILE_ANNOTATION_FQNS
                resolved = value_known and (fully_qualified or by_import)
                if fully_qualified and not afqn:
                    resolved = False
                for value in (a.get("values") or [""]):
                    out.append({
                        "path": path,
                        "type": fqn.rsplit(".", 1)[-1] or fqn,
                        "type_fqn": fqn,
                        "member": member,
                        "annotation": simple,
                        "annotation_fqn": afqn if afqn in PROFILE_ANNOTATION_FQNS else bound.get(simple, afqn),
                        "resolved_by": "compiler" if afqn in PROFILE_ANNOTATION_FQNS else ("import" if by_import else ""),
                        "profile": str(value),
                        "start": int(a.get("start") or -1),
                        "end": int(a.get("end") or -1),
                        "resolution": "full" if resolved else "inconclusive",
                        "value_known": value_known,
                    })
    return sorted(out, key=lambda r: (r["path"], r["member"], r["annotation"], r["profile"], r["start"]))


def condition_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """The identity a decision approves: this annotation on this declaration."""
    return (str(row.get("path") or ""), str(row.get("type") or ""), str(row.get("member") or ""),
            str(row.get("annotation") or ""), str(row.get("profile") or ""))


# --- the FROZEN source, from M1's own model -------------------------------
#
# Which members the legacy implemented as a state change is a question about
# resolved calls, not about text near a name. A body-scanning regular
# expression attributed EntityManager.persist to the member declared above the
# one that made the call, and a read-only findById was judged a write
# (measured live on the closeout tree, 2026-09-11).

STRUCTURE = Path("evidence") / "structure" / "structure.json"

# (owner simple name, method) pairs that change state. Owners are matched on
# the last segment so the javax/jakarta move does not change the answer.
WRITE_CALLS = {
    ("EntityManager", "persist"), ("EntityManager", "merge"), ("EntityManager", "remove"),
    ("Query", "executeUpdate"), ("TypedQuery", "executeUpdate"),
    ("JdbcTemplate", "update"), ("NamedParameterJdbcTemplate", "update"),
    ("SimpleJdbcInsert", "execute"), ("SimpleJdbcInsert", "executeAndReturnKey"),
    ("CrudRepository", "save"), ("CrudRepository", "saveAll"),
    ("CrudRepository", "delete"), ("CrudRepository", "deleteById"),
    ("JpaRepository", "save"), ("JpaRepository", "saveAll"),
    ("JpaRepository", "delete"), ("JpaRepository", "deleteById"), ("JpaRepository", "flush"),
    ("Session", "save"), ("Session", "update"), ("Session", "delete"), ("Session", "saveOrUpdate"),
}


def source_write_members(root: Path) -> tuple[set[str], str]:
    """(members the frozen source implemented as a state change, why-not).

    Read from M1's structural model of the SOURCE, whose call edges the
    compiler resolved. An empty set with a reason is not the same as an empty
    set: the caller must not read "nothing writes" out of "nothing was read"."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return set(), "M1's structural model %s is not in this tree" % STRUCTURE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return set(), "%s could not be read: %s" % (STRUCTURE, exc)
    out: set[str] = set()
    for t in doc.get("types") or []:
        for m in t.get("methods") or []:
            for call in m.get("calls") or []:
                owner = str(call.get("owner") or "").rsplit(".", 1)[-1]
                if (owner, str(call.get("name") or "")) in WRITE_CALLS:
                    out.add(str(m.get("name") or ""))
                    break
    return {n for n in out if n}, ""
