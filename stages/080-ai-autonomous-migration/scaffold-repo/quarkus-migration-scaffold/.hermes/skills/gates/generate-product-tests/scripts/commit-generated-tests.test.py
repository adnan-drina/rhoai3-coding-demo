#!/usr/bin/env python3
"""commit-generated-tests selftest: what makes the M4 tree retrievable again.

The generated parity tests are written at M4, into a tree that
``assert-retrievable-tree`` still requires to be committed. That gate is not
weakened; this step is what satisfies it, and only for the files the harness
wrote:

  commits      exactly the manifest's ``files[]``, the manifest, and whatever
               else sits under the generated roots.
  refuses      any other change to ``src`` or ``pom.xml`` -- a worker's edit is
               never swept into a harness commit. The pom is the bootstrap's
               (ADR-015), so it is already in HEAD when this runs.
  refuses      a tree ``generate-product-tests.py --check`` rejects: committing
               an edited expectation would make the edit the harness's own.
  idempotent   a re-run with nothing to commit says so and exits 0.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "commit-generated-tests.py"
GENERATOR = HERE / "generate-product-tests.py"
RETRIEVABLE = HERE.parents[1] / "assert-retrievable-tree" / "scripts" / "assert-retrievable-tree.py"
MANIFEST = "evidence/tests/generated-manifest.json"

sys.path.insert(0, str(HERE))
import parity_pom  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The fixture builder is the generator selftest's: this step reads exactly what
# that producer wrote, so a second fixture would be a second contract.
FIX = _load("generate_product_tests_test", HERE / "generate-product-tests.test.py")

FAILURES: list[str] = []


def fail(msg: str) -> int:
    FAILURES.append(msg)
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], text=True, capture_output=True)


def generate(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GENERATOR), "--root", str(root), *args], text=True, capture_output=True)


def scoped_status(root: Path) -> list[str]:
    out = git(root, "status", "--porcelain", "--untracked-files=all", "--", "src", "pom.xml")
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def bootstrapped_tree(tmp: Path, name: str) -> Path:
    """A destination as the bootstrap leaves it: the m4-parity block already in
    the committed pom (ADR-015), so M4 adds only the generated files."""
    root = FIX.build_root(tmp / name, FIX.SPEC_A)
    (root / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main" / "java" / "Placeholder.java").write_text("class Placeholder {}\n", encoding="utf-8")
    parity_pom.ensure_pom_profile(root, parity_pom.DEFAULT_OUT, parity_pom.DEFAULT_RESOURCES)
    git(root, "init", "-q")
    git(root, "config", "user.email", "dest@example.com")
    git(root, "config", "user.name", "dest")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "bootstrap")
    return root


def case_no_manifest(tmp: Path) -> int:
    root = bootstrapped_tree(tmp, "no-manifest")
    proc = run(root)
    if proc.returncode != 1 or "were never generated" not in proc.stderr:
        return fail("a tree with no manifest must refuse: rc=%s %s%s" % (proc.returncode, proc.stdout, proc.stderr))
    return 0


def case_commits_and_is_idempotent(tmp: Path) -> int:
    rc = 0
    root = bootstrapped_tree(tmp, "commit")
    proc = generate(root)
    if proc.returncode != 0:
        return fail("generation refused a bound fixture: %s%s" % (proc.stdout, proc.stderr))
    # ADR-015 at the seam: the bootstrap already wrote the block, so the M4
    # producer leaves pom.xml alone and only the generated files are dirty.
    if any(ln.endswith("pom.xml") for ln in scoped_status(root)):
        rc |= fail("the generator must not move a pom the bootstrap wrote: %s" % scoped_status(root))
    if not scoped_status(root):
        rc |= fail("test setup: the generated files must be untracked before the commit step")

    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    # The interaction this step exists for: the gate refuses the generated
    # files while they are untracked, and is not weakened to let them through.
    gate = subprocess.run([sys.executable, str(RETRIEVABLE), "--check-only", str(root)], text=True, capture_output=True)
    if gate.returncode != 1 or "src/parity-test" not in gate.stderr:
        rc |= fail("assert-retrievable-tree must refuse the untracked generated suite: rc=%s %s"
                   % (gate.returncode, gate.stderr))

    proc = run(root)
    if proc.returncode != 0:
        return fail("the commit step refused a generated tree: %s%s" % (proc.stdout, proc.stderr))
    if scoped_status(root):
        rc |= fail("src/ and pom.xml must be clean after the commit: %s" % scoped_status(root))
    gate = subprocess.run([sys.executable, str(RETRIEVABLE), "--check-only", str(root)], text=True, capture_output=True)
    if gate.returncode != 0:
        rc |= fail("assert-retrievable-tree must pass once the suite is committed: %s" % gate.stderr)

    subject = git(root, "log", "-1", "--pretty=%s").stdout.strip()
    author = git(root, "log", "-1", "--pretty=%an <%ae>").stdout.strip()
    want = "m4: generated product tests (corpus %s, generator %s)" % (
        str(manifest["corpus_sha256"])[:12], manifest["generator_version"])
    if subject != want:
        rc |= fail("the commit message must name the corpus and the generator: %r != %r" % (subject, want))
    if author != "generate-product-tests <generate-product-tests@local>":
        rc |= fail("the commit's author is the producer: %r" % author)

    committed = set(git(root, "show", "--name-only", "--pretty=", "HEAD").stdout.split())
    listed = {str(row["path"]) for row in manifest["files"]}
    if not listed <= committed:
        rc |= fail("every manifest file must be in the commit: %s" % sorted(listed - committed))
    if MANIFEST not in committed:
        rc |= fail("the manifest must be in the commit: %s" % sorted(committed))
    outside = {p for p in committed if not (p in listed or p == MANIFEST or p.startswith("src/parity-test/"))}
    if outside:
        rc |= fail("nothing outside the generated suite may be committed: %s" % sorted(outside))

    head = git(root, "rev-parse", "HEAD").stdout.strip()
    proc = run(root)
    if proc.returncode != 0 or "nothing to commit" not in proc.stdout:
        rc |= fail("a re-run with nothing to commit must say so and exit 0: rc=%s %s%s"
                   % (proc.returncode, proc.stdout, proc.stderr))
    if git(root, "rev-parse", "HEAD").stdout.strip() != head:
        rc |= fail("an idempotent re-run must not write a second commit")

    # a change that is not this producer's is never swept into a harness commit
    (root / "src" / "main" / "java" / "Worker.java").write_text("class Worker {}\n", encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1 or "not this producer's" not in proc.stderr or "Worker.java" not in proc.stderr:
        rc |= fail("a foreign change under src/ must refuse by name: rc=%s %s%s"
                   % (proc.returncode, proc.stdout, proc.stderr))
    if git(root, "rev-parse", "HEAD").stdout.strip() != head:
        rc |= fail("a refusal must not commit anything")
    (root / "src" / "main" / "java" / "Worker.java").unlink()

    # a pom moved after the bootstrap is a change this step does not own either
    (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8").replace(
        "</project>", "  <!-- hand edit -->\n</project>"), encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1 or "pom.xml" not in proc.stderr:
        rc |= fail("a pom changed outside the bootstrap must refuse: rc=%s %s%s"
                   % (proc.returncode, proc.stdout, proc.stderr))
    git(root, "checkout", "--", "pom.xml")
    return rc


def case_refuses_an_edited_expectation(tmp: Path) -> int:
    rc = 0
    root = bootstrapped_tree(tmp, "edited")
    if generate(root).returncode != 0:
        return fail("generation refused a bound fixture")
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    target = next(root / row["path"] for row in manifest["files"] if str(row["path"]).endswith(".java"))
    target.write_text(target.read_text(encoding="utf-8") + "// weakened\n", encoding="utf-8")
    proc = run(root)
    if proc.returncode != 1 or "--check refuses" not in proc.stderr:
        rc |= fail("an edited generated expectation must refuse before any commit: rc=%s %s%s"
                   % (proc.returncode, proc.stdout, proc.stderr))
    if git(root, "log", "--oneline").stdout.count("\n") != 1:
        rc |= fail("a refusal must leave HEAD where it was")
    return rc


def main() -> int:
    cases = (case_no_manifest, case_commits_and_is_idempotent, case_refuses_an_edited_expectation)
    rc = 0
    with tempfile.TemporaryDirectory(prefix="commit-generated-tests-") as td:
        tmp = Path(td)
        for case in cases:
            try:
                rc |= case(tmp)
            except Exception as exc:  # a case that cannot run is a failure, not a pass
                import traceback
                traceback.print_exc()
                rc |= fail("%s raised %s" % (case.__name__, exc))
    if rc:
        print("FAIL: commit-generated-tests %d check(s) failed" % len(FAILURES), file=sys.stderr)
        return 1
    print("OK: commit-generated-tests %d case(s)" % len(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
