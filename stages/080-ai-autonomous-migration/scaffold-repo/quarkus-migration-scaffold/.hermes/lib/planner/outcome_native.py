"""Native Hermes Kanban access for the outcome board: what the board really says.

Reads go to ``kanban.db`` opened READ-ONLY (the pinned CLI exposes neither the
idempotency key nor archived identities by key, and returns no attachment
digest). Mutations go through the pinned CLI only (``hermes kanban create /
attach / assign / link / comment``); nothing here writes the database.

The database path the authority trusts is the one recorded at publication
(``meta.native_db``). A later caller that resolves another path refuses
NATIVE_REDIRECTED, so an exported HERMES_KANBAN_DB cannot point a check at a
forged board.

``FakeNative`` implements the same surface in memory for synthetic tests. It is
not evidence of native behaviour. The exact-runtime tests drive
``KanbanNative`` against the patched runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Callable

Runner = Callable[[list[str]], tuple[int, str, str]]
MARKER = "[outcome-board]"


class NativeError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def default_db_path(env: dict[str, str] | None = None) -> str:
    env = dict(os.environ if env is None else env)
    pinned = (env.get("HERMES_KANBAN_DB") or "").strip()
    if pinned:
        return os.path.realpath(pinned)
    home = (env.get("HERMES_HOME") or "").strip()
    if home:
        parent, name = os.path.split(home.rstrip("/"))
        root, profiles = os.path.split(parent)
        if profiles == "profiles" and name and root:
            home = root
        return os.path.realpath(os.path.join(home, "kanban.db"))
    return ""


def subprocess_runner(argv: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class KanbanNative:
    def __init__(self, db_path: str, *, hermes: list[str] | None = None, runner: Runner | None = None,
                 env: dict[str, str] | None = None):
        self.db_path = os.path.realpath(db_path) if db_path else ""
        self.hermes = list(hermes or ["hermes"])
        self.env = env
        self._runner = runner

    # -- read side (read-only sqlite) ------------------------------------------
    def _ro(self) -> sqlite3.Connection:
        if not self.db_path or not os.path.isfile(self.db_path):
            raise NativeError("NATIVE_UNAVAILABLE", "kanban database %r is absent" % self.db_path)
        con = sqlite3.connect("file:%s?mode=ro" % self.db_path, uri=True, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def task(self, task_id: str) -> dict[str, Any] | None:
        con = self._ro()
        try:
            row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                return None
            out = dict(row)
            out["parents"] = sorted(r[0] for r in con.execute("SELECT parent_id FROM task_links WHERE child_id=?", (task_id,)))
            try:
                out["skills"] = json.loads(out.get("skills") or "[]") or []
            except ValueError:
                out["skills"] = []
            return out
        finally:
            con.close()

    def by_key(self, key: str) -> list[dict[str, Any]]:
        con = self._ro()
        try:
            return [{"id": r["id"], "status": r["status"]} for r in
                    con.execute("SELECT id, status FROM tasks WHERE idempotency_key=? ORDER BY created_at, id", (key,))]
        finally:
            con.close()

    def comments(self, task_id: str) -> list[str]:
        con = self._ro()
        try:
            return [r[0] for r in con.execute("SELECT body FROM task_comments WHERE task_id=? ORDER BY id", (task_id,))]
        finally:
            con.close()

    def attachments(self, task_id: str) -> list[dict[str, Any]]:
        con = self._ro()
        try:
            return [dict(r) for r in con.execute(
                "SELECT id, filename, stored_path, size FROM task_attachments WHERE task_id=? ORDER BY id", (task_id,))]
        finally:
            con.close()

    def run(self, run_id: int) -> dict[str, Any] | None:
        con = self._ro()
        try:
            row = con.execute("SELECT * FROM task_runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row else None
        finally:
            con.close()

    def comment_rows(self, task_id: str) -> list[dict[str, Any]]:
        """Every comment of a task, oldest first: id (board-wide order), author, body."""
        con = self._ro()
        try:
            return [{"id": int(r["id"]), "author": r["author"], "body": r["body"]} for r in
                    con.execute("SELECT id, author, body FROM task_comments WHERE task_id=? ORDER BY id", (task_id,))]
        finally:
            con.close()

    def runs(self, task_id: str) -> list[dict[str, Any]]:
        """The task's native run history, oldest first."""
        con = self._ro()
        try:
            return [dict(r) for r in con.execute("SELECT * FROM task_runs WHERE task_id=? ORDER BY id", (task_id,))]
        finally:
            con.close()

    def tasks_with_key_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Every task whose idempotency key starts with ``prefix`` (archived included)."""
        con = self._ro()
        try:
            like = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            return [{"id": r["id"], "status": r["status"], "idempotency_key": r["idempotency_key"]} for r in
                    con.execute("SELECT id, status, idempotency_key FROM tasks WHERE idempotency_key LIKE ? ESCAPE '\\' "
                                "ORDER BY created_at, id", (like,))]
        finally:
            con.close()

    # -- write side (pinned CLI) ----------------------------------------------
    def _cli(self, *args: str) -> str:
        argv = self.hermes + ["kanban", *args]
        runner = self._runner or (lambda a: subprocess_runner(a, self.env))
        rc, out, err = runner(argv)
        if rc != 0:
            raise NativeError("NATIVE_CLI", "%s exited %s: %s" % (" ".join(args[:2]), rc, (err or out).strip()[:300]))
        return out

    def create(self, *, title: str, body: str, assignee: str | None, parents: list[str], key: str,
               skills: list[str], workspace: str, max_retries: int, max_runtime: str = "2h", branch: str = "") -> str:
        args = ["create", title, "--body", body, "--idempotency-key", key, "--max-retries", str(max_retries),
                "--max-runtime", max_runtime, "--json"]
        if branch:
            # a worktree task's branch (pinned CLI: --branch is only valid with --workspace worktree)
            args += ["--branch", branch]
        if assignee:
            args += ["--assignee", assignee]
        for p in parents:
            args += ["--parent", p]
        if workspace:
            args += ["--workspace", workspace]
        for s in skills:
            args += ["--skill", s]
        out = self._cli(*args)
        try:
            doc = json.loads(out[out.find("{"):out.rfind("}") + 1])
        except ValueError as exc:
            raise NativeError("NATIVE_CLI", "create --json unparseable (%s)" % exc) from exc
        tid = str(doc.get("id") or doc.get("task_id") or "")
        if not tid.startswith("t_"):
            raise NativeError("NATIVE_CLI", "create returned no t_* id")
        return tid

    def attach(self, task_id: str, path: str, name: str) -> int:
        out = self._cli("attach", task_id, path, "--name", name)
        import re
        m = re.search(r"attachment (\d+)", out)
        if not m:
            raise NativeError("NATIVE_CLI", "attach printed no attachment id: %s" % out.strip()[:200])
        return int(m.group(1))

    def assign(self, task_id: str, profile: str) -> None:
        self._cli("assign", task_id, profile)

    def link(self, parent: str, child: str) -> None:
        self._cli("link", parent, child)

    def comment(self, task_id: str, text: str, author: str = "") -> None:
        args = ["comment", task_id, text]
        if author:
            args += ["--author", author]
        self._cli(*args)


class FakeNative:
    """In-memory stand-in with the pinned semantics the qualification measured:
    a repeated idempotency key returns the existing live id without updating
    it; archived rows are excluded from key lookup (a new row is created);
    repeated attachments get new ids and collision-renamed names; unassigned
    tasks are never dispatched here. SYNTHETIC: not native evidence."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.db_path = str(self.root / "fake-kanban.db")
        self.tasks: dict[str, dict[str, Any]] = {}
        self.links: set[tuple[str, str]] = set()
        self.comments_: dict[str, list[str]] = {}
        self.comment_meta: dict[str, list[dict[str, Any]]] = {}
        self.attach_: dict[str, list[dict[str, Any]]] = {}
        self.runs_: dict[int, dict[str, Any]] = {}
        self.n = 0
        self.fail_after: dict[str, int] = {}
        self.calls: list[tuple[str, ...]] = []

    def sync(self) -> None:
        """Mirror the in-memory board into a SQLite file with the pinned
        kanban.db column names, so a separate process (the K2 hook under
        test) reads it through KanbanNative exactly as it reads a real board."""
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(
                "DROP TABLE IF EXISTS tasks; DROP TABLE IF EXISTS task_links; DROP TABLE IF EXISTS task_comments;"
                "DROP TABLE IF EXISTS task_attachments; DROP TABLE IF EXISTS task_runs;"
                "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT, status TEXT,"
                " idempotency_key TEXT, skills TEXT, workspace_path TEXT, max_retries INTEGER, current_run_id INTEGER,"
                " claim_lock TEXT, worker_pid INTEGER, created_at INTEGER);"
                "CREATE TABLE task_links (parent_id TEXT, child_id TEXT);"
                "CREATE TABLE task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, author TEXT, body TEXT, created_at INTEGER);"
                "CREATE TABLE task_attachments (id INTEGER PRIMARY KEY, task_id TEXT, filename TEXT, stored_path TEXT, size INTEGER);"
                "CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT, claim_lock TEXT, profile TEXT,"
                " outcome TEXT);")
            for i, t in enumerate(self.tasks.values()):
                con.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (t["id"], t.get("title"), t.get("body"), t.get("assignee"), t.get("status"), t.get("idempotency_key"),
                             json.dumps(t.get("skills") or []), t.get("workspace_path"), t.get("max_retries"),
                             t.get("current_run_id"), t.get("claim_lock"), t.get("worker_pid"), i))
            con.executemany("INSERT INTO task_links VALUES (?,?)", sorted(self.links))
            rows_all = sorted((m["id"], tid, m["author"], m["body"]) for tid, ms in self.comment_meta.items() for m in ms)
            for cid, tid, author, body in rows_all:
                con.execute("INSERT INTO task_comments(id, task_id, author, body, created_at) VALUES (?,?,?,?,0)", (cid, tid, author, body))
            for tid, rows in self.attach_.items():
                for a in rows:
                    con.execute("INSERT INTO task_attachments VALUES (?,?,?,?,?)", (a["id"], tid, a["filename"], a["stored_path"], a["size"]))
            for rid, r in self.runs_.items():
                con.execute("INSERT INTO task_runs VALUES (?,?,?,?,?,?)", (rid, r["task_id"], r["status"], r.get("claim_lock"),
                                                                        r.get("profile"), r.get("outcome")))
            con.commit()
        finally:
            con.close()

    def _maybe_fail(self, op: str) -> None:
        if op in self.fail_after:
            self.fail_after[op] -= 1
            if self.fail_after[op] < 0:
                del self.fail_after[op]
                raise NativeError("NATIVE_CLI", "injected failure on %s" % op)

    def task(self, task_id: str) -> dict[str, Any] | None:
        t = self.tasks.get(task_id)
        if not t:
            return None
        return dict(t, parents=sorted(p for p, c in self.links if c == task_id))

    def by_key(self, key: str) -> list[dict[str, Any]]:
        return [{"id": t["id"], "status": t["status"]} for t in self.tasks.values() if t.get("idempotency_key") == key]

    def comments(self, task_id: str) -> list[str]:
        return list(self.comments_.get(task_id, []))

    def comment_rows(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(m) for m in self.comment_meta.get(task_id, [])]

    def runs(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(r) for _rid, r in sorted(self.runs_.items()) if r["task_id"] == task_id]

    def tasks_with_key_prefix(self, prefix: str) -> list[dict[str, Any]]:
        return [{"id": t["id"], "status": t["status"], "idempotency_key": t.get("idempotency_key")}
                for t in self.tasks.values() if str(t.get("idempotency_key") or "").startswith(prefix)]

    def attachments(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(a) for a in self.attach_.get(task_id, [])]

    def run(self, run_id: int) -> dict[str, Any] | None:
        return self.runs_.get(run_id)

    def create(self, *, title, body, assignee, parents, key, skills, workspace, max_retries, max_runtime="2h", branch="") -> str:
        self.calls.append(("create", key))
        self._maybe_fail("create")
        for t in self.tasks.values():
            if t.get("idempotency_key") == key and t["status"] != "archived":
                return t["id"]
        self.n += 1
        tid = "t_%08x" % (0x1000 + self.n)
        status = "todo" if any(self.tasks.get(p, {}).get("status") not in ("done", "archived") for p in parents) else "ready"
        self.tasks[tid] = {"id": tid, "title": title, "body": body, "assignee": assignee, "status": status,
                           "idempotency_key": key, "skills": list(skills), "workspace_path": workspace,
                           "workspace_kind": workspace.split(":", 1)[0] if ":" in workspace else "dir",
                           "branch_name": branch or None,
                           "max_retries": max_retries, "current_run_id": None, "claim_lock": None,
                           "worker_pid": None}
        for p in parents:
            self.links.add((p, tid))
        self._maybe_fail("after-create")
        return tid

    def attach(self, task_id: str, path: str, name: str) -> int:
        self.calls.append(("attach", task_id))
        self._maybe_fail("attach")
        rows = self.attach_.setdefault(task_id, [])
        self.n += 1
        stored = self.root / "fake-attachments" / task_id
        stored.mkdir(parents=True, exist_ok=True)
        fname = name if not any(r["filename"] == name for r in rows) else "%s (%d)%s" % (
            os.path.splitext(name)[0], len(rows), os.path.splitext(name)[1])
        target = stored / fname
        target.write_bytes(Path(path).read_bytes())
        rows.append({"id": self.n, "filename": fname, "stored_path": str(target), "size": target.stat().st_size})
        return self.n

    def assign(self, task_id: str, profile: str) -> None:
        self.calls.append(("assign", task_id))
        self._maybe_fail("assign")
        self.tasks[task_id]["assignee"] = profile

    def link(self, parent: str, child: str) -> None:
        self.calls.append(("link", parent, child))
        self.links.add((parent, child))
        # pinned kanban_db.link_tasks: a ready child of a parent that is not done goes back to todo
        ch, pa = self.tasks.get(child), self.tasks.get(parent)
        if ch and pa and pa["status"] != "done" and ch["status"] == "ready":
            ch["status"] = "todo"

    def comment(self, task_id: str, text: str, author: str = "") -> None:
        self.calls.append(("comment", task_id))
        self._maybe_fail("comment")
        self.n += 1
        self.comments_.setdefault(task_id, []).append(text)
        self.comment_meta.setdefault(task_id, []).append({"id": self.n, "author": author or "user", "body": text.strip()})

    # -- test helpers standing in for dispatcher / worker lifecycle ------------
    def claim(self, task_id: str, *, pid: int = 0) -> tuple[int, str]:
        t = self.tasks[task_id]
        self.n += 1
        run_id = self.n
        lock = "lock-%d" % run_id
        t.update(status="running", current_run_id=run_id, claim_lock=lock, worker_pid=pid)
        self.runs_[run_id] = {"id": run_id, "task_id": task_id, "status": "running", "claim_lock": lock,
                              "profile": t.get("assignee"), "outcome": None}
        return run_id, lock

    def end_run(self, task_id: str, status: str = "ready", outcome: str | None = None) -> None:
        t = self.tasks[task_id]
        if t.get("current_run_id") in self.runs_:
            self.runs_[t["current_run_id"]]["status"] = "ended"
            self.runs_[t["current_run_id"]]["outcome"] = outcome
        t.update(status=status, current_run_id=None, claim_lock=None, worker_pid=None)

    def complete(self, task_id: str) -> None:
        self.end_run(task_id, "done", "completed")
        for p, c in self.links:
            if p == task_id:
                ch = self.tasks.get(c)
                if ch and ch["status"] == "todo" and all(self.tasks[pp]["status"] in ("done", "archived")
                                                           for pp, cc in self.links if cc == c):
                    ch["status"] = "ready"

    def archive(self, task_id: str) -> None:
        self.tasks[task_id]["status"] = "archived"

    # -- the pinned review / dependency semantics (kanban_db.request_review,
    #    request_changes, block_task kind=dependency), for synthetic tests ------
    def _parents_done(self, task_id: str) -> bool:
        return all(self.tasks[p]["status"] in ("done", "archived") for p, c in self.links if c == task_id)

    def request_review(self, task_id: str, reviewer: str = "reviewer") -> None:
        t = self.tasks[task_id]
        t["_implementer"] = t.get("assignee")
        self.end_run(task_id, "review", "review_requested")
        t["assignee"] = reviewer

    def claim_review(self, task_id: str, *, pid: int = 0) -> tuple[int, str]:
        assert self.tasks[task_id]["status"] == "review", self.tasks[task_id]["status"]
        return self.claim(task_id, pid=pid)

    def request_changes(self, task_id: str, reason: str = "") -> None:
        t = self.tasks[task_id]
        self.end_run(task_id, "ready" if self._parents_done(task_id) else "todo", "changes_requested")
        t["assignee"] = t.get("_implementer") or t.get("assignee")

    def block_dependency(self, task_id: str) -> None:
        """kind=dependency: back to todo while a parent is open (native promotion), else blocked."""
        self.end_run(task_id, "todo" if not self._parents_done(task_id) else "blocked", "blocked")
