#!/usr/bin/env python3
"""Deterministic dependency analysis of a legacy Java tree (MigIQ
adoption: graph-driven task ordering, without the graphify runtime).

Usage: dependency-order.py <source-root> [> migration/dependency-order.md]

Builds the intra-project reference graph from explicit imports PLUS
same-package simple-name references (V4: token-scan for sibling class
names — the S01 blind spot where ShoppingCart -> ShoppingCartItem was
invisible because same-package use needs no import). Emits markdown:
per-class fan-in/fan-out, god nodes, and a dependencies-first conversion
order. In a single-shot rewrite the tree must compile at every commit,
so dependencies convert BEFORE their dependents (the inverse of
strangler-style leaf-first migration).
"""
import collections
import os
import re
import sys


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    pkg_re = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
    imp_re = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(?:\.\*)?\s*;", re.M)

    classes = {}  # FQN -> relpath
    imports = {}  # FQN -> set of referenced FQNs (project-internal, filled later)
    raw_imports = {}
    bodies = {}
    for dirpath, _, files in os.walk(root):
        if any(part in dirpath for part in ("/target", "/.git", "/node_modules", "/src/test")):
            continue
        for fn in files:
            if not fn.endswith(".java"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            pkg = pkg_re.search(text)
            fqn = (pkg.group(1) + "." if pkg else "") + fn[:-5]
            classes[fqn] = os.path.relpath(path, root)
            raw_imports[fqn] = set(imp_re.findall(text))
            bodies[fqn] = text

    # simple name -> FQNs per package, for same-package resolution
    by_pkg = collections.defaultdict(dict)
    for fqn in classes:
        pkg, _, simple = fqn.rpartition(".")
        by_pkg[pkg][simple] = fqn

    for fqn, imps in raw_imports.items():
        imports[fqn] = {i for i in imps if i in classes and i != fqn}
        # wildcard package imports: pull in every project class of that package
        for i in imps:
            for other in classes:
                if other != fqn and other.rpartition(".")[0] == i:
                    imports[fqn].add(other)
        # same-package references need no import (the S01 blind spot):
        # a whole-word token match on a sibling simple name is an edge.
        pkg = fqn.rpartition(".")[0]
        for simple, sibling in by_pkg[pkg].items():
            if sibling == fqn or sibling in imports[fqn]:
                continue
            if re.search(rf"\b{re.escape(simple)}\b", bodies[fqn]):
                imports[fqn].add(sibling)

    fan_in = collections.Counter()
    for fqn, deps in imports.items():
        for d in deps:
            fan_in[d] += 1

    # Kahn topological sort: dependencies first; ties by fan-in desc then name
    remaining = dict(imports)
    order, cycle = [], []
    while remaining:
        ready = sorted((f for f, d in remaining.items() if not (d & remaining.keys())),
                       key=lambda f: (-fan_in[f], f))
        if not ready:  # cycle — emit the rest as a coupled group
            cycle = sorted(remaining)
            break
        for f in ready:
            order.append(f)
            del remaining[f]

    print("# Legacy dependency analysis (scripted, M1)")
    print()
    print(f"- Classes: {len(classes)}; intra-project reference edges: "
          f"{sum(len(v) for v in imports.values())}")
    print("- Edges from explicit imports AND same-package simple-name"
          " references (token scan; over-approximates on name collisions,"
          " which only tightens coupling groups).")
    print()
    print("## God nodes (highest fan-in — pin behavior with characterization"
          " tests BEFORE converting)")
    print()
    print("| class | fan-in | fan-out |")
    print("|---|---|---|")
    for fqn, n in fan_in.most_common(5):
        print(f"| {fqn} | {n} | {len(imports.get(fqn, ()))} |")
    print()
    print("## Conversion order (dependencies first — the tree must compile at"
          " every commit)")
    print()
    for i, fqn in enumerate(order, 1):
        marks = []
        if fan_in[fqn] >= 3:
            marks.append("god-node: characterization tests first")
        print(f"{i}. {fqn} ({classes[fqn]})" + (" — " + "; ".join(marks) if marks else ""))
    if cycle:
        print()
        print("## Circular group (convert together in ONE task)")
        print()
        for fqn in cycle:
            print(f"- {fqn} ({classes[fqn]})")


if __name__ == "__main__":
    main()
