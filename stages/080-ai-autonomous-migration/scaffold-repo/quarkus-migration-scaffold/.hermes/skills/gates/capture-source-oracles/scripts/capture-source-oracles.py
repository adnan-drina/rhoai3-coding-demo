#!/usr/bin/env python3
"""Capture expected READ behaviour from the running SOURCE system.

Writes verification/source-oracles/<slug>.json per admitted entry point.
HTTP GET/HEAD are requested mechanically, with --path-var supplying any
templated segment from the source's own seeded data. Non-HTTP kinds need
--observation <id>=<file>.

Writes are NOT captured here. A write is a complete request against a known
initial state whose effects have to be read back, so it belongs to the
scenario corpus (capture-source-scenarios.py). Anything not captured is
recorded UNCAPTURED or INCONCLUSIVE, never invented.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import IDEMPOTENT, ORACLES, entry_points, http_observe, normalize_observation, slug  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import digest, load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402


def substitute_path(template: str, values: dict[str, str]) -> tuple[str, dict[str, str], list[str]]:
    """(concrete path, substitutions used, variables with no value)."""
    used: dict[str, str] = {}
    missing: list[str] = []
    out = template
    for name in re.findall(r"\{([^{}]+)\}", template):
        if name in values:
            out = out.replace("{%s}" % name, values[name])
            used[name] = values[name]
        elif name not in missing:
            missing.append(name)
    return out, used, missing


def _pairs(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        if "=" in it:
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--base-url", default="")
    ap.add_argument("--entry-point", action="append", default=[])
    ap.add_argument("--observation", action="append", default=[], help="<entry point id>=<captured file>")
    ap.add_argument("--path-var", action="append", default=[], help="<name>=<value> for a templated path segment, e.g. ownerId=1; the value must exist in the source system's own seeded data. The concrete path is recorded in the oracle, so the destination is compared at the same URL.")
    ap.add_argument("--any-status", action="store_true", help="allow a non-ADMITTED receipt (capture may precede admission)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    # Reads are captured at M1, from the running source, BEFORE the plan is
    # admitted: requiring an admission receipt made a fresh M1 impossible. The
    # capture binds to the evidence bundle (the frozen source it describes) and
    # records the receipt only when there already is one.
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        print("REFUSE: ORACLES missing %s; the reads are captured from the source that bundle describes" % EVIDENCE_BUNDLE, file=sys.stderr)
        return 1
    bundle_sha = digest(load_json(bundle_p))
    receipt, gaps = verify_receipt(root, require_admitted=not args.any_status)
    if receipt is not None and gaps:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: ORACLES the admission receipt on disk is not authoritative", file=sys.stderr)
        return 1
    path_vars = _pairs(args.path_var)
    obs = _pairs(args.observation)
    eps = entry_points(root)
    if args.entry_point:
        eps = [e for e in eps if e["id"] in set(args.entry_point)]
    if not eps:
        print("REFUSE: ORACLES no entry points selected", file=sys.stderr)
        return 1
    captured = 0
    inconclusive = 0
    for ep in eps:
        rec = {"schema": "rhoai3.source-oracle/v1", "entry_point": ep["id"], "kind": ep["kind"],
               "receipt_sha256": receipt["receipt_digest"] if receipt else "", "evidence_bundle_sha256": bundle_sha,
               "status": "UNCAPTURED", "reason": "", "oracle": {}}
        if ep["kind"] == "http":
            method = ep.get("http_method") or "GET"
            template = ep.get("http_path") or "/"
            # A path is a request or it is nothing. A template still carrying a
            # variable, or a wildcard the mapping flattened, would be requested
            # literally: both systems would answer 404 and the comparison would
            # pass while proving nothing. That is refused, and the missing value
            # is named.
            path, used, missing = substitute_path(template, path_vars)
            extra = {"path_template": template, "path_vars": used} if used else {}
            if not args.base_url:
                rec["reason"] = "no --base-url"
            elif missing:
                rec["status"] = "INCONCLUSIVE"
                rec["reason"] = "templated path %s needs %s (a value from the source system's own seeded data)" % (template, ", ".join("--path-var %s=<value>" % m for m in missing))
            elif "*" in path:
                rec["status"] = "INCONCLUSIVE"
                rec["reason"] = "path %s carries a wildcard and is not a request; the entry-point mapping must name a concrete path" % path
            elif method in IDEMPOTENT:
                o = http_observe(args.base_url, method, path)
                rec["oracle"] = {"method": method, "path": path, **extra, **o}
                rec["status"] = "CAPTURED" if o.get("status") else "UNCAPTURED"
                rec["reason"] = o.get("error", "")
            else:
                # A write is not a method and a path. It is a complete request
                # against a known initial state, with effects that prove what
                # it did -- and the retired body-only option recorded a body
                # the destination comparator never sent. Writes belong to
                # the scenario corpus (capture-source-scenarios.py).
                rec["status"] = "INCONCLUSIVE"
                rec["reason"] = ("non-idempotent %s belongs in the scenario corpus (verification/scenarios/corpus.json): "
                                 "a complete recorded request, its initial state, and the effects that prove the write happened"
                                 % method)
        else:
            f = obs.get(ep["id"])
            if f and Path(f).is_file():
                sha, n = normalize_observation(Path(f))
                rec["oracle"] = {"observation_sha256": sha, "lines": n, "source_file_sha256": sha256_file(Path(f))}
                rec["status"] = "CAPTURED"
            else:
                rec["reason"] = "%s entry point needs --observation <id>=<file> captured from the source system" % ep["kind"]
        if rec["status"] == "CAPTURED":
            captured += 1
        elif rec["status"] == "INCONCLUSIVE":
            inconclusive += 1
        write_canonical(root / ORACLES / (slug(ep["id"]) + ".json"), rec)
    print("OK: oracles captured=%d inconclusive=%d of %d → %s" % (captured, inconclusive, len(eps), ORACLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
