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
from planner.canonical import load_json, write_canonical  # noqa: E402
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


WRITE_METHOD_PREFIXES = ("save", "delete", "remove", "update", "insert", "persist", "merge")
QUERY_ON_METHOD_RE = re.compile(
    r'@Query\s*(?:\(\s*(?:value\s*=\s*)?"(?P<q>[^"]*)"[^)]*\)|\(\s*\)|\b)'
    r'(?P<between>(?:\s*@[\w.]+(?:\([^)]*\))?)*)'
    r'\s*[\w.<>,\[\]]+\s+(?P<name>\w+)\s*\(', re.S)


def query_annotated_writes(text: str) -> list[tuple[str, str]]:
    """(method, query) for write-named methods this source annotates with
    @Query without a modifying statement.

    Spring Data derives writes from CrudRepository, not from a query: a @Query
    on save or delete either does nothing or does the wrong thing, and a bare
    one exists only to stop the platform complaining. A real modifying
    statement (@Modifying with UPDATE/DELETE/INSERT) is legitimate and is left
    alone."""
    out: list[tuple[str, str]] = []
    for m in QUERY_ON_METHOD_RE.finditer(text or ""):
        name = m.group("name")
        if not name.lower().startswith(WRITE_METHOD_PREFIXES):
            continue
        query = (m.group("q") or "").strip()
        # @Modifying may sit on either side of @Query; look at the declaration
        # as a whole rather than at one side of it
        window = (text[max(0, m.start() - 200): m.end()] or "")
        modifying = "@Modifying" in window
        if modifying and query[:6].upper() in ("UPDATE", "DELETE", "INSERT"):
            continue
        out.append((name, query))
    return out


def attempt_budget(steps: dict[str, Any], cluster: str, limit: int) -> int:
    """How many rejected attempts this cluster may spend before it defers.

    The attempt history is append-only: clearing a deferral changes that
    deferral's disposition, it never deletes the attempts or the identities of
    the cards they minted (the live-board comparator expects every one of them,
    and the record is the audit). So a clearance raises the budget instead of
    resetting the counter -- the cluster gets ``limit`` fresh attempts from
    where it stood when the Operator cleared it."""
    spent_at_clearance = [int(c.get("attempts") or 0) for c in (steps.get("deferral_clearances") or [])
                          if str(c.get("cluster") or "") == cluster]
    return limit + (max(spent_at_clearance) if spent_at_clearance else 0)


def load_deferred(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_DEFERRED, {"schema": "rhoai3.loop-deferred/v1", "clusters": [], "reasons": {}})


def save_deferred(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_DEFERRED, doc)


def load_state(root: Path) -> dict[str, Any] | None:
    p = root / LOOP_STATE
    return load_json(p) if p.is_file() else None


def save_state(root: Path, doc: dict[str, Any]) -> None:
    write_canonical(root / LOOP_STATE, doc)


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
