#!/usr/bin/env python3
"""RHDH runtime catalog: one bundle, one revision (B2).

The generator used to run from a synced ConfigMap while fetching all.yaml
from the branch HEAD. On 2026-09-24 an older script published a newer
catalog's __RHOAI3_MAAS_*__ placeholders verbatim, and a later change that
added no new placeholder would not have been caught at all.

Now the generator script, this renderer, the catalog and every template and
skeleton file are ONE ConfigMap produced by kustomize's configMapGenerator
from the same checkout. Its name carries a content hash, so a catalog-only or
template-only change is a manifest change Argo CD applies. This module:

  digest   -- the bundle's identity: sha256 over (key, sha256(content))
  verify   -- every bundled file is byte-identical at the revision the
              catalog will link to; otherwise FACTORY_BUNDLE_MISMATCH and the
              runtime catalog is left as it was
  render   -- substitutes the platform values and the ONE revision into the
              bundled catalog; refuses any placeholder it did not resolve

A bundle key is the file's path under gitops/.../base/rhdh with "/" spelled
"__" (a ConfigMap key cannot hold "/").
"""
import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

RHDH_BASE = "gitops/stages/050-advanced-app-platform/base/rhdh"
CATALOG_KEY = "catalog__all.yaml"
HOST_RE = re.compile(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*")
IPV4_RE = re.compile(r"(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}")
SHA_RE = re.compile(r"[0-9a-f]{40}")


class Refusal(SystemExit):
    pass


def key_path(key: str) -> str:
    return "%s/%s" % (RHDH_BASE, key.replace("__", "/"))


def bundle_files(bundle: Path) -> Dict[str, bytes]:
    """The bundle's files by key; a ConfigMap volume's ..data links and the
    generator's own dot-named work files are not files of it."""
    out = {}
    for p in sorted(Path(bundle).iterdir()):
        if p.name.startswith(".") or not p.is_file():
            continue
        out[p.name] = p.read_bytes()
    return out


def digest(files: Dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for key in sorted(files):
        h.update(key.encode("utf-8") + b"\0" + hashlib.sha256(files[key]).digest())
    return h.hexdigest()


def fetch_raw(raw_base: str) -> Callable[[str, str], Optional[bytes]]:
    def fetch(revision: str, path: str) -> Optional[bytes]:
        try:
            with urllib.request.urlopen("%s/%s/%s" % (raw_base.rstrip("/"), revision, path), timeout=20) as resp:
                return resp.read()
        except Exception:
            return None
    return fetch


def verify(files: Dict[str, bytes], revision: str, fetch: Callable[[str, str], Optional[bytes]]) -> List[str]:
    """Every bundled file as the repository holds it at `revision`, or why not.

    The catalog's links, its template Locations and the scaffolder's skeleton
    fetches all resolve at that one revision; a bundle that is not what that
    revision holds would publish links to content the generator never saw."""
    if not SHA_RE.fullmatch(revision or ""):
        return ["the revision %r is not a commit sha; a catalog is only ever pinned to one" % revision]
    if CATALOG_KEY not in files:
        return ["the bundle carries no %s" % CATALOG_KEY]
    gaps = []
    for key in sorted(files):
        got = fetch(revision, key_path(key))
        if got is None:
            gaps.append("%s is not readable at %s" % (key_path(key), revision[:12]))
        elif hashlib.sha256(got).digest() != hashlib.sha256(files[key]).digest():
            gaps.append("%s at %s is not the bundled file (%s vs %s)" % (
                key_path(key), revision[:12], hashlib.sha256(got).hexdigest()[:12],
                hashlib.sha256(files[key]).hexdigest()[:12]))
    return gaps


def render(content: str, *, revision: str, devspaces_url: str, rhdh_url: str, coolstore_url: str,
           sonarqube_url: str, maas_host: str, maas_internal_ip: str) -> str:
    # A hostAlias hostname must be a bare RFC 1123 host: a URL fragment here
    # made the v7 workspace deployment invalid. Refuse rather than publish one.
    if not HOST_RE.fullmatch(maas_host or ""):
        raise Refusal("MaaS gateway https listener hostname %r is not an RFC 1123 host" % maas_host)
    if not IPV4_RE.fullmatch(maas_internal_ip or ""):
        raise Refusal("maas-gateway-internal clusterIP %r is not an IPv4 address" % maas_internal_ip)
    if not SHA_RE.fullmatch(revision or ""):
        raise Refusal("the catalog revision %r is not a commit sha" % revision)
    out = content.replace("https://coolstore-inventory-route.placeholder.example.com", coolstore_url.rstrip("/"))
    for placeholder in ("https://devspaces.placeholder.example.com", "https://devspaces-inventory.placeholder.example.com"):
        out = out.replace(placeholder, devspaces_url.rstrip("/"))
    out = out.replace("https://rhdh.placeholder.example.com", rhdh_url.rstrip("/"))
    out = out.replace("https://sonarqube.placeholder.example.com", sonarqube_url.rstrip("/"))
    # B2: template Locations resolve at the SAME revision as every other link,
    # so the template and its skeleton are the bundled ones, never a moving
    # branch head (superseded Locations are pruned by the generator).
    out = out.replace("__RHOAI3_DEMO_LOCATION_REF__", revision)
    out = out.replace("__RHOAI3_DEMO_REVISION__", revision)
    out = out.replace("__RHOAI3_MAAS_HOST__", maas_host)
    out = out.replace("__RHOAI3_MAAS_INTERNAL_IP__", maas_internal_ip)
    if "placeholder.example.com" in out:
        raise Refusal("a placeholder link was not replaced: %s" % sorted(set(re.findall(r"https://[\w.-]*placeholder\.example\.com", out))))
    leftover = sorted(set(re.findall(r"__RHOAI3_[A-Z0-9_]+__", out)))
    if leftover:
        raise Refusal("unreplaced catalog placeholders %s" % leftover)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True   # add_subparsers(required=...) is Python 3.7+; the job image has 3.6
    d = sub.add_parser("digest")
    d.add_argument("--bundle", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--bundle", required=True)
    v.add_argument("--raw-base", required=True)
    v.add_argument("--revision", required=True)
    r = sub.add_parser("render")
    r.add_argument("--bundle", required=True)
    r.add_argument("--out", required=True)
    for name in ("revision", "devspaces-url", "rhdh-url", "coolstore-url", "sonarqube-url", "maas-host", "maas-internal-ip"):
        r.add_argument("--" + name, default="")
    a = ap.parse_args(argv)
    files = bundle_files(Path(a.bundle))
    if a.cmd == "digest":
        print(digest(files))
        return 0
    if a.cmd == "verify":
        gaps = verify(files, a.revision, fetch_raw(a.raw_base))
        if gaps:
            print("REFUSE FACTORY_BUNDLE_MISMATCH: bundle %s, revision %s: %s; runtime catalog unchanged"
                  % (digest(files)[:16], a.revision[:12], "; ".join(gaps[:3])), file=sys.stderr)
            return 1
        print("bundle %s is what %s holds (%d files)" % (digest(files)[:16], a.revision[:12], len(files)))
        return 0
    content = files[CATALOG_KEY].decode("utf-8")
    try:
        out = render(content, revision=a.revision, devspaces_url=a.devspaces_url, rhdh_url=a.rhdh_url,
                     coolstore_url=a.coolstore_url, sonarqube_url=a.sonarqube_url, maas_host=a.maas_host,
                     maas_internal_ip=a.maas_internal_ip)
    except Refusal as exc:
        print("REFUSE CATALOG_RENDER: %s; runtime catalog unchanged" % exc.code, file=sys.stderr)
        return 1
    Path(a.out).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
