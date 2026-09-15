#!/usr/bin/env python3
"""Commit the generated product parity tests as the harness-owned files they are.

The generator writes ``src/parity-test/java`` (+ resources) and the manifest at
M4. ``assert-retrievable-tree`` then asks whether ``src/`` and ``pom.xml`` are
committed against HEAD -- and an untracked generated file is exactly the dirt
it refuses. That gate is right and is not weakened: what was missing is the
step that makes the tree retrievable, which is this one.

WHAT IT WILL COMMIT, and nothing else:

  the files ``evidence/tests/generated-manifest.json`` lists by digest,
  the manifest itself, and anything under the generated roots the manifest
  names (``out`` / ``resources``, default ``src/parity-test/``).

Any other change to ``src`` or ``pom.xml`` is a REFUSAL, not something to
sweep into a harness commit: a worker's edit, a build artifact under src, or a
pom the generator was not the one to change belongs to whoever made it. The
m4-parity profile is written by ``bootstrap-destination.py`` (ADR-015), so the
pom is already committed when this runs and appears here only if something
else moved it.

  commit-generated-tests.py --root <dest>

Idempotent: with nothing to commit it says so and exits 0 -- a phase re-run is
not a failure. Exit 0 committed (or nothing to commit), 1 refused, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import subprocess
import sys
from pathlib import Path
from typing import Any

SELF = "commit-generated-tests"
GENERATOR = Path(__file__).resolve().parent / "generate-product-tests.py"
MANIFEST = "evidence/tests/generated-manifest.json"
SCHEMA = "rhoai3.generated-tests/v1"
DEFAULT_OUT = "src/parity-test/java"
DEFAULT_RESOURCES = "src/parity-test/resources"
AUTHOR = "generate-product-tests <generate-product-tests@local>"
FALLBACK_IDENT = ("user.name=generate-product-tests", "user.email=generate-product-tests@local")


def _fail(msg: str) -> int:
    print("REFUSE: COMMIT_TESTS " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def load_manifest(root: Path) -> dict[str, Any] | str:
    p = root / MANIFEST
    if not p.is_file():
        return ("no %s; the product parity tests were never generated, so there is nothing this step may commit "
                "(generate-product-tests.py)" % MANIFEST)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (MANIFEST, exc)
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        return "%s is not a %s document" % (MANIFEST, SCHEMA)
    return doc


def generated_roots(manifest: dict[str, Any]) -> list[str]:
    """The roots the manifest says the harness generated into, plus the parent
    they share when they have one (``src/parity-test``): a stray file there is
    the generator's leftover, not a worker's edit."""
    out = str(manifest.get("out") or DEFAULT_OUT).rstrip("/")
    resources = str(manifest.get("resources") or DEFAULT_RESOURCES).rstrip("/")
    roots = {out, resources}
    parent = posixpath.dirname(out)
    if parent and parent == posixpath.dirname(resources):
        roots.add(parent)
    return sorted(roots)


def _under(rel: str, roots: list[str]) -> bool:
    return any(rel == r or rel.startswith(r + "/") for r in roots)


def porcelain_paths(line: str) -> list[str]:
    """Every path a ``git status --porcelain`` line names. A rename names two,
    and both must be allowed or the commit is not "exactly those paths"."""
    body = line[3:]
    if " -> " in body:
        return [p.strip().strip('"') for p in body.split(" -> ")]
    return [body.strip().strip('"')]


def commit(root: Path, *, check: bool = True) -> tuple[int, str]:
    manifest = load_manifest(root)
    if isinstance(manifest, str):
        return 1, manifest

    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return 1, "%s is not a git work tree; a generated suite that cannot be committed cannot be retrieved" % root

    # The bytes on disk must be the ones the harness wrote BEFORE they are
    # committed: committing an edited expectation would make the edit the
    # harness's own and --check would never see it again.
    if check:
        proc = subprocess.run([sys.executable, str(GENERATOR), "--root", str(root), "--check"], text=True, capture_output=True)
        if proc.returncode != 0:
            return 1, ("generate-product-tests.py --check refuses this tree, so there is nothing here to commit: %s"
                       % (proc.stderr.strip() or proc.stdout.strip() or "rc=%d" % proc.returncode))

    listed = sorted({str((row or {}).get("path") or "") for row in (manifest.get("files") or []) if (row or {}).get("path")})
    roots = generated_roots(manifest)
    allowed = set(listed) | {MANIFEST}

    scope = ["src", "pom.xml", MANIFEST]
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "--", *scope)
    if status.returncode != 0:
        return 1, (status.stderr or status.stdout or "git status failed").strip()

    dirty: list[str] = []
    foreign: list[str] = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        for rel in porcelain_paths(line):
            if not rel:
                continue
            if rel in allowed or _under(rel, roots):
                dirty.append(rel)
            else:
                foreign.append("%s (%s)" % (rel, line[:2]))
    if foreign:
        return 1, ("%d change(s) to src/ or pom.xml are not this producer's: %s. This step commits the generated suite "
                   "(%s and the manifest) and nothing else; whoever made those changes commits them."
                   % (len(foreign), ", ".join(sorted(set(foreign))[:6]), ", ".join(roots)))

    paths = sorted(set(dirty))
    if not paths:
        return 0, ("OK: COMMIT_TESTS nothing to commit — the %d generated file(s) and %s are already in HEAD"
                   % (len(listed), MANIFEST))

    add = _git(root, "add", "--all", "--", *paths)
    if add.returncode != 0:
        return 1, (add.stderr or add.stdout or "git add failed").strip()

    corpus = str(manifest.get("corpus_sha256") or "")
    version = str(manifest.get("generator_version") or "")
    message = "m4: generated product tests (corpus %s, generator %s)" % (corpus[:12] or "<none>", version or "<none>")

    ident: list[str] = []
    who = _git(root, "config", "--get", "user.email")
    if who.returncode != 0 or not who.stdout.strip():
        # A destination with no committer identity must not turn a green phase
        # into a git error; the AUTHOR is the harness either way.
        for pair in FALLBACK_IDENT:
            ident += ["-c", pair]
    done = _git(root, *ident, "commit", "-m", message, "--author", AUTHOR, "--", *paths)
    if done.returncode != 0:
        return 1, (done.stderr or done.stdout or "git commit failed").strip()
    head = _git(root, "rev-parse", "HEAD").stdout.strip()[:12]
    return 0, ("OK: COMMIT_TESTS %d path(s) committed as %s (%s) — %s"
               % (len(paths), head or "<unknown>", AUTHOR, message))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--root", required=True, help="the destination tree")
    ap.add_argument("--no-check", action="store_true",
                    help="skip generate-product-tests.py --check (tests only; the road never passes it)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("REFUSE: COMMIT_TESTS --root %s is not a directory" % args.root, file=sys.stderr)
        return 2
    rc, message = commit(root, check=not args.no_check)
    if rc:
        return _fail(message)
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
