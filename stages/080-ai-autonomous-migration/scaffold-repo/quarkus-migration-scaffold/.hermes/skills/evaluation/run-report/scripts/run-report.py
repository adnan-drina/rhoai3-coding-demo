#!/usr/bin/env python3
"""Run report: what one destination's record says about how its run went.

Reads ONLY what the destination already records (the loop journal, the
planning seals, the bootstrap receipt, the build/parity/M4 receipts, the
harness install manifests, the destination's git history) plus, when given,
the Hermes board export (``hermes kanban list --json``), the per-card worker
logs, a copy of the live Hermes configuration, a declared run budget and the
reports of other runs to compare with. Writes
``evidence/reports/run-report.json`` (schema ``rhoai3.run-report/v1``) and a
short markdown rendering to stdout. It runs nothing, mints nothing and edits
nothing else.

Every reported value is a ``{"value", "source"}`` pair; an unknown value is
``null`` with a ``reason``. Nothing is guessed: a time the record does not
carry stays null, and the reason says which record would have carried it. A
milestone the record shows was never reached is ``"unreached"``, which is a
claim, so it is only made when the records that would show it are present.

The clock starts before bootstrap (ADR-019 §4): at the earliest of the
destination's first commit and the M1 dispatch, so bootstrap and dispatch time
are inside it; harness installs before that are prior preparation, reported
apart.

Classification (ADR-018, ADR-019):

  autonomous                                    no live intervention, and the
                                                bootstrap receipt records no
                                                decided repair
  autonomous_execution_with_predecided_repairs  no live intervention, and the
                                                bootstrap applied decided repairs
  assisted-by-decision                          every operator step applies an
                                                ACCEPTED ADR and names a reviewer;
                                                no rewind, no disposition
  assisted                                      anything else (reasons listed)

Live interventions are operator steps, rewinds and dispositions. Prior
assistance (decided bootstrap repairs) is reported beside the class and is
never reported as zero when no bootstrap receipt was read. Harness installs
are harness changes, reported separately; they do not change the class.

  python3 run-report.py --root /projects/modernized \
      [--out FILE] [--kanban-json FILE] [--kanban-logs DIR] [--git-log FILE] \
      [--hermes-config FILE ...] [--budget FILE] [--compare [LABEL=]REPORT ...]

``--git-log`` replaces ``git log`` with a file of ``<sha> <epoch> <subject>``
lines (``git log --format='%H %ct %s'``), for a replica that has no history.

Exit 0 written; 2 usage (no such root, unreadable board export or comparison).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "rhoai3.run-report/v1"
VERSION = "1.1.0"
OUT_REL = Path("evidence") / "reports" / "run-report.json"

STEPS = "verification/loop/steps.json"
STATE = "verification/loop/state.json"
ISSUED = "verification/loop/issued.json"
DEFERRED = "verification/loop/deferred.json"
BLOCKERS = "verification/loop/release-blockers.json"
FREEZE = "evidence/producers/freeze.json"
BUILD = "evidence/producers/build.json"
BOOTSTRAP = "evidence/producers/bootstrap.json"
SOURCE_MANIFEST = "evidence/frozen/source-manifest.json"
BUNDLE = "evidence/planning/evidence-bundle.json"
ADMISSION = "evidence/planning/admission-receipt.json"
WORKLIST = "evidence/planning/worklist.json"
BATCH_SCOPE = "evidence/planning/batch-scope"
MINTS = "evidence/receipts/k4/mints.json"
DECISIONS = "decisions.yaml"
PINS = ".hermes/pins.json"
MAVEN_CONFIG = ".mvn/maven.config"
RUN = "verification/build/run.json"
PACKAGE = "verification/build/package.json"
BOOT = "verification/build/boot.json"
M4_VERDICT = "evidence/verdicts/m4-verdict.json"
COVERAGE = "evidence/verdicts/coverage-account.json"
GENERATED = "evidence/tests/generated-manifest.json"
INSTALLS = "evidence/harness/install-manifest-*.json"
CORPUS = "verification/scenarios/corpus.json"
PARITY_DIR = "verification/parity"
ORACLES_DIR = "verification/source-oracles"
# the decided repairs the bootstrap applied (ADR-019 §2/§3): one row per
# transformation, bound by the bootstrap receipt's decided_repairs.receipt_sha256
DECIDED_REPAIRS = "evidence/producers/decided-repairs.json"
DECIDED_REPAIRS_SCHEMA = "rhoai3.decided-repairs-receipt/v1"
APPLIED = ("applied", "already-applied")
# the live configuration a Managed Scope may leave inside the tree
CONFIG_CANDIDATES = (".hermes/home/config.yaml",)
CONFIG_PROFILE_GLOB = ".hermes/home/profiles/*/config.yaml"
CONFIG_TEMPLATE = ".hermes/config/config.yaml.template"
MODEL_KEYS = ("provider", "model", "default", "api_mode", "model_override", "provider_override")
INFERENCE_KEYS = ("context_length", "max_tokens", "max_output_tokens", "temperature", "top_p", "top_k", "reasoning_effort",
                  "stale_timeout_seconds", "timeout", "request_timeout", "max_turns", "max_iterations")
CONCURRENCY_KEYS = ("max_in_progress", "failure_limit", "dispatch_interval_seconds", "max_concurrent", "concurrency",
                    "max_workers", "max_parallel", "parallelism")
SECRET_KEYS = ("api_key", "key", "secret", "password", "token", "authorization", "credentials")
BUDGET_CANDIDATES = ("run-budget.json", "run-budget.yaml", "evidence/run/budget.json", "evidence/run/budget.yaml",
                     "verification/run-budget.json")
COMPARATOR_SCRIPTS = (".hermes/skills/gates/capture-source-oracles/scripts/compare-scenario-parity.py",
                      ".hermes/skills/gates/capture-source-oracles/scripts/compare-runtime-parity.py",
                      ".hermes/skills/gates/capture-source-oracles/scripts/compose-parity-receipt.py",
                      ".hermes/skills/gates/capture-source-oracles/scripts/_scenarios.py",
                      ".hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py",
                      ".hermes/skills/gates/generate-product-tests/scripts/generate-product-tests.py")
# where the latest test reports are: the M4 snapshot first (it survives a
# rebuild), then the live Maven output
REPORT_DIRS = ("evidence/m4-pre-rebuild/test-reports", "target/surefire-reports", "target/failsafe-reports")
PASSING_M4 = ("PROVISIONAL_ACCEPT", "ACCEPT", "SHIP", "PASS")
UNREACHED = "unreached"

SUBJECT_BASELINE = re.compile(r"^fix-until-green: baseline\b")
SUBJECT_OPERATOR = re.compile(r"^fix-until-green: operator step by (\S+?) \(([^)]*)\)")
SUBJECT_LOOP = re.compile(r"^fix-until-green: (\S+) attempt (\d+)\b")
SUBJECT_INSTALL = re.compile(r"^harness: install golden ([0-9a-f]+) \(project ([0-9a-f]+)\) over ([0-9a-f]+)")
SUBJECT_HARNESS = re.compile(r"^harness: ")
SUBJECT_M4 = re.compile(r"^m4: ")
K1_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.S)
LOG_TOOL_TIME = re.compile(r"┊.*?\s(\d+(?:\.\d+)?)s(?:\s+\[exit \d+\])?\s*$")
EXIT_RE = re.compile(r"\[exit (\d+)\]")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def V(value: Any, source: Any, reason: str = "") -> Dict[str, Any]:
    """A reported value with where it came from; unknown is null + reason."""
    out = {"value": value, "source": source}
    if value is None:
        out["reason"] = reason or "not recorded"
    elif reason:
        out["note"] = reason
    return out


def U(reason: str, source: Any = None) -> Dict[str, Any]:
    return V(None, source, reason)


class Tree:
    """Read-only access to the destination."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel

    def rel(self, p: Any) -> str:
        return os.path.relpath(str(p), str(self.root))

    def json(self, rel: str) -> Tuple[Any, str]:
        """(document, why-not). why-not is "" when the document loaded."""
        p = self.path(rel)
        if not p.is_file():
            return None, "%s is absent" % rel
        try:
            return json.loads(p.read_text(encoding="utf-8")), ""
        except (OSError, ValueError) as exc:
            return None, "%s is unreadable: %s" % (rel, exc)

    def glob(self, pattern: str) -> List[str]:
        return sorted(self.rel(p) for p in glob.glob(str(self.path(pattern)), recursive=True) if os.path.isfile(p))

    def sha256(self, rel: str) -> Optional[str]:
        p = self.path(rel)
        return sha256_path(p) if p.is_file() else None


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canon_digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def iso(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return _dt.datetime.fromtimestamp(float(epoch), _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(raw: Any) -> Optional[float]:
    """ISO-8601 Z or compact 20260916T162907Z → epoch; anything else None."""
    s = str(raw or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return _dt.datetime.strptime(s, fmt).replace(tzinfo=_dt.timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def span(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    sign = "-" if seconds < 0 else "+"
    s = int(abs(seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    return "%s%s%dh%02dm" % (sign, ("%dd" % d) if d else "", h, m)


class Clock:
    """Offsets from the run's start and from the bootstrap baseline."""

    def __init__(self) -> None:
        self.start: Optional[float] = None
        self.baseline: Optional[float] = None

    def stamp(self, entry: Dict[str, Any], epoch: Optional[float]) -> Dict[str, Any]:
        entry["since_start"] = span(epoch - self.start) if (epoch is not None and self.start is not None) else None
        entry["since_baseline"] = span(epoch - self.baseline) if (epoch is not None and self.baseline is not None) else None
        entry["seconds_since_start"] = int(epoch - self.start) if (epoch is not None and self.start is not None) else None
        return entry


def head(text: Any, limit: int = 160) -> str:
    """The first sentence of a reason, bounded."""
    s = " ".join(str(text or "").split())
    for sep in (". ", "; "):
        i = s.find(sep)
        if 0 < i < limit:
            return s[: i + 1].rstrip(";")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def as_list(x: Any) -> List[Any]:
    return list(x) if isinstance(x, list) else []


def as_dict(x: Any) -> Dict[str, Any]:
    return dict(x) if isinstance(x, dict) else {}


def load_yaml_path(p: Path) -> Tuple[Any, str]:
    """A YAML file through PyYAML when importable, else the harness's strict
    loader (no schema gate: a report reads what is there, it does not admit it)."""
    if not p.is_file():
        return None, "%s is absent" % p.name
    try:
        import yaml  # type: ignore
        with p.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except ImportError:
        try:
            from planner.yamlite import load_yaml as _load  # type: ignore
        except ImportError as exc:
            return None, "no YAML loader is importable: %s" % exc
        try:
            doc = _load(p)
        except Exception as exc:  # noqa: BLE001 - any parse refusal is a reason
            return None, "%s did not parse: %s" % (p.name, exc)
    except Exception as exc:  # noqa: BLE001
        return None, "%s did not parse: %s" % (p.name, exc)
    return (doc, "") if isinstance(doc, dict) else (None, "%s is not a mapping" % p.name)


def load_doc(p: Path) -> Tuple[Any, str]:
    if p.suffix in (".yaml", ".yml"):
        return load_yaml_path(p)
    if not p.is_file():
        return None, "%s is absent" % p
    try:
        return json.loads(p.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return None, "%s is unreadable: %s" % (p, exc)


def load_decisions(tree: Tree) -> Tuple[Any, str]:
    doc, why = load_yaml_path(tree.path(DECISIONS))
    return doc, (why.replace("decisions.yaml is absent", "%s is absent" % DECISIONS) if why else "")


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return


# --------------------------------------------------------------------------
# git history
# --------------------------------------------------------------------------

class History:
    def __init__(self, rows: List[Dict[str, Any]], source: str, reason: str = "") -> None:
        self.rows = rows            # newest first, as git prints them
        self.source = source
        self.reason = reason
        self.by_sha = {r["sha"]: r for r in rows}

    @property
    def known(self) -> bool:
        return bool(self.rows)

    def find(self, sha: Any) -> Optional[Dict[str, Any]]:
        s = str(sha or "")
        if not s:
            return None
        if s in self.by_sha:
            return self.by_sha[s]
        hits = [r for r in self.rows if r["sha"].startswith(s)] if len(s) >= 7 else []
        return hits[0] if len(hits) == 1 else None

    def time_of(self, sha: Any) -> Dict[str, Any]:
        if not sha:
            return U("the record names no commit")
        if not self.known:
            return U("no git history (%s)" % self.reason, self.source)
        row = self.find(sha)
        if row is None:
            return U("commit %s is not in the history" % str(sha)[:12], self.source)
        return V(iso(row["epoch"]), self.source)


def parse_log_lines(lines: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for line in lines:
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        subject = parts[2] if len(parts) > 2 else ""
        rows.append({"sha": parts[0], "epoch": int(parts[1]), "subject": subject, "class": classify_subject(subject)})
    return rows


def classify_subject(subject: str) -> Dict[str, Any]:
    if SUBJECT_BASELINE.match(subject):
        return {"kind": "baseline"}
    m = SUBJECT_OPERATOR.match(subject)
    if m:
        return {"kind": "operator", "operator": m.group(1), "adr": m.group(2)}
    m = SUBJECT_INSTALL.match(subject)
    if m:
        return {"kind": "harness-install", "golden": m.group(1), "project": m.group(2), "over": m.group(3)}
    if SUBJECT_HARNESS.match(subject):
        return {"kind": "harness-other"}
    m = SUBJECT_LOOP.match(subject)
    if m:
        return {"kind": "loop", "cluster": m.group(1), "attempt": int(m.group(2))}
    if SUBJECT_M4.match(subject):
        return {"kind": "m4"}
    return {"kind": "other"}


def load_history(root: Path, git_log: Optional[Path]) -> History:
    if git_log is not None:
        try:
            lines = git_log.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return History([], str(git_log), "unreadable --git-log: %s" % exc)
        return History(parse_log_lines(lines), "git-log:%s" % git_log.name)
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True, capture_output=True, timeout=30)
        if top.returncode != 0:
            return History([], "git log", "the root is not a git work tree")
        if Path(top.stdout.strip()).resolve() != root.resolve():
            return History([], "git log", "the root is not the top of its git work tree (%s is); refusing an enclosing history" % top.stdout.strip())
        proc = subprocess.run(["git", "-C", str(root), "log", "--format=%H %ct %s"], text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return History([], "git log", "git log did not run: %s" % exc)
    if proc.returncode != 0:
        return History([], "git log", "git log exited %d: %s" % (proc.returncode, head(proc.stderr, 120)))
    return History(parse_log_lines(proc.stdout.splitlines()), "git log")


# --------------------------------------------------------------------------
# board
# --------------------------------------------------------------------------

def load_board(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {"provided": False, "cards": [], "by_id": {}}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else as_list(as_dict(raw).get("tasks") or as_dict(raw).get("items"))
    cards = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        title = str(r.get("title") or "")
        phase = title.split(" ", 1)[0] if title[:2] in ("M1", "M2", "M3", "M4", "M5") else "other"
        k1: Dict[str, Any] = {}
        m = K1_BLOCK.search(str(r.get("body") or ""))
        if m:
            try:
                k1 = as_dict(json.loads(m.group(1)))
            except ValueError:
                k1 = {}
        ident = as_dict(k1.get("identity"))
        cards.append({"id": str(r["id"]), "title": title, "phase": phase, "status": r.get("status"), "assignee": r.get("assignee"),
                      "created_at": r.get("created_at"), "started_at": r.get("started_at"), "completed_at": r.get("completed_at"),
                      "cluster": k1.get("increment_id") or ident.get("increment_id"), "kind": k1.get("increment_kind") or ident.get("increment_kind"),
                      "attempt": k1.get("attempt"), "result": r.get("result"),
                      "model_override": r.get("model_override"), "provider_override": r.get("provider_override"), "max_retries": r.get("max_retries")})
    return {"provided": True, "source": "kanban-json:%s" % path.name, "cards": cards, "by_id": {c["id"]: c for c in cards}}


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def installs(tree: Tree, hist: History, clock: Clock) -> List[Dict[str, Any]]:
    rows = []
    for rel in tree.glob(INSTALLS):
        doc, why = tree.json(rel)
        if not isinstance(doc, dict):
            rows.append({"source": rel, "error": why or "not an object", "_epoch": None})
            continue
        golden = str(doc.get("golden") or doc.get("golden_sha") or "")
        prev = str(doc.get("previous_golden") or doc.get("prev_sha") or "")
        project = str(doc.get("project_commit") or doc.get("project") or "")
        at = parse_time(doc.get("installed_at") or doc.get("generated_at"))
        commit = None
        for r in hist.rows:
            c = r["class"]
            if c["kind"] == "harness-install" and golden.startswith(c["golden"]) and (not prev or prev.startswith(c["over"]) or c["over"].startswith(prev[:8])):
                commit = r
                break
        when = at if at is not None else (commit["epoch"] if commit else None)
        rows.append({
            "golden": golden, "previous_golden": prev, "project_commit": project,
            "installed_at": iso(at), "commit": commit["sha"] if commit else None,
            "commit_at": iso(commit["epoch"]) if commit else None,
            "before_start": (None if when is None or clock.start is None else when < clock.start),
            "after_baseline": (None if when is None or clock.baseline is None else when > clock.baseline),
            "source": rel, "_epoch": when,
        })
    rows.sort(key=lambda r: (r.get("_epoch") is None, r.get("_epoch") or 0))
    return rows


def public(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def pinned_inputs(tree: Tree, hist: History, clock: Clock, decisions: Any, dec_why: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    cands = []
    doc, _ = tree.json(FREEZE)
    if isinstance(doc, dict) and doc.get("source_digest"):
        cands.append((FREEZE, str(doc["source_digest"])))
    doc, _ = tree.json(SOURCE_MANIFEST)
    if isinstance(doc, dict) and doc.get("digest"):
        cands.append((SOURCE_MANIFEST, str(doc["digest"])))
    bundle, _ = tree.json(BUNDLE)
    if isinstance(bundle, dict) and as_dict(bundle.get("source")).get("digest"):
        cands.append((BUNDLE + "#source.digest", str(bundle["source"]["digest"])))
    if cands:
        entry = V(cands[0][1], cands[0][0])
        entry["agrees"] = [s for s, v in cands[1:] if v == cands[0][1]]
        if len({v for _, v in cands}) > 1:
            entry["conflicts"] = [{"source": s, "value": v} for s, v in cands if v != cands[0][1]]
        out["frozen_source_digest"] = entry
    else:
        out["frozen_source_digest"] = U("none of %s, %s, %s carries a source digest" % (FREEZE, SOURCE_MANIFEST, BUNDLE))

    adm, adm_why = tree.json(ADMISSION)
    seals = as_dict(as_dict(adm).get("seals"))
    wl, wl_why = tree.json(WORKLIST)
    if seals.get("evidence_bundle"):
        entry = V(str(seals["evidence_bundle"]), ADMISSION + "#seals.evidence_bundle")
        if isinstance(wl, dict) and wl.get("evidence_bundle_sha256"):
            entry["worklist_agrees"] = str(wl["evidence_bundle_sha256"]) == str(seals["evidence_bundle"])
        out["bundle_digest"] = entry
    elif isinstance(wl, dict) and wl.get("evidence_bundle_sha256"):
        out["bundle_digest"] = V(str(wl["evidence_bundle_sha256"]), WORKLIST + "#evidence_bundle_sha256")
    else:
        out["bundle_digest"] = U("no admission seal (%s) and no work-list binding (%s)" % (adm_why or "no seals.evidence_bundle", wl_why or "no evidence_bundle_sha256"))

    file_sha = tree.sha256(DECISIONS)
    if file_sha is None:
        out["decisions_digest"] = U("%s is absent" % DECISIONS)
    else:
        entry = V(file_sha, DECISIONS + " (sha256 of the file)")
        entry["admission_seal"] = str(seals["decisions_yaml"]) if seals.get("decisions_yaml") else None
        entry["matches_admission_seal"] = (str(seals["decisions_yaml"]) == file_sha) if seals.get("decisions_yaml") else None
        out["decisions_digest"] = entry
    out["pins_digest"] = V(str(seals["pins"]), ADMISSION + "#seals.pins") if seals.get("pins") else U(adm_why or "the admission receipt seals no pins digest", ADMISSION)
    if isinstance(decisions, dict):
        loop = as_dict(decisions.get("loop"))
        for key in ("unit_formation", "runtime_feedback"):
            mode = str(loop.get(key) or "").strip()
            out[key] = V(mode or "off", DECISIONS + "#loop." + key, "" if mode else "loop.%s is not set; absent means off" % key)
        adrs = [a for a in as_list(decisions.get("adrs")) if isinstance(a, dict)]
        out["accepted_adrs"] = V(sorted(str(a.get("id")) for a in adrs if str(a.get("status") or "") == "accepted"), DECISIONS + "#adrs")
    else:
        for key in ("unit_formation", "runtime_feedback", "accepted_adrs"):
            out[key] = U(dec_why, DECISIONS)
    act = as_dict(as_dict(adm).get("activation"))
    out["pilot_run_id"] = V(str(act["pilot_run_id"]), ADMISSION + "#activation.pilot_run_id") if act.get("pilot_run_id") else U(adm_why or "the admission receipt names no pilot run", ADMISSION)
    rows = installs(tree, hist, clock)
    out["installed_goldens"] = V(public(rows), INSTALLS) if rows else U("no %s" % INSTALLS)
    first_prev = next((r.get("previous_golden") for r in rows if r.get("previous_golden")), None)
    out["created_from_golden"] = V(first_prev, rows[0]["source"] + "#previous_golden",
                                   "the golden the earliest recorded install replaced") if first_prev else U("no install manifest names a previous golden", INSTALLS)
    projects = [r["project_commit"] for r in rows if r.get("project_commit")]
    out["project_commits"] = V(projects, INSTALLS + "#project_commit") if projects else U("no install manifest names a project commit")
    return out


def pinned_environment(tree: Tree, decisions: Any, dec_why: str, configs: List[Path], board: Dict[str, Any]) -> Dict[str, Any]:
    """Model/provider, inference, concurrency, toolchain, database/reset,
    corpus, captures and comparators — what the run was measured WITH."""
    out: Dict[str, Any] = {}
    pins, pwhy = tree.json(PINS)
    p = as_dict(as_dict(pins).get("pins"))
    if p:
        compact = {}
        for k, v in sorted(p.items()):
            v = as_dict(v)
            compact[k] = {kk: v[kk] for kk in ("version", "product_version", "build", "artifact_sha256", "digest", "status", "activation") if kk in v}
            if not compact[k] and isinstance(v, dict):
                compact[k] = {kk: vv for kk, vv in v.items() if isinstance(vv, dict) and "digest" in vv} or {"keys": sorted(v)}
        e = V(compact, PINS)
        e["sha256"] = tree.sha256(PINS)
        out["tool_pins"] = e
        agent = as_dict(p.get("hermes_agent"))
        out["hermes_agent"] = V({"version": agent.get("version"), "build": agent.get("build")}, PINS + "#pins.hermes_agent") if agent else U("pins.json names no hermes_agent", PINS)
    else:
        out["tool_pins"] = U(pwhy or "pins.json has no pins", PINS)
        out["hermes_agent"] = U(pwhy or "pins.json has no pins", PINS)

    found: List[Tuple[str, Dict[str, Any]]] = []
    notes = []
    for c in configs:
        doc, why = load_doc(c)
        if isinstance(doc, dict):
            found.append(("hermes-config:%s" % c.name, doc))
        else:
            notes.append(why)
    for rel in list(CONFIG_CANDIDATES) + tree.glob(CONFIG_PROFILE_GLOB):
        if tree.path(rel).is_file():
            doc, why = load_yaml_path(tree.path(rel))
            if isinstance(doc, dict):
                found.append((rel, doc))
            else:
                notes.append(why)
    for name, keys in (("model_provider", MODEL_KEYS), ("inference", INFERENCE_KEYS), ("concurrency", CONCURRENCY_KEYS)):
        vals = {}
        for src, doc in found:
            for path_, v in config_leaves(doc, keys):
                vals["%s#%s" % (src, path_)] = v
        if vals:
            out[name] = V(vals, sorted({k.split("#", 1)[0] for k in vals}))
        else:
            reason = ("no %s key in the given configuration" % name) if found else \
                "the live Hermes configuration is not in the destination tree (Managed Scope owns it); pass --hermes-config"
            out[name] = U(reason + ("; " + "; ".join(notes) if notes else ""))
    if tree.path(CONFIG_TEMPLATE).is_file():
        doc, why = load_yaml_path(tree.path(CONFIG_TEMPLATE))
        tvals = {path_: v for path_, v in config_leaves(doc, CONCURRENCY_KEYS + MODEL_KEYS)} if isinstance(doc, dict) else {}
        out["config_template"] = V(tvals, CONFIG_TEMPLATE, "the golden template, not the live pin") if isinstance(doc, dict) else U(why, CONFIG_TEMPLATE)
    else:
        out["config_template"] = U("%s is absent" % CONFIG_TEMPLATE)
    overrides = sorted({"%s/%s" % (c.get("provider_override") or "-", c.get("model_override") or "-") for c in as_list(board.get("cards"))
                        if c.get("model_override") or c.get("provider_override")})
    out["card_model_overrides"] = V(overrides, board.get("source")) if board.get("provided") else U("not provided (board export)")

    tool: Dict[str, Any] = {}
    b, bwhy = tree.json(BUILD)
    tool["legacy_build"] = V(as_dict(b).get("toolchain"), BUILD + "#toolchain") if as_dict(b).get("toolchain") else U(bwhy or "the build receipt names no toolchain", BUILD)
    pk, kwhy = tree.json(PACKAGE)
    tool["package_argv"] = V(as_list(as_dict(pk).get("argv")), PACKAGE + "#argv") if as_dict(pk).get("argv") else U(kwhy or "package.json records no argv", PACKAGE)
    mc = tree.path(MAVEN_CONFIG)
    tool["maven_config"] = V(mc.read_text(encoding="utf-8").split(), MAVEN_CONFIG) if mc.is_file() else U("%s is absent" % MAVEN_CONFIG)
    out["toolchain"] = tool

    db: Dict[str, Any] = {}
    ds = as_dict(as_dict(decisions).get("datasource"))
    if ds:
        db["datasource"] = V({k: ds.get(k) for k in ("db_kind", "db_version", "instance", "profile", "schema_owner", "reset_procedure", "source_baseline_db_kind") if k in ds}, DECISIONS + "#datasource")
        assets = {}
        for k in ("schema_sql", "seed_sql", "baseline_sql", "reset_sql"):
            if ds.get(k):
                assets[str(ds[k])] = tree.sha256(str(ds[k]))
        db["assets"] = V(assets, "sha256 of the files decisions.datasource names") if assets else U("decisions.datasource names no asset", DECISIONS)
    else:
        db["datasource"] = U(dec_why or "decisions.yaml has no datasource section", DECISIONS)
    bs, _ = tree.json(BOOTSTRAP)
    db["bootstrap_baseline"] = V(as_dict(bs).get("baseline"), BOOTSTRAP + "#baseline") if as_dict(bs).get("baseline") else U("the bootstrap receipt records no baseline data (%s)" % ("absent" if bs is None else "no baseline key"), BOOTSTRAP)
    runs = {}
    for rel in tree.glob(PARITY_DIR + "/_run*.json"):
        d, _ = tree.json(rel)
        if as_dict(d).get("reset_cmd"):
            runs[rel] = str(d["reset_cmd"])
    db["reset_cmd"] = V(runs, PARITY_DIR + "/_run*.json#reset_cmd") if runs else U("no parity run records a reset command")
    out["database"] = db

    corpus: Dict[str, Any] = {}
    cdoc, cwhy = tree.json(CORPUS)
    seen = {}
    for rel in [CORPUS] if cdoc is not None else []:
        seen[rel + " (sha256 of the file)"] = tree.sha256(rel)
    for rel in tree.glob(PARITY_DIR + "/receipt*.json") + tree.glob(PARITY_DIR + "/_run*.json") + [GENERATED]:
        d, _ = tree.json(rel)
        if as_dict(d).get("corpus_sha256"):
            seen[rel + "#corpus_sha256"] = str(d["corpus_sha256"])
    if cdoc is not None or seen:
        e = V(seen, "corpus digests as each record states them")
        e["scenarios"] = len(as_list(as_dict(cdoc).get("scenarios"))) if isinstance(cdoc, dict) else None
        e["approved_by"] = as_dict(cdoc).get("approved_by")
        e["distinct_digests"] = sorted({v for k, v in seen.items() if "#" in k and v})
        corpus["corpus"] = e
    else:
        corpus["corpus"] = U(cwhy)
    caps = {}
    for rel in tree.glob(ORACLES_DIR + "/scenarios*/_capture.json"):
        d, _ = tree.json(rel)
        folder = os.path.dirname(rel)
        caps[folder] = {"sha256": tree.sha256(rel), "security_mode": as_dict(d).get("security_mode"),
                        "at": as_dict(d).get("at") or as_dict(d).get("captured_at"), "corpus_sha256": as_dict(d).get("corpus_sha256"),
                        "files": len(tree.glob(folder + "/*.json"))}
    corpus["captures"] = V(caps, ORACLES_DIR + "/scenarios*/_capture.json") if caps else U("no capture receipt under %s/scenarios*/" % ORACLES_DIR)
    out["corpus_and_captures"] = corpus

    comp = {}
    for rel in COMPARATOR_SCRIPTS:
        sha = tree.sha256(rel)
        if sha:
            comp[rel] = sha
    producers = {}
    for rel in tree.glob(PARITY_DIR + "/receipt*.json") + tree.glob(PARITY_DIR + "/_run*.json"):
        d, _ = tree.json(rel)
        if as_dict(d).get("producer"):
            producers[rel] = d["producer"]
    g, _ = tree.json(GENERATED)
    if isinstance(g, dict):
        producers[GENERATED] = "%s %s" % (g.get("generator"), g.get("generator_version"))
    e = V(comp, "sha256 of the destination's comparator scripts") if comp else U("the destination tree carries none of the comparator scripts")
    e["producers"] = producers
    out["comparators"] = e
    return out


def config_leaves(doc: Any, keys: Tuple[str, ...], prefix: str = "") -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            ks = str(k)
            if ks.lower() in SECRET_KEYS:
                continue
            p = "%s.%s" % (prefix, ks) if prefix else ks
            if isinstance(v, (dict, list)):
                out.extend(config_leaves(v, keys, p))
            elif ks in keys:
                out.append((p, v))
    elif isinstance(doc, list):
        for n, v in enumerate(doc):
            out.extend(config_leaves(v, keys, "%s[%d]" % (prefix, n)))
    return out


def _names(items: Any, keys: Tuple[str, ...]) -> List[str]:
    out = []
    for s in as_list(items):
        if isinstance(s, dict):
            name = next((s.get(k) for k in keys if s.get(k)), None)
            out.append(str(name) if name else json.dumps(s, sort_keys=True))
        elif s:
            out.append(str(s))
    return out


def bootstrap_repairs(tree: Tree, decisions: Any) -> Dict[str, Any]:
    """Decided repairs applied at bootstrap (ADR-019 §2/§3): files and
    symbols, apart from worker repairs and live interventions."""
    out: Dict[str, Any] = {}
    bs, bwhy = tree.json(BOOTSTRAP)
    if isinstance(bs, dict):
        ops: Dict[str, int] = {}
        for ch in as_list(bs.get("changes")):
            op = str(as_dict(ch).get("op") or "?")
            ops[op] = ops.get(op, 0) + 1
        out["mechanical_changes"] = V(ops, BOOTSTRAP + "#changes",
                                      "catalog and decision-driven rewrites the bootstrap always makes, counted by op; not decided repairs")
        out["bootstrap_status"] = V(bs.get("status"), BOOTSTRAP + "#status")
    else:
        out["mechanical_changes"] = U(bwhy, BOOTSTRAP)
        out["bootstrap_status"] = U(bwhy, BOOTSTRAP)
    sec = as_dict(as_dict(decisions).get("decided_repairs"))
    out["decision"] = V({k: sec.get(k) for k in ("adr", "applies", "manifest", "manifest_sha256") if k in sec}, DECISIONS + "#decided_repairs") if sec \
        else U("decisions.yaml decides no repair for bootstrap" if isinstance(decisions, dict) else "decisions.yaml unreadable", DECISIONS)
    rec, rwhy = tree.json(DECIDED_REPAIRS)
    binding = as_dict(as_dict(bs).get("decided_repairs"))
    no_binding = "decided_repairs" not in as_dict(bs) or binding == {"declared": False}
    if not isinstance(rec, dict):
        if isinstance(bs, dict) and isinstance(decisions, dict) and not sec and no_binding and rec is None:
            # nothing was decided for bootstrap and the bootstrap recorded
            # nothing: zero is READ here, from the decision and the receipt
            e = V([], DECISIONS + "#decided_repairs + " + BOOTSTRAP, "decisions.yaml decides no repair for bootstrap and the bootstrap receipt binds none")
            e.update({"applied": 0, "refused": 0, "adrs": []})
            out["decided"] = e
        elif isinstance(bs, dict) and no_binding:
            out["decided"] = U("no bootstrap receipt: %s, and %s carries no decided_repairs binding (bootstrapped before decided repairs existed)" % (rwhy, BOOTSTRAP), DECIDED_REPAIRS)
        else:
            out["decided"] = U("no bootstrap receipt: %s" % (rwhy if isinstance(bs, dict) else "%s; %s" % (bwhy, rwhy)), DECIDED_REPAIRS)
        return out
    rows = []
    inventory = [i for i in as_list(rec.get("inventory")) if isinstance(i, dict)]
    for n, r in enumerate(as_list(rec.get("rows"))):
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id") or "")
        mine = [i for i in inventory if rid and rid in (str(i.get("id") or ""), str(i.get("transformation") or ""), str(i.get("row") or ""))]
        files = set(_names(r.get("files"), ("path",)) + _names(r.get("outputs"), ("path",)) + _names(r.get("changed"), ("path",)))
        files |= {str(i.get("path") or i.get("file")) for i in mine if i.get("path") or i.get("file")}
        symbols = _names(r.get("symbols"), ("fqn", "symbol", "name")) + [str(i.get("symbol") or i.get("fqn")) for i in mine if i.get("symbol") or i.get("fqn")]
        status = str(r.get("status") or "")
        rows.append({"id": rid or None, "adr": r.get("adr"), "status": status or None, "applied": status in APPLIED,
                     "files": sorted(files), "symbols": sorted(set(symbols)),
                     "implementation_version": r.get("implementation_version") or r.get("version"),
                     "refusal": r.get("refusal"), "source": "%s#rows[%d]" % (DECIDED_REPAIRS, n)})
    e = V(rows, DECIDED_REPAIRS, "" if rows else "the receipt records no transformation row")
    e["applied"] = sum(1 for r in rows if r["applied"])
    e["refused"] = sum(1 for r in rows if r["status"] == "refused")
    e["adrs"] = sorted({str(r["adr"]) for r in rows if r["applied"] and r.get("adr")})
    e["schema_ok"] = rec.get("schema") == DECIDED_REPAIRS_SCHEMA
    e["receipt_status"] = rec.get("status")
    e["inventory_rows"] = len(inventory)
    e["manifest_sha256"] = as_dict(rec.get("decision")).get("manifest_sha256")
    e["bound_by_bootstrap"] = (binding.get("receipt_sha256") == tree.sha256(DECIDED_REPAIRS)) if binding else None
    if not binding:
        e["bound_by_bootstrap_reason"] = "%s carries no decided_repairs binding" % BOOTSTRAP
    out["decided"] = e
    return out


def classify_rejected(row: Dict[str, Any]) -> str:
    if str(row.get("kind") or "") == "close":
        return "m4-close"
    if str(row.get("reason") or "").startswith("closed by operator") or (row.get("measure") is None and not row.get("budget") and not row.get("changed")):
        return "closed-without-verdict"
    return "reverted"


def first_step(steps: List[Dict[str, Any]], pred) -> Optional[Tuple[int, Dict[str, Any]]]:
    for i, s in enumerate(steps):
        if pred(s):
            return i, s
    return None


def parity_modes(tree: Tree) -> List[Dict[str, str]]:
    """Every security mode (and fixture variant) the parity road wrote: the
    default mode keeps the unsuffixed names."""
    suffixes = set()
    for rel in tree.glob(PARITY_DIR + "/receipt*.json"):
        suffixes.add(os.path.basename(rel)[len("receipt"):-len(".json")])
    for rel in tree.glob(PARITY_DIR + "/_run*.json"):
        suffixes.add(os.path.basename(rel)[len("_run"):-len(".json")])
    suffixes.add("")
    return [{"mode": (s.lstrip("-") or "default"), "receipt": "%s/receipt%s.json" % (PARITY_DIR, s), "run": "%s/_run%s.json" % (PARITY_DIR, s),
             "scenarios": "%s/scenarios%s" % (PARITY_DIR, s)} for s in sorted(suffixes)]


def timeline(tree: Tree, hist: History, steps_doc: Any, steps_why: str, m4: Dict[str, Any], board: Dict[str, Any], clock: Clock) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    steps = [s for s in as_list(as_dict(steps_doc).get("steps")) if isinstance(s, dict)]

    # the clock: the earliest of the destination's creation and the M1 dispatch
    comps: Dict[str, Any] = {}
    if hist.known:
        root_c = hist.rows[-1]
        comps["destination_created"] = {"at": iso(root_c["epoch"]), "source": hist.source + " (oldest commit)", "subject": root_c["subject"], "_e": root_c["epoch"]}
    for phase in ("M1", "M2"):
        cards = sorted((c for c in as_list(board.get("cards")) if c.get("phase") == phase and c.get("created_at")), key=lambda c: c["created_at"])
        if cards:
            c = cards[0]
            comps["%s_dispatched" % phase.lower()] = {"at": iso(c["created_at"]), "source": "kanban-json#%s.created_at" % c["id"], "_e": float(c["created_at"])}
            if c.get("started_at"):
                comps["%s_started" % phase.lower()] = {"at": iso(c["started_at"]), "source": "kanban-json#%s.started_at" % c["id"], "_e": float(c["started_at"])}
    base = first_step(steps, lambda s: s.get("verdict") == "baseline")
    if base is not None:
        t = hist.time_of(base[1].get("commit"))
        if t["value"] is not None:
            clock.baseline = parse_time(t["value"])
            comps["bootstrap_baseline"] = {"at": t["value"], "source": t["source"], "_e": clock.baseline}
    starts = [(v["_e"], k, v) for k, v in comps.items() if k in ("destination_created", "m1_dispatched")]
    if starts:
        e0, k0, v0 = min(starts)
        clock.start = e0
        entry = V(v0["at"], v0["source"], "the earliest of the destination's first commit and the M1 dispatch: bootstrap and dispatch are inside the clock")
        entry["from"] = k0
    else:
        entry = U("neither a git history (%s) nor a board export with an M1 card is available" % (hist.reason or "empty"))
    entry["components"] = {k: {kk: vv for kk, vv in v.items() if kk != "_e"} for k, v in comps.items()}
    for k, v in entry["components"].items():
        clock.stamp(v, comps[k]["_e"])
    out["clock_start"] = entry

    def at_step(idx_step: Optional[Tuple[int, Dict[str, Any]]], what: str) -> Dict[str, Any]:
        if steps_doc is None:
            return U(steps_why, STEPS)
        if idx_step is None:
            return V(UNREACHED, STEPS, "no step in %s %s" % (STEPS, what))
        i, s = idx_step
        t = hist.time_of(s.get("commit"))
        if t["value"] is None and s.get("at"):
            t = V(s["at"], "%s#steps[%d].at" % (STEPS, i))
        entry = dict(t)
        entry.update({"step": i, "card": s.get("card") or None, "cluster": s.get("cluster"), "commit": s.get("commit"),
                      "record": "%s#steps[%d]" % (STEPS, i)})
        return clock.stamp(entry, parse_time(entry.get("value")))

    out["baseline"] = at_step(base, "is the baseline")
    out["first_accepted_step"] = at_step(first_step(steps, lambda s: s.get("verdict") == "accepted"), "was accepted")
    out["first_zero_measure"] = at_step(first_step(steps, lambda s: as_list(as_dict(s.get("measure")).get("tuple")) and all(x == 0 for x in as_dict(s.get("measure")).get("tuple"))), "reached a [0, 0, 0] measure")

    def pkg_ok(s: Dict[str, Any]) -> bool:
        p = as_dict(as_dict(s.get("runtime")).get("package"))
        return s.get("verdict") == "accepted" and bool(p.get("ran")) and p.get("rc") == 0

    def boot_ok(s: Dict[str, Any]) -> bool:
        b = as_dict(as_dict(s.get("runtime")).get("boot"))
        return s.get("verdict") == "accepted" and bool(b.get("ran")) and bool(b.get("ready"))

    out["first_package_pass"] = at_step(first_step(steps, pkg_ok), "records runtime.package ran with rc 0")
    out["first_boot_pass"] = at_step(first_step(steps, boot_ok), "records runtime.boot ready")

    # full parity compositions: only the latest run per mode is kept on disk
    runs = []
    any_parity = False
    for m in parity_modes(tree):
        doc, _ = tree.json(m["run"])
        rec, _ = tree.json(m["receipt"])
        any_parity = any_parity or doc is not None or rec is not None
        if isinstance(doc, dict):
            full = not as_list(doc.get("scenario_filter")) and str(as_dict(doc.get("binding")).get("mode") or "sealed") != "candidate"
            if full:
                runs.append({"mode": str(doc.get("security_mode") or m["mode"]), "at": doc.get("at"), "ok": doc.get("ok"),
                             "run_receipt_verdict": doc.get("receipt_verdict") or None,
                             "receipt_verdict_on_disk": as_dict(rec).get("verdict"),
                             "receipt_binding_mode": as_dict(as_dict(rec).get("binding")).get("mode"),
                             "failures": [head(f, 140) for f in as_list(doc.get("failures"))][:5], "source": m["run"]})
        if isinstance(rec, dict) and str(as_dict(rec.get("binding")).get("mode") or "") != "candidate" and not any(r["source"] == m["run"] for r in runs):
            # a sealed receipt with no full-run record beside it: its composition time is not recorded
            runs.append({"mode": str(rec.get("security_mode") or m["mode"]), "at": None, "ok": None, "run_receipt_verdict": None,
                         "receipt_verdict_on_disk": rec.get("verdict"), "receipt_binding_mode": as_dict(rec.get("binding")).get("mode"),
                         "failures": [], "source": m["receipt"]})
    runs.sort(key=lambda r: (parse_time(r.get("at")) is None, parse_time(r.get("at")) or 0))
    note = "only the latest full run per security mode is kept on disk; an earlier composition leaves no record here"
    dated = [r for r in runs if r.get("at")]
    if dated:
        e = V(dated[0]["at"], dated[0]["source"] + "#at", note)
        e.update({k: dated[0][k] for k in ("mode", "ok", "run_receipt_verdict", "receipt_verdict_on_disk")})
        out["first_full_parity"] = clock.stamp(e, parse_time(dated[0]["at"]))
    elif any_parity:
        out["first_full_parity"] = V(UNREACHED, PARITY_DIR, "no full (unscoped, sealed) parity run is recorded; " + note)
    else:
        out["first_full_parity"] = U("no parity record under %s" % PARITY_DIR)
    out["full_parity_runs"] = runs
    passing = {}
    for r in runs:
        verdict = r.get("run_receipt_verdict") or r.get("receipt_verdict_on_disk")
        if verdict == "PASS":
            e = V(r.get("at"), r["source"], "" if r.get("at") else "the passing receipt carries no composition time")
            e["mode"] = r["mode"]
            passing[r["mode"]] = clock.stamp(e, parse_time(r.get("at")))
    for r in runs:
        if r["mode"] not in passing:
            passing[r["mode"]] = V(UNREACHED, r["source"], "the full composition on disk is %s; %s" % (r.get("run_receipt_verdict") or r.get("receipt_verdict_on_disk") or "not composed", note))
    if passing:
        out["first_passing_parity"] = passing
    else:
        out["first_passing_parity"] = V(UNREACHED, PARITY_DIR, "no full parity composition is recorded") if any_parity else U("no parity record under %s" % PARITY_DIR)

    rows = [clock.stamp(dict(v), parse_time(v.get("at"))) for v in as_list(m4.get("verdicts"))]
    out["m4_verdicts"] = rows
    m4_known = steps_doc is not None or m4.get("current", {}).get("value") is not None
    dated_rows = [r for r in rows if r.get("at")]
    if dated_rows:
        out["first_m4_verdict"] = dated_rows[0]
    elif rows:
        out["first_m4_verdict"] = dict(rows[0], note="no recorded time")
    else:
        out["first_m4_verdict"] = V(UNREACHED, STEPS, "no M4 verdict is recorded (%s, close rows in %s)" % (M4_VERDICT, STEPS)) if m4_known \
            else U("neither %s nor %s is readable" % (STEPS, M4_VERDICT))
    ok_rows = [r for r in rows if str(r.get("verdict") or "") in PASSING_M4]
    if ok_rows:
        out["first_passing_m4"] = ok_rows[0]
    else:
        out["first_passing_m4"] = V(UNREACHED, M4_VERDICT + " + " + STEPS, "no recorded M4 verdict is one of %s" % ", ".join(PASSING_M4)) if m4_known \
            else U("neither %s nor %s is readable" % (STEPS, M4_VERDICT))

    gen = [r for r in hist.rows if r["class"]["kind"] == "m4"]
    out["m4_commits"] = [clock.stamp({"commit": r["sha"], "at": iso(r["epoch"]), "subject": r["subject"]}, r["epoch"]) for r in reversed(gen)]
    last = []
    if hist.known:
        last.append((hist.rows[0]["epoch"], hist.source, hist.rows[0]["subject"]))
    for c in as_list(board.get("cards")):
        if c.get("completed_at"):
            last.append((float(c["completed_at"]), "kanban-json#%s.completed_at" % c["id"], c["title"]))
    if last:
        e, src, subj = max(last)
        out["last_event"] = clock.stamp(V(iso(e), src), e)
        out["last_event"]["subject"] = subj
    else:
        out["last_event"] = U("no git history (%s) and no board export" % hist.reason, hist.source)
    return out


def m4_verdicts(tree: Tree, steps_doc: Any, board: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    closes = [(i, r) for i, r in enumerate(as_list(as_dict(steps_doc).get("rejected"))) if isinstance(r, dict) and str(r.get("kind") or "") == "close"]
    seen = set()
    for i, r in closes:
        seen.add(str(r.get("card") or ""))
        rows.append({"card": r.get("card"), "verdict": r.get("verdict"), "at": r.get("at"), "failed_floors": as_list(r.get("failed_floors")),
                     "resumed": r.get("resumed"), "resumed_by": r.get("operator"), "time_source": "%s#rejected[%d].at" % (STEPS, i),
                     "source": "%s#rejected[%d]" % (STEPS, i)})
    cur, why = tree.json(M4_VERDICT)
    if isinstance(cur, dict):
        card = str(cur.get("card_id") or "")
        current = V(cur.get("verdict"), M4_VERDICT)
        current.update({"card": card or None, "failed_floors": as_list(cur.get("failed_floors")), "ship": cur.get("ship"),
                        "floors": [{"name": f.get("name"), "rc": f.get("rc")} for f in as_list(cur.get("floors")) if isinstance(f, dict)],
                        "coverage_account": cur.get("coverage_account")})
        if card and card not in seen:
            bc = as_dict(board.get("by_id")).get(card)
            at = iso(bc.get("completed_at")) if bc and bc.get("completed_at") else None
            rows.append({"card": card, "verdict": cur.get("verdict"), "at": at, "failed_floors": as_list(cur.get("failed_floors")),
                         "resumed": False, "time_source": ("kanban-json#%s.completed_at" % card) if at else None,
                         "time_reason": None if at else "m4-verdict.json carries no time and its card has no close row; a board export would give the card's completion",
                         "source": M4_VERDICT})
    else:
        current = U(why, M4_VERDICT)
    for c in as_list(board.get("cards")):
        if str(c.get("phase")) == "M4" and c["id"] not in seen and c["id"] != str(as_dict(cur).get("card_id") or ""):
            rows.append({"card": c["id"], "verdict": None, "at": iso(c.get("completed_at")), "failed_floors": None, "resumed": None,
                         "time_source": "kanban-json#%s.completed_at" % c["id"], "source": "kanban-json",
                         "board_result": head(c.get("result"), 200),
                         "verdict_reason": "the loop record keeps no verdict row for this card; the board's result text is quoted, not parsed"})
    rows.sort(key=lambda r: (r.get("at") is None, r.get("at") or ""))
    return {"verdicts": rows, "current": current}


def verification_rows(steps_doc: Any) -> List[Dict[str, Any]]:
    rows = []
    sd = as_dict(steps_doc)
    for key in ("steps", "rejected"):
        for i, r in enumerate(as_list(sd.get(key))):
            v = as_dict(as_dict(r).get("verify"))
            if v.get("total_ms") is not None:
                rows.append({"mode": v.get("mode"), "total_ms": v.get("total_ms"), "stages_ms": as_dict(v.get("stages_ms")), "source": "%s#%s[%d].verify" % (STEPS, key, i)})
    for i, r in enumerate(as_list(sd.get("pending"))):
        r = as_dict(r)
        if r.get("total_ms") is not None:
            rows.append({"mode": r.get("run_mode"), "total_ms": r.get("total_ms"), "stages_ms": as_dict(r.get("stages_ms")), "source": "%s#pending[%d]" % (STEPS, i)})
    return rows


def _stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    v = sorted(values)
    mid = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
    return {"n": len(v), "total_s": int(sum(v)), "median_s": int(mid), "max_s": int(v[-1])}


def union_seconds(intervals: List[Tuple[float, float]]) -> float:
    total = 0.0
    cur_s = cur_e = None
    for s, e in sorted(i for i in intervals if i[1] >= i[0]):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def cost(tree: Tree, steps_doc: Any, steps_why: str, board: Dict[str, Any], logs: Optional[Path], clock: Clock, last_event: Dict[str, Any]) -> Dict[str, Any]:
    """Cache conditions, verification counts and time, and where the wall time went."""
    out: Dict[str, Any] = {}
    rows = verification_rows(steps_doc)
    if steps_doc is None:
        out["verifications"] = U(steps_why, STEPS)
    else:
        stages: Dict[str, int] = {}
        modes: Dict[str, int] = {}
        for r in rows:
            modes[str(r["mode"])] = modes.get(str(r["mode"]), 0) + 1
            for k, v in r["stages_ms"].items():
                if isinstance(v, (int, float)):
                    stages[k] = stages.get(k, 0) + int(v)
        warm = [float(r["stages_ms"]["warmup"]) / 1000.0 for r in rows if isinstance(r["stages_ms"].get("warmup"), (int, float))]
        e = V({"count": len(rows), "total_s": int(sum(float(r["total_ms"]) for r in rows) / 1000), "by_mode": modes,
               "stage_totals_s": {k: v // 1000 for k, v in sorted(stages.items())}}, STEPS + " (verify records of accepted, rejected and pending rows)",
              "verifications whose record was discarded (a refusal with no row) are not counted")
        e["warmup_seconds"] = _stats(warm)
        out["verifications"] = e
    run, rwhy = tree.json(RUN)
    out["cache"] = V({"warmup": as_dict(run).get("warmup"), "classpath": as_dict(run).get("classpath")}, RUN) if isinstance(run, dict) else U(rwhy, RUN)
    mc = tree.path(MAVEN_CONFIG)
    out["cache"]["maven_config"] = mc.read_text(encoding="utf-8").split() if mc.is_file() else None

    t: Dict[str, Any] = {}
    end = parse_time(last_event.get("value"))
    t["wall_seconds"] = V(int(end - clock.start), "clock_start → last_event") if (end is not None and clock.start is not None) else U("the clock start or the last event is unknown")
    if board.get("provided"):
        runs = [(float(c["started_at"]), float(c["completed_at"])) for c in board["cards"] if c.get("started_at") and c.get("completed_at")]
        queue = [float(c["started_at"]) - float(c["created_at"]) for c in board["cards"] if c.get("started_at") and c.get("created_at")]
        t["card_run_seconds"] = V({"sum": int(sum(e - s for s, e in runs)), "union": int(union_seconds(runs)), "cards": len(runs)}, board["source"])
        t["queue_seconds"] = V({"sum": int(sum(queue)), "cards": len(queue)}, board["source"], "created → started per card; a child card is created before its parent completes")
        if t["wall_seconds"]["value"] is not None:
            t["outside_card_runs_seconds"] = V(int(t["wall_seconds"]["value"] - union_seconds(runs)), "wall − union of card runs",
                                               "time with no card running: dispatch gaps, queueing, operator work, waiting")
    else:
        t["card_run_seconds"] = U("not provided (board export)")
        t["queue_seconds"] = U("not provided (board export)")
    t["verification_seconds"] = V(out["verifications"]["value"]["total_s"], STEPS) if as_dict(out["verifications"]).get("value") else U(steps_why or "no verification record", STEPS)
    tool_s = None
    if logs is not None and logs.is_dir():
        tool_s = 0.0
        for f in sorted(logs.glob("*.log")):
            try:
                for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    m = LOG_TOOL_TIME.search(line)
                    if m:
                        tool_s += float(m.group(1))
            except OSError:
                continue
        t["tool_seconds"] = V(int(tool_s), "kanban-logs:%s/*.log (per-tool durations)" % logs.name)
    else:
        t["tool_seconds"] = U("not provided (worker logs)")
    t["provider_seconds"] = U("no provider or model latency is recorded in the destination, the board export or the tool-duration lines of the logs")
    if tool_s is not None and board.get("provided"):
        t["unattributed_in_card_runs_seconds"] = V(int(t["card_run_seconds"]["value"]["sum"] - tool_s), "card run sum − tool time",
                                                   "model/provider time, turn overhead and anything the logs do not time")
    else:
        t["unattributed_in_card_runs_seconds"] = U("needs both the board export and the worker logs")
    out["time"] = t
    return out


def loop_work(tree: Tree, steps_doc: Any, steps_why: str, board: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(steps_doc, dict):
        return {"record": U(steps_why, STEPS)}
    steps = [s for s in as_list(steps_doc.get("steps")) if isinstance(s, dict)]
    rejected = [r for r in as_list(steps_doc.get("rejected")) if isinstance(r, dict)]
    pending = [r for r in as_list(steps_doc.get("pending")) if isinstance(r, dict)]
    issued, _ = tree.json(ISSUED)
    issued = as_dict(issued)
    out: Dict[str, Any] = {}

    accepted = [s for s in steps if s.get("verdict") == "accepted"]
    classes: Dict[str, List[Dict[str, Any]]] = {"reverted": [], "closed-without-verdict": [], "m4-close": []}
    for r in rejected:
        classes[classify_rejected(r)].append(r)
    record_cards = set()
    for r in steps + rejected + pending:
        if r.get("card"):
            record_cards.add(str(r["card"]))
    if issued.get("task_id"):
        record_cards.add(str(issued["task_id"]))
    mints, mints_why = tree.json(MINTS)
    minted_ids = sorted({str(c.get("task_id")) for m in as_list(as_dict(mints).get("mints")) for c in as_list(as_dict(m).get("created")) if isinstance(c, dict) and c.get("task_id")})
    cards: Dict[str, Any] = {}
    if minted_ids:
        cards["minted"] = V(len(minted_ids), MINTS)
    elif board.get("provided"):
        n = sum(1 for c in board["cards"] if c.get("phase") in ("M3", "M4"))
        cards["minted"] = V(n, "kanban-json (M3/M4 titles)", "%s: %s" % (MINTS, mints_why or "no created cards"))
    else:
        cards["minted"] = U("%s: %s; no board export given" % (MINTS, mints_why or "no created cards"), MINTS)
    cards["in_loop_record"] = V(len(record_cards), STEPS + " (+ issued.json)")
    cards["accepted"] = V(len(accepted), STEPS + "#steps[verdict=accepted]")
    cards["reverted"] = V(len(classes["reverted"]), STEPS + "#rejected (attempt rows)")
    cards["reverted_then_rewound"] = V(sum(1 for r in classes["reverted"] if r.get("rewound")), STEPS + "#rejected[rewound]")
    cards["closed_without_verdict"] = V([{"card": r.get("card"), "cluster": r.get("cluster")} for r in classes["closed-without-verdict"]], STEPS + "#rejected")
    cards["m4_closed"] = V(len(classes["m4-close"]), STEPS + "#rejected[kind=close]")
    open_p = [r for r in pending if not r.get("cleared") and not r.get("rewound")]
    causes: Dict[str, int] = {}
    for r in pending:
        causes[str(r.get("cause") or "")] = causes.get(str(r.get("cause") or ""), 0) + 1
    cards["pending"] = V({"rows": len(pending), "open": [{"card": r.get("card"), "cluster": r.get("cluster"), "cause": r.get("cause")} for r in open_p],
                          "cleared": {k: sum(1 for r in pending if r.get("cleared") == k) for k in sorted({str(r.get("cleared")) for r in pending if r.get("cleared")})},
                          "rewound": sum(1 for r in pending if r.get("rewound") and not r.get("cleared")), "causes": causes}, STEPS + "#pending")
    deferred, dwhy = tree.json(DEFERRED)
    clearances = [c for c in as_list(steps_doc.get("deferral_clearances")) if isinstance(c, dict)]
    cards["deferred"] = V({"open": as_list(as_dict(deferred).get("clusters")),
                           "deferred_then_cleared": [{"cluster": c.get("cluster"), "because": head(c.get("was_deferred_because"), 140)} for c in clearances if c.get("was_deferred_because")]},
                          DEFERRED + " + " + STEPS + "#deferral_clearances",
                          "" if deferred is not None else dwhy)
    cards["issued_now"] = V({"cluster": issued.get("cluster"), "card": issued.get("task_id"), "attempt": issued.get("attempt"), "kind": issued.get("kind")} if issued else None,
                            ISSUED, "no card is issued (%s absent)" % ISSUED)
    out["cards"] = cards

    per: Dict[str, Dict[str, Any]] = {}
    for s in accepted:
        e = per.setdefault(str(s.get("cluster")), {"accepted": 0, "reverted": 0, "max_attempt": 0, "cards": []})
        e["accepted"] += 1
        e["max_attempt"] = max(e["max_attempt"], int(s.get("attempt") or 0))
        e["cards"].append(s.get("card"))
    for r in classes["reverted"]:
        e = per.setdefault(str(r.get("cluster")), {"accepted": 0, "reverted": 0, "max_attempt": 0, "cards": []})
        e["reverted"] += 1
        e["max_attempt"] = max(e["max_attempt"], int(as_dict(r.get("budget")).get("spent") or 0))
        e["cards"].append(r.get("card"))
    out["attempts_per_cluster"] = V(per, STEPS + " (accepted steps + attempt rows)")
    out["attempt_counters_now"] = V(as_dict(steps_doc.get("attempts")), STEPS + "#attempts")
    deferrals = len([c for c in clearances if c.get("was_deferred_because")]) + len(as_list(as_dict(deferred).get("clusters")))
    out["retries"] = V(max(0, len(classes["reverted"]) - deferrals), STEPS,
                       "reverted attempts that re-issued their cluster: %d reverted minus %d that reached the threshold and deferred" % (len(classes["reverted"]), deferrals))

    amend = []
    revis = []
    for s in accepted:
        amend += [dict(a, card=s.get("card")) for a in as_list(s.get("amendments")) if isinstance(a, dict)]
        revis += [dict(a, card=s.get("card")) for a in as_list(s.get("revisions")) if isinstance(a, dict)]
    for src in [issued] + [as_dict(p.get("issued")) for p in pending]:
        amend += [dict(a, card=src.get("task_id")) for a in as_list(src.get("amendments")) if isinstance(a, dict)]
        revis += [dict(a, card=src.get("task_id")) for a in as_list(src.get("revisions")) if isinstance(a, dict)]
    out["scope_amendments"] = V(len(amend), STEPS + "#steps[].amendments + issued/pending")
    out["scope_revisions"] = V([{"card": r.get("card"), "path": r.get("path"), "evidence": r.get("evidence")} for r in revis], STEPS + "#steps[].revisions + issued/pending")

    seals = []
    schemas: Dict[str, int] = {}
    for rel in tree.glob(BATCH_SCOPE + "/**/*.json"):
        doc, _ = tree.json(rel)
        if not isinstance(doc, dict):
            continue
        sch = str(doc.get("schema") or "")
        schemas[sch] = schemas.get(sch, 0) + 1
        if sch == "rhoai3.batch-scope/v4":
            b = as_dict(doc.get("bounds"))
            seals.append({"cluster": doc.get("cluster"), "unit_id": doc.get("unit_id"), "rule": doc.get("rule"),
                          "files": b.get("files", len(as_list(doc.get("writable_paths")))), "sites": b.get("sites"),
                          "symbols": b.get("symbols", len(as_list(doc.get("symbols")))), "narrowed": bool(b.get("narrowed")), "source": rel})
    out["batch_scopes"] = V(schemas, BATCH_SCOPE + "/**") if schemas else U("no sealed batch-scope inventory under %s" % BATCH_SCOPE)
    out["unit_sizes"] = V(seals, BATCH_SCOPE + "/** (rhoai3.batch-scope/v4)") if seals else U("no rhoai3.batch-scope/v4 seal under %s" % BATCH_SCOPE)
    out["unit_steps_accepted"] = V(sum(1 for s in accepted if as_dict(s.get("unit")).get("unit_id")), STEPS + "#steps[].unit")

    # A kind belongs to a CARD: a cluster id can be re-issued under another
    # kind once its obligation changes (a compile cluster whose file later
    # carries a package, boot or parity obligation keeps its id).
    card_kind: Dict[str, Tuple[str, str]] = {}
    ksrc = []
    for c in as_list(board.get("cards")):
        if c.get("cluster") and c.get("kind"):
            card_kind[c["id"]] = (str(c["cluster"]), str(c["kind"]))
    if card_kind:
        ksrc.append("kanban-json (K1 increment_kind)")
    for src, doc in [(ISSUED, issued)] + [("%s#pending" % STEPS, as_dict(p.get("issued"))) for p in pending]:
        key = str(doc.get("task_id") or "") or "issued:%s:%s" % (doc.get("cluster"), doc.get("attempt"))
        if doc.get("cluster") and doc.get("kind") and key not in card_kind:
            card_kind[key] = (str(doc["cluster"]), str(doc["kind"]))
            if src not in ksrc:
                ksrc.append(src)
    by_kind: Dict[str, List[str]] = {}
    cards_by_kind: Dict[str, int] = {}
    for _, (cid, k) in sorted(card_kind.items()):
        cards_by_kind[k] = cards_by_kind.get(k, 0) + 1
        if cid not in by_kind.setdefault(k, []):
            by_kind[k].append(cid)
    known = {cid for cid, _ in card_kind.values()}
    unknown = sorted({str(s.get("cluster")) for s in accepted} - known)
    entry = V({k: len(v) for k, v in sorted(by_kind.items())}, " + ".join(ksrc) if ksrc else None,
              "" if not unknown else "%d accepted cluster(s) have no recorded kind: the loop record does not carry one; K1 bodies on the board do" % len(unknown))
    if not card_kind:
        entry = U("the loop record does not carry a cluster's kind; pass --kanban-json (K1 increment_kind)", STEPS)
    entry["clusters"] = {k: sorted(v) for k, v in sorted(by_kind.items())}
    entry["cards_by_kind"] = cards_by_kind
    entry["unknown_kind"] = unknown
    entry["clusters_with_several_kinds"] = sorted(c for c in known if sum(1 for v in by_kind.values() if c in v) > 1)
    out["clusters_by_kind"] = entry
    gates: Dict[str, int] = {}
    for s in accepted:
        g = str(s.get("gate") or "compile/incident/test (no gate)")
        gates[g] = gates.get(g, 0) + 1
    out["accepted_by_gate"] = V(gates, STEPS + "#steps[].gate")
    return out


def interventions(tree: Tree, hist: History, steps_doc: Any, steps_why: str, decisions: Any, dec_why: str, clock: Clock) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    out: Dict[str, Any] = {}
    rows = installs(tree, hist, clock)
    harness: Dict[str, Any] = {
        "prior_preparation": public([r for r in rows if r.get("before_start")]),
        "installs_after_start": public([r for r in rows if r.get("before_start") is False]),
        "installs_undated": [r["source"] for r in rows if r.get("before_start") is None],
    }
    other = [{"commit": r["sha"], "at": iso(r["epoch"]), "subject": r["subject"]} for r in reversed(hist.rows)
             if r["class"]["kind"] == "harness-other" and (clock.start is None or r["epoch"] >= clock.start)]
    harness["other_harness_commits"] = V(other, hist.source) if hist.known else U("no git history (%s)" % hist.reason, hist.source)
    harness["note"] = "harness changes, not application interventions; they do not change the classification"
    if not isinstance(steps_doc, dict):
        out["record"] = U(steps_why, STEPS)
        return out, harness
    accepted_ids = None
    if isinstance(decisions, dict):
        accepted_ids = {str(a.get("id")) for a in as_list(decisions.get("adrs")) if isinstance(a, dict) and str(a.get("status") or "") == "accepted"}
    ops = []
    for i, s in enumerate(as_list(steps_doc.get("steps"))):
        if not isinstance(s, dict) or s.get("verdict") != "operator":
            continue
        adrs = [a.strip() for a in str(s.get("adr") or "").split(",") if a.strip()]
        applied = None if accepted_ids is None else (bool(adrs) and all(a in accepted_ids for a in adrs))
        t = V(s.get("at"), "%s#steps[%d].at" % (STEPS, i)) if s.get("at") else hist.time_of(s.get("commit"))
        ops.append(clock.stamp({"step": i, "at": t.get("value"), "commit": s.get("commit"), "adr": adrs, "author": s.get("author"),
                                "operator": s.get("operator"), "reviewer": s.get("reviewer") or None,
                                "applies_accepted_adr": applied,
                                "applies_accepted_adr_reason": None if applied is not None else "decisions.yaml unreadable: %s" % dec_why,
                                "beside_pending": s.get("beside_pending"), "cleared_deferred": as_list(s.get("cleared_deferred")),
                                "changed": as_list(s.get("changed")), "reason_head": head(s.get("reason")),
                                "source": "%s#steps[%d]" % (STEPS, i)}, parse_time(t.get("value"))))
    out["operator_steps"] = ops
    rw = []
    for i, r in enumerate(as_list(steps_doc.get("rewinds"))):
        if isinstance(r, dict):
            rw.append(clock.stamp({"at": r.get("at"), "operator": r.get("operator"), "closed_cards": as_list(r.get("closed_cards")),
                                   "moved_steps": as_list(r.get("moved_steps")), "to_step": r.get("to_step"), "to_commit": r.get("to_commit"),
                                   "cleared_attempts": r.get("cleared_attempts"), "reason_head": head(r.get("reason")),
                                   "source": "%s#rewinds[%d]" % (STEPS, i)}, parse_time(r.get("at"))))
    out["rewinds"] = rw
    ds = []
    for i, c in enumerate(as_list(steps_doc.get("deferral_clearances"))):
        if isinstance(c, dict):
            ds.append(clock.stamp({"at": c.get("at"), "cluster": c.get("cluster"), "kind": c.get("kind"), "operator": c.get("operator"),
                                   "attempts": c.get("attempts"), "cards": as_list(c.get("cards")), "commit": c.get("commit") or None,
                                   "reason_head": head(c.get("reason")), "source": "%s#deferral_clearances[%d]" % (STEPS, i)}, parse_time(c.get("at"))))
    out["dispositions"] = ds
    res = []
    for i, r in enumerate(as_list(steps_doc.get("rejected"))):
        if isinstance(r, dict) and str(r.get("kind") or "") == "close" and r.get("operator"):
            res.append({"at": r.get("at"), "card": r.get("card"), "verdict": r.get("verdict"), "operator": r.get("operator"),
                        "contract_reseal": as_list(as_dict(r.get("contract_reseal")).get("changed")) or None,
                        "source": "%s#rejected[%d]" % (STEPS, i)})
    out["m4_resumes"] = V(res, STEPS + "#rejected[kind=close]", "the documented after-M4 transaction (resume-after-m4.py); listed, not counted as an application intervention")
    worker_files = sorted({str(f) for s in as_list(steps_doc.get("steps")) if isinstance(s, dict) and s.get("verdict") == "accepted" for f in as_list(s.get("changed"))})
    operator_files = sorted({str(f) for o in ops for f in o["changed"]})
    out["repair_inventory"] = V({"worker_files": worker_files, "operator_files": operator_files, "both": sorted(set(worker_files) & set(operator_files))},
                                STEPS + "#steps[].changed", "worker repairs and live Operator repairs apart; decided bootstrap repairs are under bootstrap_repairs")
    return out, harness


def reason_of(entry: Dict[str, Any]) -> str:
    return head(entry.get("reason"), 200)


def parity_final(tree: Tree) -> Dict[str, Any]:
    """Per security mode: the receipt (entry-point denominator) and the run
    and scenario records (scenario denominator)."""
    out: Dict[str, Any] = {}
    for m in parity_modes(tree):
        doc, why = tree.json(m["receipt"])
        run, rwhy = tree.json(m["run"])
        recs = []
        legacy = 0
        for rel in tree.glob(m["scenarios"] + "/*.json"):
            d, _ = tree.json(rel)
            if not isinstance(d, dict) or str(d.get("schema") or "") != "rhoai3.scenario-parity/v1":
                continue
            if str(d.get("scenario") or "").startswith("sc:"):
                recs.append(d)
            else:
                legacy += 1
        if doc is None and run is None and not recs:
            if m["mode"] == "default":
                out[m["mode"]] = U("%s, %s and %s/ are absent" % (m["receipt"], m["run"], m["scenarios"]))
            continue
        if isinstance(doc, dict):
            eps = [e for e in as_list(doc.get("entry_points")) if isinstance(e, dict)]
            counts: Dict[str, int] = {}
            for e in eps:
                counts[str(e.get("verdict"))] = counts.get(str(e.get("verdict")), 0) + 1
            e = V(doc.get("verdict"), m["receipt"])
            e.update({"security_mode": doc.get("security_mode"), "binding": doc.get("binding"),
                      "entry_points": {"denominator": doc.get("total", len(eps)), "PASS": counts.get("PASS", 0), "FAIL": counts.get("FAIL", 0),
                                       "INCONCLUSIVE": counts.get("INCONCLUSIVE", 0),
                                       "other": {k: v for k, v in counts.items() if k not in ("PASS", "FAIL", "INCONCLUSIVE")}},
                      "verdicts": {str(x.get("entry_point")): x.get("verdict") for x in eps},
                      "not_passed": [{"entry_point": x.get("entry_point"), "verdict": x.get("verdict"), "reason_head": reason_of(x)}
                                     for x in eps if x.get("verdict") in ("FAIL", "INCONCLUSIVE")],
                      "coverage_gaps": len(as_list(doc.get("coverage_gaps")))})
        else:
            e = U(why, m["receipt"])
        sc: Dict[str, Any] = {}
        if isinstance(run, dict):
            s = as_dict(run.get("scenarios"))
            sc["run"] = {"source": m["run"], "declared": s.get("declared"), "selected": s.get("selected"), "run": s.get("run"),
                         "PASS": s.get("passed"), "FAIL": s.get("failed"), "INCONCLUSIVE": s.get("inconclusive")}
            ep = as_dict(run.get("entry_points"))
            sc["run_entry_points"] = {k: ep.get(k) for k in ("admitted", "compared", "passed", "failed", "inconclusive", "skipped")}
            e["run"] = {"source": m["run"], "at": run.get("at"), "ok": run.get("ok"), "scoped": bool(as_list(run.get("scenario_filter"))),
                        "security_mode": run.get("security_mode"), "receipt_verdict": run.get("receipt_verdict") or None,
                        "failures": [head(f, 160) for f in as_list(run.get("failures"))][:5]}
        else:
            e["run"] = U(rwhy, m["run"])
        if recs:
            by: Dict[str, int] = {}
            for d in recs:
                by[str(d.get("verdict"))] = by.get(str(d.get("verdict")), 0) + 1
            sc["records"] = {"source": m["scenarios"] + "/*.json", "denominator": len(recs), "PASS": by.get("PASS", 0), "FAIL": by.get("FAIL", 0),
                             "INCONCLUSIVE": by.get("INCONCLUSIVE", 0), "legacy_records_ignored": legacy}
        e["scenarios"] = sc if sc else U("no scenario run or record for this mode")
        out[m["mode"]] = e
    return out


def generated_tests(tree: Tree) -> Dict[str, Any]:
    man, why = tree.json(GENERATED)
    out: Dict[str, Any] = {}
    classes: set = set()
    if not isinstance(man, dict):
        out["manifest"] = U(why, GENERATED)
    else:
        cases = [c for c in as_list(man.get("cases")) if isinstance(c, dict)]
        classes = {str(c.get("class")) for c in cases if c.get("class")}
        out["manifest"] = V({"cases": len(cases), "classes": len(classes), "files": len(as_list(man.get("files"))),
                             "gaps": [{"scenario": g.get("scenario"), "kind": g.get("kind"), "reason_head": reason_of(g)} for g in as_list(man.get("gaps")) if isinstance(g, dict)],
                             "generator_version": man.get("generator_version"), "corpus_sha256": man.get("corpus_sha256")}, GENERATED)
    found = None
    for d in REPORT_DIRS:
        files = tree.glob(d + "/**/TEST-*.xml")
        if files:
            found = (d, files)
            break
    if found is None:
        out["execution"] = U("no TEST-*.xml under %s" % ", ".join(REPORT_DIRS))
        return out
    d, files = found
    tot = {"executed": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    gen = dict(tot)
    unreadable = []
    for rel in files:
        try:
            root = ET.parse(str(tree.path(rel))).getroot()
        except (ET.ParseError, OSError):
            unreadable.append(rel)
            continue
        for tc in root.iter("testcase"):
            bucket = [tot] + ([gen] if str(tc.get("classname") or "") in classes else [])
            kind = "passed"
            if tc.find("failure") is not None:
                kind = "failed"
            elif tc.find("error") is not None:
                kind = "errors"
            elif tc.find("skipped") is not None:
                kind = "skipped"
            for b in bucket:
                b[kind] += 1
                if kind != "skipped":
                    b["executed"] += 1
    e = V(gen if classes else None, d + "/**/TEST-*.xml",
          "" if classes else "the generated manifest names no test class, so generated cases cannot be told apart")
    e["all_tests"] = tot
    e["report_files"] = len(files)
    e["unreadable"] = unreadable
    e["note"] = "latest reports on disk; their freshness against the accepted tree is not re-judged here"
    out["execution"] = e
    return out


def final_state(tree: Tree, m4: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    st, why = tree.json(STATE)
    if isinstance(st, dict):
        meas = as_dict(st.get("measure"))
        out["measure"] = V(as_list(meas.get("tuple")) or None, STATE + "#measure.tuple", "" if meas.get("tuple") else "state.json has no measure tuple")
        out["measure"].update({"known": meas.get("known"), "parity_mismatches": meas.get("parity_mismatches"),
                               "open_clusters": st.get("open_clusters"), "head": st.get("head") or None, "deferred": as_list(st.get("deferred"))})
    else:
        out["measure"] = U(why, STATE)
    adm, awhy = tree.json(ADMISSION)
    if isinstance(adm, dict):
        out["admission"] = V(adm.get("status"), ADMISSION)
        out["admission"].update({"loop_complete": adm.get("loop_complete"), "loop_epoch": adm.get("loop_epoch"), "counts": adm.get("counts")})
    else:
        out["admission"] = U(awhy, ADMISSION)
    for name, rel in (("package_gate", PACKAGE), ("boot_gate", BOOT)):
        doc, w = tree.json(rel)
        if isinstance(doc, dict):
            ok = doc.get("ran") and doc.get("rc") == 0 and (name != "boot_gate" or doc.get("ready"))
            e = V("pass" if ok else ("fail" if doc.get("ran") else "not-run"), rel)
            e.update({"rc": doc.get("rc"), "at": doc.get("at"), "candidate_sha256": doc.get("candidate_sha256"), "artifact_sha256": doc.get("artifact_sha256")})
            out[name] = e
        else:
            out[name] = U(w, rel)
    run, w = tree.json(RUN)
    out["last_verification"] = V({"mode": run.get("mode"), "total_ms": run.get("total_ms"), "candidate_sha256": run.get("candidate_sha256")}, RUN) if isinstance(run, dict) else U(w, RUN)
    out["parity"] = parity_final(tree)
    out["m4_verdict"] = m4["current"]
    rb, w = tree.json(BLOCKERS)
    if isinstance(rb, dict):
        e = V(rb.get("verdict"), BLOCKERS)
        e.update({"verdict_card": rb.get("verdict_card"), "at": rb.get("at"), "owners": as_list(rb.get("owners")),
                  "floors": [{"floor": f.get("floor"), "adr": f.get("adr") or None, "owner": f.get("owner"), "explained_by": f.get("explained_by")} for f in as_list(rb.get("floors")) if isinstance(f, dict)],
                  "entry_points": [{"entry_point": x.get("entry_point"), "verdict": x.get("verdict"), "adr": x.get("adr") or None, "owner": x.get("owner"), "reason_head": reason_of(x)} for x in as_list(rb.get("entry_points")) if isinstance(x, dict)],
                  "withheld_obligations": len(as_list(rb.get("withheld_obligations"))), "parity_obligations_resumed": len(as_list(rb.get("parity_obligations"))),
                  # a CLEAN M4 close-out (resume-after-m4.py) rewrites this file
                  # as an EMPTY record: no floor, because the verdict cleared
                  # them, plus what still stands between closed and shipped
                  "closed": bool(rb.get("closed")), "cleared_by": as_dict(rb.get("cleared_by")),
                  "outstanding": [{"kind": x.get("kind"), "count": x.get("count"), "detail": x.get("detail")}
                                  for x in as_list(rb.get("outstanding")) if isinstance(x, dict)]})
        out["release_blockers"] = e
    else:
        out["release_blockers"] = U(w, BLOCKERS)
    out["generated_tests"] = generated_tests(tree)
    cov, w = tree.json(COVERAGE)
    if isinstance(cov, dict):
        s = as_dict(cov.get("summary"))
        e = V({"retired": s.get("retired"), "replaced": s.get("replaced"), "remaining_gaps": s.get("remaining_gaps"),
               "uncovered_capabilities": s.get("uncovered_capabilities")}, COVERAGE + "#summary")
        e["uncovered"] = [{"scenario": u.get("scenario"), "kind": u.get("kind"), "reason_head": reason_of(u)} for u in as_list(cov.get("uncovered_capabilities")) if isinstance(u, dict)]
        e["parity_receipt_verdict"] = cov.get("parity_receipt_verdict")
        out["coverage_account"] = e
    else:
        out["coverage_account"] = U(w, COVERAGE)
    return out


def contract(tree: Tree) -> Dict[str, Any]:
    """The comparable contract: entry points (bundle) and scenarios (corpus),
    each with a content digest, so runs can be compared on what is unchanged."""
    out: Dict[str, Any] = {}
    b, why = tree.json(BUNDLE)
    eps = {str(e.get("id")): canon_digest(e)[:16] for e in as_list(as_dict(b).get("entry_points")) if isinstance(e, dict) and e.get("id")}
    out["entry_points"] = V(eps, BUNDLE + "#entry_points (sha256 of each canonical row, 16 hex)") if eps else U(why or "the bundle lists no entry point", BUNDLE)
    c, cwhy = tree.json(CORPUS)
    scs = {}
    for s in as_list(as_dict(c).get("scenarios")):
        if isinstance(s, dict) and s.get("id"):
            body = str(s.get("body_file") or "")
            scs[str(s["id"])] = canon_digest({"row": s, "body": tree.sha256(body) if body else None})[:16]
    out["scenarios"] = V(scs, CORPUS + "#scenarios (row + body file, 16 hex)") if scs else U(cwhy or "the corpus lists no scenario", CORPUS)
    return out


def budget(tree: Tree, budget_file: Optional[Path], decisions: Any, dec_why: str, clock: Clock) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    cands: List[Tuple[str, Path]] = []
    if budget_file is not None:
        cands.append(("budget:%s" % budget_file.name, budget_file))
    cands += [(rel, tree.path(rel)) for rel in BUDGET_CANDIDATES]
    doc = None
    src = None
    for name, p in cands:
        if p.is_file():
            doc, why = load_doc(p)
            src = name
            if doc is None:
                out["declared"] = U(why, name)
            break
    if doc is None and isinstance(decisions, dict) and isinstance(decisions.get("budget"), dict):
        doc, src = decisions["budget"], DECISIONS + "#budget"
    if isinstance(doc, dict):
        e = V(doc, src)
        at = parse_time(doc.get("declared_at"))
        e["declared_before_launch"] = (at < clock.start) if (at is not None and clock.start is not None) else None
        if e["declared_before_launch"] is None:
            e["declared_before_launch_reason"] = "the budget carries no declared_at" if at is None else "the clock start is unknown"
        out["declared"] = e
    elif "declared" not in out:
        out["declared"] = V("undeclared", [n for n, _ in cands] + [DECISIONS + "#budget"], "no budget or stopping condition was declared in any of the named places")
    if isinstance(decisions, dict):
        th = as_dict(decisions.get("thresholds"))
        out["loop_stopping_rule"] = V({"max_attempts": th.get("max_attempts"), "adr": th.get("adr"),
                                       "rule": "a cluster is deferred at the attempt threshold and the loop stops until a human clears it"},
                                      DECISIONS + "#thresholds") if th else U("decisions.yaml has no thresholds section", DECISIONS)
    else:
        out["loop_stopping_rule"] = U(dec_why, DECISIONS)
    return out


# --------------------------------------------------------------------------
# board and logs
# --------------------------------------------------------------------------

LOG_TOKENS = (("blocked", "kanban_block"), ("protocol_violation", "protocol_violation"), ("refuse", "REFUSE:"),
              ("complete", "kanban_complete"), ("request_review", "kanban_request_review"), ("runs", "Query: work kanban task"))


def board_section(board: Dict[str, Any], logs: Optional[Path], steps_doc: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not board.get("provided"):
        out["cards"] = U("not provided (pass --kanban-json with the output of `hermes kanban list --json`)")
    else:
        cards = board["cards"]
        by_phase: Dict[str, Dict[str, Any]] = {}
        for c in cards:
            e = by_phase.setdefault(c["phase"], {"cards": 0, "statuses": {}, "_run": [], "_wall": [], "_queue": []})
            e["cards"] += 1
            e["statuses"][str(c["status"])] = e["statuses"].get(str(c["status"]), 0) + 1
            if c.get("started_at") and c.get("completed_at"):
                e["_run"].append(float(c["completed_at"]) - float(c["started_at"]))
            if c.get("created_at") and c.get("completed_at"):
                e["_wall"].append(float(c["completed_at"]) - float(c["created_at"]))
            if c.get("created_at") and c.get("started_at"):
                e["_queue"].append(float(c["started_at"]) - float(c["created_at"]))
        for e in by_phase.values():
            e["run_seconds"] = _stats(e.pop("_run"))
            e["created_to_completed_seconds"] = _stats(e.pop("_wall"))
            e["queue_seconds"] = _stats(e.pop("_queue"))
        statuses: Dict[str, int] = {}
        for c in cards:
            statuses[str(c["status"])] = statuses.get(str(c["status"]), 0) + 1
        record = set()
        sd = as_dict(steps_doc)
        for key in ("steps", "rejected", "pending"):
            for r in as_list(sd.get(key)):
                if isinstance(r, dict) and r.get("card"):
                    record.add(str(r["card"]))
        loop_cards = {c["id"] for c in cards if c["phase"] in ("M3", "M4")}
        e = V({"total": len(cards), "statuses": statuses, "by_phase": by_phase}, board["source"])
        e["never_started"] = [c["id"] for c in cards if not c.get("started_at")]
        e["loop_cards_not_in_record"] = sorted(loop_cards - record)
        e["record_cards_not_on_board"] = sorted(record - set(board["by_id"]))
        e["with_result_text"] = [{"id": c["id"], "title": c["title"][:60], "result_head": head(c.get("result"), 160)} for c in cards if c.get("result")]
        out["cards"] = e
    if logs is None:
        out["logs"] = U("not provided (pass --kanban-logs with the per-card log directory)")
        return out
    if not logs.is_dir():
        out["logs"] = U("%s is not a directory" % logs)
        return out
    per = {}
    totals = {k: 0 for k, _ in LOG_TOKENS}
    totals["nonzero_exits"] = 0
    files = sorted(logs.glob("*.log"))
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        row = {k: text.count(tok) for k, tok in LOG_TOKENS}
        row["nonzero_exits"] = sum(1 for m in EXIT_RE.finditer(text) if m.group(1) != "0")
        for k in totals:
            totals[k] += row[k]
        if any(row[k] for k in ("blocked", "protocol_violation", "refuse")) or row["runs"] > 1:
            per[f.stem] = row
    e = V(totals, "kanban-logs:%s/*.log" % logs.name, "token counts over the raw logs (a worker quoting a token counts too)")
    e["files"] = len(files)
    e["cards_with_events"] = per
    out["logs"] = e
    return out


# --------------------------------------------------------------------------
# classification, comparison and rendering
# --------------------------------------------------------------------------

def classification(steps_doc: Any, steps_why: str, inter: Dict[str, Any], boot: Dict[str, Any]) -> Dict[str, Any]:
    decided = as_dict(boot.get("decided"))
    if decided.get("value") is None:
        prior = U(str(decided.get("reason")), decided.get("source"))
    else:
        prior = V(decided.get("applied", 0), decided.get("source"))
        prior["adrs"] = decided.get("adrs") or []
    if not isinstance(steps_doc, dict):
        return {"value": None, "source": STEPS, "reason": "cannot classify: %s" % steps_why, "reasons": [], "prior_assistance": prior}
    reasons = []
    ops = as_list(inter.get("operator_steps"))
    by_decision = True
    for o in ops:
        ok = bool(o["adr"]) and o.get("applies_accepted_adr") is True and bool(o.get("reviewer"))
        why = []
        if not o["adr"]:
            why.append("names no ADR")
        elif o.get("applies_accepted_adr") is None:
            why.append("ADR acceptance unverifiable (%s)" % o.get("applies_accepted_adr_reason"))
        elif not o.get("applies_accepted_adr"):
            why.append("an ADR it names is not accepted in decisions.yaml")
        if not o.get("reviewer"):
            why.append("no reviewer recorded")
        by_decision = by_decision and ok
        reasons.append("operator step %s (%s) at %s%s" % (str(o.get("commit") or "")[:8], ",".join(o["adr"]) or "no ADR", o.get("at"),
                                                           "" if ok else ": " + "; ".join(why)))
    for r in as_list(inter.get("rewinds")):
        reasons.append("rewind by %s at %s closing %s" % (r.get("operator"), r.get("at"), ",".join(r.get("closed_cards") or []) or "no card"))
    for d in as_list(inter.get("dispositions")):
        reasons.append("disposition (%s) of %s by %s at %s" % (d.get("kind"), d.get("cluster"), d.get("operator"), d.get("at")))
    live = bool(ops or inter.get("rewinds") or inter.get("dispositions"))
    if prior["value"] is None:
        reasons.append("prior assistance unrecorded: %s" % prior["reason"])
    elif prior["value"]:
        reasons.append("prior assistance: %d decided bootstrap repair(s) (%s)" % (prior["value"], ", ".join(prior["adrs"]) or "no ADR named"))
    if not live:
        value = "autonomous_execution_with_predecided_repairs" if prior["value"] else "autonomous"
    elif ops and by_decision and not inter.get("rewinds") and not inter.get("dispositions"):
        value = "assisted-by-decision"
    else:
        value = "assisted"
    return {"value": value, "source": STEPS + "#steps[verdict=operator], #rewinds, #deferral_clearances; " + BOOTSTRAP,
            "reasons": reasons, "prior_assistance": prior,
            "counts": {"operator_steps": len(ops), "rewinds": len(as_list(inter.get("rewinds"))), "dispositions": len(as_list(inter.get("dispositions"))),
                       "bootstrap_repairs": prior["value"]}}


def headline(rep: Dict[str, Any]) -> Dict[str, Any]:
    t = rep["timeline"]
    w = rep["loop_work"]
    f = rep["final_state"]
    c = rep["classification"]

    def secs(e: Any) -> Any:
        if isinstance(e, dict) and "seconds_since_start" in e:
            return e.get("seconds_since_start") if e.get("value") != UNREACHED else UNREACHED
        if isinstance(e, dict) and e.get("value") == UNREACHED:
            return UNREACHED
        return None

    fpp = t.get("first_passing_parity")
    return {
        "classification": c.get("value"), "prior_assistance": as_dict(c.get("prior_assistance")).get("value"),
        "interventions": c.get("counts"),
        "seconds_since_start": {"baseline": secs(t.get("baseline")), "first_package_pass": secs(t.get("first_package_pass")),
                                "first_boot_pass": secs(t.get("first_boot_pass")), "first_full_parity": secs(t.get("first_full_parity")),
                                "first_passing_parity": ({k: secs(v) for k, v in fpp.items()} if isinstance(fpp, dict) and "value" not in fpp else secs(fpp)),
                                "first_m4_verdict": secs(t.get("first_m4_verdict")), "first_passing_m4": secs(t.get("first_passing_m4"))},
        "retries": as_dict(w.get("retries")).get("value"), "reverted": as_dict(as_dict(w.get("cards")).get("reverted")).get("value"),
        "accepted": as_dict(as_dict(w.get("cards")).get("accepted")).get("value"),
        "final_measure": as_dict(f.get("measure")).get("value"),
        "m4_verdict": as_dict(f.get("m4_verdict")).get("value"), "failed_floors": as_dict(f.get("m4_verdict")).get("failed_floors"),
        "release_blocker_entry_points": len(as_list(as_dict(f.get("release_blockers")).get("entry_points"))),
        "coverage_gaps": as_dict(as_dict(f.get("coverage_account")).get("value")).get("remaining_gaps"),
    }


def compare(rep: Dict[str, Any], others: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
    runs = [(str(as_dict(rep["pinned_inputs"].get("pilot_run_id")).get("value") or "this"), rep)] + others
    labels = [l for l, _ in runs]
    out: Dict[str, Any] = {"runs": labels}
    for kind in ("entry_points", "scenarios"):
        maps = [as_dict(as_dict(as_dict(r.get("contract")).get(kind)).get("value")) for _, r in runs]
        if not all(maps):
            out[kind] = U("run(s) without a %s contract: %s" % (kind, ", ".join(l for (l, _), m in zip(runs, maps) if not m)))
            continue
        common_ids = set(maps[0])
        for m in maps[1:]:
            common_ids &= set(m)
        unchanged = sorted(i for i in common_ids if len({m[i] for m in maps}) == 1)
        out[kind] = V({"common_unchanged": unchanged, "common_changed": sorted(common_ids - set(unchanged)),
                       "extra": {l: sorted(set(m) - common_ids) for (l, _), m in zip(runs, maps)}}, "contract.%s of each report" % kind)
    common = set(as_dict(as_dict(out.get("entry_points")).get("value")).get("common_unchanged") or [])
    parity = {}
    for l, r in runs:
        per_mode = {}
        for mode, e in as_dict(as_dict(r.get("final_state")).get("parity")).items():
            v = as_dict(as_dict(e).get("verdicts"))
            if not v:
                continue
            sub = {k: x for k, x in v.items() if k in common}
            counts: Dict[str, int] = {}
            for x in sub.values():
                counts[str(x)] = counts.get(str(x), 0) + 1
            per_mode[mode] = {"denominator": len(common), "PASS": counts.get("PASS", 0), "FAIL": counts.get("FAIL", 0),
                              "INCONCLUSIVE": counts.get("INCONCLUSIVE", 0), "absent": len(common) - len(sub)}
        parity[l] = per_mode
    out["parity_on_common_entry_points"] = parity
    out["differing_pins"] = differing_pins(runs)
    out["headline"] = {l: headline(r) for l, r in runs}
    return out


# ADR-019 §4 refuses attributing a difference to one change when others moved
# too. A comparison therefore names every pinned input that is NOT the same
# across the runs it compares. Deltas are descriptive: the contribution of
# any individual changed input is unknown. It reports what the reports say -- a pin a report could not
# read is "unknown", which is neither "same" nor "differs".
PIN_FIELDS = (("pinned_environment", ("model_provider", "inference", "concurrency", "toolchain", "database", "corpus_and_captures", "comparators", "tool_pins", "hermes_agent", "card_model_overrides")),
              ("pinned_inputs", ("installed_goldens", "project_commits", "pins_digest", "bundle_digest", "accepted_adrs", "decisions_digest", "unit_formation", "runtime_feedback", "frozen_source_digest",
                                 "created_from_golden")),
              ("bootstrap_repairs", ("decided", "decision")))


def differing_pins(runs: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
    def leaves(value: Any, prefix: str) -> Dict[str, Any]:
        if not isinstance(value, dict) or not value or "value" in value:
            return {prefix: as_dict(value).get("value")}
        out = {}
        for key, child in value.items():
            out.update(leaves(child, prefix + "." + key))
        return out

    flattened = {}
    for label, rep in runs:
        pins = {}
        for section, fields in PIN_FIELDS:
            for field in fields:
                name = section + "." + field if section == "bootstrap_repairs" else field
                pins.update(leaves(as_dict(rep.get(section)).get(field), name))
        flattened[label] = pins
    differs, unknown = {}, {}
    for key in sorted({k for pins in flattened.values() for k in pins}):
        seen = {label: pins[key] for label, pins in flattened.items() if pins.get(key) is not None}
        blind = sorted(label for label, pins in flattened.items() if pins.get(key) is None)
        if blind:
            unknown[key] = blind
        if len({json.dumps(v, sort_keys=True) for v in seen.values()}) > 1:
            differs[key] = seen
    return {"differs": differs, "unknown": unknown}



def val(e: Any) -> str:
    if isinstance(e, dict) and "value" in e:
        if e["value"] is None:
            return "unknown (%s)" % e.get("reason")
        return str(e["value"])
    return str(e)


def when(e: Any) -> str:
    e = as_dict(e)
    if e.get("value") is None:
        return val(e)
    if e.get("value") == UNREACHED:
        return "unreached (%s)" % (e.get("note") or e.get("reason") or "")
    return "%s (start %s, baseline %s)" % (e["value"], e.get("since_start"), e.get("since_baseline"))


def render(rep: Dict[str, Any]) -> str:
    L: List[str] = []
    p = rep["pinned_inputs"]
    t = rep["timeline"]
    w = rep["loop_work"]
    i = rep["interventions"]
    f = rep["final_state"]
    c = rep["classification"]
    env = rep["pinned_environment"]
    bs = rep["bootstrap_repairs"]
    L.append("# Run report: %s" % val(p.get("pilot_run_id")))
    L.append("")
    L.append("Classification: **%s**" % (c.get("value") or "unknown (%s)" % c.get("reason")))
    for r in c.get("reasons") or []:
        L.append("- %s" % r)
    L.append("")
    L.append("## Pinned inputs")
    for k in ("frozen_source_digest", "bundle_digest", "decisions_digest", "pins_digest", "unit_formation", "runtime_feedback", "created_from_golden"):
        e = p.get(k) or {}
        extra = ""
        if k == "decisions_digest" and e.get("value"):
            extra = " (admission seal %s: %s)" % (str(e.get("admission_seal") or "none")[:12],
                                                 "matches" if e.get("matches_admission_seal") else ("DIFFERS" if e.get("admission_seal") else "n/a"))
        v = val(e)
        L.append("- %s: `%s`%s" % (k, v[:16] if e.get("value") and len(v) in (40, 64) else v, extra))
    g = as_dict(p.get("installed_goldens"))
    if g.get("value"):
        L.append("- goldens: " + " → ".join("%s@%s(p %s)%s" % (x.get("golden", "?")[:8], (x.get("installed_at") or x.get("commit_at") or "?")[5:16],
                                                               x.get("project_commit") or "?", "*" if x.get("before_start") else "") for x in g["value"])
                 + "  (* = before the clock start)")
    else:
        L.append("- goldens: %s" % val(g))
    L.append("- environment: hermes %s; model/provider %s; inference %s; concurrency %s; template %s" % (
        val(env.get("hermes_agent")), val(env.get("model_provider")), val(env.get("inference")), val(env.get("concurrency")), val(env.get("config_template"))))
    db = as_dict(env.get("database"))
    cc = as_dict(env.get("corpus_and_captures"))
    L.append("- database %s; reset %s" % (val(db.get("datasource")), "recorded" if as_dict(db.get("reset_cmd")).get("value") else val(db.get("reset_cmd"))))
    corpus = as_dict(cc.get("corpus"))
    L.append("- corpus: %s, digests %s; captures %s; comparators %s script digest(s)" % (
        ("%s scenario(s)" % corpus["scenarios"]) if corpus.get("scenarios") is not None else "corpus file absent", ", ".join(d[:12] for d in corpus.get("distinct_digests") or []) or val(corpus),
        ", ".join("%s(%s)" % (k.rsplit("/", 1)[-1], v.get("security_mode")) for k, v in as_dict(as_dict(cc.get("captures")).get("value")).items()) or val(cc.get("captures")),
        len(as_dict(as_dict(env.get("comparators")).get("value")))))
    L.append("")
    L.append("## Timeline (UTC)")
    cs = as_dict(t.get("clock_start"))
    L.append("- clock start: %s" % (("%s from %s" % (cs["value"], cs.get("from"))) if cs.get("value") else val(cs)))
    for k, v in as_dict(as_dict(t.get("clock_start")).get("components")).items():
        L.append("  - %s: %s (%s)" % (k, v.get("at"), v.get("since_start")))
    for k in ("baseline", "first_accepted_step", "first_zero_measure", "first_package_pass", "first_boot_pass", "first_full_parity"):
        e = as_dict(t.get(k))
        tail = ""
        if e.get("card") or (e.get("cluster") and e.get("value") not in (None, UNREACHED)):
            tail = " %s %s" % (e.get("card") or "", e.get("cluster") or "")
        if k == "first_full_parity" and e.get("value") not in (None, UNREACHED):
            tail = " mode=%s receipt=%s ok=%s (the latest full run on disk; earlier ones leave no record)" % (
                e.get("mode"), e.get("run_receipt_verdict") or e.get("receipt_verdict_on_disk"), e.get("ok"))
        L.append("- %s: %s%s" % (k, when(e) if k != "first_full_parity" or e.get("value") in (None, UNREACHED) else "%s (start %s, baseline %s)" % (e["value"], e.get("since_start"), e.get("since_baseline")), tail))
    fpp = t.get("first_passing_parity")
    if isinstance(fpp, dict) and "value" not in fpp:
        for mode, e in fpp.items():
            L.append("- first_passing_parity[%s]: %s" % (mode, when(e)))
    else:
        L.append("- first_passing_parity: %s" % when(fpp))
    for v in t.get("m4_verdicts") or []:
        L.append("- M4 %s: %s at %s (start %s)%s failed_floors=%s" % (
            v.get("card"), v.get("verdict") or "no verdict row", v.get("at"), v.get("since_start"),
            " [board completion]" if str(v.get("time_source") or "").startswith("kanban-json") else "",
            ",".join(v.get("failed_floors") or []) or "-"))
        if v.get("board_result"):
            L.append("  - board result: %s" % v["board_result"])
    fpm = as_dict(t.get("first_passing_m4"))
    L.append("- first_passing_m4: %s" % (when(fpm) if "value" in fpm else "%s at %s (%s)" % (fpm.get("verdict"), fpm.get("at"), fpm.get("since_start"))))
    L.append("- last event: %s — %s" % (when(t.get("last_event")), as_dict(t.get("last_event")).get("subject")))
    L.append("")
    L.append("## Bootstrap repairs (decided, before the loop)")
    d = as_dict(bs.get("decided"))
    if d.get("value") is None:
        L.append("- %s" % val(d))
    else:
        L.append("- %d applied (%s)" % (d.get("applied", 0), ", ".join(d.get("adrs") or []) or "none"))
        for r in d["value"]:
            L.append("  - %s %s %s: %d file(s), %d symbol(s)" % (r.get("adr"), r.get("id"), r.get("status"), len(r["files"]), len(r["symbols"])))
    L.append("- mechanical bootstrap changes: %s" % val(bs.get("mechanical_changes")))
    L.append("")
    L.append("## Loop work")
    cards = as_dict(w.get("cards"))
    if cards:
        pend = as_dict(as_dict(cards.get("pending")).get("value"))
        dv = as_dict(as_dict(cards.get("deferred")).get("value"))
        L.append("- cards: minted %s, accepted %s, reverted %s (%s later rewound), closed without verdict %d, M4 closed %s, pending rows %s (open %d), deferred open %d, deferred-then-cleared %d" % (
            val(cards.get("minted")), val(cards.get("accepted")), val(cards.get("reverted")), val(cards.get("reverted_then_rewound")),
            len(as_list(as_dict(cards.get("closed_without_verdict")).get("value"))), val(cards.get("m4_closed")),
            pend.get("rows"), len(as_list(pend.get("open"))), len(as_list(dv.get("open"))), len(as_list(dv.get("deferred_then_cleared")))))
        us = as_dict(w.get("unit_sizes"))
        L.append("- retries: %s; scope amendments %s, revisions %d; units: %s" % (
            val(w.get("retries")), val(w.get("scope_amendments")), len(as_list(as_dict(w.get("scope_revisions")).get("value"))),
            val(us) if us.get("value") is None else "%d sealed" % len(us["value"])))
        ck = as_dict(w.get("clusters_by_kind"))
        L.append("- clusters by kind: %s (cards by kind %s%s); accepted by gate: %s" % (
            val(ck), ck.get("cards_by_kind"),
            "; re-issued under another kind: %s" % ", ".join(ck["clusters_with_several_kinds"]) if ck.get("clusters_with_several_kinds") else "",
            val(w.get("accepted_by_gate"))))
        multi = {k: v for k, v in as_dict(as_dict(w.get("attempts_per_cluster")).get("value")).items() if v.get("reverted") or v.get("accepted", 0) > 1}
        for k, v in sorted(multi.items()):
            L.append("  - %s: accepted %d, reverted %d, max attempt %d" % (k, v["accepted"], v["reverted"], v["max_attempt"]))
    else:
        L.append("- %s" % val(w.get("record")))
    L.append("")
    L.append("## Live interventions")
    for o in i.get("operator_steps") or []:
        L.append("- operator step %s (start %s) %s by %s (author %s, reviewer %s)%s, %d file(s): %s" % (
            (o.get("at") or "?"), o.get("since_start"), ",".join(o["adr"]) or "no ADR", o.get("operator"), o.get("author"), o.get("reviewer") or "none",
            " [beside %s]" % as_dict(o.get("beside_pending")).get("card") if o.get("beside_pending") else "", len(o.get("changed") or []), o.get("reason_head")))
    for r in i.get("rewinds") or []:
        L.append("- rewind %s by %s closed %s: %s" % (r.get("at"), r.get("operator"), ",".join(r.get("closed_cards") or []) or "-", r.get("reason_head")))
    for d in i.get("dispositions") or []:
        L.append("- disposition %s %s (%s) by %s, %s attempts: %s" % (d.get("at"), d.get("cluster"), d.get("kind"), d.get("operator"), d.get("attempts"), d.get("reason_head")))
    for r in as_list(as_dict(i.get("m4_resumes")).get("value")):
        L.append("- M4 resume (protocol, not counted) %s %s %s by %s%s" % (r.get("at"), r.get("card"), r.get("verdict"), r.get("operator"),
                                                                          " (contract reseal: %s)" % ",".join(r["contract_reseal"]) if r.get("contract_reseal") else ""))
    ri = as_dict(as_dict(i.get("repair_inventory")).get("value"))
    if ri:
        L.append("- repaired files: worker %d, operator %d, both %d" % (len(ri.get("worker_files") or []), len(ri.get("operator_files") or []), len(ri.get("both") or [])))
    h = rep.get("harness_changes") or {}
    L.append("- harness (not counted): %d install(s) before the clock start, %d after%s; %d other harness commit(s)" % (
        len(h.get("prior_preparation") or []), len(h.get("installs_after_start") or []),
        (": " + ", ".join("%s@%s" % (x["golden"][:8], (x.get("installed_at") or "?")[5:16]) for x in h.get("installs_after_start") or [])) if h.get("installs_after_start") else "",
        len(as_list(as_dict(h.get("other_harness_commits")).get("value")))))
    L.append("")
    L.append("## Cost")
    k = as_dict(rep.get("cost"))
    vv = as_dict(as_dict(k.get("verifications")).get("value"))
    L.append("- verifications: %s (%s s total; stages %s; warmup %s)" % (vv.get("count", val(k.get("verifications"))), vv.get("total_s"), vv.get("stage_totals_s"),
                                                                        as_dict(k.get("verifications")).get("warmup_seconds")))
    L.append("- cache: %s" % val(k.get("cache")))
    tt = as_dict(k.get("time"))
    L.append("- time: wall %s s; card runs %s; queue %s; outside card runs %s; tool %s; provider %s; unattributed in runs %s" % (
        val(tt.get("wall_seconds")), val(tt.get("card_run_seconds")), val(tt.get("queue_seconds")), val(tt.get("outside_card_runs_seconds", {"value": None, "reason": "n/a"})),
        val(tt.get("tool_seconds")), val(tt.get("provider_seconds")), val(tt.get("unattributed_in_card_runs_seconds"))))
    L.append("")
    L.append("## Final state")
    m = as_dict(f.get("measure"))
    L.append("- measure %s (parity mismatches %s, open clusters %s); admission %s; package %s; boot %s" % (
        val(m), m.get("parity_mismatches"), m.get("open_clusters"), val(f.get("admission")), val(f.get("package_gate")), val(f.get("boot_gate"))))
    for mode, e in as_dict(f.get("parity")).items():
        e = as_dict(e)
        if e.get("value") is None and not e.get("scenarios"):
            L.append("- parity %s: %s" % (mode, val(e)))
            continue
        ep = as_dict(e.get("entry_points"))
        sc = as_dict(e.get("scenarios"))
        srun = as_dict(sc.get("run"))
        srec = as_dict(sc.get("records"))
        parts = ["entry points PASS %s / FAIL %s / INCONCLUSIVE %s of %s" % (ep.get("PASS"), ep.get("FAIL"), ep.get("INCONCLUSIVE"), ep.get("denominator")) if ep else "no receipt"]
        if srun:
            parts.append("scenarios in the last run PASS %s / FAIL %s / INCONCLUSIVE %s of %s declared (%s run)" % (
                srun.get("PASS"), srun.get("FAIL"), srun.get("INCONCLUSIVE"), srun.get("declared"), srun.get("run")))
        if srec:
            parts.append("scenario records PASS %s / FAIL %s / INCONCLUSIVE %s of %s" % (srec.get("PASS"), srec.get("FAIL"), srec.get("INCONCLUSIVE"), srec.get("denominator")))
        L.append("- parity %s (security %s, binding %s): %s — %s" % (
            mode, e.get("security_mode"), as_dict(e.get("binding")).get("mode"), val(e), "; ".join(parts)))
        reasons: Dict[str, List[str]] = {}
        for x in e.get("not_passed") or []:
            reasons.setdefault("%s: %s" % (x["verdict"], x["reason_head"][:90]), []).append(str(x["entry_point"]).split("#")[-1].split("(")[0])
        for rk, eps in sorted(reasons.items(), key=lambda kv: -len(kv[1]))[:6]:
            L.append("  - %d× %s (%s)" % (len(eps), rk, ", ".join(eps[:4]) + (" …" if len(eps) > 4 else "")))
        run = as_dict(e.get("run"))
        if run.get("at"):
            L.append("  - last run %s ok=%s scoped=%s receipt=%s %s" % (run.get("at"), run.get("ok"), run.get("scoped"), run.get("receipt_verdict"), "; ".join(run.get("failures") or [])[:160]))
    mv = as_dict(f.get("m4_verdict"))
    L.append("- M4 verdict: %s (card %s, failed floors %s)" % (val(mv), mv.get("card"), ",".join(mv.get("failed_floors") or []) or "-"))
    rb = as_dict(f.get("release_blockers"))
    if rb.get("value") is not None and rb.get("closed"):
        # a CLEAN M4 rewrote this file as an empty record (resume-after-m4.py's
        # close-out). It names no blocker BECAUSE the verdict cleared them, and
        # what it does name is what stands between closed and shipped
        cleared = as_dict(rb.get("cleared_by"))
        L.append("- release blockers (%s): none — cleared by %s at %s; the run is CLOSED, not shipped" % (
            rb.get("verdict_card"), cleared.get("verdict") or rb.get("verdict"), cleared.get("at") or rb.get("at")))
        for x in as_list(rb.get("outstanding")):
            L.append("  - outstanding (%s): %s" % (as_dict(x).get("kind"), str(as_dict(x).get("detail"))[:200]))
    elif rb.get("value") is not None:
        L.append("- release blockers (%s): floors %s; %d entry point(s) owned by %s; %s obligation(s) withheld" % (
            rb.get("verdict_card"), ", ".join("%s→%s" % (x["floor"], x.get("adr") or x.get("owner")) for x in rb.get("floors") or []),
            len(rb.get("entry_points") or []), ",".join(rb.get("owners") or []), rb.get("withheld_obligations")))
    else:
        L.append("- release blockers: %s" % val(rb))
    gt = as_dict(f.get("generated_tests"))
    ex = as_dict(gt.get("execution"))
    man = as_dict(as_dict(gt.get("manifest")).get("value"))
    L.append("- generated tests: manifest %s case(s), %d gap(s); execution %s" % (
        man.get("cases", "?"), len(as_list(man.get("gaps"))), val(ex) if ex.get("value") is None else "%s (all tests %s)" % (ex["value"], ex.get("all_tests"))))
    L.append("- coverage account: %s" % val(f.get("coverage_account")))
    ct = as_dict(rep.get("contract"))
    L.append("- contract: %s entry point(s), %s scenario(s)" % (
        len(as_dict(as_dict(ct.get("entry_points")).get("value"))) or val(ct.get("entry_points")),
        len(as_dict(as_dict(ct.get("scenarios")).get("value"))) or val(ct.get("scenarios"))))
    bd = as_dict(rep.get("budget"))
    L.append("- budget: %s; loop stopping rule: %s" % (val(bd.get("declared"))[:200], val(bd.get("loop_stopping_rule"))[:160]))
    b = rep.get("board") or {}
    L.append("")
    L.append("## Board")
    bc = as_dict(b.get("cards"))
    if bc.get("value") is None:
        L.append("- cards: %s" % val(bc))
    else:
        L.append("- %d card(s), statuses %s" % (bc["value"]["total"], bc["value"]["statuses"]))
        for ph, e in sorted(bc["value"]["by_phase"].items()):
            rs = e["run_seconds"]
            L.append("  - %s: %d card(s), run total %s s, median %s s, max %s s; queue total %s s" % (
                ph, e["cards"], rs.get("total_s"), rs.get("median_s"), rs.get("max_s"), e["queue_seconds"].get("total_s")))
        if bc.get("loop_cards_not_in_record"):
            L.append("  - loop cards the record has no row for: %s" % ", ".join(bc["loop_cards_not_in_record"]))
    L.append("- logs: %s" % val(b.get("logs")))
    cmp_ = rep.get("comparison")
    if cmp_:
        L.append("")
        L.append("## Comparison")
        for kind in ("entry_points", "scenarios"):
            e = as_dict(cmp_.get(kind))
            if e.get("value") is None:
                L.append("- %s: %s" % (kind, val(e)))
            else:
                L.append("- %s: %d common unchanged, %d common changed; extra %s" % (kind, len(e["value"]["common_unchanged"]), len(e["value"]["common_changed"]),
                                                                                    {k: len(v) for k, v in e["value"]["extra"].items()}))
        dp = as_dict(cmp_.get("differing_pins"))
        if dp.get("differs"):
            L.append("- pinned inputs that DIFFER across these runs: %s" % ", ".join(sorted(dp["differs"])))
            for field, per in sorted(dp["differs"].items()):
                L.append("  - %s: %s" % (field, json.dumps(per, sort_keys=True)))
            L.append("  - deltas describe configurations that differ in these inputs; their individual causal contributions are unknown")
        elif dp:
            L.append("- pinned inputs: none of the compared fields differ across these runs")
        if dp.get("unknown"):
            L.append("- pinned inputs neither same nor different (a run could not read them): %s"
                     % ", ".join("%s (%s)" % (k, ", ".join(v)) for k, v in sorted(dp["unknown"].items())))
        for l, hl in cmp_["headline"].items():
            L.append("- %s: %s" % (l, json.dumps(hl, sort_keys=True)))
            L.append("  - parity on the common subset: %s" % json.dumps(cmp_["parity_on_common_entry_points"].get(l), sort_keys=True))
    return "\n".join(L) + "\n"


def build_report(root: Path, *, kanban_json: Optional[Path] = None, kanban_logs: Optional[Path] = None, git_log: Optional[Path] = None,
                 hermes_configs: Optional[List[Path]] = None, budget_file: Optional[Path] = None,
                 compare_with: Optional[List[Tuple[str, Dict[str, Any]]]] = None) -> Dict[str, Any]:
    ensure_hermes_lib()
    tree = Tree(root)
    hist = load_history(root, git_log)
    board = load_board(kanban_json)
    steps_doc, steps_why = tree.json(STEPS)
    if steps_doc is not None and not isinstance(steps_doc, dict):
        steps_doc, steps_why = None, "%s is not an object" % STEPS
    decisions, dec_why = load_decisions(tree)
    clock = Clock()
    m4 = m4_verdicts(tree, steps_doc, board)
    tl = timeline(tree, hist, steps_doc, steps_why, m4, board, clock)
    inter, harness = interventions(tree, hist, steps_doc, steps_why, decisions, dec_why, clock)
    boot = bootstrap_repairs(tree, decisions)
    rep = {
        "schema": SCHEMA,
        "generator": {"name": "run-report.py", "version": VERSION},
        "generated_at": iso(_dt.datetime.now(_dt.timezone.utc).timestamp()),
        "root": str(root),
        "inputs": {"git_history": hist.source if hist.known else None, "git_history_reason": None if hist.known else hist.reason,
                   "commits": len(hist.rows), "kanban_json": board.get("source") if board.get("provided") else None,
                   "kanban_logs": str(kanban_logs) if kanban_logs else None,
                   "hermes_config": [str(p) for p in hermes_configs or []], "budget": str(budget_file) if budget_file else None},
        "pinned_inputs": pinned_inputs(tree, hist, clock, decisions, dec_why),
        "pinned_environment": pinned_environment(tree, decisions, dec_why, list(hermes_configs or []), board),
        "timeline": tl,
        "bootstrap_repairs": boot,
        "loop_work": loop_work(tree, steps_doc, steps_why, board),
        "interventions": inter,
        "harness_changes": harness,
        "cost": cost(tree, steps_doc, steps_why, board, kanban_logs, clock, tl["last_event"]),
        "final_state": final_state(tree, m4),
        "contract": contract(tree),
        "budget": budget(tree, budget_file, decisions, dec_why, clock),
        "board": board_section(board, kanban_logs, steps_doc),
    }
    rep["classification"] = classification(steps_doc, steps_why, inter, boot)
    if compare_with:
        rep["comparison"] = compare(rep, compare_with)
    return rep


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, required=True, help="the destination root")
    ap.add_argument("--out", type=Path, help="report path (default <root>/%s)" % OUT_REL)
    ap.add_argument("--kanban-json", type=Path, help="output of `hermes kanban list --json`")
    ap.add_argument("--kanban-logs", type=Path, help="directory of per-card worker logs (<task>.log)")
    ap.add_argument("--git-log", type=Path, help="file of `git log --format='%%H %%ct %%s'` lines, instead of running git")
    ap.add_argument("--hermes-config", type=Path, action="append", default=[], help="a copy of the live Hermes config (YAML/JSON); repeatable")
    ap.add_argument("--budget", type=Path, help="the run budget and stopping conditions declared before launch (JSON/YAML)")
    ap.add_argument("--compare", action="append", default=[], help="[LABEL=]another run-report.json to compare with; repeatable")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print("FAIL: --root %s is not a directory" % root, file=sys.stderr)
        return 2
    others = []
    for spec in args.compare:
        label, _, path = spec.rpartition("=") if "=" in spec else ("", "", spec)
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("FAIL: --compare %s: %s" % (spec, exc), file=sys.stderr)
            return 2
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            print("FAIL: --compare %s is not a %s report" % (spec, SCHEMA), file=sys.stderr)
            return 2
        others.append((label or str(as_dict(as_dict(doc.get("pinned_inputs")).get("pilot_run_id")).get("value") or Path(path).stem), doc))
    try:
        rep = build_report(root, kanban_json=args.kanban_json, kanban_logs=args.kanban_logs, git_log=args.git_log,
                           hermes_configs=args.hermes_config, budget_file=args.budget, compare_with=others)
    except (OSError, ValueError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2
    out = args.out or (root / OUT_REL)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    sys.stdout.write(render(rep))
    print("\nOK: wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
