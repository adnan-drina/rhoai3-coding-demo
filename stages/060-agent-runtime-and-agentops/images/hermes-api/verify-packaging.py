"""Build-time proof that packaging preserves the selected fork and existing packages."""
import hashlib
import importlib.metadata as metadata
import json
import os
import shutil
from pathlib import Path
import sys

root = Path('/opt/rhoai3/hermes-api')
source = json.loads((root / 'dependency-source.json').read_text())
stamp = Path('/opt/rhoai3/080.pins').read_bytes()
assert source['hermesSourceCommit'].encode() in stamp and source['hermesPatchedTree'].encode() in stamp
versions = {d.metadata['Name'].lower().replace('_', '-'): d.version for d in metadata.distributions()}
baseline = Path('/tmp/hermes-api-before.json')
if sys.argv[1] == 'before':
    for name, version in source['existingUnchanged'].items():
        assert versions[name.replace('_', '-')] == version
    # A private physical interpreter narrows executable policy to this image.
    target = Path('/opt/hermes-venv/bin/python3.11')
    assert target.is_symlink() and target.resolve() == Path('/usr/bin/python3.11')
    links = {str(p): os.readlink(p) for p in (Path('/opt/hermes-venv/bin/python'), Path('/opt/hermes-venv/bin/python3'))}
    config_hash = hashlib.sha256(Path('/opt/hermes-venv/pyvenv.cfg').read_bytes()).hexdigest()
    interpreter_hash = hashlib.sha256(Path('/usr/bin/python3.11').read_bytes()).hexdigest()
    assert interpreter_hash == source['interpreter']['sha256']
    baseline.write_text(json.dumps({'versions': versions, 'stampSha256': hashlib.sha256(stamp).hexdigest(), 'interpreterSha256': interpreter_hash, 'venvConfigSha256': config_hash, 'links': links}))
    temporary = Path('/tmp/hermes-api-python3.11')
    shutil.copyfile('/usr/bin/python3.11', temporary)
    temporary.chmod(0o755)
    target.unlink()
    temporary.replace(target)
else:
    before = json.loads(baseline.read_text())
    assert hashlib.sha256(stamp).hexdigest() == before['stampSha256']
    interpreter = Path('/opt/hermes-venv/bin/python3.11')
    assert interpreter.is_file() and not interpreter.is_symlink()
    assert hashlib.sha256(interpreter.read_bytes()).hexdigest() == before['interpreterSha256'] == hashlib.sha256(Path('/usr/bin/python3.11').read_bytes()).hexdigest()
    assert os.readlink('/proc/self/exe') == str(interpreter) and sys.prefix == '/opt/hermes-venv'
    assert hashlib.sha256(Path('/opt/hermes-venv/pyvenv.cfg').read_bytes()).hexdigest() == before['venvConfigSha256']
    assert all(Path(path).is_symlink() and os.readlink(path) == link for path, link in before['links'].items())
    assert all(versions.get(name) == version for name, version in before['versions'].items()), 'Existing distribution changed'
    expected = {w['name'].lower().replace('_', '-'): w['version'] for w in source['wheels']}
    assert all(versions.get(name) == version for name, version in expected.items())
    assert set(versions) - set(before['versions']) == set(expected) - set(before['versions']), 'Unreviewed distribution added'
    import aiohttp
    from gateway.platforms.api_server import AIOHTTP_AVAILABLE
    assert AIOHTTP_AVAILABLE and aiohttp.__version__ == '3.14.3'
    (root / 'packaging-evidence.json').write_text(json.dumps({'baseImage': source['baseImage'], 'hermesSourceCommit': source['hermesSourceCommit'], 'hermesPatchedTree': source['hermesPatchedTree'], 'baseStampSha256': before['stampSha256'], 'interpreterPath': str(interpreter), 'interpreterSha256': before['interpreterSha256'], 'venvConfigSha256': before['venvConfigSha256'], 'newDistributions': sorted(set(versions) - set(before['versions'])), 'requirementsSha256': hashlib.sha256((root / 'requirements.lock').read_bytes()).hexdigest()}))
