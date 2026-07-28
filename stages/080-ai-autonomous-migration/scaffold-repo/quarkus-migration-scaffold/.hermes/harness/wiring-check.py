#!/usr/bin/env python3
"""Behavior-preserving wiring check (PROCESS-FIX finding #1): a CDI
singleton with shared mutable state must use a concurrent collection or
confine mutation to initialization.

A class annotated @ApplicationScoped/@Singleton that declares a
non-concurrent mutable collection field (HashMap/ArrayList/HashSet/...)
which is mutated OUTSIDE a constructor or @PostConstruct method is a
thread-safety defect (V4 finding #1 / S03 T-001: the cart `carts`
HashMap mutated across request-handling methods on a singleton).

The init carve-out (constructor / @PostConstruct only) exempts the
populate-once-then-read cache, keeping false positives low.

Usage: wiring-check.py <src-main-dir>
Exit 0 = clean; exit 1 = violation(s) printed to stdout.
"""
import os
import re
import sys

SINGLETON = re.compile(r"@(ApplicationScoped|Singleton)\b")
NONCONCURRENT = r"(?:HashMap|LinkedHashMap|TreeMap|HashSet|LinkedHashSet|TreeSet|ArrayList|LinkedList)"
# a field declared as a mutable collection interface/impl
FIELD = re.compile(
    r"^\s*(?:private|protected)\s+(?:static\s+)?(?:final\s+)?"
    r"(?:Map|List|Set|Collection|" + NONCONCURRENT + r")\b[^=;\n]*?\b(\w+)\s*(?:=[^;]*)?;",
    re.M)
MUT = r"\.(?:put|putAll|putIfAbsent|add|addAll|remove|removeAll|clear|merge|replace|replaceAll|set)\s*\("


def method_spans(text, is_init):
    """Yield (start,end) char offsets of methods matching is_init(header)."""
    spans = []
    for m in re.finditer(r"([^\n;{}]*)\{", text):
        header = m.group(1)
        if not is_init(header, m.start()):
            continue
        depth, i = 0, m.end() - 1
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i))
                    break
            i += 1
    return spans


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "src/main/java"
    problems = []
    for dp, _, fs in os.walk(root):
        for fn in fs:
            if not fn.endswith(".java"):
                continue
            path = os.path.join(dp, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            if not SINGLETON.search(text):
                continue
            cls = fn[:-5]
            # init spans: constructor (name == class) or @PostConstruct-annotated
            post = [mm.end() for mm in re.finditer(r"@PostConstruct", text)]

            def is_init(header, start, cls=cls, post=post):
                if re.search(r"\b" + re.escape(cls) + r"\s*\(", header):
                    return True
                # @PostConstruct sits just above the method header
                return any(0 <= start - p < 120 for p in post)

            inits = method_spans(text, is_init)
            for fm in FIELD.finditer(text):
                # a concurrent/immutable field is safe by construction
                decl = fm.group(0)
                if re.search(r"Concurrent|CopyOnWrite|Collections\.(unmodifiable|synchronized)|(?:List|Set|Map)\.of\(", decl):
                    continue
                name = fm.group(1)
                # runtime mutation: a collection-mutator call OR a reassignment
                # (name = ...), but NOT the field's own declaration/initializer
                # and NOT `==` comparisons.
                for mm in re.finditer(r"\b" + re.escape(name) + r"(?:" + MUT + r"|\s*=(?!=))", text):
                    off = mm.start()
                    if fm.start() <= off <= fm.end():
                        continue  # the field declaration/initializer itself
                    if any(s <= off <= e for s, e in inits):
                        continue  # mutation confined to init — OK
                    line = text.count("\n", 0, off) + 1
                    problems.append(f"{path}:{line}: singleton '{cls}' mutates non-concurrent field '{name}' "
                                    f"outside init — use a concurrent collection or confine mutation to @PostConstruct/constructor")
                    break
    if problems:
        for p in problems:
            print(p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
