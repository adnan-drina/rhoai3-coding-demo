#!/usr/bin/env python3
"""Carry the last qualified isolation receipt forward to a new golden/platform
pair WITHOUT a new isolation campaign (Operator decision 2026-09-30: no further
isolation campaign; architect review F4: reconcile the preflight explicitly,
never fake, re-date or silently reuse evidence under a different binding).

A carry-forward record (schema rhoai3.isolation-carry-forward/v1) names the
receipt it carries (by sha256), the revisions that receipt qualified (from)
and the revisions it is carried to (to). It is accepted only when:

  - the receipt is a complete rhoai3.run-isolation/v1 demonstration that binds
    exactly the `from` revisions (the preflight's own completeness check);
  - between from.platform and to.platform, no isolation-relevant platform path
    changed, except image digest re-pins in DIGEST_ONLY files;
  - between from.golden and to.golden (the golden checkout), the golden's
    devfile changed only image digests.

Every per-launch live check of run-preflight.sh (worker identity, secret
targeting, kubeconfig and source mounts, pinned database/provisioner images,
harness digests) still runs. Anything else is a refusal naming the path.

Usage (read-only): isolation_carry_forward.py RECORD RECEIPT PLATFORM_REPO GOLDEN_CHECKOUT GOLDEN_SHA PLATFORM_SHA
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "rhoai3.isolation-carry-forward/v1"
# the factory, provisioning, RBAC, secrets targeting and workspace templates live here
ISOLATION_PREFIXES = ("gitops/stages/050-advanced-app-platform/",)
# files whose only permitted change is an image digest re-pin
DIGEST_ONLY = ("gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml",)
GOLDEN_DIGEST_ONLY = ("devfile.yaml",)
DIGEST_LINE = re.compile(r"^[+-]\s*(-\s*)?(image|digest)\s*:\s*\S*@?sha256:[0-9a-f]{64}\S*\s*(#.*)?$")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=60)


def _digest_only(repo: Path, a: str, b: str, path: str) -> bool:
    diff = _git(repo, "diff", "--unified=0", a, b, "--", path)
    changed = [ln for ln in diff.splitlines()
               if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return bool(changed) and all(DIGEST_LINE.match(ln) for ln in changed)


def gaps(record: dict, receipt_path: Path, platform_repo: Path, golden: Path, golden_sha: str,
         platform_sha: str) -> list[str]:
    out: list[str] = []
    if record.get("schema") != SCHEMA:
        return ["carry-forward record schema is not %s" % SCHEMA]
    frm, to = record.get("from") or {}, record.get("to") or {}
    if to.get("golden") != golden_sha or to.get("platform") != platform_sha:
        out.append("the record does not carry to the selected revisions")
    data = receipt_path.read_bytes()
    if record.get("receipt_sha256") != hashlib.sha256(data).hexdigest():
        out.append("the record names another receipt (sha256 mismatch)")
    proof = json.loads(data)
    if (proof.get("schema") != "rhoai3.run-isolation/v1" or proof.get("golden_commit") != frm.get("golden")
            or proof.get("platform_commit") != frm.get("platform")):
        out.append("the receipt does not bind the record's `from` revisions")
    if not (record.get("by") and record.get("reason")):
        out.append("the record names no Operator and reason")
    if out:
        return out
    for path in _git(platform_repo, "diff", "--name-only", frm["platform"], platform_sha).split():
        if path.startswith(ISOLATION_PREFIXES):
            if path not in DIGEST_ONLY or not _digest_only(platform_repo, frm["platform"], platform_sha, path):
                out.append("isolation-relevant platform path changed: %s" % path)
    for path in _git(golden, "diff", "--name-only", frm["golden"], golden_sha).split():
        if path in GOLDEN_DIGEST_ONLY and not _digest_only(golden, frm["golden"], golden_sha, path):
            out.append("golden %s changed beyond image digests" % path)
    return out


def main(argv: list[str]) -> int:
    rec, receipt, repo, golden, gsha, psha = argv
    found = gaps(json.loads(Path(rec).read_text()), Path(receipt), Path(repo), Path(golden), gsha, psha)
    for g in found:
        print("FAIL: isolation carry-forward: " + g)
    if not found:
        print("PASS: isolation receipt carried forward (no isolation-relevant change since its qualification)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
