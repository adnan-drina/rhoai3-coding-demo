"""Bounded M5 delivery: eligibility, idempotent mint, pipeline, deploy, live.

M4 close is not ship. Delivery is an assisted continuation with its own
budget. Application values come from ``delivery.yaml`` (or the project's
``decisions.yaml`` security section); this module does not branch on a
specimen name.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from planner.canonical import load_json, sha256_file, write_canonical
from planner.paths import (
    COVERAGE_ACCOUNT,
    DELIVERY_BUDGET,
    DELIVERY_CANDIDATE,
    DELIVERY_CONTRACT,
    DELIVERY_DEPLOYMENT,
    DELIVERY_DIR,
    DELIVERY_ELIGIBILITY,
    DELIVERY_LIVE,
    DELIVERY_PIPELINE,
    DELIVERY_START,
    FROZEN_COVERAGE_ACCOUNT,
    FROZEN_COVERAGE_HISTORY,
    FROZEN_COVERAGE_SOURCE,
    LOOP_CARDS,
    LOOP_STEPS,
    M5_VERDICT,
    PARITY_DIR,
    PIT_MEASUREMENT,
    TYPE_INVENTORY,
    VERIFY_RUN,
    WORKLIST,
)

Runner = Callable[[list[str]], tuple[int, str, str]]

SCHEMA_ELIGIBILITY = "rhoai3.m5-eligibility/v1"
SCHEMA_START = "rhoai3.m5-start/v1"
SCHEMA_CANDIDATE = "rhoai3.m5-candidate/v1"
SCHEMA_PIPELINE = "rhoai3.m5-pipeline/v1"
SCHEMA_DEPLOYMENT = "rhoai3.m5-deployment/v1"
SCHEMA_LIVE = "rhoai3.m5-live/v1"
SCHEMA_VERDICT = "rhoai3.m5-verdict/v1"
SCHEMA_BUDGET = "rhoai3.m5-budget/v1"

STAGES = ("prepare", "push", "accept")
STAGE_LABELS = {
    "prepare": "M5 PREFLIGHT",
    "push": "M5 DEPLOY",
    "accept": "M5 VALIDATE",
}
STAGE_TITLES = {
    "prepare": "M5 PREFLIGHT — release candidate",
    "push": "M5 DEPLOY — CI/CD and deployment",
    "accept": "M5 VALIDATE — live acceptance and handover",
}
STAGE_RUNTIME = {"prepare": "1h", "push": "3h", "accept": "1h"}
STAGE_WRITES = {
    "prepare": ["verification/delivery/", "k8s/"],
    "push": ["verification/delivery/"],
    "accept": ["verification/delivery/", "evidence/verdicts/m5-verdict.json"],
}
ENTRY_CMD = "python3 .hermes/skills/paved-road/paved-road-m5/scripts/start-m5-delivery.py --root ."
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}", re.I)
TASK_ID_RE = re.compile(r"^t_[A-Za-z0-9]+$")
DEFAULT_SWAGGER = "/q/swagger-ui"
DEFAULT_OPENAPI = "/q/openapi"

M4_VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
RELEASE_BLOCKERS = Path("verification") / "loop" / "release-blockers.json"
DECISIONS = Path("decisions.yaml")
G1_PIN_CANDIDATES = (
    Path("evidence") / "verdicts" / "g1-kill-ratio-pin.json",
    Path("evidence") / "derived" / "g1-kill-ratio-pin.json",
)
G1_PIN_SCHEMA = "migration/g1-kill-ratio-pin/v2-dual-denominator"
G1_BAR_SOURCES = frozenset({"ratchet_from_measured", "declared_engineering_target"})
PIT_MEASUREMENT_SCHEMA = "migration/pit-measurement/v1"
COVERAGE_SNAPSHOT_SCHEMA = "rhoai3.m4-coverage-snapshot/v1"
G1_PIN_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "gates" / "check-domain-parity" / "scripts" / "pin-kill-ratio-from-pit.py"
PARITY_RECEIPT = PARITY_DIR / "receipt.json"
COVERAGE_DISCHARGE = DELIVERY_DIR / "coverage-discharge.json"
DISCHARGE_SCHEMA = "rhoai3.coverage-discharge/v1"
# M4 close always records ship:false. Those rows, and the M4 verdict's
# explanatory prose, are historical context — not M5 release obligations.
HISTORICAL_KINDS = frozenset({"not-shipped", "verdict-reason"})
QUALIFICATION_META = {
    "parity-receipt": {
        "owner": "parity measurement on the delivery candidate",
        "evidence": "verification/parity/receipt.json",
        "resolution": "every remaining entry point measures PASS (or a named, evidenced descope) on this candidate",
    },
    "capability-gap": {
        "owner": "source capability / parity qualification",
        "evidence": "verification/parity/receipt.json coverage_gaps",
        "resolution": "the named scenario is demonstrated or retired with evidence; a 404-vs-200 qualification is not a destination FAIL",
    },
    "coverage-account": {
        "owner": "coverage-account.json / M4 coverage_account",
        "evidence": "evidence/verdicts/coverage-account.json",
        "resolution": "unique original remaining-gap identities from preserved M4 evidence are discharged against a candidate-bound account; count-only matching is not a discharge; closed M4 bytes stay put",
    },
    "cors-gap": {
        "owner": "restore-source-response-shape",
        "evidence": "verification/parity/receipt.json cors.gaps",
        "resolution": "named CORS gaps close against the source oracles",
    },
    "g1-kill-ratio": {
        "owner": "check-domain-parity / pin-kill-ratio-from-pit.py",
        "evidence": "evidence/derived/g1-kill-ratio-pin.json",
        "resolution": "producer-bound live mutationCoverage pin evaluates PASS with the threshold pinned; conflicting identities, inconsistent counts, or stored/recomputed disagreement are not PASS; do not invent PASS, decorate a pin, or author a waiver",
    },
}


def _run(argv: list[str], *, cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def git_rev(root: Path, runner: Runner | None = None) -> str:
    code, out, err = (runner or _run)(["git", "-C", str(root), "rev-parse", "HEAD"])
    if code != 0:
        return ""
    return (out or "").strip()


def git_remote_name(root: Path, runner: Runner | None = None) -> str:
    code, out, _ = (runner or _run)(["git", "-C", str(root), "remote", "get-url", "origin"])
    if code != 0:
        return ""
    url = (out or "").strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.rsplit("/", 1)[-1]


def close_row(steps: dict[str, Any] | None) -> dict[str, Any] | None:
    rows = [r for r in ((steps or {}).get("rejected") or []) if isinstance(r, dict) and r.get("kind") == "close"]
    if not rows:
        return None
    return rows[-1]


def _count(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    raw = str(value if value is not None else "0").strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return 0


def remaining_from_coverage(cov: dict[str, Any]) -> int:
    summary = cov.get("summary") if isinstance(cov.get("summary"), dict) else {}
    if summary:
        n = _count(summary.get("remaining_gaps"))
        if n:
            return n
    return _count(cov.get("remaining_gaps"))


def remaining_ids_from_coverage(cov: dict[str, Any]) -> list[str]:
    from_list = _path_ids(cov.get("remaining_gaps"))
    if from_list:
        return from_list
    rows = cov.get("rows") if isinstance(cov.get("rows"), list) else []
    return [str(r.get("path")) for r in rows if isinstance(r, dict) and r.get("remaining_gap") and r.get("path")]


def _path_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            path = str(item.get("path") or item.get("id") or "")
        else:
            path = str(item or "")
        if path:
            out.append(path)
    return out


def _unique_ids(ids: list[str]) -> list[str] | None:
    if len(ids) != len(set(ids)):
        return None
    return list(ids)


def _bound_candidate_sha(doc: dict[str, Any]) -> str:
    identity = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    return str(doc.get("candidate_sha") or identity.get("candidate_sha") or "").strip()


def _coverage_snapshot_binding(root: Path) -> dict[str, Any]:
    path = root / FROZEN_COVERAGE_SOURCE
    if not path.is_file():
        return {}
    try:
        doc = load_json(path)
    except Exception:
        return {}
    return doc if isinstance(doc, dict) else {}


def _m4_coverage_card_id(root: Path) -> str:
    vp = root / M4_VERDICT
    if not vp.is_file():
        return ""
    try:
        verdict = load_json(vp)
    except Exception:
        return ""
    if not isinstance(verdict, dict):
        return ""
    return str(verdict.get("card_id") or "").strip()


def _binding_card_id(src: dict[str, Any]) -> str:
    return str(src.get("card_id") or "").strip()


def _snapshot_matches_card(src: dict[str, Any], card_id: str) -> bool:
    bound = _binding_card_id(src)
    return bool(card_id) and bool(bound) and bound == card_id


def _load_coverage_doc(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = load_json(path)
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None


def load_preserved_coverage_account(root: Path) -> dict[str, Any] | None:
    """Coverage account snapshotted for the M4 card currently being discharged.

    Live coverage-account.json is never a substitute. An unbound freeze or a
    snapshot bound to a different card is not this M4's original identities.
    """
    card_id = _m4_coverage_card_id(root)
    if not card_id:
        return None
    frozen = root / FROZEN_COVERAGE_ACCOUNT
    src = _coverage_snapshot_binding(root)
    if frozen.is_file() and _snapshot_matches_card(src, card_id):
        return _load_coverage_doc(frozen)
    hist = root / FROZEN_COVERAGE_HISTORY / card_id
    if not hist.is_dir():
        return None
    matches: list[tuple[str, Path]] = []
    for account_p in hist.rglob("coverage-account.json"):
        bind_p = account_p.parent / "coverage-account.source.json"
        bind = _load_coverage_doc(bind_p) or {}
        if _snapshot_matches_card(bind, card_id):
            bound_at = str(bind.get("bound_at") or bind.get("verdict_sha256") or "")
            matches.append((bound_at, account_p))
    if not matches:
        return None
    matches.sort()
    return _load_coverage_doc(matches[-1][1])


def _archive_frozen_coverage(root: Path) -> None:
    frozen = root / FROZEN_COVERAGE_ACCOUNT
    if not frozen.is_file():
        return
    src = _coverage_snapshot_binding(root)
    card = _binding_card_id(src) or "unbound"
    digest = str(src.get("verdict_sha256") or "unknown").strip() or "unknown"
    dest = root / FROZEN_COVERAGE_HISTORY / card / digest[:16]
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(frozen, dest / "coverage-account.json")
    src_p = root / FROZEN_COVERAGE_SOURCE
    if src_p.is_file():
        shutil.copy2(src_p, dest / "coverage-account.source.json")
    elif src:
        write_canonical(dest / "coverage-account.source.json", src)


def original_coverage_obligation_ids(root: Path) -> list[str] | None:
    """Unique original remaining-gap ids from preserved M4-era evidence.

    Live coverage-account.json is not a source: it is the supporting account
    and can be rewritten. Count-only M4 remaining_gaps is not an identity.
    A freeze bound to a different M4 card is not this discharge's original set.
    """
    sources: list[list[str]] = []
    verdict_p = root / M4_VERDICT
    if verdict_p.is_file():
        try:
            verdict = load_json(verdict_p)
        except Exception:
            verdict = {}
        acct = verdict.get("coverage_account") if isinstance(verdict.get("coverage_account"), dict) else {}
        from_list = _path_ids(acct.get("remaining_gaps"))
        from_rows = [str(r.get("path")) for r in (acct.get("rows") or [])
                     if isinstance(r, dict) and r.get("remaining_gap") and r.get("path")]
        if from_list:
            sources.append(from_list)
        if from_rows:
            sources.append(from_rows)
    blockers_p = root / RELEASE_BLOCKERS
    if blockers_p.is_file():
        try:
            doc = load_json(blockers_p)
        except Exception:
            doc = {}
        blocker_ids: list[str] = []
        for row in (doc.get("outstanding") or []):
            if not isinstance(row, dict) or str(row.get("kind") or "") != "coverage-account":
                continue
            blocker_ids.extend(str(x) for x in (row.get("ids") or []) if str(x))
        if blocker_ids:
            sources.append(blocker_ids)
    snap = load_preserved_coverage_account(root)
    if snap is not None:
        snap_ids = remaining_ids_from_coverage(snap)
        if snap_ids:
            sources.append(snap_ids)
    unique_sets: list[set[str]] = []
    for src in sources:
        if _unique_ids(src) is None:
            return None
        unique_sets.append(set(src))
    if not unique_sets or not unique_sets[0]:
        return None
    first = unique_sets[0]
    for other in unique_sets[1:]:
        if other != first:
            return None
    return sorted(first)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _enrich(row: dict[str, Any]) -> dict[str, Any]:
    meta = QUALIFICATION_META.get(str(row.get("kind") or ""))
    if not meta:
        return row
    out = dict(row)
    out.setdefault("owner", meta["owner"])
    out.setdefault("evidence", meta["evidence"])
    out.setdefault("resolution", meta["resolution"])
    return out


def measured_candidate_sha(root: Path, *, runner: Runner | None = None, explicit: str = "") -> str:
    """Delivery candidate, else the measured verify-run tree, else git HEAD."""
    sha = str(explicit or "").strip()
    if sha:
        return sha
    cand = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    sha = str(cand.get("candidate_sha") or "").strip()
    if sha:
        return sha
    run = load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {}
    sha = str(run.get("candidate_sha256") or run.get("candidate_sha") or "").strip()
    if sha:
        return sha
    return git_rev(root, runner)


def delivery_candidate_sha(root: Path, *, runner: Runner | None = None) -> str:
    return measured_candidate_sha(root, runner=runner)


def preserve_m4_coverage_account(
    root: Path,
    *,
    card_id: str = "",
    verdict_sha256: str = "",
    receipt_sha256: str = "",
    parity_receipt_sha256: str = "",
) -> None:
    """Snapshot the live coverage account for one M4 card/verdict.

    Bind/close lifecycle writes this. A later live account is never copied
    onto a missing historical snapshot. Composer does not freeze. Never
    touches m4-verdict.json.
    """
    live = root / COVERAGE_ACCOUNT
    if not live.is_file():
        return
    card_id = str(card_id or "").strip() or _m4_coverage_card_id(root)
    if not card_id:
        return
    vp = root / M4_VERDICT
    if not str(verdict_sha256 or "").strip() and vp.is_file():
        try:
            verdict_sha256 = sha256_file(vp)
        except Exception:
            verdict_sha256 = ""
    if vp.is_file() and not (receipt_sha256 and parity_receipt_sha256):
        try:
            verdict = load_json(vp)
        except Exception:
            verdict = {}
        if isinstance(verdict, dict):
            receipt_sha256 = str(receipt_sha256 or verdict.get("receipt_sha256") or "").strip()
            parity_receipt_sha256 = str(
                parity_receipt_sha256 or verdict.get("parity_receipt_sha256") or ""
            ).strip()
    frozen = root / FROZEN_COVERAGE_ACCOUNT
    src = _coverage_snapshot_binding(root)
    if frozen.is_file() and _snapshot_matches_card(src, card_id):
        return
    if frozen.is_file():
        _archive_frozen_coverage(root)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(live.read_bytes())
    write_canonical(root / FROZEN_COVERAGE_SOURCE, {
        "schema": COVERAGE_SNAPSHOT_SCHEMA,
        "card_id": card_id,
        "verdict_sha256": str(verdict_sha256 or ""),
        "receipt_sha256": str(receipt_sha256 or ""),
        "parity_receipt_sha256": str(parity_receipt_sha256 or ""),
        "account_path": FROZEN_COVERAGE_ACCOUNT.as_posix(),
    })


def _g1_evaluate():
    spec = importlib.util.spec_from_file_location("pin_kill_ratio_from_pit", G1_PIN_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("G-1 evaluator %s is missing" % G1_PIN_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate


def _int_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _measurement_stats(measurement: Any) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(measurement, dict) or not measurement:
        return None, "missing measurements"
    generated = _int_count(measurement["generated"] if "generated" in measurement else measurement.get("mutations_total"))
    killed = _int_count(measurement.get("killed"))
    if generated is None or killed is None:
        return None, "missing measurements"
    if "attempted" in measurement:
        attempted = _int_count(measurement.get("attempted"))
        if attempted is None:
            return None, "missing measurements"
    else:
        survived = _int_count(measurement.get("survived") if "survived" in measurement else 0)
        timed_out = _int_count(measurement.get("timed_out") if "timed_out" in measurement else 0)
        if survived is None or timed_out is None:
            return None, "missing measurements"
        attempted = killed + survived + timed_out
    if not (0 <= killed <= attempted <= generated):
        return None, "inconsistent mutation counts"
    return {
        "generated": generated,
        "attempted": attempted,
        "killed": killed,
        "coverage_ratio": (attempted / generated) if generated else None,
        "kill_attempted_ratio": (killed / attempted) if attempted else None,
        "kill_generated_ratio": (killed / generated) if generated else None,
    }, ""


def _pin_identity_shas(data: dict[str, Any]) -> list[str]:
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    found: list[str] = []
    for raw in (data.get("candidate_sha"), data.get("measured_sha"), data.get("git_sha"),
                identity.get("candidate_sha"), identity.get("git_sha"),
                measurement.get("candidate_sha"),
                scope.get("candidate_sha"), provenance.get("candidate_sha"),
                provenance.get("git_sha")):
        sha = str(raw or "").strip()
        if sha and len(sha) != 64:
            found.append(sha)
    return found


def _pin_bound_sha(data: dict[str, Any]) -> tuple[str, str]:
    shas = _pin_identity_shas(data)
    unique: list[str] = []
    for sha in shas:
        if sha not in unique:
            unique.append(sha)
    if not unique:
        return "", "G-1 pin is not bound to the delivery candidate"
    if len(unique) > 1:
        return "", "conflicting candidate identities"
    return unique[0], ""


def _truthy_pass(value: Any) -> bool | None:
    if value in (True, "true", "yes", 1):
        return True
    if value in (False, "false", "no", 0):
        return False
    return None


def _stored_evaluation_agrees(stored: dict[str, Any], ev: dict[str, Any]) -> bool:
    if "pass" in stored:
        stored_pass = _truthy_pass(stored.get("pass"))
        if stored_pass is None or stored_pass != bool(ev.get("pass")):
            return False
    for key in ("killed", "attempted", "generated"):
        if key not in stored:
            continue
        got = _int_count(stored.get(key))
        if got is None or got != ev.get(key):
            return False
    for key in ("coverage_ratio", "kill_attempted_ratio", "kill_generated_ratio"):
        if key not in stored or stored.get(key) is None:
            continue
        recomputed = ev.get(key)
        try:
            if recomputed is None or abs(float(stored[key]) - float(recomputed)) > 1e-9:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _threshold_explicitly_pinned(data: dict[str, Any]) -> bool:
    return data.get("status") == "PINNED" or data.get("g1_kill_ratio_threshold_pinned") in (True, "true", "yes", 1)


def _fail_g1(rel: str, detail: str, *, pinned: bool = False) -> dict[str, Any]:
    return {"pass": False, "pinned": pinned, "value": "", "path": rel, "detail": detail}


def evaluate_g1_pin(data: dict[str, Any], *, candidate_sha: str, rel: str) -> dict[str, Any]:
    """Score one pin artifact. Schema name alone does not pin a threshold."""
    schema = str(data.get("schema") or "")
    if schema != G1_PIN_SCHEMA:
        return _fail_g1(rel, "unsupported pin schema %s" % (schema or "(missing)"))
    bound, bind_err = _pin_bound_sha(data)
    if bind_err:
        return _fail_g1(rel, bind_err)
    if not candidate_sha or bound != candidate_sha:
        return _fail_g1(rel, "G-1 pin is bound to a foreign candidate")
    stats, err = _measurement_stats(data.get("measurement"))
    if stats is None:
        return _fail_g1(rel, err)
    threshold = data.get("threshold") if isinstance(data.get("threshold"), dict) else {}
    if str(threshold.get("source") or "") not in G1_BAR_SOURCES:
        return _fail_g1(rel, "unsupported threshold source")
    try:
        coverage_min = float(threshold["coverage_min"])
        kill_attempted_min = float(threshold["kill_attempted_min"])
    except (KeyError, TypeError, ValueError):
        return _fail_g1(rel, "threshold contract missing coverage_min/kill_attempted_min")
    if not (0 < coverage_min <= 1) or not (0 < kill_attempted_min <= 1):
        return _fail_g1(rel, "threshold policy violated")
    raw_kg = threshold.get("kill_generated_min")
    kill_generated_min = float(raw_kg) if raw_kg is not None else None
    if kill_generated_min is not None and not (0 < kill_generated_min <= 1):
        return _fail_g1(rel, "threshold policy violated")
    eps = 1e-9
    if stats["coverage_ratio"] is not None and abs(stats["coverage_ratio"] - coverage_min) < eps:
        return _fail_g1(rel, "circular measured_from_this_run is forbidden")
    if stats["kill_attempted_ratio"] is not None and abs(stats["kill_attempted_ratio"] - kill_attempted_min) < eps:
        return _fail_g1(rel, "circular measured_from_this_run is forbidden")
    if (kill_generated_min is not None and stats["kill_generated_ratio"] is not None
            and abs(stats["kill_generated_ratio"] - kill_generated_min) < eps):
        return _fail_g1(rel, "circular measured_from_this_run is forbidden")
    ev = _g1_evaluate()(stats, coverage_min, kill_attempted_min, kill_generated_min)
    stored = data.get("evaluation_against_measurement") if isinstance(data.get("evaluation_against_measurement"), dict) else {}
    if stored and not _stored_evaluation_agrees(stored, ev):
        return _fail_g1(rel, "stored evaluation disagrees with recomputed evaluation")
    token = str(data.get("g1_kill_ratio") or "").upper()
    if token == "PASS" and not ev.get("pass"):
        return _fail_g1(rel, "contradictory G-1 fields: PASS token without evaluator PASS")
    pinned = _threshold_explicitly_pinned(data)
    if not pinned:
        return _fail_g1(rel, "threshold is not pinned (schema name is not a pin)")
    if not ev.get("pass"):
        return _fail_g1(rel, "kill-ratio pin at %s is not PASS" % rel, pinned=True)
    return {"pass": True, "pinned": True, "value": "PASS", "path": rel,
            "detail": "pinned G-1 kill-ratio PASS at %s" % rel}


def _hex_len(value: str, length: int) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == length and all(c in "0123456789abcdef" for c in s)


def _hex40(value: str) -> bool:
    return _hex_len(value, 40)


def _hex64(value: str) -> bool:
    return _hex_len(value, 64)


def _agreeing_hex(length: int, *values: str) -> str:
    found: list[str] = []
    for raw in values:
        s = str(raw or "").strip()
        if not s:
            continue
        if not _hex_len(s, length):
            return ""
        key = s.lower()
        if key not in found:
            found.append(key)
    if len(found) != 1:
        return ""
    return found[0]


def _embedded_xml_digest(data: dict[str, Any]) -> str:
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    return _agreeing_hex(
        64,
        str(provenance.get("mutations_xml_sha256") or ""),
        str(measurement.get("mutations_xml_sha256") or ""),
    )


def _pin_tree_digest(data: dict[str, Any]) -> str:
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    return _agreeing_hex(
        64,
        str(provenance.get("tree_sha256") or ""),
        str(identity.get("tree_sha256") or ""),
    )


def _g1_on_disk_provenance_error(root: Path, data: dict[str, Any], candidate_sha: str) -> str:
    """Require complete producer candidate/tree/report bindings on pin and receipt."""
    path = root / PIT_MEASUREMENT
    if not path.is_file():
        return "missing measurement provenance"
    try:
        receipt = load_json(path)
    except Exception:
        return "missing measurement provenance"
    if not isinstance(receipt, dict) or str(receipt.get("schema") or "") != PIT_MEASUREMENT_SCHEMA:
        return "missing measurement provenance"
    bound, bind_err = _pin_bound_sha(data)
    if bind_err:
        return bind_err
    pin_report = _embedded_xml_digest(data)
    pin_tree = _pin_tree_digest(data)
    receipt_candidate = _agreeing_hex(
        40,
        str(receipt.get("candidate_sha") or ""),
        str(receipt.get("git_sha") or ""),
    )
    receipt_report = str(receipt.get("mutations_xml_sha256") or "").strip()
    receipt_tree = str(receipt.get("tree_sha256") or "").strip()
    if not (
        _hex40(bound)
        and _hex40(candidate_sha)
        and _hex40(receipt_candidate)
        and _hex64(pin_report)
        and _hex64(receipt_report)
        and _hex64(pin_tree)
        and _hex64(receipt_tree)
    ):
        return "missing measurement provenance"
    if receipt_candidate != bound.lower() or bound.lower() != candidate_sha.lower():
        return "measurement provenance does not match the delivery candidate"
    if pin_report != receipt_report.lower():
        return "measurement provenance does not match the PIT report digest"
    if pin_tree != receipt_tree.lower():
        return "measurement provenance does not match the product tree"
    return ""


def read_g1_kill_ratio(root: Path, *, candidate_sha: str = "") -> dict[str, Any]:
    """Pinned G-1 kill-ratio from evidence. Never invents PASS."""
    root = Path(root)
    candidate_sha = str(candidate_sha or delivery_candidate_sha(root)).strip()
    paths: list[Path] = [root / p for p in G1_PIN_CANDIDATES]
    vdir = root / "evidence" / "verdicts"
    if vdir.is_dir():
        paths.extend(sorted(vdir.glob("*kill-ratio*pin*.json")))
    seen: set[Path] = set()
    failures: list[dict[str, Any]] = []
    for path in paths:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            data = load_json(path)
        except Exception:
            continue
        if not isinstance(data, dict) or not data:
            continue
        result = evaluate_g1_pin(data, candidate_sha=candidate_sha, rel=_rel(path, root))
        if result.get("pass") and result.get("pinned"):
            why = _g1_on_disk_provenance_error(root, data, candidate_sha)
            if why:
                result = _fail_g1(_rel(path, root), why, pinned=True)
                failures.append(result)
                continue
            return result
        failures.append(result)
    if failures:
        return failures[0]
    return {"pass": False, "pinned": False, "value": "", "path": "",
            "detail": "no pinned G-1 kill-ratio PASS on the delivery candidate"}


def _discharge_doc(root: Path) -> dict[str, Any] | None:
    dedicated = root / COVERAGE_DISCHARGE
    if dedicated.is_file():
        try:
            doc = load_json(dedicated)
        except Exception:
            return None
        if isinstance(doc, dict):
            return doc
    cov_p = root / COVERAGE_ACCOUNT
    if cov_p.is_file():
        try:
            cov = load_json(cov_p)
        except Exception:
            return None
        if isinstance(cov, dict) and (cov.get("supersedes") or cov.get("candidate_sha")):
            return cov
    return None


def coverage_discharged(root: Path, *, candidate_sha: str, historical_count: int,
                        historical_ids: list[str]) -> tuple[bool, str]:
    """Validated supersession of historical coverage-account rows. M4 bytes stay put."""
    if historical_count <= 0:
        return False, ""
    if not historical_ids:
        return False, "original coverage obligation identities are not preserved"
    if _unique_ids(historical_ids) is None or len(historical_ids) != historical_count:
        return False, "original coverage obligation identities are not unique"
    doc = _discharge_doc(root)
    if not doc:
        return False, ""
    schema = str(doc.get("schema") or "")
    if schema not in {DISCHARGE_SCHEMA, "rhoai3.coverage-account/v1"}:
        return False, "unsupported discharge schema"
    bound = _bound_candidate_sha(doc)
    if not bound:
        return False, "coverage discharge is not bound to the delivery candidate"
    if not candidate_sha or bound != candidate_sha:
        return False, "coverage discharge is bound to a foreign candidate"
    supersedes = doc.get("supersedes") if isinstance(doc.get("supersedes"), dict) else {}
    if str(supersedes.get("kind") or "coverage-account") != "coverage-account":
        return False, "discharge does not name the coverage-account obligation"
    m4_p = root / M4_VERDICT
    claimed = str(supersedes.get("m4_verdict_sha256") or doc.get("m4_verdict_sha256") or "").strip()
    if not claimed or not m4_p.is_file():
        return False, "discharge does not bind the unchanged M4 verdict"
    if claimed != sha256_file(m4_p):
        return False, "discharge m4_verdict_sha256 does not match the closed M4 verdict bytes"
    ids = [str(x) for x in (supersedes.get("obligation_ids") or doc.get("obligation_ids") or []) if str(x)]
    if not ids:
        return False, "discharge names no obligation ids"
    if _unique_ids(ids) is None:
        return False, "discharge obligation ids are not unique"
    if set(ids) != set(historical_ids):
        return False, "discharge ids do not match the original coverage-account obligation"
    cov_p = root / COVERAGE_ACCOUNT
    if not cov_p.is_file():
        return False, "supporting coverage account is absent"
    cov = load_json(cov_p)
    if not isinstance(cov, dict):
        return False, "supporting coverage account is absent"
    support_bound = _bound_candidate_sha(cov)
    if not support_bound:
        return False, "coverage account is not bound to the delivery candidate"
    if support_bound != candidate_sha:
        return False, "coverage account is bound to a foreign candidate"
    if remaining_from_coverage(cov) != 0:
        return False, "current coverage-account still reports remaining gaps"
    by_path = {}
    for row in (cov.get("rows") or []):
        if isinstance(row, dict) and row.get("path"):
            by_path[str(row["path"])] = row
    for oid in ids:
        row = by_path.get(oid)
        if not row:
            return False, "obligation %s is not in the current account" % oid
        if row.get("remaining_gap") is not False:
            return False, "obligation %s is not replaced in the current account" % oid
    return True, "coverage-account discharged against candidate %s" % candidate_sha[:16]


def _parity_identities(root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    p = root / PARITY_RECEIPT
    if not p.is_file():
        return [], []
    try:
        doc = load_json(p)
    except Exception:
        return [], []
    caps: list[dict[str, Any]] = []
    cap_eps: set[str] = set()
    for g in (doc.get("coverage_gaps") or []):
        if not isinstance(g, dict):
            continue
        sid = str(g.get("scenario") or "")
        ep = str(g.get("entry_point") or "")
        if sid:
            caps.append({"id": sid, "entry_point": ep, "kind": str(g.get("kind") or ""),
                         "detail": str(g.get("reason") or sid)})
            if ep:
                cap_eps.add(ep)
    uncovered: list[str] = []
    for row in (doc.get("entry_points") or []):
        if not isinstance(row, dict):
            continue
        eid = str(row.get("entry_point") or row.get("id") or "")
        verdict = str(row.get("verdict") or "").upper()
        if eid and verdict not in {"PASS", "OK"} and eid not in cap_eps:
            uncovered.append(eid)
    return uncovered, caps


def outstanding_from_artifacts(root: Path, *, candidate_sha: str = "") -> list[dict[str, Any]]:
    """Genuine remaining release obligations. M4 ship:false is not one."""
    root = Path(root)
    candidate_sha = str(candidate_sha or delivery_candidate_sha(root)).strip()
    out: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    def add(row: dict[str, Any]) -> None:
        kind = str(row.get("kind") or "")
        if not kind or kind in HISTORICAL_KINDS:
            return
        row = _enrich(row)
        if kind in {"coverage-account", "g1-kill-ratio"}:
            for existing in out:
                if existing.get("kind") == kind:
                    existing["count"] = max(_count(existing.get("count")), _count(row.get("count")))
                    if row.get("ids") and not existing.get("ids"):
                        existing["ids"] = list(row["ids"])
                    if row.get("id") and not existing.get("id"):
                        existing["id"] = row["id"]
                    if row.get("detail") and len(str(row.get("detail"))) > len(str(existing.get("detail") or "")):
                        existing["detail"] = row["detail"]
                    return
            out.append(row)
            return
        key = (kind, str(row.get("id") or row.get("detail") or ""))
        if key in seen_keys:
            return
        seen_keys.add(key)
        out.append(row)

    blockers_p = root / RELEASE_BLOCKERS
    if blockers_p.is_file():
        doc = load_json(blockers_p)
        for row in (doc.get("outstanding") or []):
            if isinstance(row, dict):
                add(dict(row))
    historical_count = 0
    verdict_p = root / M4_VERDICT
    if verdict_p.is_file():
        verdict = load_json(verdict_p)
        acct = verdict.get("coverage_account") if isinstance(verdict.get("coverage_account"), dict) else {}
        historical_count = remaining_from_coverage(acct)
    cov_p = root / COVERAGE_ACCOUNT
    current_count = 0
    current_ids: list[str] = []
    if cov_p.is_file():
        cov = load_json(cov_p)
        current_count = remaining_from_coverage(cov)
        current_ids = remaining_ids_from_coverage(cov)
    original_ids = original_coverage_obligation_ids(root)
    discharged, _why = coverage_discharged(
        root, candidate_sha=candidate_sha, historical_count=historical_count,
        historical_ids=list(original_ids or []),
    )
    if discharged:
        out[:] = [r for r in out if r.get("kind") != "coverage-account"]
    elif current_count:
        add({"kind": "coverage-account", "id": "coverage-account",
             "count": current_count, "ids": current_ids,
             "detail": "%d remaining coverage gap(s) in coverage-account.json" % current_count})
    elif historical_count:
        add({"kind": "coverage-account", "id": "coverage-account",
             "count": historical_count, "ids": list(original_ids or []),
             "detail": "%d remaining coverage gap(s) from the M4 coverage account" % historical_count})
    uncovered, caps = _parity_identities(root)
    if caps:
        out[:] = [r for r in out if r.get("kind") not in {"capability-gap", "parity-receipt"}]
        for cap in caps:
            add({"kind": "capability-gap", "id": cap["id"], "entry_point": cap["entry_point"],
                 "count": 1, "detail": cap["detail"] or cap["id"]})
        if uncovered:
            add({"kind": "parity-receipt", "id": "parity-unmeasured",
                 "ids": uncovered, "count": len(uncovered),
                 "detail": "%d entry point(s) did not pass and are not the named capability gap" % len(uncovered)})
    elif uncovered:
        out[:] = [r for r in out if r.get("kind") != "parity-receipt"]
        add({"kind": "parity-receipt", "id": "parity-unmeasured",
             "ids": uncovered, "count": len(uncovered),
             "detail": "%d entry point(s) did not pass" % len(uncovered)})
    kill = read_g1_kill_ratio(root, candidate_sha=candidate_sha)
    if not (kill.get("pass") and kill.get("pinned")):
        add({"kind": "g1-kill-ratio", "id": "g1-kill-ratio", "count": 0, "detail": kill.get("detail") or ""})
    return out


def worklist_open_count(root: Path) -> int:
    p = root / WORKLIST
    if not p.is_file():
        return 0
    doc = load_json(p)
    return sum(1 for it in (doc.get("items") or []) if isinstance(it, dict) and str(it.get("id") or ""))


def assess_eligibility(root: Path, *, runner: Runner | None = None) -> dict[str, Any]:
    """Whether delivery may enter the pipeline. Does not waive coverage gaps."""
    root = Path(root)
    reasons: list[dict[str, str]] = []
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else {}
    closed = close_row(steps)
    verdict = load_json(root / M4_VERDICT) if (root / M4_VERDICT).is_file() else {}
    candidate = git_rev(root, runner)
    if not closed or not closed.get("closed"):
        reasons.append({"condition": "m4-closed", "evidence": str(LOOP_STEPS),
                        "owner": "M4 close / resume-after-m4.py",
                        "resolution": "close M4 through resume-after-m4.py on a bound verdict; do not dest-dispatch M5 from the M4 worker"})
    if not (root / M4_VERDICT).is_file():
        reasons.append({"condition": "m4-verdict", "evidence": str(M4_VERDICT),
                        "owner": "compose-m4-verdict", "resolution": "compose the M4 verdict and keep the original file"})
    if not candidate:
        reasons.append({"condition": "candidate-sha", "evidence": "git rev-parse HEAD",
                        "owner": "delivery implementer", "resolution": "inspect the current git HEAD; do not reuse a previously reported identity"})
    outstanding = outstanding_from_artifacts(root, candidate_sha=candidate)
    open_items = worklist_open_count(root)
    pipeline_eligible = not reasons
    kill = read_g1_kill_ratio(root, candidate_sha=candidate)
    # M4 ship:false is historical. Release eligibility is the existing contract
    # plus pinned kill-ratio evidence — never M4 already having shipped.
    release_eligible = pipeline_eligible and not outstanding and bool(kill.get("pass") and kill.get("pinned"))
    if pipeline_eligible and not release_eligible:
        reasons.append({"condition": "release-qualifications", "evidence": str(RELEASE_BLOCKERS),
                        "owner": "existing release contract",
                        "resolution": "record outstanding qualifications; M4 ship:false is not one; an empty repair worklist is not full release eligibility"})
    return {
        "schema": SCHEMA_ELIGIBILITY,
        "m4_card": str((closed or {}).get("card") or (verdict.get("card_id") or "")),
        "m4_verdict": str((closed or {}).get("verdict") or verdict.get("verdict") or ""),
        "m4_ship": bool(verdict.get("ship")),
        "g1_kill_ratio": kill.get("value") or "",
        "g1_kill_ratio_threshold_pinned": bool(kill.get("pass") and kill.get("pinned")),
        "candidate_sha": candidate,
        "accepted_revision": str((closed or {}).get("parity_receipt_sha256") or verdict.get("parity_receipt_sha256") or ""),
        "outstanding": outstanding,
        "worklist_open_count": open_items,
        "worklist_empty": open_items == 0,
        "pipeline_eligible": pipeline_eligible,
        "release_eligible": release_eligible,
        "reasons": reasons,
        "next": {"cmd": ENTRY_CMD, "owner": "delivery implementer",
                 "note": "assisted continuation attached to the closed M4 result; M4 worker must not dest-dispatch M5"},
    }


def record_eligibility(root: Path, eligibility: dict[str, Any] | None = None, *, runner: Runner | None = None) -> Path:
    doc = eligibility if eligibility is not None else assess_eligibility(root, runner=runner)
    path = Path(root) / DELIVERY_ELIGIBILITY
    path.parent.mkdir(parents=True, exist_ok=True)
    write_canonical(path, doc)
    return path


def default_budget() -> dict[str, Any]:
    return {"schema": SCHEMA_BUDGET, "max_retries": 1,
            "max_runtime": dict(STAGE_RUNTIME),
            "note": "separate from the original migration deadline; do not extend or rewrite that deadline"}


def idempotency_key(stage: str, close_card: str, candidate: str) -> str:
    return "m5:%s:%s:%s" % (stage, close_card, (candidate or "")[:16])


def plan_cards(eligibility: dict[str, Any]) -> list[dict[str, Any]]:
    close_card = str(eligibility.get("m4_card") or "")
    candidate = str(eligibility.get("candidate_sha") or "")
    planned: list[dict[str, Any]] = []
    parent = close_card
    for stage in STAGES:
        planned.append({
            "logical_id": "M5_%s" % stage.upper(),
            "stage": stage,
            "title": STAGE_TITLES[stage],
            "assignee": "implementer",
            "skills": ["paved-road-m5"],
            "parent": parent,
            "idempotency_key": idempotency_key(stage, close_card, candidate),
            "max_runtime": STAGE_RUNTIME[stage],
            "max_retries": 1,
            "write_set": list(STAGE_WRITES[stage]),
            "initial_status": "todo",
        })
        parent = "M5_%s" % stage.upper()
    return planned


def _card_id(card: dict[str, Any]) -> str:
    for k in ("id", "task_id"):
        v = card.get(k)
        if v:
            return str(v)
    return ""


def _native_key(card: dict[str, Any]) -> str:
    for k in ("idempotency_key", "idempotencyKey"):
        v = card.get(k)
        if v:
            return str(v)
    return ""


def parse_created_id(stdout: str) -> str:
    text = (stdout or "").strip()
    blob: Any = None
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                blob = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                blob = None
    if isinstance(blob, dict):
        for key in ("task_id", "id"):
            raw = blob.get(key)
            if raw and TASK_ID_RE.match(str(raw).strip()):
                return str(raw).strip()
        nested = blob.get("task")
        if isinstance(nested, dict):
            for key in ("task_id", "id"):
                raw = nested.get(key)
                if raw and TASK_ID_RE.match(str(raw).strip()):
                    return str(raw).strip()
    return ""


def existing_by_key(cards: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for card in cards:
        key = _native_key(card)
        if key:
            out[key] = card
    return out


def m5_body(plan: dict[str, Any], eligibility: dict[str, Any], type_sha: str) -> str:
    machine = {
        "task_id": plan["logical_id"],
        "role": "implementer",
        "phase": "M5",
        "refs": [{"key": "type-inventory", "path": str(TYPE_INVENTORY), "sha256": type_sha or "pending"}],
        "identity": {"stage": plan["stage"], "m4_card": eligibility.get("m4_card"),
                     "candidate_sha": eligibility.get("candidate_sha")},
        "files_writable": list(plan["write_set"]),
        "exit_criteria": [
            {"check": "skills", "assert": "skill_view paved-road-m5 first; run only this card's scripts"},
            {"check": "script", "cmd": _stage_cmd(plan["stage"])},
            {"check": "terminator", "assert": "kanban_request_review reviewer=reviewer; never kanban_complete on implementer; never dest-dispatch a duplicate pipeline or card"},
        ],
    }
    prose = [
        "# %s" % plan["title"],
        "",
        "Pinned skill: `paved-road-m5`. Writable: `%s`." % "`, `".join(plan["write_set"]),
        "Runtime `%s`, retries %s. Bind the closed M4 card `%s` and candidate `%s`."
        % (plan["max_runtime"], plan["max_retries"], eligibility.get("m4_card"), eligibility.get("candidate_sha")),
        "Do not waive outstanding qualifications, invent release gates, or substitute localhost for deployed acceptance.",
        "",
        "```json",
        json.dumps(machine, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(prose)


def _stage_cmd(stage: str) -> str:
    scripts = {
        "prepare": "python3 .hermes/skills/paved-road/paved-road-m5/scripts/prepare-release-candidate.py --root .",
        "push": "python3 .hermes/skills/paved-road/paved-road-m5/scripts/observe-app-push.py --root . && python3 .hermes/skills/paved-road/paved-road-m5/scripts/assert-deployed-app.py --root .",
        "accept": "python3 .hermes/skills/paved-road/paved-road-m5/scripts/live-acceptance.py --root . && python3 .hermes/skills/paved-road/paved-road-m5/scripts/compose-m5-verdict.py --root .",
    }
    return scripts[stage]


def argv_for_card(plan: dict[str, Any], body: str, *, hermes: str, parent_id: str, workspace: str) -> list[str]:
    argv = [hermes, "kanban", "create", plan["title"],
            "--body", body, "--assignee", plan["assignee"],
            "--idempotency-key", plan["idempotency_key"],
            "--max-runtime", plan["max_runtime"], "--max-retries", str(plan["max_retries"]),
            "--workspace", workspace]
    # Hermes 0.20.5 --initial-status accepts only blocked|running. Omit todo
    # so the board default (todo) applies; passing todo fails the mint.
    status = str(plan.get("initial_status") or "")
    if status in {"blocked", "running"}:
        argv.extend(["--initial-status", status])
    if parent_id:
        argv.extend(["--parent", parent_id])
    for skill in plan["skills"]:
        argv.extend(["--skill", skill])
    argv.append("--json")
    return argv


def start_delivery(root: Path, *, runner: Runner, hermes: str = "hermes",
                   execute: bool = False, workspace: str = "dir:/projects/modernized") -> dict[str, Any]:
    """Mint the three M5 cards or return the existing set. Never duplicates."""
    root = Path(root)
    from planner.outcome_protocol import select_protocol
    if select_protocol(root).outcome:
        # outcome-board runs pre-create the M5 stages at publication; a stage is GRANTED
        # (assigned) by the reconciler after its predicate, never minted here
        return {"ok": False, "blocked": True, "eligibility": {}, "created": [], "reused": [],
                "reason": "PROTOCOL_NOT_SERIAL: outcome-board/v1 grants the pre-created M5 stages",
                "failed_stage": STAGE_LABELS["prepare"]}
    eligibility = assess_eligibility(root, runner=runner)
    record_eligibility(root, eligibility)
    budget_p = root / DELIVERY_BUDGET
    if not budget_p.is_file():
        write_canonical(budget_p, default_budget())
    if not eligibility["pipeline_eligible"]:
        return {"ok": False, "blocked": True, "eligibility": eligibility,
                "created": [], "reused": [], "reason": "failed prerequisite",
                "failed_stage": STAGE_LABELS["prepare"]}
    planned = plan_cards(eligibility)
    code, out, err = runner([hermes, "kanban", "list", "--json"])
    cards = []
    if code == 0:
        text = out or ""
        start, obj = text.find("["), text.find("{")
        blob: Any = None
        try:
            if start >= 0 and (obj < 0 or start < obj):
                blob = json.loads(text[start:])
            elif obj >= 0:
                blob = json.loads(text[obj:])
            else:
                blob = json.loads(text)
        except json.JSONDecodeError:
            blob = None
        if isinstance(blob, list):
            cards = blob
        elif isinstance(blob, dict):
            cards = list(blob.get("tasks") or blob.get("cards") or blob.get("items") or [])
    prior = load_json(root / DELIVERY_START) if (root / DELIVERY_START).is_file() else {}
    prior_map = dict(prior.get("by_logical_id") or {}) if isinstance(prior, dict) else {}
    by_key = existing_by_key(cards)
    type_sha = sha256_file(root / TYPE_INVENTORY) if (root / TYPE_INVENTORY).is_file() else ""
    created: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    commands: list[list[str]] = []
    for plan in planned:
        existing = by_key.get(plan["idempotency_key"])
        if existing:
            tid = _card_id(existing)
            mapping[plan["logical_id"]] = tid
            reused.append({"logical_id": plan["logical_id"], "task_id": tid, "idempotency_key": plan["idempotency_key"]})
            continue
        parent_logical = plan["parent"]
        parent_id = mapping.get(parent_logical, parent_logical if TASK_ID_RE.match(str(parent_logical or "")) else "")
        body = m5_body(plan, eligibility, type_sha)
        argv = argv_for_card(plan, body, hermes=hermes, parent_id=parent_id, workspace=workspace)
        commands.append(argv)
        if not execute:
            mapping[plan["logical_id"]] = "t_pending_%s" % plan["stage"]
            created.append({"logical_id": plan["logical_id"], "task_id": "", "idempotency_key": plan["idempotency_key"], "argv": argv, "dry_run": True})
            continue
        code, out, err = runner(argv)
        if code != 0:
            return {"ok": False, "blocked": True, "eligibility": eligibility, "created": created, "reused": reused,
                    "reason": "mint failed for %s: %s" % (plan["logical_id"], (err or out)[:300]),
                    "failed_stage": STAGE_LABELS["prepare"]}
        tid = parse_created_id(out)
        if not tid:
            return {"ok": False, "blocked": True, "eligibility": eligibility, "created": created, "reused": reused,
                    "reason": "mint produced no t_* for %s" % plan["logical_id"], "failed_stage": STAGE_LABELS["prepare"]}
        mapping[plan["logical_id"]] = tid
        if prior_map.get(plan["logical_id"]) == tid:
            reused.append({"logical_id": plan["logical_id"], "task_id": tid, "idempotency_key": plan["idempotency_key"]})
        else:
            created.append({"logical_id": plan["logical_id"], "task_id": tid, "idempotency_key": plan["idempotency_key"]})
    result = {"ok": True, "blocked": False, "eligibility": eligibility, "created": created, "reused": reused,
              "by_logical_id": mapping, "commands": commands, "execute": execute}
    write_canonical(root / DELIVERY_START, {"schema": SCHEMA_START, **{k: v for k, v in result.items() if k != "commands"}})
    _register_delivery_cards(root, mapping)
    return result


def _register_delivery_cards(root: Path, mapping: dict[str, str]) -> None:
    path = root / LOOP_CARDS
    doc = load_json(path) if path.is_file() else {"schema": "rhoai3.loop-cards/v1", "control": {}}
    control = dict(doc.get("control") or {})
    names = {"M5_PREPARE": "m5_prepare", "M5_PUSH": "m5_push", "M5_ACCEPT": "m5_accept"}
    changed = False
    for logical, tid in mapping.items():
        key = names.get(logical)
        if key and tid and TASK_ID_RE.match(tid) and control.get(key) != tid:
            control[key] = tid
            changed = True
    if changed:
        doc["control"] = control
        path.parent.mkdir(parents=True, exist_ok=True)
        write_canonical(path, doc)


def load_delivery_contract(root: Path) -> dict[str, Any]:
    """Application contract. Missing fields stay missing; nothing is invented."""
    root = Path(root)
    for rel in (DELIVERY_CONTRACT, Path("verification/delivery/contract.yaml"), Path("verification/delivery/contract.json")):
        p = root / rel
        if not p.is_file():
            continue
        if p.suffix == ".json":
            doc = load_json(p)
        else:
            from planner.yamlite import load_yaml
            doc = load_yaml(p)
        if isinstance(doc, dict) and isinstance(doc.get("delivery"), dict):
            return dict(doc["delivery"])
        if isinstance(doc, dict):
            return dict(doc)
    return {}


def prepare_candidate(root: Path, *, runner: Runner | None = None, changes: list[str] | None = None) -> dict[str, Any]:
    root = Path(root)
    eligibility = assess_eligibility(root, runner=runner)
    record_eligibility(root, eligibility)
    if not eligibility["pipeline_eligible"]:
        doc = {"schema": SCHEMA_CANDIDATE, "ok": False, "failed_stage": STAGE_LABELS["prepare"],
               "eligibility": eligibility, "reason": "failed prerequisite"}
        write_canonical(root / DELIVERY_CANDIDATE, doc)
        return doc
    prev = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    prev_sha = str(prev.get("candidate_sha") or "")
    current_sha = str(eligibility.get("candidate_sha") or "")
    if prev_sha and current_sha and prev_sha != current_sha:
        archive = root / DELIVERY_DIR / "attempts" / prev_sha[:16]
        archive.mkdir(parents=True, exist_ok=True)
        for rel in (DELIVERY_CANDIDATE, DELIVERY_PIPELINE, DELIVERY_DEPLOYMENT, DELIVERY_LIVE):
            src = root / rel
            if src.is_file():
                (archive / src.name).write_bytes(src.read_bytes())
    contract = load_delivery_contract(root)
    m4_evidence = {
        "verdict": str(M4_VERDICT),
        "parity_receipt": "verification/parity/receipt.json",
        "blockers": str(RELEASE_BLOCKERS),
        "preserved": True,
    }
    doc = {
        "schema": SCHEMA_CANDIDATE,
        "ok": True,
        "failed_stage": "",
        "candidate_sha": eligibility["candidate_sha"],
        "m4_card": eligibility["m4_card"],
        "m4_verdict": eligibility["m4_verdict"],
        "m4_evidence": m4_evidence,
        "outstanding": eligibility["outstanding"],
        "pipeline_eligible": True,
        "release_eligible": eligibility["release_eligible"],
        "worklist_empty": eligibility["worklist_empty"],
        "changes_since_m4": list(changes or []),
        "prior_candidate_archived": prev_sha if prev_sha and prev_sha != current_sha else "",
        "contract": {
            "namespace": contract.get("namespace") or "",
            "repo": contract.get("repo") or git_remote_name(root, runner),
            "swagger_path": contract.get("swagger_path") or DEFAULT_SWAGGER,
            "openapi_path": contract.get("openapi_path") or DEFAULT_OPENAPI,
            "has_crud": bool(contract.get("crud")),
            "has_reads": bool(contract.get("reads")),
        },
        "note": "empty repair worklist is not full release eligibility",
    }
    write_canonical(root / DELIVERY_CANDIDATE, doc)
    return doc


def extract_digest(text: str) -> str:
    if not text:
        return ""
    m = DIGEST_RE.search(text)
    return m.group(0).lower() if m else ""


def pipeline_revision(run: dict[str, Any]) -> str:
    spec = run.get("spec") if isinstance(run.get("spec"), dict) else {}
    params = spec.get("params") or spec.get("parameters") or []
    if isinstance(params, list):
        for p in params:
            if isinstance(p, dict) and str(p.get("name") or "") == "revision":
                return str(p.get("value") or "")
    if isinstance(params, dict):
        return str(params.get("revision") or "")
    return str(spec.get("revision") or run.get("revision") or "")


def pipeline_succeeded(run: dict[str, Any]) -> bool:
    status = run.get("status") if isinstance(run.get("status"), dict) else {}
    if str(status.get("conditions") or "") and isinstance(status.get("conditions"), list):
        for c in status["conditions"]:
            if isinstance(c, dict) and str(c.get("type") or "") == "Succeeded":
                return str(c.get("status") or "") == "True" and str(c.get("reason") or "") != "None"
    return str(status.get("phase") or run.get("status") or "").lower() in {"succeeded", "success", "true"}


def pipeline_running(run: dict[str, Any]) -> bool:
    status = run.get("status") if isinstance(run.get("status"), dict) else {}
    if isinstance(status.get("conditions"), list):
        for c in status["conditions"]:
            if isinstance(c, dict) and str(c.get("type") or "") == "Succeeded" and str(c.get("status") or "") == "Unknown":
                return True
    return str(status.get("phase") or "").lower() in {"running", "started", "pending"}


def pipeline_digest(run: dict[str, Any]) -> str:
    status = run.get("status") if isinstance(run.get("status"), dict) else {}
    buckets = [
        status.get("pipelineResults"),
        status.get("taskResults"),
        status.get("results"),
        run.get("results"),
        run.get("task_results"),
    ]
    for child in (status.get("childReferences") or []):
        if isinstance(child, dict):
            nested = child.get("status") if isinstance(child.get("status"), dict) else {}
            buckets.extend([nested.get("results"), nested.get("taskResults")])
    for bucket in buckets:
        if not isinstance(bucket, list):
            continue
        for row in bucket:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            value = str(row.get("value") or "")
            if name.upper() in {"IMAGE_DIGEST", "DIGEST"} or "DIGEST" in name.upper():
                digest = extract_digest(value) or (value if value.startswith("sha256:") else "")
                if digest:
                    return digest.lower()
    return extract_digest(json.dumps(status))


def select_pipeline_run(runs: list[dict[str, Any]], candidate: str) -> dict[str, Any]:
    """Pick the app-push run for this revision. Refuse wrong-revision reuse."""
    matching = [r for r in runs if pipeline_revision(r) == candidate]
    others = [r for r in runs if pipeline_revision(r) and pipeline_revision(r) != candidate]
    if not matching:
        if others:
            return {"ok": False, "failed_stage": STAGE_LABELS["push"], "reason": "wrong-revision",
                    "detail": "PipelineRun revision %s is not candidate %s" % (pipeline_revision(others[0]), candidate),
                    "run": others[0]}
        return {"ok": False, "failed_stage": STAGE_LABELS["push"], "reason": "no-pipeline-run",
                "detail": "no app-push PipelineRun for candidate %s" % candidate, "run": {}}
    running = [r for r in matching if pipeline_running(r)]
    succeeded = [r for r in matching if pipeline_succeeded(r)]
    if running:
        return {"ok": True, "reuse": True, "running": True, "run": running[0], "candidate_sha": candidate}
    if succeeded:
        run = succeeded[-1]
        digest = pipeline_digest(run)
        return {"ok": True, "reuse": True, "running": False, "run": run, "candidate_sha": candidate,
                "image_digest": digest, "pipeline_ok": True}
    return {"ok": False, "failed_stage": STAGE_LABELS["push"], "reason": "pipeline-unsuccessful",
            "detail": "matching PipelineRun did not succeed", "run": matching[-1], "candidate_sha": candidate}


def observe_pipeline(root: Path, runs: list[dict[str, Any]], *, start_requested: bool = False) -> dict[str, Any]:
    root = Path(root)
    candidate_doc = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    candidate = str(candidate_doc.get("candidate_sha") or "")
    selected = select_pipeline_run(runs, candidate)
    if start_requested and selected.get("ok") and selected.get("reuse"):
        selected = dict(selected)
        selected["ok"] = False
        selected["reason"] = "duplicate-pipeline"
        selected["detail"] = "a matching PipelineRun already exists; do not start another"
        selected["failed_stage"] = STAGE_LABELS["push"]
    name = ""
    run = selected.get("run") if isinstance(selected.get("run"), dict) else {}
    meta = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    name = str(meta.get("name") or run.get("name") or "")
    digest = selected.get("image_digest") or pipeline_digest(run)
    if selected.get("ok") and not selected.get("running") and not digest:
        selected = dict(selected)
        selected["ok"] = False
        selected["reason"] = "missing-image-digest"
        selected["detail"] = "a commit-named image tag is not immutable image identity"
        selected["failed_stage"] = STAGE_LABELS["push"]
    doc = {
        "schema": SCHEMA_PIPELINE,
        "ok": bool(selected.get("ok") and not selected.get("running")),
        "failed_stage": selected.get("failed_stage") or (STAGE_LABELS["push"] if not selected.get("ok") else ""),
        "reason": selected.get("reason") or "",
        "detail": selected.get("detail") or "",
        "candidate_sha": candidate,
        "pipeline_run": name,
        "revision": pipeline_revision(run),
        "image_digest": digest,
        "reused": bool(selected.get("reuse")),
        "running": bool(selected.get("running")),
        "succeeded": pipeline_succeeded(run) if run else False,
    }
    write_canonical(root / DELIVERY_PIPELINE, doc)
    return doc


def deployment_issues(deployment: dict[str, Any], service: dict[str, Any],
                      route: dict[str, Any], endpoints: dict[str, Any],
                      image_digest: str, candidate: str) -> list[str]:
    issues: list[str] = []
    if not deployment:
        issues.append("deployment-missing")
        return issues
    spec = deployment.get("spec") if isinstance(deployment.get("spec"), dict) else {}
    status = deployment.get("status") if isinstance(deployment.get("status"), dict) else {}
    ready = int(status.get("readyReplicas") or 0)
    desired = int(spec.get("replicas") or 1)
    if ready < 1 or (desired and ready < desired):
        issues.append("deployment-not-ready")
    pod = ((spec.get("template") or {}).get("spec") or {}) if isinstance(spec.get("template"), dict) else {}
    containers = pod.get("containers") if isinstance(pod, dict) else []
    images = [str(c.get("image") or "") for c in containers if isinstance(c, dict)]
    image_ids = []
    for cs in (status.get("containerStatuses") or []):
        if isinstance(cs, dict):
            image_ids.append(str(cs.get("imageID") or cs.get("image") or ""))
    blob = " ".join(images + image_ids)
    found = extract_digest(blob)
    if image_digest and found and found != image_digest.lower():
        issues.append("image-mismatch")
    if image_digest and not found:
        # A revision tag on the pod template is not digest proof.
        if not any(image_digest.lower() in img.lower() for img in images + image_ids):
            issues.append("image-digest-absent")
    if not service:
        issues.append("service-missing")
    addrs = []
    if isinstance(endpoints, dict):
        for subset in (endpoints.get("subsets") or []):
            if isinstance(subset, dict):
                addrs.extend(subset.get("addresses") or [])
    if service and not addrs:
        issues.append("service-endpoints-missing")
    if not route:
        issues.append("route-missing")
    else:
        rspec = route.get("spec") if isinstance(route.get("spec"), dict) else {}
        tls = rspec.get("tls") if isinstance(rspec.get("tls"), dict) else {}
        host = route_host(route)
        if not host:
            issues.append("route-host-missing")
        if not tls:
            issues.append("route-not-https")
    if candidate and images and all(candidate not in img and (not image_digest or extract_digest(img) != image_digest.lower()) for img in images):
        # still OK if imageID carries the digest
        if "image-mismatch" not in issues and "image-digest-absent" not in issues and not found:
            issues.append("image-unproven")
    return issues


def route_host(route: dict[str, Any]) -> str:
    spec = route.get("spec") if isinstance(route.get("spec"), dict) else {}
    host = str(spec.get("host") or "").strip()
    if host:
        return host
    status = route.get("status") if isinstance(route.get("status"), dict) else {}
    for ing in (status.get("ingress") or []):
        if isinstance(ing, dict) and str(ing.get("host") or "").strip():
            return str(ing.get("host")).strip()
    return ""


def route_url(route: dict[str, Any]) -> str:
    host = route_host(route)
    if not host:
        return ""
    spec = route.get("spec") if isinstance(route.get("spec"), dict) else {}
    tls = spec.get("tls") if isinstance(spec.get("tls"), dict) else {}
    scheme = "https" if tls else "http"
    return "%s://%s" % (scheme, host)


def deployment_from_app_pods(pods: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Build a Deployment-shaped view from app pods when Deployment GET is fenced."""
    app: list[dict[str, Any]] = []
    for pod in pods:
        if not isinstance(pod, dict):
            continue
        status = pod.get("status") if isinstance(pod.get("status"), dict) else {}
        containers = status.get("containerStatuses") or []
        names = [str(c.get("name") or "") for c in containers if isinstance(c, dict)]
        if name and name in names:
            app.append(pod)
    if not app:
        return {}
    ready = 0
    image_ids: list[str] = []
    images: list[str] = []
    for pod in app:
        status = pod.get("status") if isinstance(pod.get("status"), dict) else {}
        for cs in (status.get("containerStatuses") or []):
            if not isinstance(cs, dict):
                continue
            if str(cs.get("name") or "") != name:
                continue
            if cs.get("ready"):
                ready += 1
            if cs.get("imageID"):
                image_ids.append(str(cs["imageID"]))
            if cs.get("image"):
                images.append(str(cs["image"]))
    image = images[0] if images else ""
    return {
        "spec": {"replicas": max(1, len(app)), "template": {"spec": {"containers": [{"name": name, "image": image}]}}},
        "status": {"readyReplicas": ready, "containerStatuses": [
            {"name": name, "image": image, "imageID": image_ids[0] if image_ids else image, "ready": ready > 0}
        ]},
    }


def assert_deployed(root: Path, *, deployment: dict[str, Any], service: dict[str, Any],
                    route: dict[str, Any], endpoints: dict[str, Any]) -> dict[str, Any]:
    root = Path(root)
    pipe = load_json(root / DELIVERY_PIPELINE) if (root / DELIVERY_PIPELINE).is_file() else {}
    candidate = str(pipe.get("candidate_sha") or "")
    digest = str(pipe.get("image_digest") or "")
    if pipe.get("succeeded") and not deployment:
        issues = ["deployment-missing"]
    else:
        issues = deployment_issues(deployment, service, route, endpoints, digest, candidate)
    url = route_url(route)
    deployed_image = ""
    spec = deployment.get("spec") if isinstance(deployment.get("spec"), dict) else {}
    for c in (((spec.get("template") or {}).get("spec") or {}).get("containers") or []):
        if isinstance(c, dict) and c.get("image"):
            deployed_image = str(c.get("image"))
            break
    status = deployment.get("status") if isinstance(deployment.get("status"), dict) else {}
    for cs in (status.get("containerStatuses") or []):
        if isinstance(cs, dict) and extract_digest(str(cs.get("imageID") or "")):
            deployed_image = str(cs.get("imageID") or deployed_image)
            break
    doc = {
        "schema": SCHEMA_DEPLOYMENT,
        "ok": not issues,
        "failed_stage": "" if not issues else STAGE_LABELS["push"],
        "issues": issues,
        "candidate_sha": candidate,
        "pipeline_run": pipe.get("pipeline_run") or "",
        "image_digest": digest,
        "deployed_image": deployed_image,
        "route_url": url,
        "https": url.startswith("https://"),
        "note": "a green PipelineRun is not enough: deploy-app can exit 0 with no Deployment",
    }
    write_canonical(root / DELIVERY_DEPLOYMENT, doc)
    return doc


def _http(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
          body: bytes | None = None, opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    req = Request(url, data=body, method=method, headers=headers or {})
    fetch = opener or urlopen
    try:
        with fetch(req, timeout=20) as resp:
            raw = resp.read() if hasattr(resp, "read") else b""
            return {"ok": True, "status": int(getattr(resp, "status", 200) or 200),
                    "headers": dict(getattr(resp, "headers", {}) or {}),
                    "body": raw.decode("utf-8", "replace"), "url": url}
    except HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        return {"ok": False, "status": int(exc.code), "headers": dict(exc.headers or {}),
                "body": raw.decode("utf-8", "replace") if raw else "", "url": url, "error": str(exc)}
    except (URLError, OSError, TimeoutError, ValueError) as exc:
        return {"ok": False, "status": 0, "headers": {}, "body": "", "url": url, "error": str(exc)}


def evaluate_live(checks: dict[str, dict[str, Any]], contract: dict[str, Any],
                  deployed_image: str, auth_mode: str) -> dict[str, Any]:
    issues: list[str] = []
    swagger = checks.get("swagger") or {}
    openapi = checks.get("openapi") or {}
    if int(swagger.get("status") or 0) not in {200, 301, 302}:
        issues.append("swagger-unusable")
    if int(openapi.get("status") or 0) != 200 or not str(openapi.get("body") or "").strip():
        issues.append("openapi-unusable")
    else:
        blob = str(openapi.get("body") or "")
        if "/api/" not in blob and "paths" not in blob.lower():
            issues.append("openapi-no-application-paths")
    for row in (contract.get("reads") or []):
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or row.get("path") or "")
        got = checks.get("read:%s" % cid) or {}
        if int(got.get("status") or 0) not in {200, 204}:
            issues.append("read-failed:%s" % cid)
    crud = contract.get("crud") if isinstance(contract.get("crud"), dict) else {}
    if not crud:
        issues.append("crud-contract-missing")
    else:
        created = checks.get("crud:create") or {}
        if int(created.get("status") or 0) not in {200, 201}:
            issues.append("crud-create-failed")
        read_back = checks.get("crud:read") or {}
        if int(read_back.get("status") or 0) not in {200, 204}:
            issues.append("crud-read-failed")
        deleted = checks.get("crud:delete") or {}
        if int(deleted.get("status") or 0) not in {200, 204, 202, 404}:
            issues.append("crud-cleanup-failed")
    expected_auth = str((contract.get("auth") or {}).get("mode") or auth_mode or "")
    observed_auth = str((checks.get("auth") or {}).get("mode") or "")
    if expected_auth and observed_auth and expected_auth != observed_auth:
        issues.append("auth-mode-mismatch")
    cors_expect = contract.get("cors") if isinstance(contract.get("cors"), dict) else {}
    cors_got = checks.get("cors") or {}
    if cors_expect and cors_got:
        want_grant = bool(cors_expect.get("expect_grant"))
        got_grant = "access-control-allow-origin" in {k.lower() for k in (cors_got.get("headers") or {})}
        if want_grant != got_grant:
            issues.append("cors-mismatch")
    localhost = any("localhost" in str((c or {}).get("url") or "") or "127.0.0.1" in str((c or {}).get("url") or "")
                    for c in checks.values() if isinstance(c, dict))
    if localhost:
        issues.append("localhost-not-deployed")
    return {
        "schema": SCHEMA_LIVE,
        "ok": not issues,
        "failed_stage": "" if not issues else STAGE_LABELS["accept"],
        "issues": issues,
        "deployed_image": deployed_image,
        "auth_mode": expected_auth,
        "checks": {k: {"status": v.get("status"), "url": v.get("url")} for k, v in checks.items() if isinstance(v, dict)},
    }


def compose_verdict(root: Path) -> dict[str, Any]:
    root = Path(root)
    elig = load_json(root / DELIVERY_ELIGIBILITY) if (root / DELIVERY_ELIGIBILITY).is_file() else {}
    cand = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    pipe = load_json(root / DELIVERY_PIPELINE) if (root / DELIVERY_PIPELINE).is_file() else {}
    dep = load_json(root / DELIVERY_DEPLOYMENT) if (root / DELIVERY_DEPLOYMENT).is_file() else {}
    live = load_json(root / DELIVERY_LIVE) if (root / DELIVERY_LIVE).is_file() else {}
    candidate = str(cand.get("candidate_sha") or elig.get("candidate_sha") or "")
    stale = []
    for label, doc in (("pipeline", pipe), ("deployment", dep), ("live", live)):
        got = str(doc.get("candidate_sha") or "")
        if doc and got and candidate and got != candidate:
            stale.append(label)
    deploy_ok = bool(dep.get("ok")) and not stale
    live_ok = bool(live.get("ok"))
    outstanding = outstanding_from_artifacts(root, candidate_sha=candidate)
    kill = read_g1_kill_ratio(root, candidate_sha=candidate)
    release_eligible = (not outstanding) and bool(kill.get("pass") and kill.get("pinned"))
    failed_stage = ""
    if not cand.get("ok", True) or not elig.get("pipeline_eligible", True):
        failed_stage = STAGE_LABELS["prepare"]
    elif not pipe.get("ok") or not deploy_ok or stale:
        failed_stage = STAGE_LABELS["push"]
    elif not live_ok:
        failed_stage = STAGE_LABELS["accept"]
    if stale:
        verdict_token = "REFUSE"
        routing = "blocked"
        reason = "downstream evidence is bound to a different candidate: %s" % ", ".join(stale)
    elif failed_stage:
        verdict_token = "REFUSE"
        routing = "blocked"
        reason = "failed %s" % failed_stage
    elif not release_eligible or outstanding:
        verdict_token = "INCONCLUSIVE"
        routing = "blocked"
        reason = "deployed and live-checked; outstanding release qualifications remain"
    else:
        verdict_token = "ACCEPT"
        routing = "close"
        reason = "full release: live checks passed and the existing release contract is met"
    ship = verdict_token == "ACCEPT"
    kill_value = "PASS" if (kill.get("pass") and kill.get("pinned")) else str(kill.get("value") or "")
    kill_pinned = bool(kill.get("pass") and kill.get("pinned"))
    doc = {
        "schema": SCHEMA_VERDICT,
        "gate": "compose-m5-verdict",
        "phase": "M5",
        "ran": True,
        "verdict": verdict_token,
        "accept_kind": "full" if verdict_token == "ACCEPT" else "",
        "ship": ship,
        "routing": routing,
        "prior_verdict": str(elig.get("m4_verdict") or cand.get("m4_verdict") or ""),
        "failed_floors": [] if verdict_token != "REFUSE" else [failed_stage],
        "floors": [],
        "reason": reason,
        "failed_stage": failed_stage,
        "candidate_sha": candidate,
        "pipeline_run": pipe.get("pipeline_run") or "",
        "image_digest": pipe.get("image_digest") or dep.get("image_digest") or "",
        "deployed_image": dep.get("deployed_image") or live.get("deployed_image") or "",
        "route_url": dep.get("route_url") or "",
        "deployment_status": "deployed" if deploy_ok else "not-deployed",
        "live_ok": live_ok,
        "outstanding": outstanding,
        "limitations": [r.get("detail") or r.get("kind") for r in outstanding if isinstance(r, dict)],
        "stale_evidence": stale,
        "g1_kill_ratio": kill_value,
        "g1_kill_ratio_threshold_pinned": kill_pinned,
        "g1_kill_ratio_evidence": kill.get("path") or "",
    }
    path = root / M5_VERDICT
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        archive = root / DELIVERY_DIR / "attempts" / "m5-verdict.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.is_file():
            archive.write_bytes(path.read_bytes())
    write_canonical(path, doc)
    return doc


def walkthrough(verdict: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    url = str(verdict.get("route_url") or "")
    swagger = str(contract.get("swagger_path") or DEFAULT_SWAGGER)
    lines = [
        "Open %s%s" % (url, swagger),
        "Confirm OpenAPI at %s%s lists application paths." % (url, contract.get("openapi_path") or DEFAULT_OPENAPI),
    ]
    for row in (contract.get("reads") or []):
        if isinstance(row, dict) and row.get("path"):
            lines.append("GET %s%s (expect 200)." % (url, row["path"]))
    cred = contract.get("credential_ref") or contract.get("auth") or {}
    if str((contract.get("auth") or {}).get("mode") or "") == "disabled":
        lines.append("This deployment is in the application's configured unauthenticated mode; do not change auth to make a test pass.")
    if isinstance(cred, dict) and cred.get("header_from_env"):
        lines.append("Credential reference: environment variable %s (do not paste the secret)." % cred["header_from_env"])
    lines.append("Limitations: %s" % ("; ".join(verdict.get("limitations") or ["none recorded"])))
    return lines
