"""Shared helpers for the fix-until-green loop (not a CLI)."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


ensure_hermes_lib()
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import PRODUCT_EXEMPT, is_product_path as _is_product_path, LOOP_ACCEPTED, LOOP_CARDS, LOOP_DEFERRED, LOOP_ISSUED, LOOP_PENDING_FILES, LOOP_STATE, LOOP_STEPS, MTA_RESCAN_FINDINGS, VERIFY_BOOT, VERIFY_DIAGNOSTICS, VERIFY_PACKAGE, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST  # noqa: E402

# The accepted state's tool reports, including the gate receipts: a rejected
# candidate's packaging or startup result must not survive it. The work list is
# NOT here -- it is derived, it is rebuilt by every verification, and restoring
# an old copy makes the loop see a list its own measurement did not produce.
REPORTS = (VERIFY_DIAGNOSTICS, VERIFY_SUREFIRE, VERIFY_RUN, MTA_RESCAN_FINDINGS, VERIFY_PACKAGE, VERIFY_BOOT)


def _json_doc(root: Path, rel: Path, default: dict[str, Any]) -> dict[str, Any]:
    p = root / rel
    return load_json(p) if p.is_file() else default


def load_steps(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_STEPS, {"schema": "rhoai3.loop-steps/v1", "steps": [], "attempts": {}, "rejected": []})


def save_steps(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_STEPS, doc)


# ---------------------------------------------------------------------------
# semantic invariant SI-1 (v2): a source write must keep its state change
# ---------------------------------------------------------------------------
#
# Rule, versioned and documented, replacing the v1 name-prefix veto the
# architect review rejected (2026-09-11). The contract is not "a write may not
# use @Query" -- the platform documents @Modifying update/delete queries as
# supported (https://quarkus.io/guides/spring-data-jpa/#what-is-supported).
# The contract is that a member the SOURCE implemented as a state change must
# still perform one.
#
# What the v1 predicate got wrong, all three reproduced: it missed a
# fully-qualified @Query, borrowed @Modifying from a neighbouring declaration
# because it read a fixed window of characters, and flagged a read named
# updatedPetById because it matched on a name prefix.
#
# Syntax it cannot parse is INCONCLUSIVE, never a pass and never a violation.

SI1_RULE = "SI-1/v2"
_ANNOTATION = re.compile(r"@([\w.]+)\s*(\((?:[^()\"]|\"(?:[^\"\\]|\\.)*\")*\))?", re.S)
_DECL = re.compile(r"(?P<ret>[\w.<>,\[\]\s]+?)\s+(?P<name>\w+)\s*\((?P<args>[^)]*)\)\s*(?:throws[^;{]+)?[;{]", re.S)
_STATEMENT = re.compile(r"^\s*(SELECT|UPDATE|DELETE|INSERT)\b", re.I)
# how the frozen source performs a state change, per persistence mechanism
_SOURCE_WRITE_CALLS = ("persist(", "merge(", "remove(", "executeUpdate(", "saveAndFlush(",
                       ".update(", ".save(", ".delete(", ".insert(")


def _query_statement(args: str) -> tuple[str, bool]:
    """(the statement keyword, parsed) from a @Query's arguments.

    An argument this rule cannot read -- a constant, a SpEL expression -- is
    reported as unparsed, which makes the finding inconclusive rather than
    letting it pass or condemning it."""
    if not args or args.strip() in ("", "(", "()"):
        return "", True          # @Query carrying no statement at all
    m = re.search(r'"((?:[^"\\]|\\.)*)"', args, re.S)
    if not m:
        return "", False
    stmt = _STATEMENT.match(m.group(1).strip())
    return (stmt.group(1).upper() if stmt else ""), True


def _members(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """(member name, its own annotations) for each declaration in a type.

    Line-oriented on purpose: a regex over the whole file reads an annotation
    as a return type and then attributes it to the wrong member, which is how
    the v1 rule borrowed @Modifying from a neighbour and missed a
    fully-qualified @Query. Annotations accumulate until the declaration they
    precede, and are discarded with it.
    """
    out: list[tuple[str, list[tuple[str, str]]]] = []
    pending: list[str] = []
    buf = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith(("//", "*", "/*")):
            continue
        buf = (buf + " " + line).strip() if buf else line
        if buf.startswith("@"):
            if buf.count("(") != buf.count(")"):
                continue          # a multi-line annotation argument
            pending.append(buf)
            buf = ""
            continue
        buf = ""
        m = re.match(r"^(?:public|protected|private|default|static|abstract|final|\s)*"
                     r"[\w.<>,\[\]\s]*?\b(\w+)\s*\(", line)
        if m and ("(" in line):
            anns: list[tuple[str, str]] = []
            for a in pending:
                am = re.match(r"@([\w.]+)\s*(\(.*\))?$", a, re.S)
                if am:
                    anns.append((am.group(1).rsplit(".", 1)[-1], (am.group(2) or "").strip()))
            out.append((m.group(1), anns))
        pending = []
    return out


def source_write_members(root: Path) -> set[str]:
    """Members the FROZEN source implemented as a state change.

    Read from M1's structural model, whose call edges the compiler resolved.
    Scanning the body text near a declaration attributed one member's
    EntityManager.persist to the member above it (measured live 2026-09-11),
    which is how a read-only findById came to be judged a write."""
    from planner.dest_model import source_write_members as _model_writes

    writes, _why = _model_writes(root)
    return writes


def source_write_members_known(root: Path) -> tuple[set[str], str]:
    """The same, with the reason when the model could not be read."""
    from planner.dest_model import source_write_members as _model_writes

    return _model_writes(root)


def state_change_violations(text: str, writes: set[str]) -> tuple[list[dict], list[dict]]:
    """(violations, inconclusive) of SI-1 for one source file.

    A member the source wrote with must still write: a @Query that SELECTs, or
    one carrying no statement at all, replaces the state change with a read. A
    @Modifying UPDATE/DELETE/INSERT is a state change and passes, whatever the
    annotations' spelling or order. A member the source did not write with is
    not this rule's business, and a member with no @Query at all is inherited
    or derived and is not either."""
    violations: list[dict] = []
    inconclusive: list[dict] = []
    for name, anns in _members(text):
        if name not in writes:
            continue
        query = next((a for a in anns if a[0] == "Query"), None)
        if query is None:
            continue
        modifying = any(a[0] == "Modifying" for a in anns)
        stmt, parsed = _query_statement(query[1])
        if not parsed:
            inconclusive.append({"rule": SI1_RULE, "member": name,
                                 "detail": "the @Query argument is not a literal this rule can read (%s)" % query[1][:60]})
            continue
        if stmt in ("UPDATE", "DELETE", "INSERT") and modifying:
            continue
        violations.append({
            "rule": SI1_RULE, "member": name,
            "statement": stmt or "(none)",
            "modifying": modifying,
            "detail": ("%s is a state change in the source; this declaration answers it with %s. Spring Data provides save and delete "
                       "through CrudRepository, and a modifying query needs @Modifying with UPDATE, DELETE or INSERT"
                       % (name, ("a %s query" % stmt) if stmt else "a @Query carrying no statement")),
        })
    return violations, inconclusive


# The budget has ONE definition (planner.budget); these names stay for callers.
from planner.budget import attempt_budget, attempts_spent, budget, retry_key_for  # noqa: E402,F401


def load_deferred(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_DEFERRED, {"schema": "rhoai3.loop-deferred/v1", "clusters": [], "reasons": {}})


def save_deferred(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_DEFERRED, doc)


def load_state(root: Path) -> dict[str, Any] | None:
    p = root / LOOP_STATE
    return load_json(p) if p.is_file() else None


def save_state(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_STATE, doc)


def publish_loop_state(root: Path, worklist: dict[str, Any] | None = None) -> dict[str, Any]:
    """Operator-facing loop summary for the tree on disk.

    After rollback the accepted reports are restored and the work list is
    rebuilt; this publishes that same accepted revision as state.json so the
    summary cannot keep describing a rejected candidate (v8 Owner deferred /
    Pet still named as head, 2026-09-11)."""
    doc = worklist if isinstance(worklist, dict) else (_json_doc(root, WORKLIST, {}))
    state = {
        "schema": "rhoai3.loop-state/v1",
        "worklist_sha256": digest(doc) if doc else "",
        "candidate_sha256": candidate_sha256(root),
        "measure": doc.get("measure") or {},
        "head": doc.get("head") or "",
        "open_clusters": sum(1 for c in (doc.get("clusters") or []) if c.get("status") == "open"),
        "deferred": list(doc.get("deferred") or []),
        "blocked_clusters": list(doc.get("blocked_clusters") or []),
    }
    save_state(root, state)
    return state


def load_issued(root: Path) -> dict[str, Any] | None:
    p = root / LOOP_ISSUED
    return load_json(p) if p.is_file() else None


def load_cards(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_CARDS, {"schema": "rhoai3.loop-cards/v1", "control": {}})


def save_cards(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_CARDS, doc)


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def is_product_path(path: str) -> bool:
    """The one product-tree definition (planner.paths) — shared with the work list."""
    return _is_product_path(path)


def product_paths_changed(root: Path) -> list[str]:
    """Every product path that differs from HEAD: staged, unstaged, untracked."""
    proc = git(root, "status", "--porcelain", "--untracked-files=all")
    out: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if is_product_path(path):
            out.append(path)
    return sorted(set(out))


def candidate_sha256(root: Path) -> str:
    """Identity of the product tree as it is on disk (working tree, not the index)."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not is_product_path(rel):
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _props(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln or ln.startswith(("#", "!")) or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def profile_of(path: str) -> str:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if name.startswith("application-") and name.rsplit(".", 1)[-1] in ("properties", "yml", "yaml"):
        return name[len("application-"):].rsplit(".", 1)[0]
    return ""


def profile_keys_lost(profile: str, old_text: str, new_text: str, main_text: str, mappings: dict[str, str] | None = None) -> list[str]:
    """Keys a Spring profile file carried that a candidate drops without landing
    them in application.properties. The documented fix for
    springboot-properties-to-quarkus-00001 (Quarkus config guide, profiles) moves
    each key into the single file as %<profile>.<key>; a candidate that only
    deletes the file satisfies the rule by withdrawing the behavior (pilot v6
    t_0e1d4698: the hsqldb datasource went with the file). Only keys that carry
    behavior on the destination must land: quarkus.* keys, and keys the catalog
    maps to a Quarkus key. Spring keys with no mapping are the obligations being
    retired and may go."""
    mappings = mappings or {}
    old, new, main = _props(old_text), _props(new_text), _props(main_text)
    lost: list[str] = []
    for k in old:
        if k in new:
            continue
        target = k if k.startswith("quarkus.") else mappings.get(k, "")
        if not target:
            continue
        landed = any(cand in main for cand in ("%%%s.%s" % (profile, target), target, "%%%s.%s" % (profile, k), k))
        if not landed:
            lost.append(k)
    return lost


def profile_keys_lost_in_tree(root: Path, changed: list[str], mappings: dict[str, str] | None = None) -> dict[str, list[str]]:
    """{profile path: lost keys} across the changed product paths (HEAD vs disk)."""
    out: dict[str, list[str]] = {}
    for path in changed:
        prof = profile_of(path)
        if not prof or not path.startswith(("src/main/resources/", "src/test/resources/")):
            continue
        old = git(root, "show", "HEAD:%s" % path)
        if old.returncode != 0:
            continue  # a new profile file cannot lose keys
        p = root / path
        new_text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        main_p = root / (path.rsplit("/", 1)[0] + "/application." + path.rsplit(".", 1)[-1])
        main_text = main_p.read_text(encoding="utf-8", errors="replace") if main_p.is_file() else ""
        lost = profile_keys_lost(prof, old.stdout, new_text, main_text, mappings)
        if lost:
            out[path] = lost
    return out


def catalog_property_mappings(root: Path) -> dict[str, str]:
    p = root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
    if not p.is_file():
        return {}
    doc = load_json(p)
    return {str(k): str(v) for k, v in (doc.get("properties") or {}).items() if isinstance(v, str)}


def revert_paths(root: Path, paths: list[str]) -> None:
    """Restore HEAD for tracked paths in BOTH index and working tree; delete untracked."""
    tracked = [p for p in paths if git(root, "ls-files", "--error-unmatch", "--", p).returncode == 0]
    untracked = [p for p in paths if p not in tracked]
    if tracked:
        git(root, "reset", "-q", "HEAD", "--", *tracked)
        git(root, "checkout", "--", *tracked)
    for p in untracked:
        target = root / p
        if target.is_file():
            target.unlink()
    git(root, "reset", "-q")


def snapshot_reports(root: Path) -> None:
    """Keep the accepted state's tool reports so a rejected candidate's reports never survive it."""
    dest = root / LOOP_ACCEPTED
    dest.mkdir(parents=True, exist_ok=True)
    for rel in REPORTS:
        src = root / rel
        if src.is_file():
            shutil.copy2(src, dest / rel.name)


def restore_reports(root: Path) -> None:
    dest = root / LOOP_ACCEPTED
    for rel in REPORTS:
        src = dest / rel.name
        target = root / rel
        if src.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        elif target.is_file():
            target.unlink()


def classify_inconclusive(measure: dict[str, Any] | None, run: dict[str, Any] | None = None) -> str:
    """Why a measure is not known: harness, environment, or unresolved.

    Known product regressions are never classified here — those still reject.
    Missing Surefire stays unknown (harness): do not treat it as a pass."""
    blocked = " ".join(str(x) for x in ((measure or {}).get("blocked") or []))
    blob = blocked.lower()
    mode = str((run or {}).get("mode") or "")
    if mode == "diagnostic":
        return "harness"
    env_marks = (
        "build unresolvable",
        "runtime gate blocked by the environment",
        "connection refused",
        "password authentication failed",
        "unknownhostexception",
        "could not connect",
        "no such host",
    )
    harness_marks = (
        "no surefire",
        "tests unknown",
        "did not run in this verification",
        "mta rescan did not run",
        "disagree with maven",
        "checker is not reading",
        "mvn test exited",
    )
    if any(m in blob for m in env_marks):
        return "environment"
    if any(m in blob for m in harness_marks):
        return "harness"
    return "unresolved"


def pending_cluster_ids(steps: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for row in (steps or {}).get("pending") or []:
        if isinstance(row, dict) and row.get("cluster") and not row.get("cleared") and not row.get("rewound"):
            cid = str(row["cluster"])
            if cid not in out:
                out.append(cid)
    return out


def pending_for(steps: dict[str, Any] | None, cluster: str) -> dict[str, Any] | None:
    for row in reversed((steps or {}).get("pending") or []):
        if isinstance(row, dict) and str(row.get("cluster") or "") == cluster and not row.get("cleared") and not row.get("rewound"):
            return row
    return None


def _pending_dir(root: Path, cluster: str) -> Path:
    safe = cluster.replace(":", "_").replace("/", "_")
    return root / LOOP_PENDING_FILES / safe


class PendingRestoreError(RuntimeError):
    """A retained candidate did not come back as itself."""


def save_pending_candidate(root: Path, *, cluster: str, card: str, changed: list[str],
                           candidate_sha256_value: str, measure: dict[str, Any], reason: str,
                           cause: str, run: dict[str, Any] | None, issued: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy the candidate's changed product files aside before the tree is restored."""
    dest = _pending_dir(root, cluster)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    stored: list[str] = []
    deleted: list[str] = []
    for rel in changed:
        src = root / rel
        if not src.is_file():
            # the candidate DELETED this path; retaining only the files it
            # wrote would restore a tree the candidate never had (the
            # repository work removes declarations routinely)
            deleted.append(rel)
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        stored.append(rel)
    run_src = root / VERIFY_RUN
    if run_src.is_file():
        shutil.copy2(run_src, dest / "run.json")
    return {
        "cluster": cluster,
        "card": card,
        "cause": cause,
        "reason": reason,
        "measure": measure,
        "blocked": list((measure or {}).get("blocked") or []),
        "changed": list(changed),
        "stored": stored,
        "deleted": deleted,
        "candidate_sha256": candidate_sha256_value,
        "run_mode": str((run or {}).get("mode") or "acceptance"),
        "stages_ms": (run or {}).get("stages_ms") or {},
        "total_ms": (run or {}).get("total_ms"),
        "issued": dict(issued or {}),
        "files_dir": str(LOOP_PENDING_FILES / cluster.replace(":", "_").replace("/", "_")),
    }


def restore_pending_candidate(root: Path, cluster: str, row: dict[str, Any]) -> list[str]:
    """Put the retained candidate back on the product tree. Does not verify.

    Restores what the candidate wrote AND what it deleted, then checks that the
    tree is the candidate the row names: a retained candidate that comes back
    as something else would be promoted under its record."""
    dest = _pending_dir(root, cluster)
    restored: list[str] = []
    for rel in row.get("stored") or row.get("changed") or []:
        src = dest / rel
        if not src.is_file():
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        restored.append(rel)
    for rel in row.get("deleted") or []:
        target = root / rel
        if target.is_file():
            target.unlink()
            restored.append(rel)
    want = str(row.get("candidate_sha256") or "")
    if want:
        got = candidate_sha256(root)
        if got != want:
            raise PendingRestoreError(
                "the restored tree is %s, and the retained candidate was %s; it is not the candidate this record names"
                % (got[:12], want[:12]))
    return restored


def clear_pending(steps: dict[str, Any], cluster: str, *, why: str) -> None:
    for row in steps.get("pending") or []:
        if isinstance(row, dict) and str(row.get("cluster") or "") == cluster and not row.get("cleared"):
            row["cleared"] = why
