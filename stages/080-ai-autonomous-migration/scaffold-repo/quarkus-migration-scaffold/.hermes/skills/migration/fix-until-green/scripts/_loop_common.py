"""Shared helpers for the fix-until-green loop (not a CLI)."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


ensure_hermes_lib()
from planner.canonical import digest, load_json, product_tree_sha256, sha256_file, write_canonical  # noqa: E402
from planner.paths import DECISIONS, MIGRATION, PARITY_DIR, PRODUCT_EXEMPT, is_product_path as _is_product_path, LOOP_ACCEPTED, LOOP_CARDS, LOOP_DEFERRED, LOOP_ISSUED, LOOP_PENDING_FILES, LOOP_STATE, LOOP_STEPS, MTA_RESCAN_FINDINGS, VERIFY_BOOT, VERIFY_DIAGNOSTICS, VERIFY_PACKAGE, VERIFY_RUN, VERIFY_SUREFIRE, WORKLIST  # noqa: E402

# The accepted state's tool reports, including the gate receipts: a rejected
# candidate's packaging or startup result must not survive it. The work list is
# NOT here -- it is derived, it is rebuilt by every verification, and restoring
# an old copy makes the loop see a list its own measurement did not produce.
REPORTS = (VERIFY_DIAGNOSTICS, VERIFY_SUREFIRE, VERIFY_RUN, MTA_RESCAN_FINDINGS, VERIFY_PACKAGE, VERIFY_BOOT)
# The parity comparison the acceptance path re-runs for a parity card: the
# composed receipt and the per-verdict records the work list reads. A rejected
# candidate's comparison must not survive it either, so they are snapshotted and
# restored like the reports above -- with one difference. An ABSENT snapshot
# leaves the records on disk alone instead of deleting them: before the first
# accepted parity step the records under verification/parity are the M4 road's,
# measured on the accepted tree, and deleting them would erase the obligations
# rather than restore them.
PARITY_SNAPSHOT = Path("parity")
# WHOSE comparison the snapshot beside it is. Kept OUTSIDE the snapshot
# directory on purpose: restore_reports copies every document it finds there
# back over the live records, and a provenance note is not a verdict.
PARITY_SNAPSHOT_SOURCE = Path("parity-source.json")
PARITY_SOURCE_SCHEMA = "rhoai3.parity-baseline/v1"

# Where THIS migration's product lives. `is_product_path` is an EXEMPT list --
# everything that is not harness state, the frozen legacy copy or build output
# -- so scratch a tool drops anywhere else in the destination root is "product"
# to it. Measured on v9 card t_46556d5e: the worker's javap diagnosis left
# extracted .class files under io/quarkus/ at the root after its verification,
# advance.py counted them as a post-verification product edit, and a repair it
# had already measured was REVERTED with an attempt spent on tool output.
MIGRATION_PRODUCT_DIRS = ("src/", ".mvn/")
MIGRATION_PRODUCT_FILES = (DECISIONS.as_posix(), MIGRATION.as_posix(), "pom.xml", "mvnw", "mvnw.cmd")


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


def is_migration_product(rel: str) -> bool:
    """Is this path somewhere a repair of THIS migration is written?

    The Maven project and the decisions the loop reads. Narrower than
    `is_product_path` on purpose, and used only to decide whether an UNTRACKED
    file is part of the candidate: anything git already tracks is the
    migration's whatever it is called, and only a file nobody committed and
    nobody could have repaired is a tool's leftovers."""
    p = str(rel).replace("\\", "/").lstrip("/")
    return p.startswith(MIGRATION_PRODUCT_DIRS) or p in MIGRATION_PRODUCT_FILES


def tree_changes(root: Path) -> tuple[list[str], list[str]]:
    """(the candidate's own paths, scratch) among everything that differs from HEAD.

    A path belongs to the candidate when git TRACKS it -- HEAD knows it, the
    loop committed it, and a difference there is a change to something this
    migration owns -- or when it is an untracked file written where the
    migration's product lives (a new source file is a repair). An untracked
    file anywhere else is a tool's leftovers: it is part of no repair, and it
    is not evidence against one either."""
    proc = git(root, "status", "--porcelain", "--untracked-files=all")
    owned: list[str] = []
    scratch: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not is_product_path(path):
            continue
        (scratch if (code == "??" and not is_migration_product(path)) else owned).append(path)
    return sorted(set(owned)), sorted(set(scratch))


def candidate_sha256(root: Path, exclude: Iterable[str] = ()) -> str:
    """Identity of the product tree as it is on disk (working tree, not the index).

    One implementation, shared: ``planner.canonical.product_tree_sha256`` is
    what the destination rescan records as the tree it scanned and what the
    M4 rescan floor compares against, so the loop's accepted-step digest and
    the rescan's are the same function over the same paths."""
    return product_tree_sha256(root, exclude)


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


def parity_records(base: Path) -> list[Path]:
    """The parity documents under one tree, relative to it: the composed
    receipt and every verdict record (per entry point, per scenario). The run
    record and the destination log are not evidence of a verdict and are left
    where they are."""
    out: list[Path] = []
    d = Path(base)
    if not d.is_dir():
        return out
    out += [p.relative_to(base) for p in sorted(d.glob("*.json")) if p.name != "_run.json"]
    out += [p.relative_to(base) for p in sorted((d / "scenarios").glob("*.json"))]
    return out


def snapshot_parity(root: Path, source: dict[str, Any] | None = None) -> list[Path]:
    """Make the comparison on disk the loop's ACCEPTED parity baseline.

    Every step that changes WHAT THE BASELINE IS has to call this, not only
    the acceptance path, because `restore_reports` puts this snapshot back
    over the live records whenever a candidate is discarded. Measured on
    destination v9: an accepted parity step snapshotted its receipt, the M4
    road then composed a full receipt with thirteen FAIL rows, `resume-after-m4`
    minted the cards those rows owed and snapshotted nothing -- and the first
    reverted candidate restored the older accepted snapshot over the receipt
    its own card had been issued from. The obligation the loop was working on
    disappeared: no open cluster, no card, nothing minted.

    ``source`` records whose comparison this baseline is (mode and card); it is
    written beside the snapshot, never inside it. Returns the records kept."""
    dest = root / LOOP_ACCEPTED
    live = root / PARITY_DIR
    records = parity_records(live)
    if not records:
        return []
    dest.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(dest / PARITY_SNAPSHOT, ignore_errors=True)
    for rel in records:
        target = dest / PARITY_SNAPSHOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live / rel, target)
    if source is not None:
        write_canonical(dest / PARITY_SNAPSHOT_SOURCE, dict(source))
    return records


PARITY_UNMEASURED = "UNMEASURED"


def snapshot_parity_unmeasured(root: Path, reason: str, *, commit: str = "", by: str = "") -> dict[str, Any]:
    """F2: the accepted baseline after a step that CHANGED the product.

    The comparison on disk was made on the tree before that step, so freezing
    it would give every later revert a receipt of another tree -- on v9 the
    ADR-019 step froze the pre-adapter FAIL, a revert restored it, and the loop
    re-issued the repair it had just applied. The baseline is instead recorded
    as UNMEASURED for this tree, with the reason and the digest of the receipt
    it replaces kept as history, until refresh-accepted-parity.py snapshots a
    sealed comparison of this tree."""
    dest = root / LOOP_ACCEPTED
    live = root / PARITY_DIR / "receipt.json"
    prior = {}
    if live.is_file():
        try:
            doc = load_json(live)
        except (OSError, ValueError):
            doc = {}
        prior = {"receipt_sha256": str((doc or {}).get("receipt_sha256") or ""), "verdict": str((doc or {}).get("verdict") or ""),
                 "file_sha256": sha256_file(live), "binding": dict((doc or {}).get("binding") or {}) if isinstance((doc or {}).get("binding"), dict) else {}}
    receipt = {"schema": "rhoai3.parity-receipt/v1", "verdict": PARITY_UNMEASURED, "entry_points": [], "total": 0,
               "unmeasured": {"reason": str(reason), "commit": commit, "by": by, "prior": prior}}
    dest.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(dest / PARITY_SNAPSHOT, ignore_errors=True)
    (dest / PARITY_SNAPSHOT).mkdir(parents=True, exist_ok=True)
    write_canonical(dest / PARITY_SNAPSHOT / "receipt.json", receipt)
    write_canonical(dest / PARITY_SNAPSHOT_SOURCE, {"schema": PARITY_SOURCE_SCHEMA, "mode": "unmeasured", "reason": str(reason),
                                                    "commit": commit, "by": by, "prior": prior})
    # and the LIVE records say the same: the work list rebuilt next must not
    # mint from another tree's verdicts (they are set aside, never deleted)
    _set_parity_aside(root)
    (root / PARITY_DIR).mkdir(parents=True, exist_ok=True)
    write_canonical(root / PARITY_DIR / "receipt.json", receipt)
    return receipt


PARITY_SET_ASIDE = LOOP_ACCEPTED.parent / "parity-set-aside"
# every refreshed baseline, kept by refresh number, so a rewind to the step it
# measured can restore it instead of declaring that tree UNMEASURED
PARITY_REFRESHES = LOOP_ACCEPTED.parent / "parity-refreshes"


def archive_parity_baseline(root: Path, n: int) -> Path:
    """Copy the accepted parity baseline (records and source) under refresh ``n``."""
    dest = root / PARITY_REFRESHES / str(n)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    src = root / LOOP_ACCEPTED / PARITY_SNAPSHOT
    if src.is_dir():
        shutil.copytree(src, dest / PARITY_SNAPSHOT)
    if (root / LOOP_ACCEPTED / PARITY_SNAPSHOT_SOURCE).is_file():
        shutil.copy2(root / LOOP_ACCEPTED / PARITY_SNAPSHOT_SOURCE, dest / PARITY_SNAPSHOT_SOURCE)
    return dest


def install_parity_baseline(root: Path, src: Path, source: dict[str, Any] | None = None) -> list[Path]:
    """Make the parity records under ``src`` (a snapshot directory) the
    accepted baseline AND the live records; what was live is set aside."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="parity-baseline-") as td:
        staged = Path(td) / "parity"
        shutil.copytree(src, staged)
        records = parity_records(staged)
        dest = root / LOOP_ACCEPTED
        dest.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dest / PARITY_SNAPSHOT, ignore_errors=True)
        shutil.copytree(staged, dest / PARITY_SNAPSHOT)
        if source is not None:
            write_canonical(dest / PARITY_SNAPSHOT_SOURCE, dict(source))
        _set_parity_aside(root)
        live = root / PARITY_DIR
        for rel in records:
            target = live / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged / rel, target)
    return records


def _set_parity_aside(root: Path) -> None:
    live = root / PARITY_DIR
    for rel in parity_records(live):
        target = root / PARITY_SET_ASIDE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(live / rel), str(target))


def parity_not_of_this_tree(root: Path, *, direct: bool = False) -> str:
    """Why the parity receipt on disk is NOT a whole comparison of the tree the
    last verification measured ("" when it is): the comparison ran in that
    verification (run.json runtime.parity), unscoped, and the runner's record
    says its composer wrote the receipt, sealed. Anything else is a receipt of
    another tree or of part of this one."""
    live = root / PARITY_DIR / "receipt.json"
    if not live.is_file():
        return "no parity receipt"
    run = _json_doc(root, VERIFY_RUN, {})
    par = ((run.get("runtime") or {}).get("parity") or {}) if isinstance(run, dict) else {}
    # ``direct``: the Operator ran run-parity.py on the accepted tree after the
    # verification; the caller then binds it by admission receipt and artifact
    if not direct and not par.get("ran"):
        return "the last verification ran no parity comparison, so the receipt on disk is an earlier tree's"
    if not direct and par.get("scoped"):
        return "the last comparison was scoped to %s" % ", ".join(par.get("scenarios") or [])
    rec = _json_doc(root, PARITY_DIR / "_run.json", {})
    if list(rec.get("scenario_filter") or []):
        return "the runner's record is scoped to %s" % ", ".join(rec.get("scenario_filter") or [])
    if str(rec.get("security_mode") or "disabled") != "disabled" and direct:
        return "the runner's record is of the %s security mode; the loop's baseline is the default mode's" % rec.get("security_mode")
    if not bool((rec.get("receipt") or {}).get("composed_by_this_run")):
        return "the runner's record does not say its composer wrote the receipt on disk"
    doc = _json_doc(root, PARITY_DIR / "receipt.json", {})
    mode = str(((doc.get("binding") or {}) if isinstance(doc.get("binding"), dict) else {}).get("mode") or "sealed")
    if mode != "sealed":
        return "the receipt is %s-bound, not a sealed comparison of the accepted tree" % mode
    return ""


def snapshot_reports(root: Path, *, parity_unmeasured: str = "", commit: str = "", by: str = "") -> None:
    """Keep the accepted state's tool reports so a rejected candidate's reports never survive it."""
    dest = root / LOOP_ACCEPTED
    dest.mkdir(parents=True, exist_ok=True)
    for rel in REPORTS:
        src = root / rel
        if src.is_file():
            shutil.copy2(src, dest / rel.name)
    if parity_unmeasured and (parity_records(root / PARITY_DIR) or parity_records(dest / PARITY_SNAPSHOT)):
        snapshot_parity_unmeasured(root, parity_unmeasured, commit=commit, by=by)
    elif parity_unmeasured:
        return  # parity was never compared here: there is nothing to freeze or to mark
    else:
        snapshot_parity(root)


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
    snap = dest / PARITY_SNAPSHOT
    kept = parity_records(snap)
    if not kept:
        return  # no accepted comparison to restore: see PARITY_SNAPSHOT
    live = root / PARITY_DIR
    try:
        unmeasured = str((load_json(snap / "receipt.json") or {}).get("verdict") or "") == PARITY_UNMEASURED
    except (OSError, ValueError):
        unmeasured = False
    if unmeasured:
        # the accepted tree was never compared: no record of any other tree
        # may stand in for it (they are set aside, never deleted)
        _set_parity_aside(root)
    for rel in parity_records(live):
        if rel not in kept:
            (live / rel).unlink()
    for rel in kept:
        target = live / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snap / rel, target)


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
        "head_commit": git(root, "rev-parse", "HEAD").stdout.strip(),
        "files_dir": str(LOOP_PENDING_FILES / cluster.replace(":", "_").replace("/", "_")),
    }


def _pending_restore_drift(root: Path, cluster: str, row: dict[str, Any]) -> str:
    """Why the restored tree is not this candidate, or "" when it is.

    The whole-tree digest the row carries is the candidate ON THE BASELINE IT
    WAS WRITTEN ON, and that baseline may legitimately move while the
    candidate waits: the prerequisite a VERIFICATION_PENDING card waits for is
    sometimes Operator-owned (ADR-008, the port of a retained Spring test),
    and an Operator step commits it beside the pending card. So identity is
    checked where it is claimed -- this candidate's OWN paths are the retained
    bytes, the paths it deleted are gone, and no other product path differs
    from the committed tree -- which says the same thing as the digest when
    the baseline did not move, and stays true when it did.

    What the digest could not have told either way: an Operator step that
    changed a file this candidate also holds. Restoring would silently drop
    that change, so it is refused by name."""
    dest = _pending_dir(root, cluster)
    own = set(str(p) for p in (list(row.get("changed") or []) + list(row.get("stored") or []) + list(row.get("deleted") or [])))
    base = str(row.get("head_commit") or "")
    if base:
        moved = git(root, "diff", "--name-only", base, "HEAD")
        if moved.returncode == 0:
            collided = sorted(set(ln.strip() for ln in moved.stdout.splitlines() if ln.strip()) & own)
            if collided:
                return ("the committed tree moved from %s to %s in %s, which this candidate also holds; restoring it would drop "
                        "that change (rewind the card instead)" % (base[:12], git(root, "rev-parse", "HEAD").stdout.strip()[:12], ", ".join(collided[:3])))
    for rel in row.get("stored") or []:
        src, target = dest / rel, root / rel
        if not src.is_file():
            continue
        if not target.is_file() or target.read_bytes() != src.read_bytes():
            return "%s is not the file this record retained" % rel
    for rel in row.get("deleted") or []:
        if (root / rel).is_file():
            return "%s is back on the tree, and this candidate had deleted it" % rel
    outside = sorted(p for p in product_paths_changed(root) if p not in own)
    if outside:
        return ("the product tree differs from the committed tree outside this candidate's paths: %s"
                % ", ".join(outside[:3]))
    return ""


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
            # not the same tree -- which is only a defect if this candidate is
            # not what the record names; the accepted baseline under it may
            # have moved on purpose (an Operator step beside the pending card)
            drift = _pending_restore_drift(root, cluster, row)
            if drift:
                raise PendingRestoreError(
                    "the restored tree is %s, and the retained candidate was %s: %s" % (got[:12], want[:12], drift))
    return restored


def clear_pending(steps: dict[str, Any], cluster: str, *, why: str) -> None:
    for row in steps.get("pending") or []:
        if isinstance(row, dict) and str(row.get("cluster") or "") == cluster and not row.get("cleared"):
            row["cleared"] = why


# --- the verify count per card -------------------------------------------
# v9 t_d280284d ran run-verify.sh twice with the same seven obligations
# reported, then spent the rest of the hour exploring. The stop rule
# (paved-road-m3) needs a count the worker does not have to keep itself, so
# run-verify.sh records each run for the issued card here and prints it, and
# brief.py renders it as `verify_runs`.
LOOP_VERIFY_RUNS = LOOP_STEPS.parent / "verify-runs.json"


def load_verify_runs(root: Path) -> dict[str, Any]:
    return _json_doc(root, LOOP_VERIFY_RUNS, {"schema": "rhoai3.loop-verify-runs/v1", "runs": []})


def _issued_obligations_reported(root: Path, issued: dict[str, Any], worklist: dict[str, Any] | None) -> list[str]:
    """The issued card's obligations the CURRENT work list still reports:
    the issued item ids present in the rebuilt list, or -- when the issued
    record names none -- the issued cluster's items as the list has them now."""
    from planner.worklist import item_ids

    wl = worklist if worklist is not None else (load_json(root / WORKLIST) if (root / WORKLIST).is_file() else {})
    if not isinstance(wl, dict):
        return []
    issued_items = [str(i) for i in (issued.get("gate_items") or issued.get("items") or [])]
    if issued_items:
        present = set(item_ids(wl))
        return sorted(i for i in issued_items if i in present)
    cid = str(issued.get("cluster") or "")
    row = next((c for c in (wl.get("clusters") or []) if isinstance(c, dict) and str(c.get("id") or "") == cid), None)
    return sorted(str(i) for i in (row.get("items") or [])) if row else []


def record_verify_run(root: Path, *, mode: str, worklist: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append this run-verify.sh run for the issued card and return
    ``verify_runs_for`` plus ``line`` (what run-verify.sh prints). Nothing is
    recorded without an issued card (an Operator re-measure is not a card's run)."""
    issued = load_issued(root) or {}
    card = str(issued.get("task_id") or "")
    if not card:
        return {"card": "", "count": 0, "line": ""}
    run_p = root / VERIFY_RUN
    candidate = ""
    if run_p.is_file():
        try:
            candidate = str((load_json(run_p) or {}).get("candidate_sha256") or "")
        except (OSError, ValueError):
            candidate = ""
    reported = _issued_obligations_reported(root, issued, worklist)
    doc = load_verify_runs(root)
    runs = [r for r in (doc.get("runs") or []) if isinstance(r, dict) and str(r.get("card") or "") == card]
    doc.setdefault("runs", []).append({
        "card": card, "cluster": str(issued.get("cluster") or ""), "n": len(runs) + 1, "mode": mode,
        "candidate_sha256": candidate, "obligations_reported": reported,
        "unchanged": bool(runs) and reported == list(runs[-1].get("obligations_reported") or []),
    })
    write_canonical(root / LOOP_VERIFY_RUNS, doc)
    out = verify_runs_for(root, card)
    out["line"] = verify_runs_line(out)
    return out


def verify_runs_for(root: Path, card: str) -> dict[str, Any]:
    """The verify count for one card and what the stop rule needs: the
    obligations the last run still reported, whether they are the same as the
    run before, and whether the rule applies (two ACCEPTANCE runs, the same
    non-empty obligations reported after both)."""
    runs = [r for r in (load_verify_runs(root).get("runs") or []) if isinstance(r, dict) and str(r.get("card") or "") == card] if card else []
    acceptance = [r for r in runs if str(r.get("mode") or "") == "acceptance"]
    last = acceptance[-1] if acceptance else (runs[-1] if runs else {})
    reported = [str(x) for x in (last.get("obligations_reported") or [])]
    unchanged = len(acceptance) >= 2 and reported == [str(x) for x in (acceptance[-2].get("obligations_reported") or [])]
    return {
        "card": card, "count": len(runs), "acceptance_count": len(acceptance),
        "obligations_reported": reported, "unchanged_since_previous": unchanged,
        "stop_rule_applies": unchanged and bool(reported),
        "runs": [{"n": r.get("n"), "mode": r.get("mode"), "obligations_reported": list(r.get("obligations_reported") or [])} for r in runs],
    }


def verify_runs_line(vr: dict[str, Any]) -> str:
    """One line for the worker, printed by run-verify.sh; nothing without a card or a run."""
    if not vr.get("card") or not int(vr.get("count") or 0):
        return ""
    rep = vr.get("obligations_reported") or []
    line = "verify runs on card %s: %d (%d acceptance); obligations of the issued card still reported: %s%s" % (
        vr["card"], int(vr.get("count") or 0), int(vr.get("acceptance_count") or 0),
        (", ".join(rep) if rep else "none"),
        (" (unchanged since the previous acceptance run)" if vr.get("unchanged_since_previous") else ""))
    if vr.get("stop_rule_applies"):
        line += (". STOP RULE APPLIES: two acceptance runs left the same obligations reported. Do not run a third verify "
                 "without a new edit and never start a server to explore: write the typed diagnosis (what you changed, what "
                 "each verify measured, the one hypothesis you could not test and the evidence that would test it) and "
                 "kanban_block kind=needs_input carrying it.")
    return line
