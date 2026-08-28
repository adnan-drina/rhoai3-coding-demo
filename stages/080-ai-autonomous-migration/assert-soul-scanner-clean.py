#!/usr/bin/env python3
"""Every shipped SOUL.md must survive Hermes's own prompt-injection scanner.

gs-rest-service-v16 failed dest-init at postStart because the dest-user
SOUL.md said "Do not pretend to be them.", which matches
``tools.threat_patterns`` ``role_pretend``
(``pretend\\s+(you\\s+are|to\\s+be)``). ``load_soul_md`` then returned
``[BLOCKED: ...]``, the AD-H section 14 load-time smoke refused, and
dest-init fail-closed before the gateway.

Nothing caught it at land time: no gate ran the scanner. The smoke that
did catch it runs on a workspace, where the cost is a dead cut.

Land-time only, so it lives beside validate.sh rather than in the shipped
tree: ``.hermes/lib/`` is importable modules only (no ``__main__``).

This asserts the *same* table Hermes uses. It does not restate the
patterns — a copied literal drifts from the installed agent and would
re-create the class of defect it is meant to catch.

Absence of the agent tree is a REFUSE, never a skip: a gate that cannot
find what it checks has not checked it. Set HERMES_AGENT_ROOT to override.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
STAGE = HERE.parent
REPO = STAGE.parents[1]
SCAFFOLD = STAGE / "scaffold-repo" / "quarkus-migration-scaffold"

SOULS = [
    SCAFFOLD / ".hermes" / "SOUL.md",
    *[
        SCAFFOLD / ".hermes" / "config" / "profiles" / f"{n}.SOUL.md"
        for n in ("orchestrator", "implementer", "reviewer")
    ],
]


def candidate_roots() -> list[Path]:
    env = os.environ.get("HERMES_AGENT_ROOT", "").strip()
    if env:
        return [Path(env)]
    roots = [Path("/opt/hermes-agent")]
    out = REPO / "workspace-images" / "out"
    if out.is_dir():
        roots += sorted(
            (p for p in out.glob("hermes-agent-*") if p.is_dir()), reverse=True
        )
    return roots


def load_patterns() -> tuple[list, Path]:
    tried = []
    for root in candidate_roots():
        if not (root / "tools" / "threat_patterns.py").is_file():
            tried.append(str(root))
            continue
        sys.path.insert(0, str(root))
        try:
            import tools.threat_patterns as tp
        except Exception as exc:
            raise SystemExit(
                "REFUSE: cannot import threat_patterns from %s: %s" % (root, exc)
            )
        pats = getattr(tp, "_PATTERNS", None)
        if not pats:
            raise SystemExit(
                "REFUSE: %s/tools/threat_patterns.py exposes no _PATTERNS; the "
                "scanner shape changed — fix this gate, do not skip it" % root
            )
        return list(pats), root
    raise SystemExit(
        "REFUSE: no Hermes agent tree with tools/threat_patterns.py "
        "(searched: %s). Set HERMES_AGENT_ROOT. Absence is not a pass."
        % ", ".join(tried or ["<none>"])
    )


def main() -> int:
    pats, root = load_patterns()
    missing = [p for p in SOULS if not p.is_file()]
    if missing:
        print(
            "REFUSE: SOUL.md absent: %s" % ", ".join(str(p) for p in missing),
            file=sys.stderr,
        )
        return 1
    failures = []
    for path in SOULS:
        text = path.read_text(encoding="utf-8")
        for entry in pats:
            rx, name = entry[0], entry[1]
            m = re.search(rx, text, re.IGNORECASE)
            if m:
                failures.append((path.name, name, m.group(0).strip()[:60]))
    if failures:
        for fname, rule, frag in failures:
            print(
                "REFUSE: %s trips %s on %r — Hermes load_soul_md would return "
                "[BLOCKED] and dest-init fail-closed" % (fname, rule, frag),
                file=sys.stderr,
            )
        return 1
    print(
        "OK: SOUL injection-scanner clean (%d files, %d patterns, agent=%s)"
        % (len(SOULS), len(pats), root.name)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
