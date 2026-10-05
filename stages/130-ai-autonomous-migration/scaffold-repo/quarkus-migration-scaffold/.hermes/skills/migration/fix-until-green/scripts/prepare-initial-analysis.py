#!/usr/bin/env python3
"""The controlled initial-analysis boundary (plan semantics v1, WP3).

The JDK diagnostics producer reads target/generated-sources as source roots
and, by default, target/classes on its classpath. Before the first baseline
those directories hold whatever an earlier build left: an orphan class whose
source is gone resolves a reference and HIDES a real error, and stale
generated Java can manufacture or suppress work. Neither may silently change
the initial plan.

  --phase before   refuses unless this is the initial analysis (no loop
                   baseline recorded, no card issued): a candidate's files are
                   never deleted as a side effect of verification. Then it
                   removes target/ (build output only, never product --
                   planner.paths.is_product_path) so the warm-up regenerates
                   every generated root from its pinned inputs, and prints the
                   record run.json keeps (initial_preparation).
  --phase after    reads the diagnostics the producer wrote and refuses
                   (VERIFY_INITIAL_STALE_OUTPUT) when a registered generated
                   root holds a file older than this verification, or when
                   target/classes was still on the analysis classpath: the
                   provenance of every generated root is then explicit.

No network, no Maven: the warm-up that regenerates is run-verify.sh's own.
An offline dependency failure stays the producer failure it is
(build_unresolvable), never a smaller valid plan.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def _loop_started(root: Path) -> str:
    steps = root / "verification" / "loop" / "steps.json"
    if steps.is_file():
        try:
            doc = json.loads(steps.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "verification/loop/steps.json is unreadable"
        if (doc or {}).get("steps"):
            return "the loop baseline is already recorded (verification/loop/steps.json)"
    issued = root / "verification" / "loop" / "issued.json"
    if issued.is_file():
        return "a card is issued (verification/loop/issued.json)"
    return ""


def before(root: Path) -> dict:
    why = _loop_started(root)
    if why:
        print("REFUSE: VERIFY_INITIAL_AFTER_BASELINE %s; the initial analysis boundary is only for the first baseline "
              "and never deletes a candidate's build outputs" % why, file=sys.stderr)
        raise SystemExit(2)
    target = root / "target"
    removed = {"files": 0, "classes": 0, "generated": 0}
    if target.is_dir() and not target.is_symlink():
        for p in target.rglob("*"):
            if p.is_file():
                removed["files"] += 1
                rel = p.relative_to(target).as_posix()
                if rel.startswith("classes/") and rel.endswith(".class"):
                    removed["classes"] += 1
                if rel.startswith("generated-sources/"):
                    removed["generated"] += 1
        shutil.rmtree(target)
    elif target.is_symlink():
        print("REFUSE: VERIFY_INITIAL_TARGET_SYMLINK target/ is a symbolic link; it is not removed", file=sys.stderr)
        raise SystemExit(2)
    return {"clean": True, "removed_target": removed, "warmup_forced": True, "output_classes_excluded": True}


def after(root: Path, diagnostics: Path, since_ms: int) -> dict:
    try:
        doc = json.loads(diagnostics.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("FAIL: VERIFY_INITIAL_PROVENANCE diagnostics unreadable: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
    problems: list[str] = []
    if doc.get("output_classes_on_classpath"):
        problems.append("target/classes was on the analysis classpath")
    roots = []
    for g in doc.get("generated_roots") or []:
        rel = str(g.get("root") or "")
        base = root / rel
        stale = []
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and int(p.stat().st_mtime * 1000) < since_ms - 2000:
                    stale.append(p.relative_to(root).as_posix())
        if stale:
            problems.append("%s holds %d file(s) older than this verification (e.g. %s)" % (rel, len(stale), stale[0]))
        roots.append({"root": rel, "files": g.get("files"), "sha256": g.get("sha256"), "regenerated": not stale})
    if problems and not doc.get("build_unresolvable"):
        print("FAIL: VERIFY_INITIAL_STALE_OUTPUT %s; the initial plan is not formed from stale build outputs"
              % "; ".join(problems), file=sys.stderr)
        raise SystemExit(1)
    return {"generated_roots": roots, "stale": problems}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--phase", choices=("before", "after"), required=True)
    ap.add_argument("--diagnostics", default="")
    ap.add_argument("--since-ms", type=int, default=0)
    ap.add_argument("--out", default="", help="write the record here (JSON) as well as stdout")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    rec = before(root) if a.phase == "before" else after(root, Path(a.diagnostics), a.since_ms)
    text = json.dumps(rec, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    os.umask(0o022)
    raise SystemExit(main())
