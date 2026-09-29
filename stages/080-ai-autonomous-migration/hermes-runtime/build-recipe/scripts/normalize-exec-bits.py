#!/usr/bin/env python3
"""Set the exec bit on every runnable file (ELF or shebang) under the given trees.

dest-init's kantra-assert-exec treats every ELF or shebang file under an
install prefix as runnable and refuses the tree when one lacks the exec bit
and the workspace uid (random on OpenShift) cannot chmod it. The MTA CLI
8.2.1.1 archive ships rulesets/go/fips/tests/data/build/build.sh as 0644
(measured live 2026-09-09: the scan fell through to kantra). Run at image
build time as root with the checker's own definition of runnable.
"""
import os
import sys

fixed = 0
seen = 0
for root_dir in sys.argv[1:]:
    for d, _, files in os.walk(root_dir):
        for f in files:
            path = os.path.join(d, f)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as fh:
                    head = fh.read(4)
            except OSError:
                continue
            if head == b"\x7fELF" or head[:2] == b"#!":
                seen += 1
                mode = os.stat(path).st_mode
                if mode & 0o111 != 0o111:
                    os.chmod(path, mode | 0o111)
                    fixed += 1
print("exec bits normalized on %d of %d runnable files under %s" % (fixed, seen, " ".join(sys.argv[1:])))
if not seen:
    sys.exit("normalize-exec-bits: no runnable files found; wrong prefix?")
