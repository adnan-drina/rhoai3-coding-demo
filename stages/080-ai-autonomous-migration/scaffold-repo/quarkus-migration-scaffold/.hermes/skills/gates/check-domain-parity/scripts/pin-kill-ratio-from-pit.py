#!/usr/bin/env python3
"""Pin G-1 kill-ratio under dual-denominator rule (plan #8 / AD-H §18.0¶5).

Sole attempted ratio (killed/attempted) is forbidden as the PASS predicate —
deleting survivor-covering tests raises it (NO_COVERAGE leaves denominator).

M5 kill-ratio PASS requires all of:
  1. generated > 0 (W2 §5 volume)
  2. coverage floor: attempted/generated >= coverage_min
  3. kill strength: killed/attempted >= kill_attempted_min
  4. optional stringency: killed/generated >= kill_generated_min (when set)
Always report killed/generated. Bar source (AD-H §18.0¶5 / Architect
E-20260808T125536Z):
  - ratchet_from_measured — floors as margin under this tree's score (record
    measured_* + margin_*); prevents regression; not an engineering target
  - declared_engineering_target — bars sourced outside this subject's score
  - measured_from_this_run at equality — forbidden (script refuses)

Usage:
  pin-kill-ratio-from-pit.py <mutations.xml> -o evidence/derived/g1-kill-ratio-pin.json \\
    --root <product-tree> \\
    --coverage-min 0.41 --kill-attempted-min 0.60 --kill-generated-min 0.38 \\
    --source ratchet_from_measured \\
    --rationale "Architect E-… ratchet margins under live pack"

  --candidate-sha may be passed explicitly; otherwise --root resolves the
  expected delivery candidate from verification/delivery/candidate.json or
  git HEAD. A product-tree SHA-256 (verify-run candidate_sha256 /
  product_tree_sha256) is a different identity from a Git commit and is
  not compared to it as a string. --root does not assign a delivery
  identity to an arbitrary mutations.xml: pin emission requires
  evidence/derived/pit-measurement.json tying the XML digest to the
  measured Git commit and product tree. Record that receipt after the PIT
  run (never by the pin itself):

  pin-kill-ratio-from-pit.py <mutations.xml> --record-measurement --root . \\
    [--candidate-sha <git-commit>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PIT_MEASUREMENT_SCHEMA = "migration/pit-measurement/v1"
PIT_MEASUREMENT_REL = Path("evidence") / "derived" / "pit-measurement.json"
GIT_SHA_HEX = 40
TREE_SHA_HEX = 64
_HEX = "0123456789abcdef"


def count_mutations(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    mutants = [el for el in root.iter() if el.tag.endswith("mutation") or el.tag == "mutation"]
    by_status: dict[str, int] = {}
    for m in mutants:
        st = (m.attrib.get("status") or m.findtext("status") or "UNKNOWN").upper()
        by_status[st] = by_status.get(st, 0) + 1
    killed = by_status.get("KILLED", 0)
    survived = by_status.get("SURVIVED", 0)
    timed_out = by_status.get("TIMED_OUT", 0)
    no_cov = by_status.get("NO_COVERAGE", 0)
    not_started = by_status.get("NOT_STARTED", 0)
    generated = len(mutants)
    attempted = killed + survived + timed_out
    kill_attempted = (killed / attempted) if attempted > 0 else None
    coverage = (attempted / generated) if generated > 0 else None
    kill_generated = (killed / generated) if generated > 0 else None
    return {
        "mutations_total": generated,
        "generated": generated,
        "by_status": by_status,
        "killed": killed,
        "survived": survived,
        "timed_out": timed_out,
        "no_coverage": no_cov,
        "not_started": not_started,
        "attempted": attempted,
        "coverage_ratio": coverage,
        "kill_attempted_ratio": kill_attempted,
        "kill_generated_ratio": kill_generated,
        "kill_ratio": kill_attempted,
        "source": str(path),
    }


def evaluate(
    stats: dict,
    coverage_min: float,
    kill_attempted_min: float,
    kill_generated_min: float | None,
) -> dict:
    generated = int(stats["generated"])
    attempted = int(stats["attempted"])
    killed = int(stats["killed"])
    coverage = stats["coverage_ratio"]
    kill_att = stats["kill_attempted_ratio"]
    kill_gen = stats["kill_generated_ratio"]
    reasons: list[str] = []
    if generated <= 0:
        reasons.append("generated==0 (W2 §5 vacuity)")
    if attempted <= 0:
        reasons.append("attempted==0 (no killing population)")
    if coverage is None or coverage < coverage_min:
        reasons.append(
            f"coverage_floor FAIL: attempted/generated={coverage} < coverage_min={coverage_min}"
        )
    if kill_att is None or kill_att < kill_attempted_min:
        reasons.append(
            f"kill_strength FAIL: killed/attempted={kill_att} < kill_attempted_min={kill_attempted_min}"
        )
    if kill_generated_min is not None:
        if kill_gen is None or kill_gen < kill_generated_min:
            reasons.append(
                f"kill_generated FAIL: killed/generated={kill_gen} < kill_generated_min={kill_generated_min}"
            )
    return {
        "pass": not reasons,
        "coverage_ratio": coverage,
        "kill_attempted_ratio": kill_att,
        "kill_generated_ratio": kill_gen,
        "killed": killed,
        "attempted": attempted,
        "generated": generated,
        "fail_reasons": reasons,
    }


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return doc if isinstance(doc, dict) else {}


def is_git_sha(value: str) -> bool:
    sha = str(value or "").strip().lower()
    return len(sha) == GIT_SHA_HEX and all(c in _HEX for c in sha)


def is_tree_digest(value: str) -> bool:
    sha = str(value or "").strip().lower()
    return len(sha) == TREE_SHA_HEX and all(c in _HEX for c in sha)


def _product_tree_sha256(root: Path) -> str:
    lib = Path(__file__).resolve().parents[4] / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    from planner.canonical import product_tree_sha256

    return product_tree_sha256(root)


def _sha_from_doc(doc: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        got = str(doc.get(key) or "").strip()
        if got:
            return got
    return ""


def delivery_candidate_from_root(root: Path) -> str:
    path = root / "verification/delivery/candidate.json"
    if not path.is_file():
        return ""
    return _sha_from_doc(_load_json(path), ("candidate_sha",))


def verify_run_sha_from_root(root: Path) -> str:
    path = root / "verification/build/run.json"
    if not path.is_file():
        return ""
    return _sha_from_doc(_load_json(path), ("candidate_sha256", "candidate_sha"))


def git_head_sha(root: Path) -> str:
    top = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode != 0:
        return ""
    try:
        if Path(top.stdout.strip()).resolve() != root.resolve():
            return ""
    except OSError:
        return ""
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return (proc.stdout or "").strip()
    return ""


def resolve_measured_candidate_sha(explicit: str, root: Path | None) -> str:
    """Expected delivery Git commit. A product-tree digest is not this identity."""
    sha = str(explicit or "").strip()
    if sha:
        return sha
    if root is None:
        return ""
    root = root.resolve()
    delivery = delivery_candidate_from_root(root)
    if delivery:
        return delivery
    git = git_head_sha(root)
    if git:
        return git
    run = verify_run_sha_from_root(root)
    if run and not is_tree_digest(run):
        return run
    return ""


def measured_git_sha(explicit: str, root: Path | None) -> str:
    """Git commit the PIT execution is bound to. Tree digests are not Git commits."""
    sha = str(explicit or "").strip()
    if sha and not is_tree_digest(sha):
        return sha
    if root is None:
        return ""
    root = root.resolve()
    git = git_head_sha(root)
    if git:
        return git
    delivery = delivery_candidate_from_root(root)
    if delivery and not is_tree_digest(delivery):
        return delivery
    run = verify_run_sha_from_root(root)
    if run and not is_tree_digest(run):
        return run
    return ""


def git_identities(explicit: str, root: Path | None) -> list[str]:
    found: list[str] = []

    def add(sha: str) -> None:
        sha = str(sha or "").strip()
        if sha and not is_tree_digest(sha) and sha not in found:
            found.append(sha)

    add(explicit)
    if root is not None:
        root = root.resolve()
        add(delivery_candidate_from_root(root))
        add(git_head_sha(root))
        run = verify_run_sha_from_root(root)
        if not is_tree_digest(run):
            add(run)
    return found


def pit_measurement_path(root: Path | None, xml: Path) -> Path:
    if root is not None:
        return root.resolve() / PIT_MEASUREMENT_REL
    return xml.resolve().parent / "pit-measurement.json"


def write_pit_measurement(
    xml: Path,
    candidate_sha: str,
    root: Path | None,
    *,
    git_sha: str = "",
    tree_sha256: str = "",
) -> Path:
    digest = sha256_hex(xml.read_bytes())
    path = pit_measurement_path(root, xml)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": PIT_MEASUREMENT_SCHEMA,
        "candidate_sha": candidate_sha,
        "mutations_xml_sha256": digest,
        "source": str(xml),
    }
    if git_sha:
        doc["git_sha"] = git_sha
    if tree_sha256:
        doc["tree_sha256"] = tree_sha256
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def load_pit_measurement(root: Path | None, xml: Path) -> dict:
    path = pit_measurement_path(root, xml)
    if not path.is_file():
        return {}
    doc = _load_json(path)
    if str(doc.get("schema") or "") != PIT_MEASUREMENT_SCHEMA:
        return {}
    return doc


def provenance_error(
    xml: Path, expected_sha: str, root: Path | None, explicit: str = ""
) -> str:
    git_ids = git_identities(explicit, root)
    if len(git_ids) > 1:
        return "conflicting candidate identities"
    receipt = load_pit_measurement(root, xml)
    if not receipt:
        return "missing measurement provenance"
    measured = str(receipt.get("candidate_sha") or receipt.get("git_sha") or "").strip()
    digest = str(receipt.get("mutations_xml_sha256") or "").strip()
    if not measured or not digest:
        return "missing measurement provenance"
    if measured != expected_sha:
        return "measurement provenance does not match the delivery candidate"
    if digest != sha256_hex(xml.read_bytes()):
        return "measurement provenance does not match the PIT report digest"
    if root is not None:
        computed = _product_tree_sha256(root)
        receipt_tree = str(receipt.get("tree_sha256") or "").strip()
        if receipt_tree and computed and receipt_tree != computed:
            return "measurement provenance does not match the product tree"
        receipt_git = str(receipt.get("git_sha") or "").strip()
        head = git_head_sha(root)
        if receipt_git and head and receipt_git != head:
            return "measurement provenance does not match the Git commit"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mutations_xml", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument(
        "--record-measurement",
        action="store_true",
        help="write execution evidence tying this mutations.xml digest to the measured tree; do not emit a pin",
    )
    ap.add_argument(
        "--candidate-sha",
        default="",
        help="delivery candidate this PIT measurement is bound to (written into the pin; M5 does not decorate afterwards)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="product tree used to resolve the expected delivery candidate from candidate.json, verify-run, or git HEAD",
    )
    ap.add_argument("--story-id", default="B-OWNER-PET-1")
    ap.add_argument(
        "--scope",
        default="measured live PIT slice",
    )
    ap.add_argument("--coverage-min", type=float, default=None)
    ap.add_argument("--kill-attempted-min", type=float, default=None)
    ap.add_argument(
        "--kill-generated-min",
        type=float,
        default=None,
        help="optional stringency floor killed/generated (Architect before first M5 ACCEPT)",
    )
    ap.add_argument("--rationale", default="")
    ap.add_argument(
        "--source",
        choices=("ratchet_from_measured", "declared_engineering_target"),
        default="",
        help="AD-H §18.0¶5 bar source (Architect E-20260808T125536Z)",
    )
    ap.add_argument(
        "--invalidate-prior",
        default="prior dual pin coverage_min=0.25 without kill_generated_min (stringency raise)",
    )
    args = ap.parse_args()
    if not args.mutations_xml.is_file():
        print(f"FAIL: missing {args.mutations_xml}", file=sys.stderr)
        return 1
    if args.record_measurement:
        git_sha = measured_git_sha(args.candidate_sha, args.root)
        tree_sha256 = _product_tree_sha256(args.root) if args.root is not None else ""
        measured = git_sha or str(args.candidate_sha or "").strip()
        if not measured:
            print(
                "FAIL: --record-measurement needs --candidate-sha or --root with a Git commit identity",
                file=sys.stderr,
            )
            return 1
        path = write_pit_measurement(
            args.mutations_xml, measured, args.root,
            git_sha=git_sha, tree_sha256=tree_sha256,
        )
        print(
            f"OK: recorded PIT measurement candidate={measured} git_sha={git_sha or '-'} "
            f"tree_sha256={tree_sha256 or '-'} digest={sha256_hex(args.mutations_xml.read_bytes())} → {path}",
            file=sys.stderr,
        )
        return 0
    if args.output is None or args.coverage_min is None or args.kill_attempted_min is None or not args.source or not args.rationale:
        print(
            "FAIL: pin emission requires -o, --coverage-min, --kill-attempted-min, --source, and --rationale",
            file=sys.stderr,
        )
        return 1
    candidate_sha = resolve_measured_candidate_sha(args.candidate_sha, args.root)
    if not candidate_sha:
        print(
            "FAIL: --candidate-sha or --root with a resolvable measured candidate is required to bind the measurement",
            file=sys.stderr,
        )
        return 1
    why = provenance_error(args.mutations_xml, candidate_sha, args.root, args.candidate_sha)
    if why:
        print(f"FAIL: {why}", file=sys.stderr)
        return 1
    receipt = load_pit_measurement(args.root, args.mutations_xml)
    xml_digest = str(receipt.get("mutations_xml_sha256") or "")
    if args.coverage_min <= 0 or args.coverage_min > 1:
        print("FAIL: coverage-min must be in (0,1]", file=sys.stderr)
        return 1
    if args.kill_attempted_min <= 0 or args.kill_attempted_min > 1:
        print("FAIL: kill-attempted-min must be in (0,1]", file=sys.stderr)
        return 1
    if args.kill_generated_min is not None and (
        args.kill_generated_min <= 0 or args.kill_generated_min > 1
    ):
        print("FAIL: kill-generated-min must be in (0,1]", file=sys.stderr)
        return 1

    stats = count_mutations(args.mutations_xml)
    if stats["mutations_total"] <= 0:
        print("FAIL: zero mutants — refuse vacuous pin (W2 §5)", file=sys.stderr)
        return 1
    if stats["not_started"] == stats["mutations_total"]:
        print(
            "FAIL: all mutants NOT_STARTED (dry-run only) — not a kill-ratio pin",
            file=sys.stderr,
        )
        return 1

    cov = stats["coverage_ratio"]
    katt = stats["kill_attempted_ratio"]
    kgen = stats["kill_generated_ratio"]
    if cov is not None and abs(cov - args.coverage_min) < 1e-9:
        print(
            "FAIL: coverage_min equals measured coverage (circular measured_from_this_run)",
            file=sys.stderr,
        )
        return 1
    if katt is not None and abs(katt - args.kill_attempted_min) < 1e-9:
        print(
            "FAIL: kill_attempted_min equals measured kill strength (circular)",
            file=sys.stderr,
        )
        return 1
    if (
        args.kill_generated_min is not None
        and kgen is not None
        and abs(kgen - args.kill_generated_min) < 1e-9
    ):
        print(
            "FAIL: kill_generated_min equals measured kill_generated (circular)",
            file=sys.stderr,
        )
        return 1

    ev = evaluate(
        stats, args.coverage_min, args.kill_attempted_min, args.kill_generated_min
    )
    threshold = {
        "coverage_min": args.coverage_min,
        "kill_attempted_min": args.kill_attempted_min,
        "rule": (
            "PASS iff generated>0 AND attempted>0 AND "
            "attempted/generated >= coverage_min AND "
            "killed/attempted >= kill_attempted_min"
            + (
                " AND killed/generated >= kill_generated_min"
                if args.kill_generated_min is not None
                else ""
            )
            + "; always report killed/generated; "
            "sole killed/attempted PASS predicate FORBIDDEN"
        ),
        "source": args.source,
        "rationale": args.rationale,
        "folklore": False,
    }
    if args.kill_generated_min is not None:
        threshold["kill_generated_min"] = args.kill_generated_min
    if args.source == "ratchet_from_measured":
        threshold["measured_coverage"] = cov
        threshold["measured_kill_attempted"] = katt
        threshold["measured_kill_generated"] = kgen
        if cov is not None:
            threshold["margin_coverage"] = cov - args.coverage_min
        if katt is not None:
            threshold["margin_kill_attempted"] = katt - args.kill_attempted_min
        if args.kill_generated_min is not None and kgen is not None:
            threshold["margin_kill_generated"] = kgen - args.kill_generated_min
    pin_authority_extra = (
        "; pin-source E-20260808T125536Z"
        if args.source == "ratchet_from_measured"
        else ""
    )

    pin = {
        "schema": "migration/g1-kill-ratio-pin/v2-dual-denominator",
        "authority": "EXECUTION-LIVE-VALIDATION-PLAN #8; W2 §5/§9; AD-H §18.0¶5; "
        "Architect decide E-20260808T115649Z; stringency E-20260808T120152Z/"
        "E-20260808T121549Z/E-20260808T123742Z"
        + pin_authority_extra,
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "story_id": args.story_id,
        "candidate_sha": candidate_sha,
        "identity": {
            "candidate_sha": candidate_sha,
            **({"git_sha": receipt.get("git_sha")} if receipt.get("git_sha") else {}),
            **({"tree_sha256": receipt.get("tree_sha256")} if receipt.get("tree_sha256") else {}),
        },
        "scope": args.scope,
        "tool": "pitest-maven",
        "pinned_version": "1.25.5",
        "mode": "live_mutationCoverage",
        "prior_pin": {
            "status": "SUPERSEDED",
            "reason": args.invalidate_prior,
            "defect": "coverage_min=0.25 admitted ~75% NO_COVERAGE; stringency "
            "required before first M5 ACCEPT",
        },
        "measurement": {
            **stats,
            "candidate_sha": candidate_sha,
            "mutations_xml_sha256": xml_digest,
        },
        "provenance": {
            "schema": PIT_MEASUREMENT_SCHEMA,
            "candidate_sha": candidate_sha,
            "mutations_xml_sha256": xml_digest,
            "source": str(receipt.get("source") or args.mutations_xml),
            **({"git_sha": receipt.get("git_sha")} if receipt.get("git_sha") else {}),
            **({"tree_sha256": receipt.get("tree_sha256")} if receipt.get("tree_sha256") else {}),
        },
        "threshold": threshold,
        "evaluation_against_measurement": ev,
        "waiver_path": {
            "token": None,
            "authority": "none",
            "effect": "deleted — M5 ACCEPT requires kill-ratio PASS+pin; "
            "a waiver cannot author ACCEPT (B-4/C-3(a))",
            "location": None,
        },
        "m5_note": "Pinning does NOT grant M5 ACCEPT — plan #1e still required "
        "(G-4 both-modes + dual-denominator kill-ratio PASS).",
        "status": "PINNED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: pin coverage_min={args.coverage_min} "
        f"kill_attempted_min={args.kill_attempted_min} "
        f"kill_generated_min={args.kill_generated_min} "
        f"(measured coverage={cov} kill_attempted={katt} "
        f"kill_generated={kgen}) eval_pass={ev['pass']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
