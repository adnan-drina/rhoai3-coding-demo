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
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

PROFILE_ANNOTATION_FQNS = (
    "org.springframework.context.annotation.Profile",
    "io.quarkus.arc.profile.IfBuildProfile",
    "io.quarkus.arc.profile.UnlessBuildProfile",
)
PROFILE_ANNOTATION_SIMPLE = tuple(f.rsplit(".", 1)[-1] for f in PROFILE_ANNOTATION_FQNS)

SOURCE_ROOTS = ("src/main/java", "src/test/java")
GENERATED_SOURCES = "target/generated-sources"
_TOOL = Path(__file__).resolve().parents[2] / "skills" / "migration" / "fix-until-green" / "scripts" / "jdk-dest-model" / "DestModel.java"


class DestModelUnavailable(RuntimeError):
    """The model could not be produced. Never downgrade this to an assumption."""


def generated_source_dirs(root: Path) -> list[Path]:
    """The generator outputs the build compiles WITH the tree (openapi DTOs,
    annotation-processor sources). Without them every file that imports a
    generated type is only partially resolved, and a partially resolved file
    is one this model will not speak about -- which is how the controllers the
    Location repair touched were invisible to it (measured on v8, 2026-09-11)."""
    base = Path(root) / GENERATED_SOURCES
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and any(d.rglob("*.java")))


def _digest_generated(h: "hashlib._Hash", root: Path) -> None:
    h.update(b"generated\0")
    for d in generated_source_dirs(root):
        for p in sorted(d.rglob("*.java")):
            h.update(p.relative_to(root).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")


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
    _digest_generated(h, Path(root))
    # and the tool is an input too: a model cached by an older tool does not
    # carry the facts a newer one emits (unhandled_throws, throws_checked)
    h.update(b"tool\0")
    h.update(_tool_sha().encode("utf-8"))
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


def _tool_sha() -> str:
    return hashlib.sha256(_TOOL.read_bytes()).hexdigest() if _TOOL.is_file() else ""


def _jdk() -> tuple[str, str]:
    java_home = os.environ.get("JAVA_HOME_21") or os.environ.get("JAVA_HOME") or ""
    bindir = (Path(java_home) / "bin") if java_home else None
    javac = str(bindir / "javac") if bindir and (bindir / "javac").is_file() else shutil.which("javac")
    java = str(bindir / "java") if bindir and (bindir / "java").is_file() else shutil.which("java")
    if not javac or not java:
        raise DestModelUnavailable("javac/java are not on PATH (a JDK, not a JRE, is the model)")
    return javac, java


def _tool_classes(work: Path, javac: str) -> Path:
    """The tool is compiled once per tree, not once per question: a refresh of
    both source roots used to rebuild it four times over."""
    if not _TOOL.is_file():
        raise DestModelUnavailable("the model tool %s is not in this tree" % _TOOL.name)
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
    return classes


def _run_tool(root: Path, src: Path, work: Path) -> dict[str, Any]:
    """One compiler run over `src`, under THIS tree's compiler configuration:
    its classpath, its release and its generated sources. A baseline and a
    candidate modelled with different configurations would disagree about
    things neither of them changed."""
    javac, java = _jdk()
    classes = _tool_classes(work, javac)
    out = work / ("raw-%s.json" % hashlib.sha256(str(src).encode("utf-8")).hexdigest()[:12])
    argv = [java, "-cp", str(classes), "DestModel", "--source", str(src), "--out", str(out), "--release", _release(root)]
    cp = Path(root) / "verification" / "build" / ".work" / "classpath.txt"
    if cp.is_file() and cp.stat().st_size:
        argv += ["--classpath", str(cp)]
    for d in generated_source_dirs(root):
        argv += ["--also-source", str(d)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out.is_file():
        raise DestModelUnavailable("DestModel exited %s: %s" % (proc.returncode, (proc.stderr or "")[-300:]))
    doc = json.loads(out.read_text(encoding="utf-8"))
    out.unlink()
    return doc


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
    doc = _run_tool(root, src, work)
    cp = root / "verification" / "build" / ".work" / "classpath.txt"
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


# --- checked exceptions, asked of the compiler ----------------------------
#
# javac reports ONE unreported checked exception per compilation, whichever
# its flow analysis reaches first (control: three files with the same defect
# are one reported error). So a diagnostic count cannot say how many sites a
# transformation broke, and a diagnostic id -- which hashes the line -- cannot
# say whether the site it named is still there after an edit moved it. The
# model enumerates every site and names each without its line: the file, the
# type, the member, the resolved callee, the exception and which call of that
# callee in the member it is.


def member_ids(typ: dict[str, Any]) -> dict[str, str]:
    """A member's stable name: its simple name when the type declares only one
    member of that name, else its signature. Adding a parameter to addOwner()
    does not make the sites inside it new ones; two overloads stay two."""
    counts: dict[str, int] = {}
    for m in typ.get("declared") or []:
        counts[str(m.get("name") or "")] = counts.get(str(m.get("name") or ""), 0) + 1
    return {str(m.get("signature") or ""): (str(m.get("name") or "") if counts.get(str(m.get("name") or "")) == 1
                                            else str(m.get("signature") or ""))
            for m in typ.get("declared") or []}


def unhandled_sites(model: dict[str, Any], source_root: str = "src/main/java") -> list[dict[str, Any]]:
    """Every call site whose checked exception nothing handles, or whose
    handling the compiler could not decide (state inconclusive), with a
    line-free key."""
    prefix = source_root.rstrip("/") + "/"
    out: list[dict[str, Any]] = []
    for t in model.get("types") or []:
        path = prefix + str(t.get("path") or "")
        fqn = str(t.get("fqn") or "")
        ids = member_ids(t)
        for s in t.get("unhandled_throws") or []:
            member = str(s.get("member") or "")
            mid = ids.get(member, member)
            key = "%s|%s|%s|%s|%s#%d" % (path, fqn, mid, s.get("callee"), s.get("exception"), int(s.get("occurrence") or 0))
            out.append(dict(s, path=path, type=fqn, member_id=mid, key=key, type_resolution=str(t.get("resolution") or "")))
    return out


def site_signature(site: dict[str, Any]) -> str:
    """What makes two sites the same DEFECT: the callee and the exception."""
    return "%s!%s" % (site.get("callee"), site.get("exception"))


def site_for_diagnostic(model: dict[str, Any], item: dict[str, Any], source_root: str = "src/main/java") -> dict[str, Any] | None:
    """The enumerated site a javac diagnostic is about, or None.

    Matched on file, on a line inside the site's span and on the exception the
    message names; the narrowest span wins. A diagnostic that matches no site
    is not guessed at."""
    path = str(item.get("path") or "")
    try:
        line = int(item.get("line") or -1)
    except (TypeError, ValueError):
        return None
    msg = str(item.get("message") or item.get("detail") or "")
    rows = [s for s in unhandled_sites(model, source_root)
            if s["path"] == path and str(s.get("exception") or "") in msg
            and int(s.get("line") or -2) <= line <= max(int(s.get("end_line") or -2), int(s.get("line") or -2))]
    rows.sort(key=lambda r: (int(r.get("end") or 0) - int(r.get("start") or 0), int(r.get("start") or 0)))
    return rows[0] if rows else None


def diagnostic_identity(model: dict[str, Any] | None, item: dict[str, Any], source_root: str = "src/main/java") -> str:
    """A compile diagnostic's identity WITHOUT its line.

    chk:<site key> when the model can place it; otherwise diag:<file>|<code>|
    <message digest>, which is still line-free. Whether an issued failure is
    "still reported" is asked of this, never of the err: id, which hashes the
    line and so changes when an edit above the site moves it."""
    site = site_for_diagnostic(model, item, source_root) if model else None
    if site is not None:
        return "chk:" + site["key"]
    msg = re.sub(r"\s+", " ", str(item.get("message") or item.get("detail") or "")).strip()
    code = str(item.get("rule_id") or item.get("code") or "")
    return "diag:%s|%s|%s" % (item.get("path") or "", code, hashlib.sha256(msg.encode("utf-8")).hexdigest()[:12])


def model_at_commit(root: Path, ref: str, *, source_root: str = "src/main/java") -> dict[str, Any]:
    """The model of `source_root` as it was at commit `ref`, under THIS tree's
    compiler configuration (classpath, release, generated sources).

    A baseline and a candidate are only comparable when the same compiler
    looked at both the same way; the configuration is therefore taken from
    the tree being judged, and only the sources come from the commit."""
    root = Path(root)
    proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "%s^{commit}" % ref], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DestModelUnavailable("%s is not a commit of this tree" % ref)
    sha = proc.stdout.strip()
    h = hashlib.sha256()
    h.update(("commit\0%s\0%s\0" % (sha, source_root)).encode("utf-8"))
    cp = root / "verification" / "build" / ".work" / "classpath.txt"
    h.update(cp.read_bytes() if cp.is_file() else b"")
    _digest_generated(h, root)
    h.update(_tool_sha().encode("utf-8"))
    key = h.hexdigest()
    work = root / "verification" / "build" / ".dest-model"
    cache = work / ("commit-%s-%s.json" % (sha[:12], key[:16]))
    if cache.is_file():
        try:
            doc = json.loads(cache.read_text(encoding="utf-8"))
            if str(doc.get("sources_digest") or "") == key:
                return doc
        except (OSError, ValueError):
            pass
    arch = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", sha, "--", source_root], capture_output=True)
    if arch.returncode != 0:
        raise DestModelUnavailable("commit %s has no %s: %s" % (sha[:12], source_root, arch.stderr.decode("utf-8", "replace")[-200:]))
    tree = work / "trees" / sha[:16]
    if tree.is_dir():
        shutil.rmtree(tree)
    tree.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(arch.stdout)) as tf:
            try:
                tf.extractall(tree, filter="data")
            except TypeError:  # a Python without extraction filters
                tf.extractall(tree)
        doc = _run_tool(root, tree / source_root, work)
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    doc["sources_digest"] = key
    doc["source_root"] = source_root
    doc["commit"] = sha
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def callee_simple_name(callee: str) -> str:
    """java.net.URI.<init>(java.lang.String) -> URI; a.B.save(int) -> save."""
    head = str(callee).split("(", 1)[0]
    owner, _, name = head.rpartition(".")
    return owner.rsplit(".", 1)[-1] if name == "<init>" else name


def _absent_by_syntax(base_types: dict[tuple[str, str], dict[str, Any]], site: dict[str, Any]) -> str:
    """A proof, from the baseline's parse tree, that `site` did not exist; "" if none."""
    mid = str(site.get("member_id") or "")
    if not mid or mid.startswith("<"):
        return ""  # a field initializer or initializer block: no per-member call list
    bt = base_types.get((str(site.get("path") or ""), str(site.get("type") or "")))
    if bt is None:
        return "the type %s did not exist in the baseline" % site.get("type")
    ids = member_ids(bt)
    bm = next((m for m in bt.get("declared") or [] if ids.get(str(m.get("signature") or "")) == mid), None)
    if bm is None:
        return "the member %s did not exist in the baseline" % mid
    if "call_names" not in bm:
        return ""
    name = callee_simple_name(str(site.get("callee") or ""))
    made = sum(1 for n in bm.get("call_names") or [] if n == name)
    if made <= int(site.get("occurrence") or 0):
        return "the baseline member %s made %d call(s) named %s, so this one (occurrence %d) is new" % (mid, made, name, int(site.get("occurrence") or 0))
    return ""


def checked_exception_delta(root: Path, base_ref: str, paths: list[str] | None = None, *,
                            source_root: str = "src/main/java") -> dict[str, Any]:
    """What the candidate on disk did to unhandled checked exceptions,
    relative to commit `base_ref`, in `paths` (tree-relative; None = all).

    introduced    an unhandled site the baseline did not have, in a file the
                  baseline fully resolved (or a file that did not exist). A
                  proven introduction vetoes acceptance whatever the tuple does.
    exposed       an unhandled site the baseline already had. javac may not have
                  named it before; it was not made by this candidate.
    resolved      a baseline site the candidate no longer has.
    throws_added  a checked exception added to an existing member's throws.
                  Declaring what used to be handled is an introduction too.
    inconclusive  a site the compiler could not decide, or a baseline that
                  did not fully cover the file. Never a pass: the caller must
                  treat an undecidable introduction as undecided.

    state is "unavailable" when either model could not be produced."""
    prefix = source_root.rstrip("/") + "/"
    out: dict[str, Any] = {"state": "known", "why": "", "base": "", "introduced": [], "exposed": [], "resolved": [],
                           "throws_added": [], "inconclusive": [], "coverage": []}
    try:
        cur = dest_model(root, source_root=source_root)
        base = model_at_commit(root, base_ref, source_root=source_root)
    except DestModelUnavailable as exc:
        out["state"] = "unavailable"
        out["why"] = str(exc)
        return out
    out["base"] = str(base.get("commit") or "")
    want = set(paths) if paths is not None else None

    def _in(path: str) -> bool:
        return want is None or path in want

    base_types = {(prefix + str(t.get("path") or ""), str(t.get("fqn") or "")): t for t in base.get("types") or []}
    base_paths: dict[str, bool] = {}
    for (path, _fqn), t in base_types.items():
        base_paths[path] = base_paths.get(path, True) and str(t.get("resolution") or "") == "full"
    cur_types = {(prefix + str(t.get("path") or ""), str(t.get("fqn") or "")): t for t in cur.get("types") or []}
    fields = ("key", "path", "type", "member_id", "callee", "exception", "occurrence", "line", "consumer", "state")
    base_sites = {s["key"]: s for s in unhandled_sites(base, source_root)}
    cur_sites = [s for s in unhandled_sites(cur, source_root) if _in(s["path"])]
    # A candidate file the compiler could not fully attribute still has its
    # decidable sites judged; the calls it could not resolve are compile errors
    # the measure already counts, and when they resolve they are judged against
    # the baseline of THAT step (whose parse tree can still prove them new).
    # So it is recorded, not a refusal: refusing would stall every partial
    # compile repair.
    out["coverage"] = sorted({path for (path, _f), t in cur_types.items() if _in(path) and str(t.get("resolution") or "") != "full"})
    for s in cur_sites:
        row = {k: s.get(k) for k in fields}
        b = base_sites.get(s["key"])
        if s.get("state") != "unhandled":
            if b is None or b.get("state") != s.get("state"):
                out["inconclusive"].append(dict(row, why="the compiler could not decide whether this site is handled"))
            continue
        if b is not None:
            if b.get("state") == "unhandled":
                out["exposed"].append(row)
            else:
                out["inconclusive"].append(dict(row, why="the baseline could not decide this site, so it cannot be called new or old"))
            continue
        if s["path"] in base_paths and not base_paths[s["path"]]:
            # The baseline could not attribute this file, so its site list is
            # not a complete answer. The PARSE tree still is: a baseline member
            # that made fewer calls by this name than this site's occurrence
            # needs cannot have held it. Anything else stays undecided.
            proof = _absent_by_syntax(base_types, s)
            if proof:
                out["introduced"].append(dict(row, proof=proof))
            else:
                out["inconclusive"].append(dict(row, why="the baseline did not fully resolve %s and made a call of this name there, so whether this site is new cannot be decided" % s["path"]))
            continue
        out["introduced"].append(dict(row, proof="the baseline fully resolved %s and had no such site" % s["path"]))
    cur_keys = {s["key"] for s in cur_sites}
    out["resolved"] = [{k: s.get(k) for k in fields} for key, s in sorted(base_sites.items())
                       if _in(s["path"]) and s.get("state") == "unhandled" and key not in cur_keys]
    for (path, fqn), t in sorted(cur_types.items()):
        bt = base_types.get((path, fqn))
        if not _in(path) or bt is None or str(bt.get("resolution") or "") != "full" or str(t.get("resolution") or "") != "full":
            continue
        cur_ids, base_ids = member_ids(t), member_ids(bt)
        base_members = {base_ids.get(str(m.get("signature") or ""), ""): m for m in bt.get("declared") or []}
        for m in t.get("declared") or []:
            mid = cur_ids.get(str(m.get("signature") or ""), "")
            bm = base_members.get(mid)
            if bm is None or "throws_checked" not in m or "throws_checked" not in bm:
                continue
            added = sorted(set(m.get("throws_checked") or []) - set(bm.get("throws_checked") or []))
            if added:
                out["throws_added"].append({"path": path, "type": fqn, "member_id": mid, "exceptions": added})
    if out["inconclusive"] and not (out["introduced"] or out["throws_added"]):
        out["state"] = "inconclusive"
    return out
