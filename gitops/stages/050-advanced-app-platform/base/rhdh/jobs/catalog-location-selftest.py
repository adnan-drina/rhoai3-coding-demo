#!/usr/bin/env python3
"""Negative controls for Lead:catalog-location-must-not-accumulate.

Pre-fix: Location spec.target was blob/<40-hex-sha>/template.yaml, so each
catalog re-stamp minted a new Backstage location while the old one stayed.
Post-fix: Location targets use Argo targetRevision; SHA blob URLs for the
golden-path templates are the prune set.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

JOBS = Path(__file__).resolve().parent
CATALOG = JOBS.parent / "catalog" / "all.yaml"
GENERATOR = JOBS / "rhdh-catalog-generator-script.yaml"
RBAC = JOBS / "generate-rhdh-catalog.yaml"

SHA_BLOB_TEMPLATE = re.compile(
    r"/blob/[0-9a-f]{40}/gitops/stages/050-advanced-app-platform"
    r"/base/rhdh/templates/[^/]+/template\.yaml"
)
LOCATION_TARGET = re.compile(
    r"target:\s+(\S*templates/(?:app-migration|agentic-quarkus-scaffold)/template\.yaml)"
)


def _fail(msg: str) -> int:
    print("FAIL:", msg, file=sys.stderr)
    return 1


def is_sha_pinned_template_location(url: str) -> bool:
    return bool(SHA_BLOB_TEMPLATE.search(url or ""))


def render(content: str, *, revision: str, location_ref: str) -> str:
    out = content.replace("__RHOAI3_DEMO_LOCATION_REF__", location_ref)
    out = out.replace("__RHOAI3_DEMO_REVISION__", revision)
    return out


def main() -> int:
    catalog = CATALOG.read_text(encoding="utf-8")
    gen = GENERATOR.read_text(encoding="utf-8")
    rbac = RBAC.read_text(encoding="utf-8")

    loc_targets = LOCATION_TARGET.findall(catalog)
    if len(loc_targets) != 2:
        return _fail("expected 2 golden-path Location targets, got %s" % loc_targets)
    for t in loc_targets:
        if "__RHOAI3_DEMO_LOCATION_REF__" not in t:
            return _fail("Location target is not the stable-ref placeholder: %s" % t)
        if "__RHOAI3_DEMO_REVISION__" in t:
            return _fail("Location target still uses the SHA placeholder: %s" % t)

    if "backstage.io/techdocs-ref: url:" not in catalog or "__RHOAI3_DEMO_REVISION__" not in catalog:
        return _fail("techdocs-ref must still use __RHOAI3_DEMO_REVISION__")

    if "__RHOAI3_DEMO_LOCATION_REF__" not in gen or "sys.argv[8]" not in gen:
        return _fail("generator must replace LOCATION_REF from argv[8] (Argo targetRevision)")
    if "Pruned SHA-pinned" not in gen or SHA_BLOB_TEMPLATE.pattern.split("templates")[0] not in gen:
        if "blob/[0-9a-f]{40}/gitops/stages/050-advanced-app-platform" not in gen:
            return _fail("generator must prune SHA-pinned template Locations")
    if "pods/exec" not in rbac:
        return _fail("job Role must grant pods/exec for the postgres prune")

    sha = "a" * 40
    branch = "harness-v2"
    rendered = render(catalog, revision=sha, location_ref=branch)
    if "__RHOAI3_DEMO_" in rendered:
        return _fail("placeholders remain after render")

    rendered_targets = LOCATION_TARGET.findall(rendered)
    for t in rendered_targets:
        if is_sha_pinned_template_location(t):
            return _fail("rendered Location still SHA-pinned: %s" % t)
        if f"/blob/{branch}/" not in t:
            return _fail("rendered Location missing stable ref %s: %s" % (branch, t))
        if sha in t:
            return _fail("rendered Location contains the commit SHA: %s" % t)

    if f"tree/{sha}" not in rendered:
        return _fail("techdocs-ref must still pin the catalog SHA")

    pre = render(catalog.replace("__RHOAI3_DEMO_LOCATION_REF__", "__RHOAI3_DEMO_REVISION__"),
                 revision=sha, location_ref=branch)
    pre_targets = LOCATION_TARGET.findall(pre)
    if not pre_targets or not all(is_sha_pinned_template_location(t) for t in pre_targets):
        return _fail("pre-fix simulation must SHA-pin Location targets: %s" % pre_targets)

    keep = (
        f"https://github.com/adnan-drina/rhoai3-coding-demo/blob/{branch}/"
        "gitops/stages/050-advanced-app-platform/base/rhdh/templates/"
        "app-migration/template.yaml"
    )
    drop = (
        f"https://github.com/adnan-drina/rhoai3-coding-demo/blob/{sha}/"
        "gitops/stages/050-advanced-app-platform/base/rhdh/templates/"
        "app-migration/template.yaml"
    )
    other = "https://github.com/example/coolstore-app/blob/%s/catalog-info.yaml" % sha
    if not is_sha_pinned_template_location(drop):
        return _fail("SHA template blob must match prune regex")
    if is_sha_pinned_template_location(keep):
        return _fail("branch template blob must not match prune regex")
    if is_sha_pinned_template_location(other):
        return _fail("unrelated SHA blob must not match prune regex")

    print("OK: catalog Locations use Argo targetRevision; SHA blob templates are the prune set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
