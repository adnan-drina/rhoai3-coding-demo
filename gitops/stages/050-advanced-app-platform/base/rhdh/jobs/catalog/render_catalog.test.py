#!/usr/bin/env python3
"""B2 regressions for the RHDH runtime catalog bundle, run locally.

  * every file under templates/ and catalog/, and the generator and renderer
    themselves, are in the configMapGenerator bundle (so a template-only
    change changes the bundle)
  * a catalog-only change changes the bundle's content-hashed name, and the
    Job and CronJob follow it (kustomize)
  * an old generator against a new catalog, and a semantic skew that adds no
    placeholder, are FACTORY_BUNDLE_MISMATCH: generate.sh publishes nothing
  * a failed render publishes nothing: the last good catalog stays
  * a published catalog pins every link -- techdocs AND template Locations --
    to the one revision the bundle was verified at, and stamps the bundle id
The end-to-end cases run the real generate.sh against a fake `oc` and a
file:// repository, twice, under two revisions and two host sets.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RHDH = HERE.parents[1]
sys.path.insert(0, str(HERE))
import render_catalog as rc  # noqa: E402

FAKE_OC = r'''#!/usr/bin/env bash
# fake oc: answers what generate.sh asks, records every mutation
log="${FAKE_OC_LOG}"
args="$*"
echo "$args" >> "${log}.calls"
case "$args" in
  *"get application"*"syncResult.revision"*) echo -n "${FAKE_REVISION}";;
  *"get application"*"sync.revision"*) echo -n "${FAKE_REVISION}";;
  *"get application"*"repoURL"*) echo -n "https://github.com/example/demo.git";;
  *"get route devspaces"*) echo -n "devspaces.${FAKE_DOMAIN}";;
  *"get route coolstore-inventory-service"*) echo -n "coolstore.${FAKE_DOMAIN}";;
  *"get route sonarqube"*) echo -n "sonarqube.${FAKE_DOMAIN}";;
  *"get gateway maas-default-gateway"*) echo -n "${FAKE_MAAS_HOST}";;
  *"get service maas-gateway-internal"*) echo -n "${FAKE_MAAS_IP}";;
  *"get configmap catalog-runtime-rhdh"*"annotations"*) exit 1;;
  *"get configmap catalog-runtime-rhdh"*) exit 0;;
  *"get pods"*) exit 0;;
  *"patch configmap catalog-runtime-rhdh"*) echo "$args" >> "${log}.published";;
  *"create configmap"*|*"annotate configmap"*) echo "$args" >> "${log}.published";;
  *) exit 0;;
esac
'''


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _listed() -> dict[str, str]:
    text = (RHDH / "kustomization.yaml").read_text(encoding="utf-8")
    return dict(re.findall(r"^\s*-\s+([\w.-]+)=(\S+)\s*$", text, re.M))


def _coverage_case() -> int:
    listed = _listed()
    want = {p.relative_to(RHDH).as_posix() for d in ("templates", "catalog") for p in (RHDH / d).rglob("*") if p.is_file()}
    want |= {"jobs/catalog/generate.sh", "jobs/catalog/render_catalog.py"}
    missing = sorted(want - set(listed.values()))
    if missing:
        return _fail("files the bundle must carry are not in the configMapGenerator: %s" % missing)
    bad = sorted(k for k, v in listed.items() if rc.key_path(k) != "%s/%s" % (rc.RHDH_BASE, v))
    if bad:
        return _fail("bundle keys that do not spell their path: %s" % bad)
    return 0


def _kustomize(dir_: Path) -> str:
    return subprocess.run(["oc", "kustomize", str(dir_)], check=True, capture_output=True, text=True).stdout


def _bundle_name_case() -> int:
    if not shutil.which("oc"):
        print("SKIP bundle-name case: no oc on PATH")
        return 0
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / "rhdh"
        shutil.copytree(RHDH, copy)
        before = re.findall(r"rhdh-catalog-bundle-[a-z0-9]+", _kustomize(copy))
        cat = copy / "catalog" / "all.yaml"
        cat.write_text(cat.read_text(encoding="utf-8") + "\n# a catalog-only change\n", encoding="utf-8")
        after = re.findall(r"rhdh-catalog-bundle-[a-z0-9]+", _kustomize(copy))
    if len(set(before)) != 1 or len(set(after)) != 1 or set(before) == set(after):
        return _fail("a catalog-only change changes the bundle name: %s -> %s" % (sorted(set(before)), sorted(set(after))))
    if len(after) < 3:
        return _fail("the ConfigMap, the Job and the CronJob all name the bundle: %d references" % len(after))
    return 0


def _stage(td: Path, revision: str, *, skew: dict[str, bytes] | None = None) -> tuple[Path, Path]:
    """A bundle dir (as the ConfigMap volume presents it) and a file:// repo
    holding the same files at `revision`, optionally skewed."""
    bundle = td / "bundle"
    bundle.mkdir()
    for key, rel in _listed().items():
        shutil.copy(RHDH / rel, bundle / key)
    (bundle / "..data").mkdir()  # a ConfigMap volume's own link dir is not a bundle file
    repo = td / "repo" / revision
    for key in rc.bundle_files(bundle):
        dst = repo / rc.key_path(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((skew or {}).get(key, (bundle / key).read_bytes()))
    return bundle, td / "repo"


def _generate(td: Path, bundle: Path, repo: Path, revision: str, host: str, ip: str, domain: str) -> tuple[int, str, Path]:
    bindir = td / "bin"
    bindir.mkdir(exist_ok=True)
    oc = bindir / "oc"
    oc.write_text(FAKE_OC, encoding="utf-8")
    oc.chmod(oc.stat().st_mode | stat.S_IEXEC)
    log = td / "oc"
    env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ.get("PATH", "")), FAKE_OC_LOG=str(log),
               FAKE_REVISION=revision, FAKE_MAAS_HOST=host, FAKE_MAAS_IP=ip, FAKE_DOMAIN=domain,
               BUNDLE_DIR=str(bundle), CATALOG_RAW_BASE=repo.as_uri())
    p = subprocess.run(["bash", str(bundle / "jobs__catalog__generate.sh")], env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr, log


def _end_to_end_case(revision: str, host: str, ip: str, domain: str) -> int:
    # (1) the published catalog: one revision everywhere, the bundle stamped
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        bundle, repo = _stage(td, revision)
        rcode, out, log = _generate(td, bundle, repo, revision, host, ip, domain)
        if rcode != 0:
            return _fail("a coherent bundle publishes: %s" % out[-800:])
        published = (Path(str(log) + ".published")).read_text(encoding="utf-8")
        patch = json.loads(published.split("-p ", 1)[1].strip())
        body = patch["data"]["all.yaml"]
        ann = patch["metadata"]["annotations"]
        if ann.get("rhoai3.redhat.com/catalog-revision") != revision or ann.get("rhoai3.redhat.com/catalog-bundle") != rc.digest(rc.bundle_files(bundle)):
            return _fail("the published catalog is stamped with its revision and bundle id: %s" % ann)
        locations = re.findall(r"target:\s+(\S*templates/[^/]+/template\.yaml)", body)
        if len(locations) != 2 or not all("/blob/%s/" % revision in t for t in locations):
            return _fail("template Locations resolve at the bundle revision, never a branch: %s" % locations)
        if "tree/%s" % revision not in body or "__RHOAI3_" in body or "placeholder.example.com" in body:
            return _fail("every link is pinned and every placeholder resolved")
        if "maas-host: %s" % host not in body or "maas-internal-ip: %s" % ip not in body:
            return _fail("the MaaS route values reach the platform entity")
    # (2) an OLD generator (and renderer) against a NEW catalog at the revision
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        newer = (RHDH / "catalog" / "all.yaml").read_bytes() + b"\n# the catalog moved on\n"
        bundle, repo = _stage(td, revision, skew={"catalog__all.yaml": newer})
        rcode, out, log = _generate(td, bundle, repo, revision, host, ip, domain)
        if rcode == 0 or "FACTORY_BUNDLE_MISMATCH" not in out or Path(str(log) + ".published").exists():
            return _fail("an old generator against a new catalog publishes nothing: rc=%s %s" % (rcode, out[-600:]))
    # (3) a semantic skew with no new placeholder: a template changed at the revision
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        key = "templates__app-migration__template.yaml"
        changed = (RHDH / "templates/app-migration/template.yaml").read_bytes().replace(b"maasHost", b"maasHostName", 1)
        bundle, repo = _stage(td, revision, skew={key: changed})
        rcode, out, log = _generate(td, bundle, repo, revision, host, ip, domain)
        if rcode == 0 or "FACTORY_BUNDLE_MISMATCH" not in out or "app-migration/template.yaml" not in out \
                or Path(str(log) + ".published").exists():
            return _fail("a template skew that adds no placeholder is refused: rc=%s %s" % (rcode, out[-600:]))
    # (4) a failed render keeps the last good catalog
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        bundle, repo = _stage(td, revision)
        rcode, out, log = _generate(td, bundle, repo, revision, "https://not-a-host/", ip, domain)
        if rcode == 0 or "CATALOG_RENDER" not in out or Path(str(log) + ".published").exists():
            return _fail("a failed render publishes nothing: rc=%s %s" % (rcode, out[-600:]))
    return 0


def main() -> int:
    if _coverage_case() or _bundle_name_case():
        return 1
    if (_end_to_end_case("a" * 40, "maas.apps.example.test", "172.30.250.250", "apps.example.test")
            or _end_to_end_case("0123456789abcdef0123456789abcdef01234567", "gw.cluster-b.lab", "10.0.4.7", "cluster-b.lab")):
        return 1
    print("OK: rhdh catalog bundle (every template and catalog file is bundled; a catalog-only change renames the bundle "
          "and the Job and CronJob follow; an old generator against a new catalog and a placeholder-free template skew are "
          "FACTORY_BUNDLE_MISMATCH with nothing published; a failed render publishes nothing; a published catalog pins "
          "techdocs and template Locations to the one verified revision and stamps the bundle id)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
