"""The protected outcome-board authority: a service in its own principal (architect F1).

WHAT IT IS. One process, run in a sidecar container of the migration workspace
as a DIFFERENT uid than the worker, from root-owned image code
(``/opt/rhoai3/outcome-authority``). It owns the authority store in a directory
mounted ONLY into its own container, and answers transition REQUESTS on a unix
socket in a volume the worker container mounts read-only (it may connect, it
cannot replace the socket). Every decision is the same lifecycle code the
in-process qualification runs, executed HERE against records the worker cannot
reach, with every value the service can measure itself replaced by its own
measurement:

  candidate / attempt key   the service's own product-tree digest of the tree
  writer process group      the native board's worker pid + the caller's snapshot
  scope at acceptance       git: changed product paths since the issued baseline
                            (working tree at accept-begin, baseline..commit at
                            accept-commit) within the issue's allowed paths
  baseline ancestry         git: the accepted commit's parent is the issued
                            baseline and HEAD is that commit
  budget, issue, revision,  its own hash-chained store; the worker can neither
  acceptance, grants        write, delete, redirect nor roll it back

WHAT STAYS COOPERATIVE (stated with every claim, never hidden):
  * native lifecycle data (kanban.db) is worker-writable; it can never GRANT
    anything the store does not also record;
  * heavy measurement receipts (build, tests, parity, MTA, M4 verdict, M5 stage
    receipts) are produced by the worker; the check classes an acceptance
    names are recorded as ``classes_asserted_by: worker-receipts``. Enabled
    execution requires the platform to DECLARE that trust
    (outcome_board.measurement_trust); it is the open architect decision;
  * the hook's profile / audit-green facts and a push result are the caller's
    report.

WHAT IT NEVER TRUSTS: peer credentials (SO_PEERCRED is forgeable from a user
namespace the worker can enter: /etc/subuid is group-writable in the workspace
image), a worker-supplied PASS, scope, budget, candidate or store path, and the
worker's Hermes home (the pinned CLI runs with a private, empty HERMES_HOME and
only the recorded board database / attachment root). Git runs with protected
configuration that disables fsmonitor, hooks and submodule recursion, and only
plumbing commands that run no filters.

Wire format: one JSON line per request and per answer on an AF_UNIX stream.

  request  {"op": "hello"|"status"|"transition"|"publish"|"readback"|"tick",
            "args": {...}, "procs": {"<pid>": <pgid>, ...}}
  answer   {"ok": true, "result": ...} | {"ok": false, "code": ..., "detail": ...}
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

SCHEMA = "rhoai3.outcome-authority/v1"
MAX_LINE = 4 << 20
DEFAULT_TIMEOUT = 120.0

# the code the service runs; its identity is the image stamp
# outcome_authority.code_sha256 (outcome_protocol.STAMP_KEY)
CODE_TREES = ("kernel", "lib", "planning", "skills")

GIT_PROTECTED = (
    ("safe.directory", "*"), ("core.fsmonitor", "false"), ("core.hooksPath", "/dev/null"),
    ("core.untrackedCache", "false"), ("submodule.recurse", "false"), ("diff.ignoreSubmodules", "all"),
    ("status.submoduleSummary", "false"), ("diff.external", ""), ("core.pager", "cat"), ("credential.helper", ""),
    # a repository-configured remote.<name>.uploadpack runs only over the file and
    # ssh transports; the service probes pushes over https only
    ("protocol.ext.allow", "never"), ("protocol.file.allow", "never"), ("protocol.ssh.allow", "never"),
    ("core.sshCommand", "false"),
)


class AuthorityError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------

def procsnap() -> dict[str, int]:
    """{pid: pgid} of every process visible to the CALLER (the worker's
    container): the service has no view of it."""
    out: dict[str, int] = {}
    proc = Path("/proc")
    if proc.is_dir():
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                stat = (d / "stat").read_text()
                fields = stat[stat.rfind(")") + 2:].split()
                out[d.name] = int(fields[2])
            except (OSError, ValueError, IndexError):
                continue
        return out
    try:
        p = subprocess.run(["ps", "-axo", "pid=,pgid="], capture_output=True, text=True, timeout=10)
        for line in p.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                out[parts[0]] = int(parts[1])
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def call(endpoint: str, op: str, args: dict[str, Any], *, timeout: float | None = None) -> Any:
    """One request on the service socket; the result, or AuthorityError."""
    req = json.dumps({"op": op, "args": args, "procs": procsnap()}, sort_keys=True, default=str).encode() + b"\n"
    if len(req) > MAX_LINE:
        raise AuthorityError("AUTHORITY_BAD_REQUEST", "request of %d bytes exceeds %d" % (len(req), MAX_LINE))
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout or DEFAULT_TIMEOUT)
    try:
        try:
            s.connect(str(endpoint))
            s.sendall(req)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_LINE:
                    raise AuthorityError("AUTHORITY_BAD_ANSWER", "answer exceeds %d bytes" % MAX_LINE)
        except OSError as exc:
            raise AuthorityError("AUTHORITY_UNREACHABLE", "%s: %s" % (endpoint, exc)) from exc
    finally:
        s.close()
    try:
        ans = json.loads(buf.decode("utf-8"))
    except ValueError as exc:
        raise AuthorityError("AUTHORITY_BAD_ANSWER", "unparseable answer (%s)" % exc) from exc
    if not isinstance(ans, dict):
        raise AuthorityError("AUTHORITY_BAD_ANSWER", "answer is not an object")
    if ans.get("ok"):
        return ans.get("result")
    raise AuthorityError(str(ans.get("code") or "AUTHORITY_REFUSED"), str(ans.get("detail") or ""))


def hello(endpoint: str) -> dict[str, Any]:
    out = call(endpoint, "hello", {}, timeout=5.0)
    if not isinstance(out, dict):
        raise AuthorityError("AUTHORITY_BAD_ANSWER", "hello answered %r" % type(out).__name__)
    return out


# ---------------------------------------------------------------------------
# code identity
# ---------------------------------------------------------------------------

def code_files(base: Path) -> list[Path]:
    """Everything the service can execute or load, under ``base`` (a
    .hermes-shaped tree): the harness release trees kernel/, lib/ and skills/
    (the lifecycle reaches across lib/planner, the kernel K-modules and the
    skills' Java model tools) plus planning/ (catalogs, schemas). Bytecode
    caches excluded. This is exactly the tree the image bakes under
    /opt/rhoai3/outcome-authority."""
    base = Path(base)
    out = []
    for top in CODE_TREES:
        d = base / top
        if d.is_dir():
            out += [p for p in d.rglob("*") if p.is_file() and not p.is_symlink()
                    and "__pycache__" not in p.parts and p.suffix != ".pyc" and not p.name.startswith("._")]
    return sorted(out)


def code_identity(base: Path) -> str:
    h = hashlib.sha256()
    base = Path(base)
    for p in code_files(base):
        h.update(p.relative_to(base).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------

def protect_git_environment(env: dict[str, str] | None = None) -> dict[str, str]:
    """Command-scope configuration (GIT_CONFIG_COUNT) outranks the repository's
    own config: the worker-writable .git/config can neither run a hook, an
    fsmonitor nor an external diff in the service's principal."""
    e = os.environ if env is None else env
    e["GIT_CONFIG_NOSYSTEM"] = "1"
    e["GIT_CONFIG_GLOBAL"] = "/dev/null"
    e["GIT_TERMINAL_PROMPT"] = "0"
    e["GIT_OPTIONAL_LOCKS"] = "0"
    e["GIT_CONFIG_COUNT"] = str(len(GIT_PROTECTED))
    for i, (k, v) in enumerate(GIT_PROTECTED):
        e["GIT_CONFIG_KEY_%d" % i] = k
        e["GIT_CONFIG_VALUE_%d" % i] = v
    return dict(e)


def safe_tree(root: Path) -> str:
    """The product-tree digest (canonical.product_tree_sha256) computed by the
    authority, refusing a product path that is a symlink leaving the tree: the
    service never hashes (or waits on) a file the worker pointed at."""
    from planner.canonical import product_tree_sha256
    from planner.paths import is_product_path
    r = os.path.realpath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            if os.path.islink(p):
                rel = os.path.relpath(p, root).replace(os.sep, "/")
                target = os.path.realpath(p)
                if is_product_path(rel) and not (target == r or target.startswith(r + os.sep)):
                    raise AuthorityError("TREE_UNSAFE", "%s is a symlink leaving the destination tree" % rel)
        dirnames[:] = [d for d in dirnames if d != ".git"]
    return product_tree_sha256(Path(root))


class Service:
    """The authority. ``root`` is the destination tree as this container
    sees it (read by the service, never written); ``store_dir`` its private
    directory; ``code_base`` the root-owned code it runs from."""

    def __init__(self, root: Path, store_dir: Path, *, code_base: Path | None = None,
                 hermes: list[str] | None = None, native_db: str = ""):
        from planner import outcome_store
        self.root = Path(os.path.realpath(root))
        self.store_dir = outcome_store.bind_service(Path(store_dir), self.root)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.store_dir, 0o700)
        self.code_base = Path(code_base or Path(__file__).resolve().parents[2])
        self.code_sha256 = code_identity(self.code_base)
        self.hermes = list(hermes or ["hermes"])
        self.native_db = native_db
        self.private_home = self.store_dir / "hermes-home"
        self.private_home.mkdir(parents=True, exist_ok=True)
        # the analyzer (DestModel) compiles, runs and caches ONLY here, from the
        # tool source baked beside this code -- never from the destination
        # tree's verification/build/.dest-model, which the worker writes
        from planner import dest_model
        dest_model.bind_private_work(self.store_dir / "analyzer", self.root)
        protect_git_environment()
        self.lock = threading.Lock()

    # -- identity --------------------------------------------------------------
    def identity(self) -> dict[str, Any]:
        from planner.outcome_store import store_path
        return {"schema": SCHEMA, "uid": os.getuid(), "pid": os.getpid(), "root": str(self.root),
                "store_dir": str(self.store_dir), "store_path": str(store_path(self.root)),
                "code_sha256": self.code_sha256, "code_base": str(self.code_base)}

    # -- context ---------------------------------------------------------------
    def _native(self, db: str) -> Any:
        """The pinned CLI with a PRIVATE Hermes home: no worker plugin, hook or
        config is ever loaded in this principal. Only the recorded board
        database and its attachment root are shared."""
        from planner.outcome_native import KanbanNative
        env = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_")}
        env.update(HERMES_HOME=str(self.private_home), HERMES_KANBAN_DB=db)
        if db:
            env["HERMES_KANBAN_ATTACHMENTS_ROOT"] = os.path.join(os.path.dirname(db), "kanban", "attachments")
        return KanbanNative(db, hermes=self.hermes, env=env)

    def _alive(self, procs: dict[str, int]):
        pids = {int(k) for k in procs}
        pgids = set(procs.values())

        def alive(pid: int | None, pgid: int | None) -> bool:
            return bool((pid and int(pid) in pids) or (pgid and int(pgid) in pgids))
        return alive

    def _ctx(self, procs: dict[str, int]):
        from planner.outcome_lifecycle import Ctx
        from planner.outcome_store import Store
        store = Store(self.root)
        return Ctx(self.root, store, self._native(store.meta("native_db") or self.native_db),
                   tree=safe_tree, alive=self._alive(procs), observer_writes=False)

    # -- operations ------------------------------------------------------------
    def _sanitize(self, name: str, kw: dict[str, Any], ctx: Any, procs: dict[str, int]) -> dict[str, Any]:
        """Replace every value the authority measures itself; never sign the
        caller's. Unknown keyword arguments fail in the call itself."""
        kw = dict(kw)
        if name == "issue":
            t = ctx.native.task(str(kw.get("task_id") or "")) or {}
            pid = int(t.get("worker_pid") or 0)
            kw["pid"] = pid
            kw["pgid"] = int(procs.get(str(pid)) or 0) if pid else 0
        elif name == "record_verdict":
            cand = ctx.product_tree()
            kw["candidate"] = cand
            kw["attempt"] = cand[:16]
        elif name == "accept_commit":
            kw["attempt"] = ctx.product_tree()[:16]
        elif name == "restore_pending":
            kw["candidate_now"] = ctx.product_tree()
        return kw

    def handle(self, op: str, args: dict[str, Any], procs: dict[str, int]) -> Any:
        from planner import outcome_lifecycle as L
        from planner.outcome_store import StoreError
        if op == "hello":
            return self.identity()
        if op == "status":
            try:
                ctx = self._ctx(procs)
            except StoreError as exc:
                if exc.code == "STORE_MISSING":
                    return {"published": False, "publication_state": "", "revision": 0}
                raise
            try:
                return L.TRANSITIONS["status"](ctx)
            finally:
                ctx.store.close()
        if op == "transition":
            name = str(args.get("name") or "")
            fn = L.TRANSITIONS.get(name)
            if fn is None or name == "status":
                raise AuthorityError("AUTHORITY_BAD_REQUEST", "no transition %r" % name)
            kwargs = args.get("kwargs") if isinstance(args.get("kwargs"), dict) else {}
            ctx = self._ctx(procs)
            try:
                return fn(ctx, **self._sanitize(name, kwargs, ctx, procs))
            finally:
                ctx.store.close()
        if op == "publish":
            import k4_graph
            db = self.native_db or ""
            if not db:
                raise AuthorityError("AUTHORITY_NATIVE_UNSET", "the service knows no board database")
            return k4_graph.publish_initial(self.root, self._native(db), m2=str(args.get("m2_task") or ""),
                                            plan_file=str(args.get("plan_file") or ""))
        if op == "readback":
            import k4_graph
            ctx = self._ctx(procs)
            try:
                return {"gaps": k4_graph.readback(ctx.store, ctx.native), "publication_state": ctx.store.meta("publication_state")}
            finally:
                ctx.store.close()
        if op == "tick":
            import outcome_reconcile
            try:
                ctx = self._ctx(procs)
            except StoreError:
                return []
            try:
                return outcome_reconcile.tick(self.root, ctx.native, alive=self._alive(procs), observer_writes=False)
            finally:
                ctx.store.close()
        raise AuthorityError("AUTHORITY_BAD_REQUEST", "unknown op %r" % op)

    def answer(self, line: bytes) -> dict[str, Any]:
        from planner.outcome_lifecycle import Refusal
        from planner.outcome_store import StoreError
        try:
            req = json.loads(line.decode("utf-8"))
            if not isinstance(req, dict):
                raise ValueError("request is not an object")
            procs = {str(k): int(v) for k, v in (req.get("procs") or {}).items()}
            args = req.get("args") if isinstance(req.get("args"), dict) else {}
            return {"ok": True, "result": self.handle(str(req.get("op") or ""), args, procs)}
        except (Refusal, StoreError, AuthorityError) as exc:
            return {"ok": False, "code": exc.code, "detail": exc.detail}
        except (ValueError, TypeError) as exc:
            return {"ok": False, "code": "AUTHORITY_BAD_REQUEST", "detail": "%s: %s" % (type(exc).__name__, exc)}
        except Exception as exc:  # fail closed, never crash the service
            code = getattr(exc, "code", "") or "AUTHORITY_ERROR"
            return {"ok": False, "code": str(code), "detail": "%s: %s" % (type(exc).__name__, exc)}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE:
            ans = {"ok": False, "code": "AUTHORITY_BAD_REQUEST", "detail": "request too large"}
        else:
            ans = self.server.service.answer(line)  # type: ignore[attr-defined]
        self.wfile.write(json.dumps(ans, sort_keys=True, default=str).encode() + b"\n")


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(service: Service, socket_path: Path, *, ready: threading.Event | None = None) -> _Server:
    sp = Path(socket_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    if sp.exists() or sp.is_symlink():
        sp.unlink()
    srv = _Server(str(sp), _Handler)
    srv.service = service  # type: ignore[attr-defined]
    os.chmod(str(sp), 0o666)   # any local uid may CONNECT; only this principal decides
    if ready is not None:
        ready.set()
    return srv


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="outcome_authority")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the authority service")
    s.add_argument("--root", required=True, help="the destination tree (read, never written)")
    s.add_argument("--store-dir", required=True, help="a directory mounted only into this container")
    s.add_argument("--socket", required=True)
    s.add_argument("--native-db", default="", help="the board database (default: $HERMES_KANBAN_DB)")
    s.add_argument("--hermes", default="hermes")
    h = sub.add_parser("hello", help="ask a running service who it is")
    h.add_argument("--socket", required=True)
    c = sub.add_parser("code-identity", help="the digest the image stamps as outcome_authority.code_sha256")
    c.add_argument("--base", default=str(Path(__file__).resolve().parents[2]))
    ns = ap.parse_args(argv)
    if ns.cmd == "code-identity":
        print(code_identity(Path(ns.base)))
        return 0
    if ns.cmd == "hello":
        try:
            print(json.dumps(hello(ns.socket), indent=2, sort_keys=True))
        except AuthorityError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    svc = Service(Path(ns.root), Path(ns.store_dir), hermes=ns.hermes.split(),
                  native_db=ns.native_db or os.environ.get("HERMES_KANBAN_DB", ""))
    srv = serve(svc, Path(ns.socket))
    print(json.dumps({"serving": str(ns.socket), **svc.identity()}, sort_keys=True), flush=True)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
    return 0
