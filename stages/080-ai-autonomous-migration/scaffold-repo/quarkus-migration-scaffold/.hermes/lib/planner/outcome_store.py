"""The outcome-board authority store: one SQLite database, short transactions.

Path: ``verification/outcome-board/authority.sqlite3`` under the destination
root. There is no environment override, and a symlinked store directory or file
refuses STORE_REDIRECTED. A missing store refuses STORE_MISSING. It is never
re-created by a reader.

Serialization (architect F4): every decision runs in one ``BEGIN IMMEDIATE``
transaction that re-reads what it decides on. SQLite's database lock is the
single cross-process exclusion mechanism for revision commit, writer grants and
effect admission. A crashed owner releases it with its process. No transaction
spans a build, a native CLI call or an external request.

Integrity: the ledger is hash-chained (each row's hash covers the previous
hash and the row). ``meta.ledger_head`` / ``meta.ledger_count`` name the head,
and a mismatch refuses STORE_TAMPERED. That rejects inconsistent edits and
truncation. It does NOT reject a consistent rewrite of the whole database by
the same UID: this store is cooperative (outcome_protocol.authority_protected).
``claimed_control`` stays false.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

from planner.outcome_protocol import STORE_DIR, STORE_FILE

SCHEMA_VERSION = "rhoai3.outcome-authority/v1"
GENESIS = "0" * 64

DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (
  rev INTEGER PRIMARY KEY, parent INTEGER, kind TEXT NOT NULL, digest TEXT NOT NULL,
  doc TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id TEXT PRIMARY KEY, role TEXT NOT NULL, native_key TEXT NOT NULL UNIQUE,
  first_rev INTEGER NOT NULL, budget_key TEXT NOT NULL, budget_limit INTEGER NOT NULL,
  natural_key TEXT, aliases TEXT NOT NULL DEFAULT '[]', lineage TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'open', accepted_tree TEXT, accepted_commit TEXT, accepted_rev INTEGER);
CREATE TABLE IF NOT EXISTS ownership (
  obligation_id TEXT NOT NULL, rev INTEGER NOT NULL, outcome_id TEXT, disposition TEXT NOT NULL,
  reason TEXT, PRIMARY KEY (obligation_id, rev));
CREATE TABLE IF NOT EXISTS publication (
  outcome_id TEXT PRIMARY KEY, native_key TEXT NOT NULL, task_id TEXT, expected TEXT NOT NULL,
  attachment_id INTEGER, attachment_sha256 TEXT, attachment_name TEXT, rev INTEGER NOT NULL,
  state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS issues (
  issue_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, run_id INTEGER NOT NULL,
  claim_digest TEXT, outcome_id TEXT NOT NULL, rev INTEGER NOT NULL, baseline_commit TEXT,
  baseline_tree TEXT, cluster TEXT, allowed_paths TEXT NOT NULL, pins TEXT NOT NULL,
  budget_key TEXT NOT NULL, generation INTEGER NOT NULL, ledger_head TEXT NOT NULL,
  state TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
  seq INTEGER PRIMARY KEY, outcome_id TEXT NOT NULL, kind TEXT NOT NULL, budget_key TEXT,
  attempt_key TEXT, doc TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL,
  UNIQUE (outcome_id, kind, attempt_key));
CREATE TABLE IF NOT EXISTS intents (
  intent_id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_task TEXT, doc TEXT NOT NULL,
  steps TEXT NOT NULL DEFAULT '{}', state TEXT NOT NULL, created_at REAL NOT NULL,
  done_at REAL, result TEXT);
CREATE TABLE IF NOT EXISTS effects (
  effect_id TEXT PRIMARY KEY, kind TEXT NOT NULL, candidate TEXT NOT NULL, operation_id TEXT NOT NULL,
  rev INTEGER NOT NULL, generation INTEGER NOT NULL, state TEXT NOT NULL, doc TEXT NOT NULL,
  admitted_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS writer (
  slot TEXT PRIMARY KEY, task_id TEXT, run_id INTEGER, pid INTEGER, pgid INTEGER,
  generation INTEGER NOT NULL, granted_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS grants (
  outcome_id TEXT PRIMARY KEY, stage TEXT NOT NULL, cycle INTEGER NOT NULL, candidate TEXT NOT NULL,
  assessment TEXT NOT NULL, state TEXT NOT NULL, doc TEXT NOT NULL, granted_at REAL NOT NULL);
"""

UNRESOLVED_EFFECT_STATES = ("admitted", "sent", "uncertain")


class Crash(BaseException):
    """Test-only injected crash (OB_FAULT_MODE=raise). BaseException, so no
    ``except Exception`` handler can swallow it."""


def fault(point: str) -> None:
    """Crash injection for recovery tests: OB_FAULT=<point> ends the process at
    that point (os._exit), or raises Crash when OB_FAULT_MODE=raise."""
    if os.environ.get("OB_FAULT") == point:
        if os.environ.get("OB_FAULT_MODE") == "raise":
            raise Crash(point)
        os._exit(97)


class StoreError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_path(root: Path) -> Path:
    return Path(root) / STORE_FILE


def _redirected(root: Path) -> str:
    root = Path(root)
    cur = root
    for part in STORE_FILE.parts:
        cur = cur / part
        if cur.is_symlink():
            return "%s is a symlink" % cur.relative_to(root)
    real = Path(os.path.realpath(root / STORE_FILE))
    if not str(real).startswith(os.path.realpath(root) + os.sep):
        return "%s resolves outside the destination root" % STORE_FILE
    return ""


class Store:
    """One connection per process, opened on demand. ``create=True`` only for
    the publisher's first transaction; every other caller refuses a missing
    store."""

    def __init__(self, root: Path, *, create: bool = False):
        self.root = Path(root)
        self.path = store_path(self.root)
        why = _redirected(self.root)
        if why:
            raise StoreError("STORE_REDIRECTED", why)
        if not self.path.is_file():
            if not create:
                raise StoreError("STORE_MISSING", "%s is absent: nothing was published under the outcome protocol" % STORE_FILE)
            (self.root / STORE_DIR).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=60, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=60000")
        if create:
            self.conn.executescript(DDL)
        else:
            names = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"meta", "ledger", "issues", "publication", "intents", "effects"} <= names:
                raise StoreError("STORE_TAMPERED", "authority tables are missing")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()

    @contextlib.contextmanager
    def txn(self) -> Iterator[sqlite3.Connection]:
        """BEGIN IMMEDIATE: the writer lock is taken before anything is read."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    # -- meta ---------------------------------------------------------------
    def meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, c: sqlite3.Connection, key: str, value: Any) -> None:
        c.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))

    # -- ledger -------------------------------------------------------------
    def verify_chain(self) -> tuple[str, int]:
        prev = GENESIS
        n = 0
        for r in self.conn.execute("SELECT seq, outcome_id, kind, budget_key, attempt_key, doc, prev, hash FROM ledger ORDER BY seq"):
            n += 1
            if r["seq"] != n or r["prev"] != prev:
                raise StoreError("STORE_TAMPERED", "ledger row %s breaks the chain" % r["seq"])
            want = sha(prev + canonical([r["outcome_id"], r["kind"], r["budget_key"], r["attempt_key"], r["doc"]]))
            if want != r["hash"]:
                raise StoreError("STORE_TAMPERED", "ledger row %s hash does not cover its content" % r["seq"])
            prev = r["hash"]
        head, count = self.meta("ledger_head", GENESIS), int(self.meta("ledger_count", "0") or 0)
        if head != prev or count != n:
            raise StoreError("STORE_TAMPERED", "ledger head %s/%d does not match rows %s/%d" % (head[:12], count, prev[:12], n))
        return prev, n

    def append(self, c: sqlite3.Connection, outcome_id: str, kind: str, doc: dict[str, Any], *,
               budget_key: str = "", attempt_key: str = "") -> tuple[int, bool]:
        """(seq, appended). A row with the same (outcome, kind, attempt_key)
        already present is returned instead: a replayed transition never
        spends twice."""
        if attempt_key:
            row = c.execute("SELECT seq FROM ledger WHERE outcome_id=? AND kind=? AND attempt_key=?",
                            (outcome_id, kind, attempt_key)).fetchone()
            if row:
                return int(row[0]), False
        head = self.meta("ledger_head", GENESIS)
        count = int(self.meta("ledger_count", "0") or 0)
        text = canonical(doc)
        h = sha(head + canonical([outcome_id, kind, budget_key, attempt_key or None, text]))
        c.execute("INSERT INTO ledger(seq, outcome_id, kind, budget_key, attempt_key, doc, prev, hash) VALUES(?,?,?,?,?,?,?,?)",
                  (count + 1, outcome_id, kind, budget_key, attempt_key or None, text, head, h))
        self.set_meta(c, "ledger_head", h)
        self.set_meta(c, "ledger_count", count + 1)
        return count + 1, True

    def ledger(self, outcome_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT seq, outcome_id, kind, budget_key, attempt_key, doc FROM ledger"
        args: tuple = ()
        if outcome_id:
            q += " WHERE outcome_id=?"
            args = (outcome_id,)
        return [dict(r, doc=json.loads(r["doc"])) for r in self.conn.execute(q + " ORDER BY seq", args)]

    def spent(self, budget_key: str) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM ledger WHERE budget_key=? AND kind='reject'", (budget_key,)).fetchone()[0])

    # -- revisions ----------------------------------------------------------
    def current_revision(self) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT rev, doc, digest, state FROM revisions WHERE state='published' ORDER BY rev DESC LIMIT 1").fetchone()
        if not row:
            return None
        doc = json.loads(row["doc"])
        if sha(canonical(doc)) != row["digest"]:
            raise StoreError("STORE_TAMPERED", "revision %s content does not match its digest" % row["rev"])
        return doc

    def unresolved_effects(self, c: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        c = c or self.conn
        return [dict(r) for r in c.execute("SELECT * FROM effects WHERE state IN (%s)" % ",".join("?" * len(UNRESOLVED_EFFECT_STATES)),
                                           UNRESOLVED_EFFECT_STATES)]

    def commit_revision(self, doc: dict[str, Any], *, kind: str, parent: int | None) -> int:
        """Publish a new plan revision. Refuses while an effect is unresolved
        (REVISION_BLOCKED_BY_EFFECT), while M2 release is in progress, or when
        the parent is not the current revision (REVISION_STALE)."""
        text = canonical(doc)
        with self.txn() as c:
            eff = self.unresolved_effects(c)
            if eff:
                raise StoreError("REVISION_BLOCKED_BY_EFFECT", "effect %s is %s" % (eff[0]["effect_id"], eff[0]["state"]))
            if self.meta("release_in_progress") == "1":
                raise StoreError("REVISION_BLOCKED_BY_RELEASE", "M2 release is in progress")
            cur = c.execute("SELECT MAX(rev) FROM revisions WHERE state='published'").fetchone()[0]
            if (cur or None) != parent:
                raise StoreError("REVISION_STALE", "parent %s is not the current revision %s" % (parent, cur))
            rev = (cur or 0) + 1
            if int(doc.get("revision") or 0) != rev:
                raise StoreError("REVISION_STALE", "document revision %s, expected %d" % (doc.get("revision"), rev))
            c.execute("UPDATE revisions SET state='superseded' WHERE state='published'")
            c.execute("INSERT INTO revisions(rev, parent, kind, digest, doc, state, created_at) VALUES(?,?,?,?,?,?,?)",
                      (rev, parent, kind, sha(text), text, "published", time.time()))
            self.set_meta(c, "revision", rev)
            self.set_meta(c, "generation", int(self.meta("generation", "0") or 0) + 1)
            return rev
