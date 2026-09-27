#!/usr/bin/env python3
"""Stage the outcome-authority code the ws-080 image bakes, from a COMMIT.

    stage-outcome-authority.py --repo <git checkout> --commit <full sha> \\
        [--prefix stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes] \\
        --out <workspace-images>/out/outcome-authority

Extracts .hermes/{kernel,lib,planning,skills} of that commit with `git archive`
(never the working tree, so no local edit, bytecode or untracked file enters),
and prints the code identity the image must stamp as
`outcome_authority.code_sha256` (planner.outcome_authority.code_identity over
the staged tree). The Dockerfile hunk refuses a build whose baked tree does not
compute the identity passed as OUTCOME_AUTHORITY_CODE_SHA256.
"""
from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

# the identity is computed by importing the STAGED planner: never write
# bytecode into the tree that is baked (the image build refuses __pycache__)
sys.dont_write_bytecode = True

TREES = ("kernel", "lib", "planning", "skills")
DEFAULT_PREFIX = "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="the .hermes directory inside the repository ('.hermes' for a golden)")
    ap.add_argument("--out", required=True)
    ns = ap.parse_args()
    if len(ns.commit) not in (40, 64):
        print("REFUSE: a full commit id is required", file=sys.stderr)
        return 1
    prefix = ns.prefix.strip("/")
    arc = subprocess.run(["git", "-C", ns.repo, "archive", "--format=tar", ns.commit] + ["%s/%s" % (prefix, t) for t in TREES],
                         capture_output=True)
    if arc.returncode != 0:
        print("REFUSE: git archive failed: %s" % arc.stderr.decode()[-400:], file=sys.stderr)
        return 1
    out = Path(ns.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(arc.stdout)) as tf:
        for m in tf.getmembers():
            rel = m.name[len(prefix) + 1:] if m.name.startswith(prefix + "/") else ""
            if not rel or m.issym() or m.islnk() or ".." in Path(rel).parts:
                continue
            m.name = rel
            tf.extract(m, out)
    sys.path.insert(0, str(out / "lib"))
    from planner.outcome_authority import code_identity
    ident = code_identity(out)
    (out.parent / "outcome-authority.code_sha256").write_text(ident + "\n")
    print(ident)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
