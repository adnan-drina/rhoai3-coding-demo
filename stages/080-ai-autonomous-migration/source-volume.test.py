#!/usr/bin/env python3
"""Execute the template's source initializer against a local Git fixture.

Only the public URL transport is replaced. The clone, retained checkout,
receipt and refusal logic are the actual shipped code. Live mount enforcement
is qualified separately against an admitted DevWorkspace Pod.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/skeleton/devfile.yaml'
CODE = textwrap.dedent(TEMPLATE.read_text().split('      args:\n        - |\n', 1)[1].split('  - name: legacy-input', 1)[0])
URL = 'https://example.test/source.git'


class SourceVolume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.upstream = self.root / 'upstream'
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init', '-q', str(self.upstream))
        self.commit('initial')
        self.code = CODE.replace("pathlib.Path('/source')", 'pathlib.Path(' + repr(str(self.source)) + ')')

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', *args], text=True).strip()

    def commit(self, content):
        (self.upstream / 'input.txt').write_text(content)
        self.git('-C', str(self.upstream), 'add', 'input.txt')
        self.git('-C', str(self.upstream), 'commit', '-qm', content)

    def run_initializer(self, url=URL):
        original = subprocess.check_output
        def transport(args, **kwargs):
            return original([str(self.upstream) if a == URL else a for a in args], **kwargs)
        with patch.dict(os.environ, {'LEGACY_REPO_URL':url}), patch('subprocess.check_output', side_effect=transport), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(self.code, str(TEMPLATE), 'exec'), {})

    def test_first_clone_and_restart_pin_the_initial_commit(self):
        self.run_initializer()
        receipt = self.source / '.git/rhoai3-source.json'
        first = receipt.read_bytes()
        self.commit('later upstream commit')
        self.run_initializer()
        self.assertEqual(first, receipt.read_bytes())
        self.assertEqual('initial', (self.source / 'input.txt').read_text())
        self.assertEqual(self.git('-C', str(self.source), 'rev-parse', 'HEAD'), json.loads(first)['commit'])

    def test_dirty_source_refuses_without_repairing_it(self):
        self.run_initializer()
        (self.source / 'input.txt').write_text('changed')
        with self.assertRaisesRegex(SystemExit, 'retained source differs'):
            self.run_initializer()
        self.assertEqual('changed', (self.source / 'input.txt').read_text())

    def test_missing_receipt_refuses_without_recloning(self):
        self.run_initializer()
        (self.source / '.git/rhoai3-source.json').unlink()
        with self.assertRaisesRegex(SystemExit, 'partial or unrecorded'):
            self.run_initializer()

    def test_changed_url_refuses(self):
        self.run_initializer()
        with self.assertRaisesRegex(SystemExit, 'retained source differs'):
            self.run_initializer('https://example.test/other.git')

    def test_credential_or_non_https_urls_refuse_before_clone(self):
        for url in ('https://user:secret@example.test/source.git', 'file:///tmp/repo', 'https://example.test/repo?token=x'):
            with self.subTest(url=url), self.assertRaisesRegex(SystemExit, 'credential-free HTTPS'):
                self.run_initializer(url)
        self.assertEqual([], list(self.source.iterdir()))


if __name__ == '__main__':
    unittest.main()
