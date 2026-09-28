#!/usr/bin/env python3
"""Execute the shipped verifier through both admission snapshots.

External build tools fail deterministically; measurement is a stub that retains
the runner's own receipt. This tests shell control flow, not Java compilation.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("run-verify.sh")


class AdmissionSnapshotTest(unittest.TestCase):
    def run_case(self, initial=None, mutation="none", invalid_after=False):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root, scripts, tools = (base / name for name in ("root", "scripts", "tools"))
            for directory in (root / ".hermes", root / ".mvn", scripts, tools):
                directory.mkdir(parents=True)
            (root / ".hermes/pins.json").write_text('{"pins":{}}')
            (root / "pom.xml").write_text("<project/>")
            (root / ".mvn/maven.config").write_text("-B\n")
            receipt = root / "evidence/planning/admission-receipt.json"
            receipt.parent.mkdir(parents=True)
            if initial == "directory":
                receipt.mkdir()
            elif initial == "dangling":
                receipt.symlink_to("missing-receipt")
            elif initial is not None:
                receipt.write_bytes(initial)
            shutil.copy2(SCRIPT, scripts / SCRIPT.name)
            (scripts / "verify.py").write_text(
                "import pathlib, shutil, sys\n"
                "root=pathlib.Path(sys.argv[sys.argv.index('--root')+1])\n"
                "shutil.copyfile(sys.argv[sys.argv.index('--run')+1], root/'verification/build/run.json')\n"
            )
            (scripts / "_loop_common.py").write_text(
                "def record_verify_run(*args, **kwargs): return {}\n"
            )
            (tools / "javac").write_text("#!/bin/sh\nexit 0\n")
            # Simulate a concurrent writer once, during the first Maven call.
            (tools / "mvn").write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, sys\n"
                "p=pathlib.Path(os.environ['TEST_RECEIPT'])\n"
                "marker=p.parent/'mutation-done'\n"
                "if not marker.exists():\n"
                " marker.touch()\n"
                " action=os.environ['TEST_MUTATION']\n"
                " if action in ('create','change'): p.write_bytes(b'new receipt')\n"
                " elif action=='delete': p.unlink()\n"
                " elif action=='directory':\n"
                "  if p.exists(): p.unlink()\n"
                "  p.mkdir()\n"
                "sys.exit(1)\n"
            )
            for tool in tools.iterdir():
                tool.chmod(0o755)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                       JAVA_HOME="", JAVA_HOME_21="", TEST_RECEIPT=str(receipt),
                       TEST_MUTATION="directory" if invalid_after else mutation)
            result = subprocess.run(
                ["bash", str(scripts / SCRIPT.name), "--root", str(root), "--mode", "diagnostic"],
                env=env, text=True, capture_output=True, timeout=30,
            )
            run = root / "verification/build/run.json"
            doc = json.loads(run.read_text()) if run.is_file() else {}
            return result, doc

    def assert_snapshot(self, initial, mutation, before, after):
        result, doc = self.run_case(initial, mutation)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(doc["mode"], "diagnostic")
        self.assertEqual(doc["classpath"]["rc"], 1)  # measurement was reached
        admission = doc["admission"]
        self.assertEqual(admission["file_sha256_before"], before)
        self.assertEqual(admission["file_sha256_after"], after)
        self.assertEqual(admission["resealed_during_verify"], before != after)
        self.assertEqual("ADMISSION_RESEALED_DURING_VERIFY" in result.stderr, before != after)

    def test_fresh_m2_with_no_receipt_reaches_measurement(self):
        self.assert_snapshot(None, "none", "", "")

    def test_existing_receipt_is_unchanged(self):
        digest = hashlib.sha256(b"original receipt").hexdigest()
        self.assert_snapshot(b"original receipt", "none", digest, digest)

    def test_change_is_recorded(self):
        self.assert_snapshot(b"original receipt", "change",
                             hashlib.sha256(b"original receipt").hexdigest(),
                             hashlib.sha256(b"new receipt").hexdigest())

    def test_creation_is_recorded(self):
        self.assert_snapshot(None, "create", "", hashlib.sha256(b"new receipt").hexdigest())

    def test_deletion_is_recorded(self):
        self.assert_snapshot(b"original receipt", "delete",
                             hashlib.sha256(b"original receipt").hexdigest(), "")

    def test_non_file_is_not_absence(self):
        result, _ = self.run_case("directory")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERIFY_ADMISSION_READ", result.stderr)

    def test_dangling_symlink_is_not_absence(self):
        result, _ = self.run_case("dangling")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERIFY_ADMISSION_READ", result.stderr)

    def test_unreadable_after_is_not_absence(self):
        result, _ = self.run_case(b"original receipt", invalid_after=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERIFY_ADMISSION_READ", result.stderr)


if __name__ == "__main__":
    unittest.main()
