#!/usr/bin/env python3
"""Negative controls for Lead:catalog-location-must-not-accumulate, under B2.

History: SHA-pinned template Locations once accumulated (every re-stamp
minted a new Backstage location and the old one stayed), so Locations were
moved to the branch ref. B2 (2026-09-24) needs the template and its skeleton
to resolve at the SAME revision as the bundle the generator published --
a branch head can move ahead of the synced bundle. So Locations are pinned
again, to the published revision, and the prune removes every template
Location of ANY OTHER revision: one Location per template, never a pile.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

JOBS = Path(__file__).resolve().parent
CATALOG = JOBS.parent / "catalog" / "all.yaml"
GENERATOR = JOBS / "catalog" / "generate.sh"
RBAC = JOBS / "generate-rhdh-catalog.yaml"
sys.path.insert(0, str(JOBS / "catalog"))
from render_catalog import render  # noqa: E402

SHA_BLOB_TEMPLATE = re.compile(
    r"/blob/[0-9a-f]{40}/gitops/stages/050-advanced-app-platform"
    r"/base/rhdh/templates/[^/]+/template\.yaml"
)
LOCATION_TARGET = re.compile(
    r"target:\s+(\S*templates/(?:app-migration|agentic-quarkus-scaffold)/template\.yaml)"
)
VALUES = dict(devspaces_url="https://devspaces.apps.example.test", rhdh_url="",
              coolstore_url="https://coolstore.apps.example.test", sonarqube_url="https://sonar.apps.example.test",
              maas_host="maas.apps.example.test", maas_internal_ip="172.30.250.250")


def _fail(msg: str) -> int:
    print("FAIL:", msg, file=sys.stderr)
    return 1


def pruned(target: str, current: str) -> bool:
    """The generator's prune predicate: a SHA-pinned template Location of a
    revision other than the published one."""
    return bool(SHA_BLOB_TEMPLATE.search(target or "")) and ("/blob/%s/" % current) not in target


def main() -> int:
    catalog = CATALOG.read_text(encoding="utf-8")
    gen = GENERATOR.read_text(encoding="utf-8")
    rbac = RBAC.read_text(encoding="utf-8")

    loc_targets = LOCATION_TARGET.findall(catalog)
    if len(loc_targets) != 2:
        return _fail("expected 2 golden-path Location targets, got %s" % loc_targets)
    sha, older = "a" * 40, "b" * 40
    rendered = render(catalog, revision=sha, **VALUES)
    targets = LOCATION_TARGET.findall(rendered)
    if len(targets) != 2 or not all(("/blob/%s/" % sha) in t for t in targets):
        return _fail("rendered Locations resolve at the published revision: %s" % targets)
    if "tree/%s" % sha not in rendered:
        return _fail("techdocs-ref pins the same revision")
    if "AND target !~ '/blob/${APP_SYNC_REVISION}/'" not in gen or "unprocessed_entity !~ '/blob/${APP_SYNC_REVISION}/'" not in gen:
        return _fail("the generator prunes template Locations of every OTHER revision, never the published one")
    if "pods/exec" not in rbac:
        return _fail("job Role must grant pods/exec for the postgres prune")
    current = [t for t in targets]
    superseded = [t.replace("/blob/%s/" % sha, "/blob/%s/" % older) for t in targets]
    other = "https://github.com/example/coolstore-app/blob/%s/catalog-info.yaml" % older
    if any(pruned(t, sha) for t in current):
        return _fail("the published revision's Locations are kept")
    if not all(pruned(t, sha) for t in superseded):
        return _fail("a superseded revision's template Locations are the prune set")
    if pruned(other, sha):
        return _fail("an unrelated SHA blob is never pruned")
    print("OK: catalog Locations resolve at the published bundle revision; every other revision's template "
          "Locations are the prune set, so they cannot accumulate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
