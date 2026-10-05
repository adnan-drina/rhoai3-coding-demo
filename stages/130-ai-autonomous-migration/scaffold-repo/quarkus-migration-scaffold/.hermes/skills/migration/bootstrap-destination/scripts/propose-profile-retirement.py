#!/usr/bin/env python3
"""Propose the profile conditions a run would retire — and accept none of them.

The bootstrap refuses to retire a profile gate the decisions file has not
enumerated, because a blanket retirement absorbs whatever the tree happens to
contain. Enumerating by hand is tedious and error-prone, so this proposes the
rows; it does not write decisions.yaml, and it never will. The whole point of
the enumeration is that a person read it.

A condition is proposed when the destination does not activate its profile,
because that is precisely the condition whose bean disappears at build time
with nothing to say about it. A condition on an ACTIVE profile is never
proposed: it is doing its job.

Retiring a condition does NOT remove its bean. `@IfBuildProfile("x")` says the
bean exists only under profile x; removing the annotation makes the bean
unconditional, so it is always there. Activating x and retiring the condition
are both ways to give the destination that bean, and they differ in what they
preserve: activation keeps the legacy's selection semantics and leaves the
sources alone, retirement records that the alternatives the condition selected
between are gone. What loses the bean is the third option -- deciding
nothing.

  python3 propose-profile-retirement.py --root .
  python3 propose-profile-retirement.py --root . --active jpa   # what-if

Paste the emitted block under build_profiles in decisions.yaml, together with
the inventory_sha256 it prints: that digest binds the list to the tree it was
read from, and the bootstrap refuses a list bound to a different one.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The condition scanner is the bootstrap's own: a proposer that read the tree
# its own way would propose rows the applier cannot match.
_spec = importlib.util.spec_from_file_location("_bootstrap_destination", HERE / "bootstrap-destination.py")
_bootstrap = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_bootstrap)

from planner.canonical import sha256_file  # noqa: E402
from planner.decisions import build_profiles, load_decisions  # noqa: E402
from planner.paths import DECISIONS, TYPE_INVENTORY  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--active", default="", help="comma-separated profiles to treat as active (default: decisions.yaml)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    if args.active:
        active = [x.strip() for x in args.active.split(",") if x.strip()]
    else:
        doc = load_decisions(root) if (root / DECISIONS).is_file() else {}
        active = [str(x) for x in (build_profiles(doc).get("active") or [])]

    rows = [c for c in _bootstrap.profile_conditions(root) if c["profile"] not in set(active)]
    ti = root / TYPE_INVENTORY
    inv = sha256_file(ti) if ti.is_file() else ""
    if not rows:
        print("nothing to propose: every profile condition in this tree is on an active profile (%s)"
              % (", ".join(active) or "none"))
        return 0
    print("# %d condition(s) on profiles this run does not activate (%s)." % (len(rows), ", ".join(active) or "none"))
    print("# Read every row before accepting it: each one makes its bean UNCONDITIONAL,")
    print("# which is a decision about the alternatives that condition selected between.")
    print("build_profiles:")
    print("  inventory_sha256: %s" % (inv or "MISSING-run-the-inventory-producer-first"))
    print("  retire:")
    for c in rows:
        print("    - path: %s" % c["path"])
        print("      type: %s" % c["type"])
        print("      member: %s" % ('"%s"' % c["member"] if c["member"] else '""'))
        print("      annotation: %s" % c["annotation"])
        print("      profile: %s" % c["profile"])
        print("      reason: \"\"  # say what the destination does instead")
    print("\n# proposed only. This tool does not write %s." % DECISIONS, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
