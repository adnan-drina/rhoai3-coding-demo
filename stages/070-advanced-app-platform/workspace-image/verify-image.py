"""Bounded image capability checks; no model, cluster or migration calls."""
import hashlib
import os
import subprocess
from pathlib import Path

assert 'hermes.patched_tree=9e5b79b9583d7aef515e8866eba993eb96679f4b' in Path('/opt/rhoai3/080.pins').read_text().splitlines()
expected = {
    '/opt/mta-cli/mta-cli': 'f2b01cdb4b6f73a8c19272eccd25893a47b1c02abb98438918afc06a219163bd',
    '/opt/rhoai3/extensions/mta-core.vsix': '7cd60047f5e19a2f953ad73ad4300eb8a4ee66c50736fe3799037547f780a237',
    '/opt/rhoai3/extensions/mta-java.vsix': '5b0c18ab51a99607f9f64450b6d0af3afdfc1d165e2990169af23cab8c42a9b8',
    '/opt/rhoai3/extensions/mta-vscode-extension.vsix': '8c3decece9c0d7ebe7b928bbb9187fd3a06e9d9e903b0ff337b653fe0f1b8e4b',
    '/opt/rhoai3/extensions/java.vsix': 'cf184d6495a2e268c43731ec3bbe058ceaf3b65e6e65b554dda30f3b90f0191a',
}
for path, digest in expected.items():
    actual = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            actual.update(chunk)
    assert actual.hexdigest() == digest, path
assert os.access('/opt/mta-cli/java-external-provider', os.X_OK)
assert Path('/opt/mta-cli/jdtls/java-analyzer-bundle/java-analyzer-bundle.core/target/java-analyzer-bundle.core.jar').is_file()
version = subprocess.check_output(['/opt/mta-cli/mta-cli', 'version'], text=True, timeout=30)
assert 'version: 8.3.0' in version
java = Path(os.environ.get('JAVA_HOME_21', '/usr/lib/jvm/java-21-openjdk')) / 'bin/java'
version = subprocess.run([str(java), '-version'], capture_output=True, text=True, check=True, timeout=30).stderr
assert 'version "21.' in version
version = subprocess.check_output(['node', '--version'], text=True, timeout=10)
assert tuple(map(int, version.strip().lstrip('v').split('.')[:2])) >= (22, 9)
print('PASS: MTA/VSIX hashes, Java 21, Node and preserved Hermes runtime')
