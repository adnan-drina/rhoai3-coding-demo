#!/usr/bin/env python3
"""Paved-road M1/M2 index: generated audit over the official log + KEEP.

``steps.json`` is the source. ``audit.json`` is generated. Official log
grep: skill steps match ``skill_view`` / skill-load lines only; kernel and
native steps match a script basename on a ``$`` terminal line with a path
boundary (never a parent directory).

Silence fails. An unmatched ``[exit 1]`` on a mandated needle fails: a
later clean invocation of the *same* needle clears an earlier red
(SOUL self-correction). Last-wins across different needles stays refused.
Do not scope the audit to the last ``Query: work kanban task`` marker —
that marker is the reviewer session. Worker-authored receipts are not
proof; only the official kanban log and KEEP files are.
CLI: ``coverage``, ``audit``, ``generate``, ``sync``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

BACKINGS = frozenset({"skill", "kernel", "native"})
PAYLOAD_KEYS = ("skill", "kernel", "native")
EXIT_RE = re.compile(r"\[exit (\d+)\]")
ALLOWLIST_KEYS = ("domain", "dest-init", "kind-not-yet")

_HERE = Path(__file__).resolve().parent
HERMES_DIR = _HERE.parent
GOLDEN_ROOT = HERMES_DIR.parent
PAVED_ROAD_DIR = HERMES_DIR / "skills" / "paved-road"
ALLOWLIST_PATH = PAVED_ROAD_DIR / "allowlist.json"

M1_ORDER = ("freeze-migration-input", "inventory-legacy-surface", "scan-with-mta", "assemble-evidence-bundle")
M2_FIRST_NATIVE = "assert-planner-activated.py"
M2_PRODUCER = "admit-migration-plan"
# m3-loop: the index views fix-until-green, then brief → run-verify → advance.
# advance.py is the producer and a VERDICT step: its exit code is not the
# grade (REVERTED / DEFERRED exit 1 by design); the grade is the loop record
# (verification/loop/steps.json) naming this card with a verdict.
# VERIFICATION_PENDING is not a complete-able verdict (kanban_block).
M3_SKILL = "fix-until-green"
# m4-verify: the source oracles come first (they are the only source of an
# expected runtime value), the pre-verdict runner runs the pinned feeding
# gates and writes their receipts, compose-m4-verdict is the only producer,
# and the readiness lint follows it (a checker may agree or refuse, never author).
M4_ORACLES = "capture-source-oracles"
M4_RUNNER = "run-m4-pre-verdict.sh"
M4_PRODUCER = "compose-m4-verdict"
M4_LINT = "check-release-readiness"
M3_ORDER = ("brief.py", "run-verify.sh", "advance.py")
M3_PRODUCER_NATIVE = "advance.py"
LOOP_STEPS_REL = "verification/loop/steps.json"
_TASK_RE = re.compile(r"Query: work kanban task (t_[A-Za-z0-9]+)")


def _fail(msg: str) -> int:
    print("REFUSE: PAVED_ROAD " + msg, file=sys.stderr)
    return 1


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def skill_load_re(name: str) -> re.Pattern[str]:
    return re.compile(r"┊\s+\S+\s+skill\s+(?:[\w.-]+/)?" + re.escape(name) + r"(?:\s|$|/)")


def kanban_root_home() -> str:
    """Official logs live under the base HERMES_HOME, not profile homes."""
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if not home:
        return ""
    parent, name = os.path.split(home.rstrip("/"))
    root, profiles = os.path.split(parent)
    if profiles == "profiles" and name and root:
        return root
    return home


def resolve_log(task_id: str | None, log: Path | None) -> Path | None:
    if log is not None:
        return log
    if not task_id:
        return None
    home = kanban_root_home()
    if not home:
        return None
    return Path(home) / "kanban" / "logs" / (task_id + ".log")


_CACHE_TERMINAL = "cache/terminal-output"
_OFFICIAL_KANBAN_LOG = re.compile(r"(?:^|/)kanban/logs/t_[A-Za-z0-9]+\.log$")
_FIXTURE_OFFICIAL_LOG = re.compile(r"(?:^|/)fixtures/.+/official\.log$")


def is_allowed_audit_log(path: Path) -> bool:
    """True for the official kanban log or a land-time fixture."""
    n = str(path).replace("\\", "/")
    if _CACHE_TERMINAL in n:
        return False
    if "/profiles/" in n and "/cache/" in n:
        return False
    if _OFFICIAL_KANBAN_LOG.search(n):
        return True
    if _FIXTURE_OFFICIAL_LOG.search(n):
        return True
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_steps_doc(doc: Any, *, path: Path | None = None) -> list[str]:
    loc = str(path) if path is not None else "steps.json"
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["%s: root must be an object" % loc]
    if not doc.get("kind"):
        errors.append("%s: missing kind" % loc)
    if not doc.get("artifact"):
        errors.append("%s: missing artifact" % loc)
    steps = doc.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("%s: steps must be a non-empty array" % loc)
        return errors
    producers = 0
    seen_ids: set[str] = set()
    for i, step in enumerate(steps):
        prefix = "%s step[%d]" % (loc, i)
        if not isinstance(step, dict):
            errors.append("%s: must be an object" % prefix)
            continue
        sid = str(step.get("id") or "").strip()
        if not sid:
            errors.append("%s: missing id" % prefix)
        elif sid in seen_ids:
            errors.append("%s: duplicate id %s" % (prefix, sid))
        else:
            seen_ids.add(sid)
        backing = step.get("backing")
        if backing not in BACKINGS:
            errors.append("%s: backing must be skill|kernel|native (got %r)" % (prefix, backing))
            continue
        present = [k for k in PAYLOAD_KEYS if k in step and step[k] not in (None, "")]
        if present != [backing]:
            errors.append("%s: exactly one backing payload matching backing=%s (got %s)" % (prefix, backing, present))
        elif backing in {"kernel", "native"}:
            payload = str(step.get(backing) or "")
            if "/" in payload or "\\" in payload or payload in {".", ".."}:
                errors.append("%s: %s must be a script basename (got %r)" % (prefix, backing, payload))
        if step.get("producer") is True:
            producers += 1
        if "verdict" in step and (step.get("verdict") is not True or backing == "skill"):
            errors.append("%s: verdict must be true and only on a kernel/native step" % prefix)
        keep = step.get("keep")
        if keep is not None:
            if not isinstance(keep, list) or not all(isinstance(x, str) for x in keep):
                errors.append("%s: keep must be a string array" % prefix)
        if "emit-findings-handoff" in sid or (backing == "skill" and "emit-findings-handoff" in str(step.get("skill") or "")):
            errors.append("%s: emit-findings-handoff.py runs inside mta-analyze-legacy.sh; do not list it as a paved-road step" % prefix)
    if producers != 1:
        errors.append("%s: exactly one producer: true (got %d)" % (loc, producers))
    kind = str(doc.get("kind") or "")
    skill_idx: dict[str, int] = {}
    for i, step in enumerate(steps):
        if isinstance(step, dict) and step.get("backing") == "skill":
            name = str(step.get("skill") or "").strip()
            if name and name not in skill_idx:
                skill_idx[name] = i
    if kind == "m1-analyze":
        missing = [n for n in M1_ORDER if n not in skill_idx]
        if missing:
            errors.append("%s: m1-analyze must include %s" % (loc, ", ".join(missing)))
        else:
            idx = [skill_idx[n] for n in M1_ORDER]
            if idx != sorted(idx):
                errors.append("%s: m1-analyze order must be freeze-migration-input → inventory-legacy-surface → scan-with-mta → assemble-evidence-bundle (the frozen original source is the baseline; the MTA handoff refuses without the inventory)" % loc)
            if idx[0] != 0:
                errors.append("%s: freeze-migration-input must be the first step" % loc)
        if "derive-legacy-boot3" in skill_idx:
            errors.append("%s: derive-legacy-boot3 is an execution-side transformation, not an M1 evidence step" % loc)
        prod = next((s for s in steps if isinstance(s, dict) and s.get("producer") is True), None)
        if prod is not None and prod.get("skill") != "assemble-evidence-bundle":
            errors.append("%s: m1-analyze producer must be assemble-evidence-bundle" % loc)
    if kind == "m2-plan":
        first = steps[0] if isinstance(steps[0], dict) else {}
        if first.get("backing") != "native" or first.get("native") != M2_FIRST_NATIVE:
            errors.append("%s: m2-plan must start with native %s (activation gate, SAD §12)" % (loc, M2_FIRST_NATIVE))
        prod = next((s for s in steps if isinstance(s, dict) and s.get("producer") is True), None)
        if prod is not None and prod.get("skill") != M2_PRODUCER:
            errors.append("%s: m2-plan producer must be %s" % (loc, M2_PRODUCER))
        for name in ("bootstrap-destination", "build-worklist"):
            if name not in skill_idx or skill_idx[name] > skill_idx.get(M2_PRODUCER, 99):
                errors.append("%s: %s must precede admit-migration-plan" % (loc, name))
        if skill_idx.get("bootstrap-destination", 99) > skill_idx.get("build-worklist", 0):
            errors.append("%s: bootstrap-destination must precede build-worklist (the baseline is verified after the deterministic bootstrap)" % loc)
        kernels = [str(s.get("kernel")) for s in steps if isinstance(s, dict) and s.get("backing") == "kernel"]
        if "k4_mint.py" not in kernels:
            errors.append("%s: m2-plan must mint through kernel k4_mint.py" % loc)
        for s in steps:
            if isinstance(s, dict) and str(s.get("skill") or s.get("native") or s.get("kernel") or "").startswith("speckit"):
                errors.append("%s: Spec Kit steps are retired" % loc)
    if kind == "m4-verify":
        prod = next((s for s in steps if isinstance(s, dict) and s.get("producer") is True), None)
        if prod is not None and prod.get("skill") != M4_PRODUCER:
            errors.append("%s: m4-verify producer must be %s (checkers never author the verdict)" % (loc, M4_PRODUCER))
        natives = [str(s.get("native")) for s in steps if isinstance(s, dict) and s.get("backing") == "native"]
        if M4_RUNNER not in natives:
            errors.append("%s: m4-verify must run the pre-verdict runner %s" % (loc, M4_RUNNER))
        idx = {}
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                continue
            name = str(s.get("skill") or s.get("native") or "")
            idx.setdefault(name, i)
        if idx.get(M4_ORACLES, 99) != 0:
            errors.append("%s: m4-verify must start with %s (the expected values come from the source oracles, nothing else)" % (loc, M4_ORACLES))
        if idx.get(M4_RUNNER, 99) > idx.get(M4_PRODUCER, 0):
            errors.append("%s: the pre-verdict runner must precede %s (the verdict is composed from measured exits)" % (loc, M4_PRODUCER))
        if idx.get(M4_LINT, 0) < idx.get(M4_PRODUCER, 99):
            errors.append("%s: %s lints the verdict and must follow %s" % (loc, M4_LINT, M4_PRODUCER))
    if kind == "m3-loop":
        first = steps[0] if isinstance(steps[0], dict) else {}
        if first.get("backing") != "skill" or first.get("skill") != M3_SKILL:
            errors.append("%s: m3-loop must start with skill_view %s (the loop procedure is the road)" % (loc, M3_SKILL))
        natives = [str(s.get("native")) for s in steps if isinstance(s, dict) and s.get("backing") == "native"]
        if natives != list(M3_ORDER):
            errors.append("%s: m3-loop native steps must be exactly %s in order (got %s)" % (loc, " → ".join(M3_ORDER), natives))
        prod = next((s for s in steps if isinstance(s, dict) and s.get("producer") is True), None)
        if prod is not None and (prod.get("native") != M3_PRODUCER_NATIVE or prod.get("verdict") is not True):
            errors.append("%s: m3-loop producer must be native %s with verdict: true" % (loc, M3_PRODUCER_NATIVE))
        if prod is not None and LOOP_STEPS_REL not in (prod.get("keep") or []):
            errors.append("%s: the verdict step must KEEP %s (the loop record is the grade)" % (loc, LOOP_STEPS_REL))
        for s in steps:
            if isinstance(s, dict) and s.get("backing") == "skill" and s.get("skill") in {"author-destination-pom", "manage-quarkus-extensions", "reference-rh-quarkus-pom"}:
                errors.append("%s: story-era pom skills are not loop steps (pilot v5: whole-pom rewrite); the brief carries the pom data" % loc)
    return errors


def load_steps(path: Path) -> dict[str, Any]:
    doc = load_json(path)
    errors = validate_steps_doc(doc, path=path)
    if errors:
        raise ValueError("\n".join(errors))
    return doc


def step_needle(step: dict[str, Any]) -> str:
    backing = step["backing"]
    return str(step[backing])


def generate_audit(doc: dict[str, Any]) -> dict[str, Any]:
    producer = None
    steps_out: list[dict[str, Any]] = []
    for step in doc["steps"]:
        item: dict[str, Any] = {
            "id": step["id"],
            "backing": step["backing"],
            "keep": list(step.get("keep") or []),
            "needle": step_needle(step),
        }
        if step.get("producer") is True:
            item["producer"] = True
            producer = step["id"]
        if step.get("verdict") is True:
            item["verdict"] = True
        steps_out.append(item)
    return {
        "artifact": doc["artifact"],
        "kind": doc["kind"],
        "last_wins_across_needles": False,
        "last_wins_within_needle": True,
        "producer": producer,
        "silence_fails": True,
        "source": "steps.json",
        "steps": steps_out,
        "unmatched_exit_1_fails": True,
        "worker_receipts_are_not_proof": True,
    }


def write_audit(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(dumps(generate_audit(doc)), encoding="utf-8")


def audit_bytes(doc: dict[str, Any]) -> str:
    return dumps(generate_audit(doc))


def sync_audit(skill_dir: Path) -> tuple[int, str]:
    steps_path = skill_dir / "steps.json"
    audit_path = skill_dir / "audit.json"
    if not steps_path.is_file():
        return 1, "missing %s" % steps_path
    doc = load_steps(steps_path)
    want = audit_bytes(doc)
    if not audit_path.is_file():
        return 1, "missing generated %s" % audit_path
    got = audit_path.read_text(encoding="utf-8")
    if got != want:
        return 1, "audit.json drifted from steps.json (%s)" % audit_path
    return 0, "OK: audit.json in sync with steps.json (%s)" % skill_dir.name


def matching_lines(text: str, needle: str) -> list[str]:
    return [ln for ln in text.splitlines() if needle in ln]


def script_basename_boundary_re(name: str) -> re.Pattern[str]:
    """Match a script basename on a ``$`` line, not a parent directory."""
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("kernel/native needle must be a script basename: %r" % name)
    return re.compile(r"(?:^|[\s/\"'`])" + re.escape(name) + r"(?:[\s\"'`;|&<>]|$)")


def matching_terminal_lines(text: str, basename: str) -> list[str]:
    pat = script_basename_boundary_re(basename)
    return [ln for ln in text.splitlines() if "$" in ln and pat.search(ln)]


def followed_skill(text: str, name: str) -> bool:
    pat = skill_load_re(name)
    return any(pat.search(ln) for ln in text.splitlines())


def terminal_runs(lines: list[str]) -> list[tuple[str, int | None]]:
    out: list[tuple[str, int | None]] = []
    for raw in lines:
        if "$" not in raw:
            continue
        cmd = raw.split("$", 1)[1]
        if "--help" in cmd:
            continue
        m = EXIT_RE.search(raw)
        rc = int(m.group(1)) if m else None
        out.append((raw.strip(), rc))
    return out


def unmatched_exit1(runs: list[tuple[str, int | None]]) -> list[tuple[str, int | None]]:
    """Reds with no later success of this same needle (omitted marker = clean)."""
    unmatched: list[tuple[str, int | None]] = []
    for i, run in enumerate(runs):
        if run[1] != 1:
            continue
        if any(later[1] in (0, None) for later in runs[i + 1 :]):
            continue
        unmatched.append(run)
    return unmatched


def keep_missing(root: Path, keep: list[str]) -> list[str]:
    """KEEP entries that are absent or empty. A KEEP may name a directory
    whose contents are produced one file per subject (the M4 pre-verdict
    runner writes one gate receipt per pinned gate): the directory must
    exist and hold at least one non-empty file."""
    missing: list[str] = []
    for rel in keep:
        path = root / rel
        if path.is_dir():
            if not any(f.is_file() and f.stat().st_size > 0 for f in path.rglob("*")):
                missing.append(rel)
            continue
        if not path.is_file() or path.stat().st_size < 1:
            missing.append(rel)
    return missing


def log_task_id(text: str) -> str:
    """The card the official log belongs to (its first `Query: work kanban task t_…`)."""
    m = _TASK_RE.search(text)
    return m.group(1) if m else ""


def loop_verdict_for(root: Path, task_id: str) -> str:
    """'accepted' / 'rejected' when verification/loop/steps.json names the card, else ''."""
    if not task_id:
        return ""
    p = root / LOOP_STEPS_REL
    if not p.is_file():
        return ""
    try:
        doc = load_json(p)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(doc, dict):
        return ""
    if any(isinstance(s, dict) and str(s.get("card") or "") == task_id for s in doc.get("steps") or []):
        return "accepted"
    if any(isinstance(r, dict) and str(r.get("card") or "") == task_id for r in doc.get("rejected") or []):
        return "rejected"
    return ""


def evaluate_audit(text: str, doc: dict[str, Any], root: Path) -> int:
    failures: list[str] = []
    task_id = log_task_id(text)
    for step in doc["steps"]:
        sid = str(step["id"])
        backing = str(step["backing"])
        needle = step_needle(step)
        keep = [str(x) for x in (step.get("keep") or [])]

        if backing == "skill":
            if not followed_skill(text, needle):
                if matching_lines(text, needle):
                    failures.append("mandated skill_view absent for %s (path mention is not follow)" % needle)
                else:
                    failures.append("silence: step %s needle %r absent from official log" % (sid, needle))
                continue
            missing = keep_missing(root, keep)
            if missing:
                failures.append("missing KEEP %s (step %s)" % (",".join(missing), sid))
            continue

        try:
            lines = matching_terminal_lines(text, needle)
        except ValueError as exc:
            failures.append(str(exc))
            continue
        runs = terminal_runs(lines) if lines else []
        if not runs:
            failures.append("silence: step %s needle %r has no terminal argv in official log" % (sid, needle))
            continue
        if step.get("verdict") is True:
            # the grade is the loop record, not the exit code: REVERTED and
            # DEFERRED exit 1 by design and are complete, recorded outcomes
            verdict = loop_verdict_for(root, task_id)
            if not verdict:
                failures.append("no loop verdict recorded for card %s after %r (a refused advance is not a verdict)" % (task_id or "?", needle))
                continue
            missing = keep_missing(root, keep)
            if missing:
                failures.append("missing KEEP %s (step %s)" % (",".join(missing), sid))
            continue
        reds = unmatched_exit1(runs)
        if reds:
            failures.append("unmatched [exit 1] on mandated needle %r (step %s, count=%d)" % (needle, sid, len(reds)))
            continue
        last_rc = runs[-1][1]
        # Hermes stamps ``[exit N]`` on failure and omits the marker on success.
        if last_rc not in (0, None):
            failures.append("last matching line for needle %r is not success (step %s rc=%s)" % (needle, sid, last_rc))
            continue
        missing = keep_missing(root, keep)
        if missing:
            failures.append("missing KEEP %s (step %s)" % (",".join(missing), sid))

    if failures:
        return _fail("; ".join(failures))

    verdict = loop_verdict_for(root, task_id) if any(s.get("verdict") is True for s in doc["steps"]) else ""
    print("OK: PAVED_ROAD kind=%s artifact=%s steps=%d%s" % (doc.get("kind"), doc.get("artifact"), len(doc["steps"]), (" verdict=%s card=%s" % (verdict, task_id)) if verdict else ""))
    return 0


def audit_paths(log: Path, root: Path, steps_path: Path) -> int:
    if not is_allowed_audit_log(log):
        return _fail("--log is not an official kanban log (%s); refuse implementer cache/terminal-output" % log)
    if not log.is_file():
        return _fail("missing official log %s" % log)
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _fail("unreadable official log %s: %s" % (log, exc))
    try:
        doc = load_steps(steps_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("steps.json: %s" % exc)
    return evaluate_audit(text, doc, root)


def dest_skill_mds(skills_root: Path) -> list[Path]:
    return sorted(p for p in skills_root.rglob("SKILL.md") if p.is_file())


def skill_dir_name(skill_md: Path) -> str:
    return skill_md.parent.name


def is_paved_road_index(skill_md: Path) -> bool:
    return skill_md.parent.parent.name == "paved-road"


def load_allowlist(path: Path) -> dict[str, list[str]]:
    doc = load_json(path)
    if not isinstance(doc, dict):
        raise ValueError("allowlist.json must be an object")
    extra = [k for k in doc if k not in ALLOWLIST_KEYS]
    if extra:
        raise ValueError("allowlist.json unknown keys: %s" % ",".join(extra))
    out: dict[str, list[str]] = {}
    for key in ALLOWLIST_KEYS:
        raw = doc.get(key, [])
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            raise ValueError("allowlist.json %s must be a string array" % key)
        out[key] = [x.strip() for x in raw if str(x).strip()]
    return out


def kind_step_files(paved_root: Path) -> list[Path]:
    return sorted(paved_root.glob("paved-road-*/steps.json"))


def cited_skills(step_files: list[Path]) -> set[str]:
    names: set[str] = set()
    for path in step_files:
        doc = load_steps(path)
        for step in doc["steps"]:
            if step.get("backing") == "skill":
                names.add(str(step["skill"]))
    return names


def coverage(root: Path | None = None) -> int:
    golden = (root or GOLDEN_ROOT).resolve()
    skills_root = golden / ".hermes" / "skills"
    paved = skills_root / "paved-road"
    allowlist_path = paved / "allowlist.json"
    if not (golden / ".hermes" / "lib" / ".hermes-lib").is_file():
        print("FAIL: .hermes/lib marker missing", file=sys.stderr)
        return 1
    if not allowlist_path.is_file():
        print("FAIL: missing %s" % allowlist_path, file=sys.stderr)
        return 1
    try:
        allow = load_allowlist(allowlist_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("FAIL: allowlist: %s" % exc, file=sys.stderr)
        return 1

    step_files = kind_step_files(paved)
    if len(step_files) < 3:
        print("FAIL: need paved-road-m1, paved-road-m2 and paved-road-m3 steps.json", file=sys.stderr)
        return 1

    bad = 0
    for path in step_files:
        try:
            load_steps(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("FAIL: %s" % exc, file=sys.stderr)
            bad = 1
            continue
        rc, msg = sync_audit(path.parent)
        if rc != 0:
            print("FAIL: %s" % msg, file=sys.stderr)
            bad = 1

    cited = cited_skills(step_files) if bad == 0 else set()
    allowlisted = set()
    for key in ALLOWLIST_KEYS:
        allowlisted.update(allow[key])

    dest_names: set[str] = set()
    index_names: set[str] = set()
    for md in dest_skill_mds(skills_root):
        name = skill_dir_name(md)
        if is_paved_road_index(md):
            index_names.add(name)
            continue
        dest_names.add(name)

    for name in sorted(dest_names):
        if name in cited or name in allowlisted:
            continue
        print("FAIL: dest skill %s is neither a steps.json skill backing nor allowlisted" % name, file=sys.stderr)
        bad = 1

    for name in sorted(allowlisted):
        if name in dest_names:
            if name in cited:
                print("FAIL: allowlisted dest skill %s is cited by steps.json; drop it" % name, file=sys.stderr)
                bad = 1
            continue
        print("FAIL: allowlist names missing dest skill %s" % name, file=sys.stderr)
        bad = 1

    if bad:
        return 1
    print("OK: PAVED_ROAD coverage dest=%d cited=%d allowlisted=%d index=%d" % (len(dest_names), len(cited), len(allowlisted), len(index_names)))
    return 0


def _cmd_generate(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="paved_road.py generate")
    ap.add_argument("--steps", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    try:
        doc = load_steps(args.steps)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    out = args.out or (args.steps.parent / "audit.json")
    write_audit(out, doc)
    print("OK: wrote %s" % out)
    return 0


def _cmd_sync(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="paved_road.py sync")
    ap.add_argument("--skill-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    rc, msg = sync_audit(args.skill_dir)
    stream = sys.stderr if rc else sys.stdout
    print(("FAIL: " if rc else "") + msg if rc else msg, file=stream)
    return rc


def _cmd_audit(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="paved_road.py audit")
    ap.add_argument("task_id", nargs="?", help="t_… (reads $HERMES_HOME/kanban/logs)")
    ap.add_argument("--log", type=Path)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--steps", type=Path, required=True)
    args = ap.parse_args(argv)
    log = resolve_log(args.task_id, args.log)
    if log is None:
        return 2
    return audit_paths(log, args.root, args.steps)


def _cmd_coverage(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="paved_road.py coverage")
    ap.add_argument("--root", type=Path)
    args = ap.parse_args(argv)
    return coverage(args.root)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: paved_road.py coverage|audit|generate|sync [args]", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "coverage":
        return _cmd_coverage(rest)
    if cmd == "audit":
        return _cmd_audit(rest)
    if cmd == "generate":
        return _cmd_generate(rest)
    if cmd == "sync":
        return _cmd_sync(rest)
    print("FAIL: unknown command %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
