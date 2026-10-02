"""Shared plumbing for the M-3 reference qualification (Stage 080 roadmap).

The reference qualification measures the SELECTED target architecture (the
Red Hat build of Quarkus platform pin, the Spring compatibility extensions,
`<Fragment>Impl` delegates behind generated Spring Data repositories) against
the FROZEN source's captured responses. This module holds only mechanics that
do not judge: the request corpus runner, a seeded disposable PostgreSQL, a
boot helper for a packaged jar or the frozen source jar, and the declared
normalizations the comparison uses.

Rules this module keeps (MIGRATION-IMPROVEMENTS.md M-3, V26-2):

* The expected value of a step is ONLY what the frozen source answered
  (fixtures/reference-qualification/source-oracle/*.json, written by
  reference-oracle-capture.py). A destination response is never an oracle.
* Each comparison is bound to the artifact, the database engine and the
  security mode that were actually measured. An oracle captured on another
  engine or mode is refused for the comparison, not substituted.
* The normalizations are declared in the corpus (origin, bound identifiers,
  Content-Type canonical form, set-valued CORS lists, the order of the
  source's field-error list) and applied identically to both sides.
* A missing prerequisite raises Skip with the precise reason; never a pass.

Python 3.9 compatible (the workspace image's interpreter)."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

import test_runtime_fixture as rt

rt_lib = rt.GOLDEN / ".hermes" / "lib"
import sys as _sys  # noqa: E402
if str(rt_lib) not in _sys.path:
    _sys.path.insert(0, str(rt_lib))
from response_equivalence import (adr_accepted, advice_equivalent, challenge_set,  # noqa: E402,F401  ADR-025 (+ D-2)
                                  outside_application_root)

Skip = rt.Skip
HERE = Path(__file__).resolve().parent
QUAL = rt.FIXTURES / "reference-qualification"
CORPUS = QUAL / "corpus.json"
ORACLE_DIR = QUAL / "source-oracle"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _advice_shapes(corpus: dict) -> list:
    """The reference source's exception-advice shapes (D-2): recorded in the corpus from its structural model."""
    return [s for s in corpus.get("advice_shapes") or [] if isinstance(s, dict)]


def load_corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def corpus_sha256() -> str:
    return sha256_file(CORPUS)


def oracle_path(engine: str, mode: str) -> Path:
    return ORACLE_DIR / ("%s-security-%s.json" % (engine, mode))


def load_oracle(engine: str, mode: str) -> dict:
    """The frozen source's captures for exactly this engine and mode. A missing
    file, or one whose provenance names another engine/mode or another corpus,
    is a Skip naming the missing input -- never another oracle."""
    p = oracle_path(engine, mode)
    if not p.is_file():
        raise Skip("no frozen-source oracle for engine=%s mode=%s (%s); run reference-oracle-capture.py with the "
                   "frozen source jar" % (engine, mode, p.name))
    o = json.loads(p.read_text(encoding="utf-8"))
    prov = o.get("provenance") or {}
    if prov.get("db", {}).get("engine") != engine or prov.get("security_mode") != mode:
        raise Skip("oracle %s is bound to engine=%s mode=%s, not %s/%s" % (
            p.name, prov.get("db", {}).get("engine"), prov.get("security_mode"), engine, mode))
    if prov.get("corpus_sha256") != corpus_sha256():
        raise Skip("oracle %s was captured for corpus %s, the corpus is now %s: re-capture from the frozen source"
                   % (p.name, str(prov.get("corpus_sha256"))[:12], corpus_sha256()[:12]))
    return o


# --------------------------------------------------------------------- database

@contextlib.contextmanager
def seeded_postgres(scripts: List[Path]) -> Iterator[dict]:
    """rt.postgres() plus the given SQL scripts loaded in order (psql inside the
    container, ON_ERROR_STOP). Yields the connection dict plus `scripts`
    ({path, sha256}) so the measurement records what state it started from."""
    with rt.postgres() as pg:
        loaded = []
        for s in scripts:
            data = Path(s).read_bytes()
            r = subprocess.run(["podman", "exec", "-i", pg["container"], "psql", "-v", "ON_ERROR_STOP=1", "-q",
                                "-h", "127.0.0.1", "-U", pg["user"], "-d", pg["url"].rsplit("/", 1)[1], "-f", "-"],
                               input=data, capture_output=True, timeout=180,
                               env=dict(os.environ, PGPASSWORD=pg["password"]))
            if r.returncode != 0:
                raise RuntimeError("loading %s failed: %s" % (s, (r.stderr or r.stdout).decode("utf-8", "replace")[-600:]))
            loaded.append({"path": str(s), "sha256": hashlib.sha256(data).hexdigest()})
        pg = dict(pg)
        pg["scripts"] = loaded
        yield pg


def sql_scalar(pg: dict, query: str) -> str:
    """One value read on a NEW connection (its own transaction), outside the
    application: the committed state, not what the application's session sees."""
    r = subprocess.run(["podman", "exec", pg["container"], "psql", "-At", "-h", "127.0.0.1", "-U", pg["user"],
                        "-d", pg["url"].rsplit("/", 1)[1], "-c", query],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return "ERROR: %s" % (r.stderr or r.stdout).strip()[-300:]
    return r.stdout.strip()


# ------------------------------------------------------------------------- HTTP

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - urllib hook
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def http(method: str, url: str, headers: Optional[Mapping[str, str]] = None,
         body: Optional[bytes] = None) -> Tuple[int, Dict[str, str], str]:
    """One exchange, redirects NOT followed (the first response is the one the
    source capture recorded). Header names lower-cased; repeated headers joined
    with ', '."""
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        resp = _OPENER.open(req, timeout=20)
    except urllib.error.HTTPError as exc:
        resp = exc
    hdrs: Dict[str, str] = {}
    for k, v in resp.headers.items():
        k = k.lower()
        hdrs[k] = v if k not in hdrs else hdrs[k] + ", " + v
    raw = resp.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return int(resp.status if hasattr(resp, "status") else resp.code), hdrs, text[:65536]


def free_port() -> int:
    return rt.free_port()


@contextlib.contextmanager
def boot_process(argv: List[str], cwd: Path, log_path: Path, probe_url: str,
                 env: Optional[Mapping[str, str]] = None, timeout: int = 120) -> Iterator[subprocess.Popen]:
    """Start argv, wait until probe_url answers anything, yield the process;
    always terminate it. The log stays at log_path."""
    log = Path(log_path).open("w")
    proc = subprocess.Popen(argv, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                            env=dict(os.environ, **(env or {})))
    try:
        deadline = time.time() + timeout
        while True:
            try:
                http("GET", probe_url)
                break
            except (urllib.error.URLError, ConnectionError, OSError, socket.timeout):
                if proc.poll() is not None or time.time() > deadline:
                    log.flush()
                    raise RuntimeError("the process did not start: %s" % Path(log_path).read_text(errors="replace")[-1200:])
                time.sleep(0.5)
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


# ------------------------------------------------------------------ the corpus

def _subst(text: str, bound: Mapping[str, str], root: str) -> str:
    text = text.replace("{root}", root)
    for k, v in bound.items():
        text = text.replace("{%s}" % k, str(v))
    return text


def _step_applies(step: dict, mode: str, engine: str) -> bool:
    modes = step.get("modes") or ["disabled"]
    engines = step.get("engines")
    return mode in modes and (engines is None or engine in engines)


def run_corpus(base: str, corpus: dict, mode: str, engine: str, pg: Optional[dict] = None,
               only_tags: Optional[List[str]] = None) -> Dict[str, dict]:
    """Send every applicable step in order; record the raw exchange. `bound`
    values (identifiers the application assigned) are captured from each side's
    OWN responses, so later steps address the row that side created."""
    root = corpus["application_root"]
    bound: Dict[str, str] = {}
    out: Dict[str, dict] = {}
    for step in corpus["steps"]:
        if not _step_applies(step, mode, engine):
            continue
        if only_tags and not set(only_tags) & set(step.get("tags") or []):
            continue
        sid = step["id"]
        refs = json.dumps(step.get("path", "")) + json.dumps(step.get("body", "")) + json.dumps(step.get("query", ""))
        missing = sorted({v for v in re.findall(r"\{([a-z_]+)\}", refs) if v != "root" and v not in bound})
        if missing:
            out[sid] = {"skipped": "an earlier step did not bind %s" % ", ".join(missing)}
            continue
        if step.get("kind") == "sql":
            if pg is None:
                out[sid] = {"skipped": "no SQL access to this database (in-process engine)"}
                continue
            q = _subst(step["query"], bound, root)
            out[sid] = {"request": {"sql": q}, "response": {"value": sql_scalar(pg, q)}}
            continue
        path = _subst(step["path"], bound, root)
        headers = dict(step.get("headers") or {})
        body: Optional[bytes] = None
        if "raw_body" in step:
            body = _subst(step["raw_body"], bound, root).encode("utf-8")
        elif "body" in step:
            body = _subst(json.dumps(step["body"]), bound, root).encode("utf-8")
        if body is not None:
            headers.setdefault("Content-Type", "application/json")
        if step.get("auth"):
            import base64
            user, pw = step["auth"]
            headers["Authorization"] = "Basic " + base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()
        status, hdrs, text = http(step["method"], base + path, headers, body)
        hdrs.pop("date", None)
        shown = dict(headers)
        if "Authorization" in shown:
            shown["Authorization"] = "Basic <corpus auth user %s; value not recorded>" % step["auth"][0]
        out[sid] = {"request": {"method": step["method"], "path": path, "headers": shown,
                                "body": body.decode("utf-8") if body is not None else None},
                    "response": {"status": status, "headers": hdrs, "body": text}}
        for var, how in (step.get("bind") or {}).items():
            if how == "location_last_segment" and hdrs.get("location"):
                # an empty trailing segment (".../owners/") binds nothing: the side assigned no identifier
                seg = urllib.parse.urlsplit(hdrs["location"]).path.rsplit("/", 1)[-1]
                if seg:
                    bound[var] = seg
            elif how.startswith("body:") and text:
                try:
                    bound[var] = str(json.loads(text).get(how[5:]))
                except (ValueError, AttributeError):
                    pass
    out["_bound"] = {"response": {"value": bound}}
    return out


# ------------------------------------------------------------- normalization

def _canon_ctype(v: str) -> str:
    parts = [p.strip() for p in v.split(";") if p.strip()]
    if not parts:
        return ""
    head = parts[0].lower()
    params = sorted(p.split("=", 1)[0].strip().lower() + "=" + p.split("=", 1)[1].strip().strip('"').lower()
                    for p in parts[1:] if "=" in p)
    return ";".join([head] + params)


def _canon_list(v: str) -> List[str]:
    return sorted({p.strip().lower() for p in v.split(",") if p.strip()})


def _unbind(value: Any, bound: Mapping[str, str]) -> Any:
    """Replace identifiers each side assigned itself by their corpus names --
    only where the identifier of the addressed resource is: the "id" of the
    body object, or of each object of a top-level list. Nested identifiers
    (a pet's id inside an owner) are other resources and stay as they are."""
    rev = {str(v): "{%s}" % k for k, v in bound.items()}

    def one(obj: Any) -> Any:
        if isinstance(obj, dict) and "id" in obj and not isinstance(obj["id"], bool) and str(obj["id"]) in rev:
            obj = dict(obj)
            obj["id"] = rev[str(obj["id"])]
        return obj
    if isinstance(value, list):
        return [one(v) for v in value]
    return one(value)


def _unbind_text(row: Any, bound: Mapping[str, str]) -> Any:
    """Inside one field-error row, a bound identifier quoted in a message
    (\"does not match pathId: 11\") is replaced as a whole token."""
    if not isinstance(row, dict):
        return row
    out = {}
    for k, v in row.items():
        if isinstance(v, str):
            for name, val in bound.items():
                v = re.sub(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(str(val)), "{%s}" % name, v)
        out[k] = v
    return out


def _json_or_text(text: str) -> Any:
    if text is None or text == "":
        return ""
    try:
        return json.loads(text)
    except ValueError:
        return text.strip()


def _errors_header(v: str) -> Any:
    try:
        rows = json.loads(v)
    except ValueError:
        return v
    if isinstance(rows, list):
        return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return rows


def normalize(step: dict, exchange: dict, bound: Mapping[str, str], origin: str, corpus: dict,
              adr025: bool = False) -> dict:
    """The comparable view of one exchange under the corpus's declared rules
    (and, with adr025, WWW-Authenticate as its set of parsed challenges)."""
    if "response" not in exchange:
        return {"absent": exchange.get("skipped", "not executed")}
    resp = exchange["response"]
    if step.get("kind") == "sql":
        return {"value": resp.get("value")}
    compared = [h.lower() for h in corpus["compared_headers"]]
    hdrs = {}
    for h in compared:
        v = resp["headers"].get(h)
        if v is None:
            continue
        if h == "location":
            u = urllib.parse.urlsplit(v)
            v = ("{origin}" if u.scheme and u.netloc else "") + u.path + (("?" + u.query) if u.query else "")
            last = u.path.rstrip("/").rsplit("/", 1)[-1]
            rev = {str(val): k for k, val in bound.items()}
            if last in rev:
                v = v[: v.rstrip("/").rfind("/") + 1] + "{%s}" % rev[last] + ("/" if v.endswith("/") else "")
        elif h == "content-type":
            v = _canon_ctype(v)
        elif h in ("access-control-allow-methods", "access-control-allow-headers", "access-control-expose-headers",
                   "vary"):
            v = _canon_list(v)
        elif h == "access-control-allow-origin":
            v = v.strip()
        elif h == "www-authenticate" and adr025:
            cs = challenge_set(v)
            v = sorted(json.dumps(c) for c in cs) if cs is not None else v
        elif h == "errors":
            v = _unbind(_errors_header(v), bound)
            if isinstance(v, list):
                v = [_unbind_text(r, bound) for r in v]
        hdrs[h] = v
    body = _unbind(_json_or_text(resp.get("body", "")), bound)
    if step.get("body_order") == "unordered" and isinstance(body, list):
        body = sorted(body, key=lambda r: json.dumps(r, sort_keys=True))
    return {"status": resp["status"], "headers": hdrs, "body": body}


def first_difference(a: Any, b: Any, path: str = "$") -> Tuple[str, Any, Any]:
    """The first JSON path where two values differ, with both values there."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s" % (path, k), a.get(k, "<absent>"), b.get(k, "<absent>")
            if a[k] != b[k]:
                return first_difference(a[k], b[k], "%s.%s" % (path, k))
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return "%s.length" % path, len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return first_difference(x, y, "%s[%d]" % (path, i))
    return path, a, b


def compare(step: dict, oracle_ex: dict, dest_ex: dict, oracle_bound: Mapping[str, str],
            dest_bound: Mapping[str, str], corpus: dict,
            ignore_headers: Optional[List[str]] = None, adr025: bool = False,
            notes: Optional[List[str]] = None) -> Tuple[str, List[str]]:
    """MATCH / MISMATCH / UNMEASURED with the list of differences. A caller that
    narrows the header set (ignore_headers) must record that scope with its result.
    With adr025 (ADR-025 accepted in the golden decisions) the three ruled
    equivalences apply, each identified from the corpus and the SOURCE capture
    only, and each application is appended to `notes`."""
    if ignore_headers:
        corpus = dict(corpus, compared_headers=[h for h in corpus["compared_headers"]
                                                if h.lower() not in {x.lower() for x in ignore_headers}])
    o = normalize(step, oracle_ex, oracle_bound, "", corpus, adr025)
    d = normalize(step, dest_ex, dest_bound, "", corpus, adr025)
    if (adr025 and "absent" not in o and "absent" not in d and step.get("kind") != "sql"
            and outside_application_root(_subst(str(step.get("path") or ""), {}, corpus["application_root"]),
                                         corpus["application_root"])):
        # ADR-025 (3): the servlet container's answer: status only; body and headers out of scope
        if notes is not None:
            notes.append("ADR-025 outside-application-root: status only (body and headers out of scope)")
        if o["status"] != d["status"]:
            return "MISMATCH", ["status: source %s, destination %s" % (o["status"], d["status"])]
        return "MATCH", []
    equiv = (advice_equivalent(o.get("status"), (oracle_ex.get("response") or {}).get("body"),
                               (dest_ex.get("response") or {}).get("body"), _advice_shapes(corpus))
             if adr025 and "absent" not in o and "absent" not in d and step.get("kind") != "sql" else None)
    if equiv is not None:
        ok, why = equiv
        if ok:
            # ADR-025 (1): keys enforced, the framework-diagnostic values present and non-empty
            if notes is not None:
                notes.append(why)
            d = dict(d, body=o["body"])
    if "absent" in o:
        return "UNMEASURED", ["the source oracle has no capture: %s" % o["absent"]]
    if "absent" in d:
        return "UNMEASURED", ["the destination was not measured: %s" % d["absent"]]
    diffs: List[str] = []
    if step.get("kind") == "sql":
        if o["value"] != d["value"]:
            diffs.append("committed state: source %r, destination %r" % (o["value"], d["value"]))
        return ("MATCH" if not diffs else "MISMATCH"), diffs
    if o["status"] != d["status"]:
        diffs.append("status: source %s, destination %s" % (o["status"], d["status"]))
    for h in sorted(set(o["headers"]) | set(d["headers"])):
        if o["headers"].get(h) != d["headers"].get(h):
            diffs.append("header %s: source %s, destination %s" % (
                h, json.dumps(o["headers"].get(h))[:300], json.dumps(d["headers"].get(h))[:300]))
    if step.get("compare_body", True) and o["body"] != d["body"]:
        at, ov, dv = first_difference(o["body"], d["body"])
        diffs.append("body at %s: source %s | destination %s" % (at, json.dumps(ov)[:300], json.dumps(dv)[:300]))
    return ("MATCH" if not diffs else "MISMATCH"), diffs


def oracle_kind(step: dict) -> str:
    return "sql" if step.get("kind") == "sql" else "http"


def load_reference_oracles(corpus: dict, mode: str) -> Dict[str, dict]:
    """The oracle each kind of step is compared with, as the corpus DECLARES it
    (reference_oracle): HTTP exchanges against the source's selected profiles,
    committed-state SQL against the source on PostgreSQL (the only engine whose
    state is readable outside the application)."""
    return {kind: load_oracle(engine, mode) for kind, engine in corpus["reference_oracle"]["engines"].items()}


def compare_all(corpus: dict, oracles: Dict[str, dict], dest_steps: Dict[str, dict], mode: str, engine: str,
                only_tags: Optional[List[str]] = None, ignore_headers: Optional[List[str]] = None,
                adr025: bool = False) -> Dict[str, dict]:
    """Per applicable step: MATCH / MISMATCH / UNMEASURED against the oracle
    its kind is bound to. `oracles` maps kind -> oracle document."""
    db = (dest_steps.get("_bound") or {}).get("response", {}).get("value") or {}
    included = [s for s in corpus["steps"] if _step_applies(s, mode, engine)
                and (not only_tags or set(only_tags) & set(s.get("tags") or []))]
    bindable = {v for s in included for v in (s.get("bind") or {})}
    rows: Dict[str, dict] = {}
    for step in corpus["steps"]:
        if not _step_applies(step, mode, engine):
            continue
        if only_tags and not set(only_tags) & set(step.get("tags") or []):
            continue
        o = oracles[oracle_kind(step)]
        osteps = o["steps"]
        ob = {k: v for k, v in ((osteps.get("_bound") or {}).get("response", {}).get("value") or {}).items()
              if k in bindable}
        notes: List[str] = []
        verdict, diffs = compare(step, osteps.get(step["id"], {"skipped": "not in the oracle"}),
                                 dest_steps.get(step["id"], {"skipped": "not sent"}), ob, db, corpus, ignore_headers,
                                 adr025=adr025, notes=notes)
        classes = sorted({d.split(":", 1)[0] for d in diffs})
        rows[step["id"]] = {"outcome": verdict, "differences": diffs, "difference_classes": classes, "equivalences": notes,
                            "tags": step.get("tags") or [], "case": step.get("case", ""),
                            "oracle": "%s-security-%s" % (o["provenance"]["db"]["engine"], mode)}
    return rows


# ------------------------------------------------------------------- the jar

def artifact_identity(app_root: Path) -> dict:
    """What was measured: the packaged quarkus-app's runner and application jar digests."""
    qa = Path(app_root) / "target" / "quarkus-app"
    ident = {"quarkus_app": str(qa)}
    runner = qa / "quarkus-run.jar"
    if runner.is_file():
        ident["quarkus_run_jar_sha256"] = sha256_file(runner)
    apps = sorted((qa / "app").glob("*.jar")) if (qa / "app").is_dir() else []
    ident["app_jars"] = {j.name: sha256_file(j) for j in apps}
    return ident


def package_tree(root: Path, clean: bool = True) -> Tuple[bool, str]:
    """mvn -o [clean] package -DskipTests with the tree's OWN .mvn configuration
    (its settings and decided build profile), the pinned platform forced. An
    offline resolution gap is a Skip."""
    p = rt.pin()
    argv = ["mvn", "-B", "-q", "-o", "-Dquarkus.platform.group-id=%s" % p["group_id"],
            "-Dquarkus.platform.version=%s" % p["version"]]
    argv += (["clean"] if clean else []) + ["package", "-DskipTests"]
    r = subprocess.run(argv, cwd=str(root), text=True, capture_output=True, timeout=1200)
    out = r.stdout + r.stderr
    if r.returncode != 0:
        hit = next((n for n in rt._OFFLINE if n in out), "")
        if hit and "BuildException" not in out:
            raise Skip("the pinned platform's artifacts are not all in the local Maven repository (%s)"
                       % next((ln.strip() for ln in out.splitlines() if hit in ln), hit)[:240])
    return r.returncode == 0, out


def write_results(path: Optional[str], payload: dict) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def podman_ready() -> Tuple[bool, str]:
    if not shutil.which("podman"):
        return False, "podman is not on PATH"
    r = subprocess.run(["podman", "info", "--format", "{{.Host.Arch}}"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        last = [ln.strip() for ln in (r.stderr or r.stdout or "").splitlines() if ln.strip()]
        return False, "podman cannot reach its machine/socket: %s" % (last[-1] if last else "no output")[-240:]
    return True, ""


def token() -> str:
    return secrets.token_hex(4)


# ------------------------------------------------------------ the candidate

CANDIDATE = QUAL / "candidate" / "candidate.json"


def _git(root: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=300)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), (r.stderr or r.stdout).strip()[-400:]))
    return r.stdout.strip()


def build_candidate(bundle: Optional[str], dest: Path) -> dict:
    """Clone the v28 bundle, check out the recorded baseline commit, verify its
    tree, apply ONLY the recipe patches candidate.json lists and verify the
    resulting tree id. Returns the identity record. A missing bundle is a Skip
    naming the input; a baseline or tree mismatch is an error (the measured
    tree would not be the declared one)."""
    spec = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    bundle = bundle or os.environ.get(spec["bundle_env"], "")
    if not bundle or not Path(bundle).is_file():
        raise Skip("the v28 destination bundle is not available (set %s or pass --bundle; it is local ignored "
                   "evidence: tmp/loop-qualification-20260929/v28-dest.bundle)" % spec["bundle_env"])
    subprocess.run(["git", "clone", "-q", str(bundle), str(dest)], check=True, capture_output=True, timeout=300)
    base = spec["baseline"]
    _git(dest, "checkout", "-q", "--detach", base["commit"])
    tree = _git(dest, "rev-parse", "HEAD^{tree}")
    if tree != base["tree"]:
        raise RuntimeError("baseline %s has tree %s, candidate.json records %s" % (base["commit"], tree, base["tree"]))
    applied = []
    for app in spec["recipe_applications"]:
        patch = CANDIDATE.parent / app["patch"]
        _git(dest, "apply", "--check", str(patch))
        _git(dest, "apply", str(patch))
        applied.append({"recipe": app["recipe"], "patch": app["patch"], "patch_sha256": sha256_file(patch)})
    _git(dest, "add", "-A")
    cand_tree = _git(dest, "write-tree")
    if cand_tree != spec["expected_candidate_tree"]:
        raise RuntimeError("the candidate tree is %s, candidate.json expects %s" % (cand_tree, spec["expected_candidate_tree"]))
    return {"bundle_sha256": sha256_file(Path(bundle)), "baseline_commit": base["commit"], "baseline_tree": base["tree"],
            "recipe_applications": applied, "candidate_tree": cand_tree}


REHEARSAL = QUAL / "rehearsal" / "rehearsal.json"
REHEARSAL_LABEL = "REHEARSAL (not a migration output, not a run result)"


def build_rehearsal(bundle: Optional[str], dest: Path) -> dict:
    """The M-3 rehearsal tree (rehearsal/rehearsal.json): the qualification
    candidate built by build_candidate, then each guided-repair patch applied
    in order, the tree id verified after EVERY step. The measured tree is
    labelled REHEARSAL: the patches apply the catalog guidance a worker
    receives, applied by the qualification, never a loop's output."""
    spec = json.loads(REHEARSAL.read_text(encoding="utf-8"))
    ident = build_candidate(bundle, dest)
    if ident["candidate_tree"] != spec["base"]["tree"]:
        raise RuntimeError("the rehearsal base is %s, rehearsal.json expects %s" % (ident["candidate_tree"], spec["base"]["tree"]))
    steps = []
    for st in spec["steps"]:
        patch = REHEARSAL.parent / st["patch"]
        _git(dest, "apply", "--check", str(patch))
        _git(dest, "apply", str(patch))
        _git(dest, "add", "-A")
        tree = _git(dest, "write-tree")
        if tree != st["tree_after"]:
            raise RuntimeError("after %s the tree is %s, rehearsal.json expects %s" % (st["patch"], tree, st["tree_after"]))
        steps.append({"step": st["id"], "patch": st["patch"], "patch_sha256": sha256_file(patch), "tree_after": tree,
                      "guidance": st["guidance"]["key"]})
    if steps and steps[-1]["tree_after"] != spec["rehearsal_tree"]:
        raise RuntimeError("the rehearsal tree is %s, rehearsal.json expects %s" % (steps[-1]["tree_after"], spec["rehearsal_tree"]))
    return dict(ident, label=REHEARSAL_LABEL, rehearsal_steps=steps, rehearsal_tree=spec["rehearsal_tree"],
                measured_tree=spec["rehearsal_tree"])


def tree_identity(root: Path, base_identity: dict, replaced: Optional[Dict[str, Path]] = None) -> dict:
    """The candidate identity plus any file a variant replaced (path, sha256)
    and the resulting git tree id."""
    ident = dict(base_identity)
    if replaced:
        _git(root, "add", "-A")
        ident["variant_files"] = {rel: sha256_file(src) for rel, src in replaced.items()}
        ident["measured_tree"] = _git(root, "write-tree")
    else:
        ident["measured_tree"] = base_identity["candidate_tree"]
    return ident


@contextlib.contextmanager
def boot_candidate(root: Path, pg: dict, mode: str, log_path: Path) -> Iterator[str]:
    """Run the candidate's packaged jar on a loopback port with the tree's own
    datasource references filled from the disposable database; yield the base URL."""
    port = free_port()
    argv = ["java", "-Dquarkus.http.host=127.0.0.1", "-Dquarkus.http.port=%d" % port,
            "-Dpetclinic.security.enable=%s" % ("true" if mode == "enabled" else "false"),
            "-jar", str(root / "target" / "quarkus-app" / "quarkus-run.jar")]
    env = {"PETCLINIC_DB_URL": pg["url"], "PETCLINIC_DB_USER": pg["user"], "PETCLINIC_DB_PASSWORD": pg["password"]}
    corpus = load_corpus()
    base = "http://127.0.0.1:%d" % port
    with boot_process(argv, root, log_path, base + corpus["application_root"] + "api/owners/1", env=env, timeout=150):
        yield base
