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

O-M1SCC: circular groups are true strongly connected components (SCCs)
with size > 1 — not the Kahn leftover / reachable-closure dump.
"""
import collections
import os
import re
import sys


def build_graph(root: str):
    """Return (classes, imports, fan_in) for project-internal Java refs."""
    pkg_re = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
    imp_re = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(?:\.\*)?\s*;", re.M)

    classes = {}  # FQN -> relpath
    imports = {}  # FQN -> set of referenced FQNs
    raw_imports = {}
    bodies = {}
    for dirpath, _, files in os.walk(root):
        # Skip build/VCS/test and Maven wrapper tooling (.mvn) — not migration units
        # (O-MVNUNIT: MavenWrapperDownloader under .mvn/wrapper must not block assign_stories).
        if any(
            part in dirpath
            for part in ("/target", "/.git", "/node_modules", "/src/test", "/.mvn")
        ):
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

    by_pkg = collections.defaultdict(dict)
    for fqn in classes:
        pkg, _, simple = fqn.rpartition(".")
        by_pkg[pkg][simple] = fqn

    for fqn, imps in raw_imports.items():
        imports[fqn] = {i for i in imps if i in classes and i != fqn}
        for i in imps:
            for other in classes:
                if other != fqn and other.rpartition(".")[0] == i:
                    imports[fqn].add(other)
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
    return classes, imports, fan_in


def strongly_connected_components(imports: dict) -> list:
    """Tarjan SCC. Returns list of components (each a list of FQNs)."""
    index = 0
    stack = []
    onstack = set()
    indices = {}
    lowlink = {}
    sccs = []

    def strongconnect(v):
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)
        for w in imports.get(v, ()):
            if w not in imports and w not in indices:
                # referenced but not a node — skip
                continue
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in sorted(imports):
        if v not in indices:
            strongconnect(v)
    return sccs


def conversion_order(imports: dict, fan_in: collections.Counter, sccs: list):
    """Dependencies-first order on the SCC condensation DAG (O-M1SCC)."""
    fqn_scc = {}
    for i, comp in enumerate(sccs):
        for f in comp:
            fqn_scc[f] = i
    # condensation edges: SCC a -> SCC b if some a member imports b member
    succ = collections.defaultdict(set)  # edge means "depends on"
    pred_count = collections.Counter()
    for i in range(len(sccs)):
        pred_count[i] = 0
    for fqn, deps in imports.items():
        a = fqn_scc.get(fqn)
        if a is None:
            continue
        for d in deps:
            b = fqn_scc.get(d)
            if b is None or b == a:
                continue
            if a not in succ[b]:  # b before a (dependency first)
                succ[b].add(a)
    for b, outs in succ.items():
        for a in outs:
            pred_count[a] += 1

    ready = sorted(
        (i for i in range(len(sccs)) if pred_count[i] == 0),
        key=lambda i: (
            -max((fan_in[f] for f in sccs[i]), default=0),
            min(sccs[i]),
        ),
    )
    order_fqn = []
    seen = set()
    while ready:
        i = ready.pop(0)
        if i in seen:
            continue
        seen.add(i)
        # within an SCC, stable by fan-in then name
        members = sorted(sccs[i], key=lambda f: (-fan_in[f], f))
        order_fqn.extend(members)
        for a in sorted(succ.get(i, ()), key=lambda j: (min(sccs[j]), j)):
            pred_count[a] -= 1
            if pred_count[a] == 0:
                ready.append(a)
        ready.sort(
            key=lambda j: (
                -max((fan_in[f] for f in sccs[j]), default=0),
                min(sccs[j]),
            )
        )
    # any orphans (shouldn't happen)
    for i, comp in enumerate(sccs):
        if i not in seen:
            order_fqn.extend(sorted(comp, key=lambda f: (-fan_in[f], f)))
    return order_fqn


def analyze(root: str) -> dict:
    classes, imports, fan_in = build_graph(root)
    # Ensure every class is a graph node (even with no imports)
    for fqn in classes:
        imports.setdefault(fqn, set())
    sccs = strongly_connected_components(imports)
    order = conversion_order(imports, fan_in, sccs)
    cycles = [sorted(c) for c in sccs if len(c) > 1]
    cycles.sort(key=lambda c: (len(c), c[0] if c else ""))
    return {
        "classes": classes,
        "imports": imports,
        "fan_in": fan_in,
        "sccs": sccs,
        "order": order,
        "cycles": cycles,
    }


def render(analysis: dict) -> str:
    classes = analysis["classes"]
    imports = analysis["imports"]
    fan_in = analysis["fan_in"]
    order = analysis["order"]
    cycles = analysis["cycles"]
    lines = []
    lines.append("# Legacy dependency analysis (scripted, M1)")
    lines.append("")
    lines.append(
        f"- Classes: {len(classes)}; intra-project reference edges: "
        f"{sum(len(v) for v in imports.values())}"
    )
    lines.append(
        "- Edges from explicit imports AND same-package simple-name"
        " references (token scan; over-approximates on name collisions,"
        " which only tightens coupling groups)."
    )
    lines.append(
        "- O-M1SCC: circular groups are true SCCs (size > 1), not Kahn leftovers."
    )
    lines.append("")
    lines.append(
        "## God nodes (highest fan-in — pin behavior with characterization"
        " tests BEFORE converting)"
    )
    lines.append("")
    lines.append("| class | fan-in | fan-out |")
    lines.append("|---|---|---|")
    for fqn, n in fan_in.most_common(5):
        lines.append(f"| {fqn} | {n} | {len(imports.get(fqn, ()))} |")
    lines.append("")
    lines.append(
        "## Conversion order (dependencies first — the tree must compile at"
        " every commit)"
    )
    lines.append("")
    for i, fqn in enumerate(order, 1):
        marks = []
        if fan_in[fqn] >= 3:
            marks.append("god-node: characterization tests first")
        lines.append(
            f"{i}. {fqn} ({classes[fqn]})"
            + (" — " + "; ".join(marks) if marks else "")
        )
    for n, comp in enumerate(cycles, 1):
        lines.append("")
        title = (
            "## Circular group (convert together in ONE task)"
            if n == 1
            else f"## Circular group {n} (convert together in ONE task)"
        )
        lines.append(title)
        lines.append("")
        for fqn in comp:
            lines.append(f"- {fqn} ({classes[fqn]})")
    lines.append("")
    return "\n".join(lines)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.stdout.write(render(analyze(root)))


if __name__ == "__main__":
    main()
